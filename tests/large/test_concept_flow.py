"""Concept descriptions in the running editor, on a real package.

Every step goes through the main window and its actions, as a user does it.
The package is a real IDTA template with 35 concept descriptions, whose
records name the IEC 61360 template in an older spelling, and whose submodel
has a semantic id that names no description. Undoing everything must give back
the package as it was read, and a save must read back as it was.
"""

from collections.abc import Iterator
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture
def editor(
    qapp: object, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[SimpleNamespace]:
    """The main window with a copy of the package, and the concept actions."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui import concept_dialogs
    from aas_workingbench.ui import reference_dialogs
    from aas_workingbench.ui.concept_actions import register_concept_actions

    register_concept_actions()
    # A window with changes asks whether to save when it closes, and waits.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
    )
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
    editor.monkeypatch = monkeypatch
    editor.messages = []
    editor.usage_plans = []
    monkeypatch.setattr(
        reference_dialogs,
        "show_message",
        lambda title, text, parent=None: editor.messages.append(text),
    )

    def ask_delete(plan: Any, parent: Any = None) -> bool:
        editor.usage_plans.append(plan)
        return False

    monkeypatch.setattr(reference_dialogs, "ask_delete", ask_delete)
    monkeypatch.setattr(
        concept_dialogs, "ask_create_kind", lambda *a, **k: False
    )
    monkeypatch.setattr(concept_dialogs, "choose_rows", lambda *a, **k: [0])
    monkeypatch.setattr(concept_dialogs, "ask_fix_keys", lambda *a, **k: True)
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _find(view, parent: QModelIndex, name: str) -> QModelIndex:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = view.model()
    for row in range(proxy.rowCount(parent)):
        child = proxy.index(row, 0, parent)
        if child.data(NAME_ROLE) == name:
            return child
    raise LookupError(name)


def _concepts_node(view) -> QModelIndex:
    return _find(view, view.model().index(0, 0), "concept_descriptions")


def _select(view, index: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)
    view.updateActions(index)


def _act(view, action_id: str) -> bool:
    action = view.registeredActions.find(action_id)
    enabled = action.isEnabled()
    action.trigger()
    return enabled


def _concept_rows(view) -> list[Any]:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    proxy = view.model()
    node = _concepts_node(view)
    return [
        proxy.index(row, 0, node).data(OBJECT_ROLE)
        for row in range(proxy.rowCount(node))
    ]


def _select_concept(view, concept: model.ConceptDescription) -> None:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    proxy = view.model()
    node = _concepts_node(view)
    for row in range(proxy.rowCount(node)):
        index = proxy.index(row, 0, node)
        if index.data(OBJECT_ROLE) is concept:
            _select(view, index)
            return
    raise LookupError(concept.id)


def _reload(package, directory: Path) -> str:
    from aas_workingbench.package import Package

    path = directory / "concept_flow_saved.aasx"
    package.write(path)
    return snapshot(Package(path).objStore)


def test_a_session_with_concept_descriptions_undoes_to_the_start_and_saves_as_shown(
    editor,
) -> None:
    from aas_workingbench.domain.concept_order import ConceptOrder
    from aas_workingbench.domain.data_specifications import TemplateMatch
    from aas_workingbench.domain.data_specifications import match_template
    from aas_workingbench.ui import concept_actions
    from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog
    from aas_workingbench.ui.value_list_dialog import ValueListImportDialog

    view, package, stack = editor.view, editor.package, editor.stack
    original = snapshot(package.objStore)
    (submodel,) = list(package.submodels)
    start = [
        c for c in package.objStore if isinstance(c, model.ConceptDescription)
    ]
    assert len(start) == 35

    # 1. One semantic id below the submodel names no description: create it.
    _select(
        view,
        _find(
            view,
            _find(view, view.model().index(0, 0), "submodels"),
            submodel.id_short,
        ),
    )
    assert _act(view, "concepts.create_all")
    (created,) = [
        c
        for c in package.objStore
        if isinstance(c, model.ConceptDescription) and c not in start
    ]
    assert created.embedded_data_specifications == []
    assert created in _concept_rows(view)

    # 2. It is empty, so it is invalid. The delete flow shows who refers to it.
    _select(view, _concepts_node(view))
    assert _act(view, "concepts.delete_invalid")
    (plan,) = editor.usage_plans
    assert [target.id for target in plan.targets] == [created.id]
    assert [u.slot.attribute for u in plan.usages] == ["semantic_id"]
    assert created not in _concept_rows(view)
    stack.undo()
    assert created in _concept_rows(view)

    # 3. Give it an IEC 61360 record through the real dialog.
    def fill_record(dialog: Any) -> None:
        dialog.preferred_name.set_rows([("en", "Contact information")])
        dialog.definition.add_row("en", "Where to reach someone")
        dialog.set_data_type(model.DataTypeIEC61360.STRING)
        dialog.accept()

    editor.monkeypatch.setattr(Iec61360Dialog, "exec", fill_record)
    _select_concept(view, created)
    assert _act(view, "concepts.add_record")
    (record,) = created.embedded_data_specifications
    assert match_template(record.data_specification) is TemplateMatch.CURRENT

    # 4. Import a value list from the clipboard, after the preview.
    QApplication.clipboard().setText(
        "Phone, urn:tel\nMail\turn:mail\nbroken line"
    )
    editor.monkeypatch.setattr(
        ValueListImportDialog, "exec", lambda dialog: dialog.accept()
    )
    _select_concept(view, created)
    assert _act(view, "concepts.import_value_list")
    content = record.data_specification_content
    assert {p.value for p in content.value_list} == {"Phone", "Mail"}  # type: ignore[attr-defined]

    # 5. Fix the keys of the 35 records that use the older spelling.
    _select(view, _concepts_node(view))
    assert _act(view, "concepts.fix_keys")
    assert all(
        match_template(r.data_specification) is TemplateMatch.CURRENT
        for c in package.objStore
        if isinstance(c, model.ConceptDescription)
        for r in c.embedded_data_specifications
    )

    # 6. The view lists the descriptions by id, and the package stays as it is.
    done = snapshot(package.objStore)
    editor.monkeypatch.setattr(
        concept_actions,
        "ask_concept_order",
        lambda current, parent=None: ConceptOrder.ID,
    )
    assert _act(view, "concepts.order")
    ids = [c.id for c in _concept_rows(view)]
    assert ids == sorted(ids, key=str.lower)
    assert snapshot(package.objStore) == done

    # 7. What is shown is what is saved.
    assert _reload(package, editor.dir) == done

    # 8. Undo gives back the package as it was read. Every step is one undo.
    steps = 0
    while stack.can_undo:
        stack.undo()
        steps += 1
    assert steps == 4  # create, record, import, fix keys
    assert snapshot(package.objStore) == original
    assert created.id not in [c.id for c in _concept_rows(view)]
    assert len(_concept_rows(view)) == 35
    while stack.can_redo:
        stack.redo()
    assert snapshot(package.objStore) == done
