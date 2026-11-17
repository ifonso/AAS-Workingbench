"""One package open at a time: opening another replaces it, after asking.

The pump package is opened through the File menu, and then the requester
package. The second open closes the first, and when the first has changes, the
answer of the person decides whether they are saved, dropped, or the open is
cancelled.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_open_window import close_window
from tests.usage_open_window import column_of
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import row_named
from tests.usage_open_window import screen  # noqa: F401
from tests.usage_open_window import write_pump_package

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, screen, every_action):  # noqa: F811
    """The main window with the pump package open, and the requester at hand."""
    pump = write_pump_package(tmp_path / "pump.aasx")
    requester = tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", requester)
    shown = open_window(qtbot)
    screen.open_paths.append(pump.as_posix())
    shown.view.openPackAct.trigger()
    shown.view.expandAll()
    shown.screen = screen
    shown.pump_file = pump
    shown.requester_file = requester
    yield shown
    close_window(shown)


def _names(editor: SimpleNamespace) -> list[str]:
    return [p.name for p in editor.model.openedPacks()]


def _edit_pump(editor: SimpleNamespace) -> None:
    view = editor.view
    cell = row_named(view, "submodels", "Submodel", "Name").siblingAtColumn(
        column_of(view, "value")
    )
    assert view.model().setData(cell, "motor", Qt.ItemDataRole.EditRole)


def _open_requester(editor: SimpleNamespace) -> None:
    editor.screen.open_paths.append(editor.requester_file.as_posix())
    editor.view.openPackAct.trigger()


def test_opening_another_package_replaces_the_one_that_is_open(editor) -> None:
    _open_requester(editor)

    assert _names(editor) == ["Requester_screwing.aasx"]
    visible = [act for act in editor.view.recentFileActs if act.isVisible()]
    assert [act.data() for act in visible][:2] == [
        editor.requester_file.absolute().as_posix(),
        editor.pump_file.absolute().as_posix(),
    ]


def test_the_tree_starts_at_the_groups_of_the_package(editor) -> None:
    root = editor.view.rootIndex()

    assert root.data() == "pump.aasx"
    assert editor.window.treePaneHeader.name.text() == "pump.aasx"


def test_cancel_keeps_the_package_with_changes_and_opens_nothing(
    editor,
) -> None:
    _edit_pump(editor)
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel

    _open_requester(editor)

    assert _names(editor) == ["pump.aasx"]
    (pump,) = editor.model.openedPacks()
    assert pump.changed


def test_discard_drops_the_changes_and_opens_the_other(editor) -> None:
    before = editor.pump_file.read_bytes()
    _edit_pump(editor)
    editor.screen.box_answer = QMessageBox.StandardButton.Discard

    _open_requester(editor)

    assert _names(editor) == ["Requester_screwing.aasx"]
    assert editor.pump_file.read_bytes() == before


def test_save_writes_the_changes_and_opens_the_other(editor) -> None:
    before = editor.pump_file.stat().st_mtime_ns
    _edit_pump(editor)
    editor.screen.box_answer = QMessageBox.StandardButton.Save

    _open_requester(editor)

    assert _names(editor) == ["Requester_screwing.aasx"]
    assert editor.pump_file.stat().st_mtime_ns != before


def test_a_recent_file_replaces_the_package_that_is_open(editor) -> None:
    _open_requester(editor)
    recent = [
        act
        for act in editor.view.recentFileActs
        if act.data() == editor.pump_file.absolute().as_posix()
    ]

    recent[0].trigger()

    assert _names(editor) == ["pump.aasx"]


def test_save_all_and_close_all_are_not_offered(editor) -> None:
    assert not editor.view.saveAllAct.isVisible()
    assert not editor.view.closeAllAct.isVisible()


def test_closing_the_window_with_changes_asks_and_cancel_keeps_it_open(
    editor,
) -> None:
    _edit_pump(editor)
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel

    closed = editor.window.close()

    assert not closed
    assert editor.window.isVisible()
    assert editor.screen.last().title == "Window Close"
