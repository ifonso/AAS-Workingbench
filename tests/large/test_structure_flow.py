"""Moving and pasting in the running editor, on a real package.

Every step goes through the main window and its actions, as a user would do it.
The order in the tree must match the order of the objects, and the order that
is saved. Undoing everything must give back the package as it was read.
"""

from collections.abc import Iterator
from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QApplication
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path) -> Iterator[SimpleNamespace]:
    """The main window with a copy of the package, and the structure actions."""
    from aas_editor.editorApp import EditorApp
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions

    register_move_actions()
    register_paste_actions()
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
    editor.dir = tmp_path
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _rows(view, parent: QModelIndex) -> list[str]:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    return [
        proxy.index(row, 0, parent).data(NAME_ROLE)
        for row in range(proxy.rowCount(parent))
    ]


def _find(view, parent: QModelIndex, name: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    for row in range(proxy.rowCount(parent)):
        child = proxy.index(row, 0, parent)
        if child.data(NAME_ROLE) == name:
            return child
    raise LookupError(name)


def _select(view, *indexes: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    for index in indexes:
        selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(
        indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
    )


def _act(view, action_id: str) -> bool:
    action = view.registeredActions.find(action_id)
    enabled = action.isEnabled()
    action.trigger()
    return enabled


def _saved_order(
    package, submodel_id: str, holder: str, directory: Path
) -> list[str]:
    from aas_editor.package import Package

    path = directory / "flow_saved.aasx"
    package.write(path)
    reloaded = Package(path).objStore.get_item(submodel_id)
    return [e.id_short for e in reloaded.get_referable(holder).value]


def test_moving_and_pasting_keep_tree_objects_and_file_in_one_order(
    editor,
) -> None:
    view, package, stack = editor.view, editor.package, editor.stack
    original = snapshot(package.objStore)
    (submodel,) = list(package.submodels)
    holder = next(
        e
        for e in submodel.submodel_element
        if isinstance(e, model.SubmodelElementCollection)
    )
    names = [e.id_short for e in holder.value]
    assert len(names) >= 3

    def node() -> QModelIndex:
        # An index is only valid until the rows change, so it is found again.
        submodels_node = _find(view, view.model().index(0, 0), "submodels")
        return _find(
            view,
            _find(view, submodels_node, submodel.id_short),
            holder.id_short,
        )

    # The tree shows the order of the package, not an alphabetical one.
    shown_first = _rows(view, node())
    last = _find(view, node(), names[-1])

    # Move the last element to the top.
    _select(view, last)
    enabled_up = _act(view, "structure.move_top")
    moved_tree = _rows(view, node())
    moved_objects = [e.id_short for e in holder.value]
    moved_saved = _saved_order(
        package, submodel.id, holder.id_short, editor.dir
    )
    selected_after = view.currentIndex().data()

    # Undo, redo.
    view.onUndo()
    undone = (_rows(view, node()), snapshot(package.objStore) == original)
    view.onRedo()
    redone = _rows(view, node())

    # Copy the second element and paste it below the first.
    second = _find(view, node(), moved_objects[1])
    _select(view, second)
    view.onCopy()
    clipboard_text = QApplication.clipboard().text()
    _select(view, _find(view, node(), moved_objects[0]))
    enabled_paste = _act(view, "structure.paste_below")
    pasted_objects = [e.id_short for e in holder.value]
    pasted_tree = _rows(view, node())
    pasted_saved = _saved_order(
        package, submodel.id, holder.id_short, editor.dir
    )

    # Everything back to the state that was read.
    while stack.can_undo:
        view.onUndo()

    assert shown_first == names
    assert enabled_up
    assert moved_tree == moved_objects == moved_saved
    assert moved_objects == [names[-1], *names[:-1]]
    assert selected_after == names[-1]
    assert undone == (names, True)
    assert redone == moved_tree
    assert clipboard_text.lstrip().startswith("[")
    assert enabled_paste
    assert pasted_tree == pasted_objects == pasted_saved
    assert len(pasted_objects) == len(names) + 1
    assert pasted_objects[1] == f"{moved_objects[1]}_1"
    assert snapshot(package.objStore) == original
    assert not package.changed
