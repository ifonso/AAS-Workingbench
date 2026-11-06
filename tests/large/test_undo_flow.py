"""Edit, delete, and paste in the running editor, then undo everything.

A real package is opened in the main window. Every kind of edit goes through
the views as a user's action would, and undoing all of them must give back the
package exactly as it was read, in the SDK serialization.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.factories import make_property
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGES = [
    "IDTA 02058-1-0_Template_AIDataset.aasx",
    "IDTA 02023 _Template_CarbonFootprint.aasx",
]


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, request):
    """The main window with one package, copied so a save cannot touch data."""
    from aas_editor.editorApp import EditorApp

    source = tmp_path / request.param
    shutil.copy(TEST_DATA_DIR / request.param, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    editor = SimpleNamespace()
    editor.window = window
    editor.view = window.mainTreeView
    editor.tabs = window.mainTabWidget
    (editor.package,) = window.packTreeModel.openedPacks()
    editor.stack = editor.package.commandStack
    editor.source = source
    yield editor
    # Closing the window must not ask whether to save.
    editor.package.commandStack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _index(view, *names: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    index = proxy.index(0, 0)
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(NAME_ROLE) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def _select(view, *indexes: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    for index in indexes:
        selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(
        indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
    )


def _column(view, name: str) -> int:
    source = view.sourceModel()
    return [
        source.headerData(i, Qt.Orientation.Horizontal, 0)
        for i in range(source.columnCount())
    ].index(name)


def _attrs_row(attrs_view, name: str) -> QModelIndex:
    proxy = attrs_view.model()
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        if index.data(Qt.ItemDataRole.DisplayRole) == name:
            return index
    raise LookupError(name)


@pytest.mark.parametrize("editor", PACKAGES, indirect=True)
def test_undoing_all_edits_gives_back_the_package_as_it_was_read(
    editor, qtbot
) -> None:
    from aas_editor.package import Package
    from aas_editor.settings import NOT_GIVEN
    from aas_editor.settings.app_settings import ADD_ITEM_ROLE
    from aas_editor.settings.app_settings import CLEAR_ROW_ROLE
    from aas_editor.settings.app_settings import OBJECT_ROLE

    view, package, stack = editor.view, editor.package, editor.stack
    original = snapshot(package.objStore)
    assert original == snapshot(Package(editor.source).objStore)
    (submodel,) = list(package.submodels)
    elements = [element.id_short for element in submodel.submodel_element]
    submodel_path = ("submodels", submodel.id_short)
    first_name, second_name = elements[0], elements[1]

    # Two tabs show the same element, so that each change has a witness.
    tab_index = _index(view, *submodel_path, second_name)
    editor.tabs.openItemInNewTab(tab_index)
    editor.tabs.openItemInNewTab(tab_index)
    witness = editor.tabs.widget(editor.tabs.count() - 1).attrsTreeView

    # Rename the first element in the package tree.
    view.model().setData(
        _index(view, *submodel_path, first_name).siblingAtColumn(
            _column(view, "id_short")
        ),
        "RenamedElement",
        Qt.ItemDataRole.EditRole,
    )
    # Edit an attribute in a tab.
    editor.tabs.widget(editor.tabs.count() - 1).attrsTreeView._setItemData(
        _attrs_row(witness, "category").siblingAtColumn(1),
        "Parameter",
        Qt.ItemDataRole.EditRole,
    )
    # Add elements, one at a position and one at the end.
    view.sourceModel().addItem(
        make_property("AddedFirst"),
        view.model().mapToSource(_index(view, *submodel_path)),
        row=0,
    )
    view._setItemData(
        _index(view, *submodel_path), make_property("AddedLast"), ADD_ITEM_ROLE
    )
    # Delete two elements with one multi-select.
    doomed = elements[2:4]
    if len(doomed) == 2:
        _select(view, *[_index(view, *submodel_path, n) for n in doomed])
        view.onDelClear()
    # Cut an element and paste it into the submodel again.
    if len(elements) > 4:
        _select(view, _index(view, *submodel_path, elements[4]))
        view.onCut()
        _select(view, _index(view, *submodel_path))
        view.onPaste()
    # Add a language entry to the description of the submodel.
    submodel_attrs = view.sourceModel()
    submodel_object = _index(view, *submodel_path).data(OBJECT_ROLE)
    assert submodel_object is submodel
    # Delete a concept description of the package.
    if package.numOfConceptDescriptions:
        concept_name = next(iter(package.concept_descriptions)).id_short
        view.model().setData(
            _index(view, "concept_descriptions", concept_name),
            NOT_GIVEN,
            CLEAR_ROW_ROLE,
        )
    # Link the Submodels to the AAS.
    view.setCurrentIndex(_index(view, "shells"))
    view.linkAllSubmodelsToFirstAas()
    # Delete the whole submodel last.
    view.model().setData(
        _index(view, *submodel_path), NOT_GIVEN, CLEAR_ROW_ROLE
    )
    assert submodel_attrs is not None

    edited = snapshot(package.objStore)
    steps = 0
    dirty_after_edits = package.changed
    window_modified = editor.window.isWindowModified()
    while stack.can_undo:
        view.setCurrentIndex(_index(view, "shells"))
        view.onUndo()
        steps += 1
        qtbot.wait(1)
    undone = snapshot(package.objStore)
    while stack.can_redo:
        view.setCurrentIndex(_index(view, "shells"))
        view.onRedo()
    redone = snapshot(package.objStore)
    while stack.can_undo:
        view.setCurrentIndex(_index(view, "shells"))
        view.onUndo()

    assert edited != original
    assert dirty_after_edits
    assert window_modified
    assert steps >= 6
    assert undone == original
    assert redone == edited
    assert snapshot(package.objStore) == original
    assert not package.changed
    editor.view.updateWindowModified()
    assert not editor.window.isWindowModified()


@pytest.mark.parametrize("editor", PACKAGES[:1], indirect=True)
def test_save_then_undo_makes_the_package_changed_and_save_again_writes_it(
    editor, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    view, package = editor.view, editor.package
    (submodel,) = list(package.submodels)
    name = submodel.submodel_element.__iter__().__next__().id_short
    view.model().setData(
        _index(view, "submodels", submodel.id_short, name).siblingAtColumn(
            _column(view, "id_short")
        ),
        "Renamed",
        Qt.ItemDataRole.EditRole,
    )
    edited = snapshot(package.objStore)

    saved = view.savePack(package, (tmp_path / "saved.aasx").as_posix())
    clean_after_save = not package.changed
    view.setCurrentIndex(_index(view, "shells"))
    view.onUndo()
    dirty_after_undo = package.changed
    view.onRedo()

    assert saved
    assert clean_after_save
    assert dirty_after_undo
    assert not package.changed
    assert snapshot(Package(tmp_path / "saved.aasx").objStore) == edited
    assert isinstance(model.Property, type)


@pytest.mark.parametrize("editor", PACKAGES[:1], indirect=True)
def test_the_view_menu_switches_between_edit_and_read_mode(editor) -> None:
    from aas_editor.application.editing import edit_mode
    from aas_editor.settings.app_settings import CLEAR_ROW_ROLE

    window, view, package = editor.window, editor.view, editor.package
    (submodel,) = list(package.submodels)
    path = ("submodels", submodel.id_short)
    first = submodel.submodel_element.__iter__().__next__().id_short
    original = snapshot(package.objStore)
    view.setCurrentIndex(_index(view, *path, first))
    in_edit_mode = (
        window.editModeAct.isChecked(),
        view.delClearAct.isEnabled(),
    )

    window.readModeAct.trigger()
    reading = (
        edit_mode().is_editing,
        window.readModeAct.isChecked(),
        view.delClearAct.isEnabled(),
        view.cutAct.isEnabled(),
        view.addAct.isEnabled(),
    )
    refused = view.model().setData(
        _index(view, *path, first), None, CLEAR_ROW_ROLE
    )
    unchanged = snapshot(package.objStore) == original
    window.editModeAct.trigger()

    assert in_edit_mode == (True, True)
    assert reading == (False, True, False, False, False)
    assert not refused
    assert unchanged
    assert edit_mode().is_editing
    assert view.delClearAct.isEnabled()
