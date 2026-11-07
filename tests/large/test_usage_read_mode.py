"""Read mode in a large package: every kind of edit is refused, with a reason.

A person who switches to Read mode wants to look at the package without the
risk of changing it. These tests try the edits that a person tries, by key, by
menu, by button and in the cells, and check that the package, its history and
its file stay as they were, and that the window says why nothing happened.
"""

from collections.abc import Iterator
import hashlib
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
import pytest
from tests import usage_window as uw
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the actions that `__main__` registers before the first view."""
    added = uw.register_all_actions()
    yield
    uw.unregister_actions(added)


@pytest.fixture
def large(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[uw.UsageWindow]:
    """The main window on a copy of the Technical Data template."""
    yield from uw.open_window(qtbot, monkeypatch, tmp_path, uw.TECHNICAL_DATA)
    uw.release_clipboard()


def _row(window: uw.UsageWindow, name: str) -> Any:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    return next(
        index
        for index in uw.all_rows(window.view)
        if isinstance(index.data(OBJECT_ROLE), model.Property)
        and index.data() == name
    )


def _read_mode(window: uw.UsageWindow) -> Any:
    """Selects a property, switches to Read mode, and returns its snapshot."""
    from aas_editor.application.editing import edit_mode

    window.view.setCurrentIndex(_row(window, "ManufacturerName"))
    original = snapshot(window.package.objStore)
    edit_mode().set_editing(False)
    QApplication.processEvents()
    return original


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


EDIT_KEYS = [
    pytest.param(
        Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier, id="Delete"
    ),
    pytest.param(Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier, id="F2"),
    pytest.param(
        Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier, id="Ctrl+X"
    ),
    pytest.param(
        Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier, id="Ctrl+V"
    ),
    pytest.param(
        Qt.Key.Key_N, Qt.KeyboardModifier.ControlModifier, id="Ctrl+N"
    ),
    pytest.param(
        Qt.Key.Key_E, Qt.KeyboardModifier.ControlModifier, id="Ctrl+E"
    ),
    pytest.param(
        Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier, id="Ctrl+Z"
    ),
    pytest.param(
        Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier, id="Ctrl+Y"
    ),
]


@pytest.mark.parametrize(("key", "modifier"), EDIT_KEYS)
def test_a_key_that_edits_in_the_tree_is_refused_and_says_why(
    large: uw.UsageWindow, key: Qt.Key, modifier: Qt.KeyboardModifier
) -> None:
    original = _read_mode(large)
    large.view.setFocus()

    QTest.keyClick(large.view, key, modifier)
    QApplication.processEvents()

    assert "Read mode is on" in large.status
    assert snapshot(large.package.objStore) == original
    assert not large.package.commandStack.can_undo
    assert large.boxes == []


@pytest.mark.parametrize(("key", "modifier"), EDIT_KEYS)
def test_a_key_that_edits_in_a_tab_is_refused_and_says_why(
    large: uw.UsageWindow, key: Qt.Key, modifier: Qt.KeyboardModifier
) -> None:
    original = _read_mode(large)
    view = large.tab.attrsTreeView
    view.expandAll()
    view.setCurrentIndex(uw.all_rows(view)[2].siblingAtColumn(1))
    view.setFocus()

    QTest.keyClick(view, key, modifier)
    QApplication.processEvents()

    assert "Read mode is on" in large.status
    assert snapshot(large.package.objStore) == original
    assert not large.package.commandStack.can_undo


def test_a_key_that_does_not_edit_says_nothing_in_read_mode(
    large: uw.UsageWindow,
) -> None:
    _read_mode(large)
    large.view.setFocus()

    QTest.keyClick(large.view, Qt.Key.Key_Down)
    QTest.keyClick(
        large.view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier
    )

    assert large.status == ""


def test_typing_in_a_cell_of_a_tab_is_refused_and_changes_nothing(
    large: uw.UsageWindow,
) -> None:
    original = _read_mode(large)
    view = large.tab.attrsTreeView
    view.expandAll()
    cell = uw.all_rows(view)[0].siblingAtColumn(1)

    view.setCurrentIndex(cell)
    QTest.mouseDClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=view.visualRect(cell).center(),
    )
    accepted = view.model().setData(cell, "Typed", Qt.ItemDataRole.EditRole)

    assert view.state() != view.State.EditingState
    assert not accepted
    assert snapshot(large.package.objStore) == original


def test_every_action_of_the_context_menu_that_edits_is_off_in_read_mode(
    large: uw.UsageWindow,
) -> None:
    from tests.menus import find_action

    _read_mode(large)
    large.view.setFocus()

    for text in (
        "Cut",
        "Paste",
        "Delete/clear",
        "Rename idShort...",
        "Add qualifier from preset...",
        "Create concept description from semantic id",
        "Convert to another element type...",
    ):
        assert not find_action(large.view.attrsMenu, text).isEnabled(), text
    for text in ("Copy", "Copy as JSON", "Push location", "Show package files"):
        assert find_action(large.view.attrsMenu, text).isEnabled(), text


def test_the_buttons_and_entries_that_read_mode_turned_off_say_why(
    large: uw.UsageWindow,
) -> None:
    from aas_editor.ui.actions import READ_MODE_REASON

    _read_mode(large)
    large.window.filesDock.show()
    large.window.filesDock.panel.follow_current_package()
    delete = large.window.focusedActs.actions["delete"]
    undo = large.window.focusedActs.actions["undo"]

    files = large.window.filesDock.panel
    assert READ_MODE_REASON in delete.toolTip()
    assert READ_MODE_REASON in delete.statusTip()
    assert READ_MODE_REASON in undo.toolTip()
    for button in (files.add_button, files.remove_button, files.rename_button):
        assert button.toolTip() == READ_MODE_REASON, button.text()


def test_copy_stays_on_in_read_mode_for_any_row_of_a_tab(
    large: uw.UsageWindow,
) -> None:
    from aas_editor.application.editing import edit_mode

    large.view.setCurrentIndex(_row(large, "ManufacturerName"))
    edit_mode().set_editing(False)
    view = large.tab.attrsTreeView
    view.expandAll()

    view.setCurrentIndex(uw.all_rows(view)[2])
    on_row = view.copyAct.isEnabled()
    view.setCurrentIndex(view.rootIndex())
    on_nothing = view.copyAct.isEnabled()

    assert on_row
    assert not on_nothing


def test_save_in_read_mode_leaves_a_package_with_no_changes_as_it_is(
    large: uw.UsageWindow,
) -> None:
    before = _digest(large.path)
    _read_mode(large)
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence("Ctrl+S"))

    assert _digest(large.path) == before
    assert "has no changes" in large.status


def test_save_in_read_mode_still_writes_the_changes_made_before_it(
    large: uw.UsageWindow,
) -> None:
    from aas_editor.application.editing import edit_mode

    large.view.setCurrentIndex(_row(large, "ManufacturerName"))
    large.view.registeredActions.find("structure.move_end").trigger()
    assert large.package.changed
    before = _digest(large.path)
    edit_mode().set_editing(False)
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence("Ctrl+S"))

    assert _digest(large.path) != before
    assert not large.package.changed


def test_edit_mode_again_brings_every_edit_back(large: uw.UsageWindow) -> None:
    from aas_editor.application.editing import edit_mode

    original = _read_mode(large)
    edit_mode().set_editing(True)
    large.view.setFocus()

    large.view.registeredActions.find("structure.move_end").trigger()

    assert large.package.commandStack.can_undo
    assert snapshot(large.package.objStore) != original
    large.view.onUndo()
    assert snapshot(large.package.objStore) == original
