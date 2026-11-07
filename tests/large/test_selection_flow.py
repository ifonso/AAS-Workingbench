"""The selection panel, and Push and Pop location, in the running editor.

The panel is looked at in the main window, with a real package. A selection of
two rows opens it, its button moves the rows, and one undo takes them back.
"""

from collections.abc import Iterator
from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path) -> Iterator[SimpleNamespace]:
    """The main window with a copy of the package, and the actions."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_workingbench.ui.location_actions import register_location_actions
    from aas_workingbench.ui.move_actions import register_move_actions

    register_move_actions()
    register_bulk_edit_actions()
    register_location_actions()
    source = tmp_path / PACKAGE.name
    shutil.copy(PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    editor = SimpleNamespace()
    editor.window = window
    editor.view = window.mainTreeView
    (editor.package,) = window.packTreeModel.openedPacks()
    editor.stack = editor.package.commandStack
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _properties(view) -> list[QModelIndex]:
    """Three Property rows that share a parent."""
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    found: dict[QModelIndex, list[QModelIndex]] = {}
    pending = [QModelIndex()]
    proxy = view.model()
    while pending:
        parent = pending.pop()
        for row in range(proxy.rowCount(parent)):
            child = proxy.index(row, 0, parent)
            if isinstance(child.data(OBJECT_ROLE), model.Property):
                found.setdefault(parent, []).append(child)
            pending.append(child)
    rows = next(rows for rows in found.values() if len(rows) >= 3)
    return rows[:3]


def _select(view, *indexes: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    for index in indexes:
        selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(
        indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
    )
    view.updateActions(view.currentIndex())


def _holder(index: QModelIndex) -> model.SubmodelElementCollection:
    """The collection that holds the row. An index does not outlive a move."""
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    obj = index.data(OBJECT_ROLE)
    return obj.parent


def _order(holder: model.SubmodelElementCollection) -> list[str]:
    return [e.id_short for e in holder.value]


def test_two_rows_open_the_panel_and_a_button_moves_them(editor) -> None:
    view, window = editor.view, editor.window
    first, _, third = _properties(view)
    original = snapshot(editor.package.objStore)
    holder = _holder(first)
    before = _order(holder)
    hidden_at_first = not window.selectionDock.isVisible()

    _select(view, first, third)
    panel = window.selectionDock.panel
    opened = window.selectionDock.isVisible()
    header = panel.header_label.text()
    panel.buttons["Move to end"].click()
    moved = _order(holder)
    view.onUndo()
    undone = (_order(holder), snapshot(editor.package.objStore) == original)

    assert hidden_at_first
    assert opened
    assert header == "Several elements selected"
    assert moved != before
    assert undone == (before, True)
    assert not editor.stack.can_undo


def test_push_and_pop_location_work_from_the_navigate_menu(editor) -> None:
    view, window = editor.view, editor.window
    first, second, _ = _properties(view)
    pushed = view.registeredActions.find("navigate.push_location")
    popped = view.registeredActions.find("navigate.pop_location")
    in_menu = set(window.menuNavigate.actions())

    _select(view, first)
    pushed.trigger()
    _select(view, second)
    popped.trigger()

    assert {pushed, popped} <= in_menu
    assert view.currentIndex().data() == first.data()
