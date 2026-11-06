"""Rename and delete with references in the running editor, on real packages.

The Carbon Footprint template has concept descriptions that the semantic ids of
its elements refer to. Every step goes through the views as a user would, and
undoing all of them must give back the package as it was read. The largest
bundled template, Purchase Order, checks that the plans stay fast.
"""

from collections import Counter
from collections.abc import Iterator
from pathlib import Path
import shutil
import time
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02023 _Template_CarbonFootprint.aasx"
LARGEST_TEMPLATE = (
    Path(__file__).parents[2]
    / "src"
    / "aas_editor"
    / "submodel_templates"
    / "Purchase Order"
    / "1"
    / "0"
    / "IDTA-02050_Template_PurchaseOrder.aasx"
)

# Generous: building the index takes about 20 ms on the largest template. The
# limit only catches a delete that becomes slow on a large package.
SLOWEST_PLAN_SECONDS = 2.0


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path) -> Iterator[SimpleNamespace]:
    """The main window with the package, copied so a save cannot touch it."""
    from aas_editor.editorApp import EditorApp

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
    # Closing the window must not ask whether to save.
    editor.package.commandStack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """Accepts every dialog and confirms every question, and counts them."""
    shown = SimpleNamespace(dialogs=0, questions=0)

    def dialog_exec(self: QDialog) -> int:
        shown.dialogs += 1
        self.accept()
        return self.result()

    def box_exec(self: QMessageBox) -> int:
        shown.questions += 1
        for button in self.buttons():
            if button.text() == "Delete":
                button.click()
        return 0

    monkeypatch.setattr(QDialog, "exec", dialog_exec)
    monkeypatch.setattr(QMessageBox, "exec", box_exec)
    return shown


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


def _referenced_concepts(package, count: int) -> list[model.ConceptDescription]:
    """Concept descriptions that others refer to and whose idShort is unique."""
    from aas_editor.domain.references import ReferenceIndex

    concepts = list(package.concept_descriptions)
    names = Counter(concept.id_short for concept in concepts)
    index = ReferenceIndex(package.objStore)
    chosen = [
        concept
        for concept in concepts
        if concept.id_short
        and names[concept.id_short] == 1
        and len(index.usages_of([concept])) >= 2
    ]
    assert len(chosen) >= count
    return chosen[:count]


def _uses_of_id(package, id_: str) -> int:
    from aas_editor.domain.references import ReferenceIndex

    return sum(
        1
        for slot in ReferenceIndex(package.objStore).slots
        if any(key.value == id_ for key in slot.reference.key)
    )


def test_renaming_and_deleting_keep_the_references_of_a_real_package(
    editor, answers, qtbot
) -> None:
    from aas_editor.domain.references import ReferenceIndex

    view, package, stack = editor.view, editor.package, editor.stack
    original = snapshot(package.objStore)
    dangling_before = len(ReferenceIndex(package.objStore).dangling())
    concept, second, third, fourth = _referenced_concepts(package, 4)
    uses = _uses_of_id(package, concept.id)
    (submodel,) = list(package.submodels)

    # Rename a concept description in the package tree.
    old_id = concept.id
    view.model().setData(
        _index(view, "concept_descriptions", concept.id_short).siblingAtColumn(
            _column(view, "id")
        ),
        "urn:test:renamed-concept",
        Qt.ItemDataRole.EditRole,
    )
    renamed = (
        _uses_of_id(package, old_id),
        _uses_of_id(package, "urn:test:renamed-concept"),
        len(ReferenceIndex(package.objStore).dangling()),
    )

    # Rename the submodel, which the shell refers to.
    view.model().setData(
        _index(view, "submodels", submodel.id_short).siblingAtColumn(
            _column(view, "id")
        ),
        "urn:test:renamed-submodel",
        Qt.ItemDataRole.EditRole,
    )
    shell_refs = [
        reference.key[0].value
        for shell in package.shells
        for reference in shell.submodel
    ]
    after_submodel = len(ReferenceIndex(package.objStore).dangling())

    # Delete one referenced concept description, and remove its references.
    dialogs_before = answers.dialogs
    _select(view, _index(view, "concept_descriptions", second.id_short))
    view.onDelClear()
    deleted_uses = _uses_of_id(package, second.id)
    one_dialog = answers.dialogs - dialogs_before

    # Delete two more together: one dialog, and one undo step for both.
    before_bulk = snapshot(package.objStore)
    dialogs_before = answers.dialogs
    _select(
        view,
        _index(view, "concept_descriptions", third.id_short),
        _index(view, "concept_descriptions", fourth.id_short),
    )
    view.onDelClear()
    bulk_dialogs = answers.dialogs - dialogs_before
    after_bulk = snapshot(package.objStore)
    view.onUndo()
    bulk_undone = snapshot(package.objStore) == before_bulk
    view.onRedo()

    edited = snapshot(package.objStore)
    while stack.can_undo:
        view.setCurrentIndex(_index(view, "shells"))
        view.onUndo()
        qtbot.wait(1)
    undone = snapshot(package.objStore)

    assert renamed == (0, uses, dangling_before)
    assert shell_refs == ["urn:test:renamed-submodel"]
    assert after_submodel == dangling_before
    assert one_dialog == 1
    assert deleted_uses == 0
    assert bulk_dialogs == 1
    assert bulk_undone
    assert after_bulk != before_bulk
    assert edited != original
    assert undone == original
    assert not package.changed


def test_the_plans_stay_fast_on_the_largest_template() -> None:
    from aas_editor.application.operations.delete import plan_delete
    from aas_editor.application.operations.fix import plan_fix_references
    from aas_editor.application.operations.rename import plan_rename_id
    from aas_editor.domain.references import ReferenceIndex
    from aas_editor.infrastructure.package_io import read_package

    parts = read_package(LARGEST_TEMPLATE, failsafe=True)
    objects = list(parts.objects)
    (submodel,) = [o for o in objects if isinstance(o, model.Submodel)]
    concept = next(
        o for o in objects if isinstance(o, model.ConceptDescription)
    )

    started = time.perf_counter()
    plan_delete(objects, [submodel])
    plan_delete(objects, [concept])
    plan_rename_id(objects, concept, "urn:test:other")
    plan_fix_references(objects)
    ReferenceIndex(objects).dangling()
    elapsed = time.perf_counter() - started

    assert elapsed < SLOWEST_PLAN_SECONDS
