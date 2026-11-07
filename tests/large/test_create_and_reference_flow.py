"""Creating, referencing, pasting and removing in the running editor (WP7).

One session on a real package, through the main window and its actions: create
an AAS and a Submodel that it refers to, pick the semantic id of an element
from the package, jump to the concept description and back, paste a Submodel
into the new AAS, and remove the qualifiers of a Submodel in bulk. Each of
these is one undo step. The saved file must hold what the editor shows, and
undoing everything must give back the package as it was read.
"""

from collections.abc import Iterator
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.medium.forms import answering
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02023 _Template_CarbonFootprint.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path) -> Iterator[SimpleNamespace]:
    """The main window with a copy of the package, and the WP7 actions."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui.bulk_actions import register_bulk_actions
    from aas_workingbench.ui.create_actions import register_create_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions
    from aas_workingbench.ui.reference_jump import register_jump_actions

    register_create_actions()
    register_bulk_actions()
    register_paste_actions()
    register_jump_actions()
    source = tmp_path / PACKAGE.name
    shutil.copy(PACKAGE, source)
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
    editor.dir = tmp_path
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _find(view, parent: QModelIndex, name: str) -> QModelIndex:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = view.model()
    view.expand(parent)
    for row in range(proxy.rowCount(parent)):
        child = proxy.index(row, 0, parent)
        if child.data(NAME_ROLE) == name:
            return child
    raise LookupError(name)


def _path(view, *names: str) -> QModelIndex:
    # An index is only valid until the rows change, so it is found again.
    index = view.model().index(0, 0)
    for name in names:
        index = _find(view, index, name)
    return index


def _select(view, index: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)


def _act(view, action_id: str) -> bool:
    action = view.registeredActions.find(action_id)
    enabled = action.isEnabled()
    action.trigger()
    return enabled


def _attrs_row(attrs, name: str) -> QModelIndex:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = attrs.model()
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        if index.data(NAME_ROLE) == name:
            return index.siblingAtColumn(1)
    raise LookupError(name)


def _undo_all(stack) -> int:
    steps = 0
    while stack.can_undo:
        stack.undo()
        steps += 1
    return steps


def test_create_reference_paste_and_remove_are_undoable_and_saved(
    editor, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.application.operations.bulk import RemovableAttribute
    from aas_workingbench.application.operations.bulk import (
        available_attributes,
    )
    from aas_workingbench.dialogs import EditObjDialog
    from aas_workingbench.package import Package
    from aas_workingbench.settings.app_settings import OBJECT_ROLE
    from aas_workingbench.ui.bulk_actions import RemoveAttributesDialog
    from aas_workingbench.ui.create_dialogs import CreateShellDialog
    from aas_workingbench.ui.create_dialogs import CreateSubmodelDialog
    from aas_workingbench.ui.reference_picker import ReferencePickerDialog

    view, package, stack, tabs = (
        editor.view,
        editor.package,
        editor.stack,
        editor.tabs,
    )
    original = snapshot(package.objStore)
    (submodel,) = list(package.submodels)
    concept = next(iter(package.concept_descriptions))
    element = submodel
    known_ids = {obj.id for obj in package.objStore}
    steps: list[str] = []

    # 1. Create an AAS with valid AssetInformation.
    _select(view, _path(view, "shells"))
    with answering(
        monkeypatch,
        CreateShellDialog,
        lambda dialog: dialog.id_short_edit.setText("NewShell"),
    ):
        assert _act(view, "create.shell")
    (shell,) = [
        o
        for o in package.objStore
        if isinstance(o, model.AssetAdministrationShell)
        and o.id not in known_ids
    ]
    steps.append("shell")
    assert shell.asset_information.global_asset_id.startswith("urn:uuid:")
    assert view.currentIndex().data(OBJECT_ROLE) is shell

    # 2. Create a Submodel that the new AAS refers to.
    with answering(
        monkeypatch,
        CreateSubmodelDialog,
        lambda dialog: dialog.id_short_edit.setText("NewSubmodel"),
    ):
        assert _act(view, "create.submodel")
    new_submodel = package.objStore.get_item(
        next(iter(shell.submodel)).key[0].value
    )
    steps.append("submodel")
    assert new_submodel.id_short == "NewSubmodel"
    assert [r.key[0].value for r in shell.submodel] == [new_submodel.id]

    # 3. Pick the semantic id of an element from the package, in a tab.
    tabs.openItemInNewTab(_path(view, "submodels", submodel.id_short))
    tab = tabs.currentWidget()
    attrs = tab.attrsTreeView
    row = _attrs_row(attrs, "semantic_id")
    attrs.setCurrentIndex(row)

    def pick(dialog: Any) -> None:
        with answering(
            monkeypatch,
            ReferencePickerDialog,
            lambda picker: picker.select(concept),
        ):
            assert dialog.inputWidget.choose_from_package()

    with answering(monkeypatch, EditObjDialog, pick):
        attrs.onEditCreate(None, row)
    steps.append("semantic id")
    assert element.semantic_id is not None
    assert element.semantic_id.key[0].value == concept.id

    # 4. Jump to the concept description, and come back with Back.
    attrs.setCurrentIndex(_attrs_row(attrs, "semantic_id"))
    assert _act(attrs, "reference.jump")
    assert tab.packItemObj is concept
    tab.backAct.trigger()
    assert tab.packItemObj is element

    # 5. Paste the Submodel into the new AAS: a copy, with its reference.
    _select(view, _path(view, "submodels", submodel.id_short))
    view.onCopy()
    _select(view, _path(view, "shells", "NewShell"))
    assert _act(view, "structure.paste_into")
    steps.append("paste")
    assert len(shell.submodel) == 2
    assert all(r.resolve(package.objStore) is not None for r in shell.submodel)

    # 6. Remove an attribute from the whole Submodel in one step.
    counts = available_attributes(submodel)
    chosen = max(counts, key=lambda attribute: counts[attribute])
    assert counts[chosen] > 0
    _select(view, _path(view, "submodels", submodel.id_short))
    with answering(
        monkeypatch,
        RemoveAttributesDialog,
        lambda dialog: dialog.check(chosen),
    ):
        assert _act(view, "bulk.remove_attributes")
    steps.append("remove")
    assert available_attributes(submodel)[chosen] == 0
    assert isinstance(chosen, RemovableAttribute)

    # The file holds what the editor shows.
    edited = snapshot(package.objStore)
    path = editor.dir / "flow_saved.aasx"
    package.write(path)
    assert snapshot(Package(path).objStore) == edited

    # Each flow was one step, and undoing them gives back the original.
    assert _undo_all(stack) == len(steps)
    assert snapshot(package.objStore) == original
    while stack.can_redo:
        stack.redo()
    assert snapshot(package.objStore) == edited
    # The window must not ask about unsaved changes when it closes.
    stack.mark_saved()
    editor.window.mainTreeView.updateWindowModified()
