"""The context menu of each kind of row, and the Edit menu, in a large package.

For each kind of row of the Technical Data template the entries of the Edit
menu and of the context menu that are on are used, and what comes of it is
read: a change, a dialog, a message. An entry that is on must not end in the
text of a Python error, and an entry that cannot work must be off.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
import pytest
from tests import usage_window as uw
from tests.menus import find_action
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PYTHON_TEXTS = (
    "Unknown parent object",
    "cannot pickle",
    "Parent type is not extendable",
    "<class",
    "Traceback",
    "NoneType",
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


def _first_of(window: uw.UsageWindow, kind: str) -> Any:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    return next(
        index
        for index in uw.all_rows(window.view)
        if type(index.data(OBJECT_ROLE)).__name__ == kind
    )


def _folders(window: uw.UsageWindow) -> list[Any]:
    window.view.expandAll()
    return [
        i
        for i in uw.all_rows(window.view)
        if i.parent().isValid() and not i.parent().parent().isValid()
    ]


# The package row


def test_a_package_cannot_be_copied_or_cut_like_an_element(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = uw.record_dialogs(monkeypatch)
    large.view.setCurrentIndex(large.view.model().index(0, 0))
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence("Ctrl+C"))
    QTest.keySequence(large.view, QKeySequence("Ctrl+X"))

    assert seen == []
    assert len(large.window.packTreeModel.openedPacks()) == 1
    assert not large.view.copyAct.isEnabled()
    assert not large.view.cutAct.isEnabled()
    assert not large.window.focusedActs.actions["copy"].isEnabled()
    assert not find_action(large.view.attrsMenu, "Cut").isEnabled()
    assert not find_action(large.view.attrsMenu, "Copy").isEnabled()


def test_a_package_row_in_read_mode_is_not_copied_either(
    large: uw.UsageWindow,
) -> None:
    from aas_workingbench.application.editing import edit_mode

    large.view.setCurrentIndex(large.view.model().index(0, 0))

    edit_mode().set_editing(False)

    assert not large.view.copyAct.isEnabled()


# The folders of a package


def test_the_folders_of_a_package_cannot_be_cut_or_deleted(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = uw.record_dialogs(monkeypatch)
    original = snapshot(large.package.objStore)
    folders = _folders(large)

    for folder in folders:
        large.view.setCurrentIndex(folder)
        large.view.setFocus()
        assert not large.view.cutAct.isEnabled(), folder.data()
        assert not large.view.delClearAct.isEnabled(), folder.data()
        assert not large.window.focusedActs.actions["delete"].isEnabled()
        QTest.keyClick(large.view, Qt.Key.Key_Delete)
        QTest.keySequence(large.view, QKeySequence("Ctrl+X"))

    assert len(folders) == 4
    assert seen == []
    assert snapshot(large.package.objStore) == original


def test_a_folder_can_still_be_copied_and_added_to(
    large: uw.UsageWindow,
) -> None:
    large.view.setCurrentIndex(_folders(large)[1])

    assert large.view.copyAct.isEnabled()
    assert large.view.addAct.isEnabled()
    assert large.view.addAct.text() == "Add submodel"


# Add


def test_add_on_a_shell_is_off_and_no_row_shows_a_python_error_for_add(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = uw.record_dialogs(monkeypatch)
    kinds = (
        "AssetAdministrationShell",
        "Submodel",
        "SubmodelElementCollection",
        "SubmodelElementList",
        "Property",
        "ConceptDescription",
        "StoredFile",
    )

    shell_add = None
    for kind in kinds:
        large.view.setCurrentIndex(_first_of(large, kind))
        large.view.setFocus()
        if kind == "AssetAdministrationShell":
            shell_add = large.view.addAct.isEnabled()
        if large.view.addAct.isEnabled():
            large.view.addAct.trigger()
        while large.package.commandStack.can_undo:
            large.view.onUndo()

    assert shell_add is False
    assert [t for t in seen for bad in PYTHON_TEXTS if bad in t] == []


# Paste


def test_paste_with_nothing_copied_says_so(large: uw.UsageWindow) -> None:
    large.view.setCurrentIndex(_first_of(large, "Property"))
    large.view.setFocus()
    QApplication.clipboard().clear()
    large.view.treeClipboard.clear()

    large.view.pasteAct.trigger()

    assert large.status.startswith("Nothing to paste")
    assert not large.package.commandStack.can_undo


# Every entry that is on, for each kind of row


KINDS = [
    "OrderedIdentifiableStore",
    "AssetAdministrationShell",
    "Submodel",
    "SubmodelElementCollection",
    "SubmodelElementList",
    "Property",
    "MultiLanguageProperty",
    "ReferenceElement",
    "Range",
    "ConceptDescription",
    "DictSupplementaryFileContainer",
    "StoredFile",
]


@pytest.mark.parametrize("kind", KINDS)
def test_no_entry_of_the_edit_menu_that_is_on_shows_a_python_error(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    seen = uw.record_dialogs(monkeypatch)
    row = _first_of(large, kind)
    large.view.setCurrentIndex(row)
    large.view.setFocus()
    QApplication.processEvents()

    for key in ("cut", "copy", "paste", "add", "edit", "delete"):
        large.view.setCurrentIndex(row)
        action = large.window.focusedActs.actions[key]
        if action.isEnabled():
            action.trigger()
            QApplication.processEvents()
        while large.package.commandStack.can_undo:
            large.view.onUndo()

    assert [t for t in seen for bad in PYTHON_TEXTS if bad in t] == []


def test_the_edit_menu_and_the_context_menu_agree_on_a_property(
    large: uw.UsageWindow,
) -> None:
    large.view.setCurrentIndex(_first_of(large, "Property"))
    large.view.setFocus()
    edit = {
        a.text(): a.isEnabled()
        for a in large.window.menuEdit.actions()
        if not a.isSeparator()
    }

    assert edit["Cut"] == find_action(large.view.attrsMenu, "Cut").isEnabled()
    assert edit["Copy"] == find_action(large.view.attrsMenu, "Copy").isEnabled()
    assert (
        edit["Delete"]
        == find_action(large.view.attrsMenu, "Delete/clear").isEnabled()
    )
    assert edit["Add"] is False
    assert edit["Edit in dialog"] is True
