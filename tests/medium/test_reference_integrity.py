"""Ids, renames, and deletes through the item models and the tree views.

The dialogs are answered by stubbing `exec` of the dialog classes. The
decisions themselves are tested in `tests/small`.
"""

from collections.abc import Callable
from collections.abc import Iterator

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import OTHER_ID
from tests.reference_factories import Linked
from tests.reference_factories import make_linked
from tests.serialization import snapshot

EDIT = Qt.ItemDataRole.EditRole


class Answers:
    """Records the dialogs that were shown, and answers them."""

    def __init__(self) -> None:
        self.dialogs: list[QDialog] = []
        self.boxes: list[QMessageBox] = []
        self.dialog_action: Callable[[QDialog], None] = lambda dialog: (
            dialog.accept()
        )
        self.box_button = "Delete"


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch) -> Iterator[Answers]:
    """Accepts every dialog, and clicks a button of every message box."""
    recorded = Answers()

    def dialog_exec(self: QDialog) -> int:
        recorded.dialogs.append(self)
        recorded.dialog_action(self)
        return self.result()

    def box_exec(self: QMessageBox) -> int:
        recorded.boxes.append(self)
        for button in self.buttons():
            if button.text() == recorded.box_button:
                button.click()
        return 0

    monkeypatch.setattr(QDialog, "exec", dialog_exec)
    monkeypatch.setattr(QMessageBox, "exec", box_exec)
    yield recorded


def _keys(reference: model.Reference | None) -> list[str]:
    assert reference is not None
    return [key.value for key in reference.key]


def _package_with(model_support, linked: Linked):
    table = model_support.pack_table(*linked.store)
    return table, model_support.package_of(table)


class TestIdEdit:
    def test_editing_an_id_updates_the_references_after_the_preview(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        original = snapshot(package.objStore)
        details = model_support.detail_table(table, "submodels", "Main")

        edited = details.setData(
            model_support.find(details, "id"), "urn:test:renamed", EDIT
        )

        assert edited
        assert linked.main.id == "urn:test:renamed"
        assert sorted(_keys(r)[0] for r in linked.shell.submodel) == [
            OTHER_ID,
            "urn:test:renamed",
        ]
        assert _keys(linked.pointer.value)[0] == "urn:test:renamed"
        assert len(answers.dialogs) == 1
        package.commandStack.undo()
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_the_preview_lists_the_references_to_change(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        details = model_support.detail_table(
            table, "concept_descriptions", "Concept"
        )
        shown: list[list[list[str]]] = []
        answers.dialog_action = lambda dialog: (
            shown.append(dialog.table.texts()),  # type: ignore[attr-defined]
            dialog.accept(),
        )

        details.setData(model_support.find(details, "id"), "urn:test:cd2", EDIT)

        assert [row[0] for row in shown[0]] == [
            "Property 'Name' of Submodel 'Main' / semantic_id",
            "Property 'Group.Inner' of Submodel 'Main' / semantic_id",
            "ReferenceElement 'ConceptLink' of Submodel 'Main' / value",
        ]

    def test_cancelling_the_preview_leaves_everything(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        original = snapshot(package.objStore)
        details = model_support.detail_table(
            table, "concept_descriptions", "Concept"
        )
        answers.dialog_action = lambda dialog: dialog.reject()

        edited = details.setData(
            model_support.find(details, "id"), "urn:test:cd2", EDIT
        )

        assert not edited
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_an_id_without_references_needs_no_preview(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        details = model_support.detail_table(table, "shells", "Shell")

        edited = details.setData(
            model_support.find(details, "id"), "urn:test:shell2", EDIT
        )

        assert edited
        assert linked.shell.id == "urn:test:shell2"
        assert answers.dialogs == []

    def test_an_id_of_another_object_is_refused_with_a_message(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        original = snapshot(package.objStore)
        details = model_support.detail_table(table, "submodels", "Main")

        edited = details.setData(
            model_support.find(details, "id"), CONCEPT_ID, EDIT
        )

        assert not edited
        assert CONCEPT_ID in details.lastErrorMsg
        assert linked.main.id == MAIN_ID
        assert snapshot(package.objStore) == original

    def test_the_package_tree_refuses_a_duplicate_id_in_its_id_column(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        main = model_support.find(
            table,
            "Main",
            model_support.find(table, "submodels", table.index(0, 0)),
        )
        cell = main.siblingAtColumn(model_support.column(table, "id"))

        edited = table.setData(cell, OTHER_ID, EDIT)

        assert not edited
        assert OTHER_ID in table.lastErrorMsg
        assert linked.main.id == MAIN_ID

    def test_the_package_tree_renames_through_its_id_column(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        main = model_support.find(
            table,
            "Main",
            model_support.find(table, "submodels", table.index(0, 0)),
        )
        cell = main.siblingAtColumn(model_support.column(table, "id"))

        edited = table.setData(cell, "urn:test:renamed", EDIT)

        assert edited
        assert _keys(linked.link.value)[0] == "urn:test:renamed"

    def test_replacing_an_object_by_one_with_another_id_updates_references(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        original = snapshot(package.objStore)
        concept = model_support.find(
            table,
            "Concept",
            model_support.find(
                table, "concept_descriptions", table.index(0, 0)
            ),
        )
        replacement = model.ConceptDescription("urn:test:cd2", "Concept")

        edited = table.setData(concept, replacement, EDIT)

        assert edited
        assert replacement in package.objStore
        assert _keys(linked.name.semantic_id) == ["urn:test:cd2"]
        package.commandStack.undo()
        assert snapshot(package.objStore) == original


class TestIdShortEdit:
    def test_editing_an_idshort_updates_the_references_through_it(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        original = snapshot(package.objStore)
        details = model_support.detail_table(
            table, "submodels", "Main", "Group"
        )

        edited = details.setData(
            model_support.find(details, "id_short"), "Cluster", EDIT
        )

        assert edited
        assert _keys(linked.link.value) == [MAIN_ID, "Cluster", "Inner"]
        assert _keys(linked.relationship.second) == [
            MAIN_ID,
            "Cluster",
            "Inner",
        ]
        package.commandStack.undo()
        assert snapshot(package.objStore) == original

    def test_an_invalid_idshort_is_replaced_by_the_suggestion_when_accepted(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        details = model_support.detail_table(table, "submodels", "Main", "Name")
        answers.box_button = "Use suggestion"

        edited = details.setData(
            model_support.find(details, "id_short"), "my motor!", EDIT
        )

        assert edited
        assert linked.name.id_short == "My_motor"
        assert "My_motor" in answers.boxes[0].informativeText()

    def test_an_invalid_idshort_changes_nothing_when_the_suggestion_is_declined(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, package = _package_with(model_support, linked)
        details = model_support.detail_table(table, "submodels", "Main", "Name")
        answers.box_button = "Cancel"

        edited = details.setData(
            model_support.find(details, "id_short"), "my motor!", EDIT
        )

        assert not edited
        assert linked.name.id_short == "Name"
        assert not package.commandStack.can_undo

    def test_an_idshort_of_a_sibling_suggests_a_numbered_name(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        details = model_support.detail_table(table, "submodels", "Main", "Name")
        answers.box_button = "Use suggestion"

        details.setData(model_support.find(details, "id_short"), "Group", EDIT)

        assert linked.name.id_short == "Group_1"


class TestSemanticIdEdit:
    def test_setting_a_semantic_id_keeps_the_position_of_the_element(
        self, model_support, answers: Answers
    ) -> None:
        linked = make_linked()
        table, _ = _package_with(model_support, linked)
        details = model_support.detail_table(
            table, "submodels", "Main", "Group"
        )
        reference = model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:other"),)
        )

        details.setData(
            model_support.find(details, "semantic_id"), reference, EDIT
        )

        names = [element.id_short for element in linked.main.submodel_element]
        assert names[:3] == ["Name", "Group", "Items"]


class TestDelete:
    def test_deleting_a_referenced_object_asks_and_removes_the_references(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(shown.index("concept_descriptions", "Concept"))

        shown.view.onDelClear()

        assert linked.concept not in package.objStore
        assert linked.name.semantic_id is None
        assert linked.concept_link.value is None
        assert len(answers.dialogs) == 1
        shown.view.onUndo()
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_deleting_can_leave_the_references(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("concept_descriptions", "Concept"))
        answers.dialog_action = lambda dialog: (
            dialog.keep_button.setChecked(True),  # type: ignore[attr-defined]
            dialog.accept(),
        )

        shown.view.onDelClear()

        assert linked.concept not in package.objStore
        assert linked.name.semantic_id is not None

    def test_cancelling_the_usages_dialog_deletes_nothing(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(shown.index("concept_descriptions", "Concept"))
        answers.dialog_action = lambda dialog: dialog.reject()

        shown.view.onDelClear()

        assert linked.concept in package.objStore
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_deleting_several_referenced_objects_shows_one_dialog_and_one_step(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(
            shown.index("submodels", "Main"),
            shown.index("submodels", "Other"),
        )

        shown.view.onDelClear()

        assert len(answers.dialogs) == 1
        assert linked.main not in package.objStore
        assert linked.other not in package.objStore
        shown.view.onUndo()
        assert snapshot(package.objStore) == original
        assert not package.commandStack.can_undo

    def test_deleting_a_submodel_without_usages_asks_for_confirmation(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        linked.shell.submodel.clear()
        shown = views()
        package = shown.open_package(linked.shell, linked.other, linked.concept)
        shown.select(shown.index("submodels", "Other"))
        answers.box_button = "Cancel"

        shown.view.onDelClear()

        assert linked.other in package.objStore
        assert len(answers.boxes) == 1

    def test_confirming_the_question_deletes(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        linked.shell.submodel.clear()
        shown = views()
        package = shown.open_package(linked.shell, linked.other)
        shown.select(shown.index("submodels", "Other"))
        answers.box_button = "Delete"

        shown.view.onDelClear()

        assert linked.other not in package.objStore
        assert len(answers.boxes) == 1
        assert answers.dialogs == []

    def test_deleting_a_plain_property_asks_nothing(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        shown.open_package(*linked.store)
        shown.select(shown.index("submodels", "Other", "Pointer"))

        shown.view.onDelClear()

        assert answers.dialogs == []
        assert answers.boxes == []
        assert len(list(linked.other.submodel_element)) == 0

    def test_cutting_asks_nothing_and_leaves_the_references(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("concept_descriptions", "Concept"))

        shown.view.onCut()

        assert answers.dialogs == []
        assert answers.boxes == []
        assert linked.concept not in package.objStore
        assert linked.name.semantic_id is not None

    def test_deleting_a_list_item_moves_references_to_later_items_up(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(shown.index("submodels", "Main", "Items", "Property"))

        shown.view.onDelClear()

        assert _keys(linked.list_link.value) == [MAIN_ID, "Items", "0"]
        shown.view.onUndo()
        assert snapshot(package.objStore) == original

    def test_deleting_a_shell_leaves_its_submodels_for_f_edt_02_criterion_6(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("shells", "Shell"))
        answers.box_button = "Delete"

        shown.view.onDelClear()

        assert linked.shell not in package.objStore
        assert linked.main in package.objStore
        assert linked.other in package.objStore
        assert len(answers.boxes) == 1

    def test_deleting_a_reference_of_a_shell_keeps_the_submodel_for_f_edt_03_criterion_6(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        attrs = shown.attrs_view("shells", "Shell")
        proxy = attrs.model()
        row = next(
            proxy.index(r, 0)
            for r in range(proxy.rowCount())
            if proxy.index(r, 0).data() == "submodel"
        )
        attrs.expand(row)
        selection = attrs.selectionModel()
        selection.setCurrentIndex(
            proxy.index(0, 0, row),
            selection.SelectionFlag.ClearAndSelect,
        )

        attrs.onDelClear()

        assert len(linked.shell.submodel) == 1
        assert linked.main in package.objStore
        assert linked.other in package.objStore
        assert answers.dialogs == []
        assert answers.boxes == []

    def test_shift_skips_the_question_but_not_the_usages(
        self, views, answers: Answers, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from PyQt6.QtWidgets import QApplication

        linked = make_linked()
        linked.shell.submodel.clear()
        shown = views()
        package = shown.open_package(linked.shell, linked.other)
        monkeypatch.setattr(
            QApplication,
            "keyboardModifiers",
            staticmethod(lambda: Qt.KeyboardModifier.ShiftModifier),
        )
        shown.select(shown.index("submodels", "Other"))

        shown.view.onDelClear()

        assert linked.other not in package.objStore
        assert answers.boxes == []
        assert answers.dialogs == []

    def test_shift_still_shows_the_usages(
        self, views, answers: Answers, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from PyQt6.QtWidgets import QApplication

        linked = make_linked()
        shown = views()
        shown.open_package(*linked.store)
        monkeypatch.setattr(
            QApplication,
            "keyboardModifiers",
            staticmethod(lambda: Qt.KeyboardModifier.ShiftModifier),
        )
        shown.select(shown.index("concept_descriptions", "Concept"))

        shown.view.onDelClear()

        assert len(answers.dialogs) == 1

    def test_delete_is_refused_in_read_mode(
        self, views, answers: Answers
    ) -> None:
        from aas_editor.application.editing import edit_mode

        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("concept_descriptions", "Concept"))
        edit_mode().set_editing(False)

        shown.view.onDelClear()

        assert linked.concept in package.objStore
        assert linked.name.semantic_id is not None


class TestActions:
    @pytest.fixture(autouse=True)
    def registered(self, qapp: object) -> None:
        from aas_editor.ui.reference_actions import register_reference_actions

        register_reference_actions()

    def test_rename_id_is_offered_for_submodels_only(self, views) -> None:
        linked = make_linked()
        shown = views()
        shown.open_package(*linked.store)

        shown.select(shown.index("submodels", "Main"))
        shown.view.updateActions(shown.view.currentIndex())
        for_submodel = shown.view.registeredActions.find(
            "references.rename_id"
        ).isEnabled()
        shown.select(shown.index("submodels", "Main", "Name"))
        shown.view.updateActions(shown.view.currentIndex())
        for_property = shown.view.registeredActions.find(
            "references.rename_id"
        ).isEnabled()

        assert for_submodel
        assert not for_property

    def test_rename_id_action_renames_with_the_references(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(shown.index("submodels", "Main"))
        shown.view.updateActions(shown.view.currentIndex())

        def type_new_id(dialog: QDialog) -> None:
            dialog.edit.setText("urn:test:renamed")  # type: ignore[attr-defined]
            dialog.accept()

        answers.dialog_action = type_new_id

        shown.view.registeredActions.find("references.rename_id").trigger()

        assert linked.main.id == "urn:test:renamed"
        assert _keys(linked.link.value)[0] == "urn:test:renamed"
        shown.view.onUndo()
        assert snapshot(package.objStore) == original

    def test_rename_id_action_does_nothing_when_cancelled(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("submodels", "Main"))
        shown.view.updateActions(shown.view.currentIndex())
        answers.dialog_action = lambda dialog: dialog.reject()

        shown.view.registeredActions.find("references.rename_id").trigger()

        assert linked.main.id == MAIN_ID
        assert not package.commandStack.can_undo

    def test_rename_id_short_action_updates_references(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        shown.open_package(*linked.store)
        shown.select(shown.index("submodels", "Main", "Group"))
        shown.view.updateActions(shown.view.currentIndex())

        def type_new_id_short(dialog: QDialog) -> None:
            dialog.edit.setText("Cluster")  # type: ignore[attr-defined]
            dialog.accept()

        answers.dialog_action = type_new_id_short

        shown.view.registeredActions.find(
            "references.rename_id_short"
        ).trigger()

        assert linked.group.id_short == "Cluster"
        assert _keys(linked.link.value) == [MAIN_ID, "Cluster", "Inner"]

    def test_fix_references_action_repairs_and_can_be_undone(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        linked.pointer.value = model.ModelReference(
            (
                model.Key(model.KeyTypes.SUBMODEL, "Main"),
                model.Key(model.KeyTypes.PROPERTY, "Name"),
            ),
            model.Property,
        )
        shown = views()
        package = shown.open_package(*linked.store)
        original = snapshot(package.objStore)
        shown.select(shown.index("submodels", "Other"))
        shown.view.updateActions(shown.view.currentIndex())

        shown.view.registeredActions.find("references.fix_references").trigger()

        assert _keys(linked.pointer.value) == [MAIN_ID, "Name"]
        shown.view.onUndo()
        assert snapshot(package.objStore) == original

    def test_fix_references_reports_when_nothing_needs_repair(
        self, views, answers: Answers
    ) -> None:
        linked = make_linked()
        shown = views()
        package = shown.open_package(*linked.store)
        shown.select(shown.index("submodels", "Other"))
        shown.view.updateActions(shown.view.currentIndex())

        shown.view.registeredActions.find("references.fix_references").trigger()

        assert not package.commandStack.can_undo
        assert "No reference needs" in answers.boxes[0].text()

    def test_actions_are_disabled_in_read_mode(self, views) -> None:
        from aas_editor.application.editing import edit_mode

        linked = make_linked()
        shown = views()
        shown.open_package(*linked.store)
        shown.select(shown.index("submodels", "Main"))
        edit_mode().set_editing(False)

        shown.view.updateActions(shown.view.currentIndex())

        for action_id in (
            "references.rename_id",
            "references.rename_id_short",
            "references.sync_id_short",
            "references.fix_references",
        ):
            action = shown.view.registeredActions.find(action_id)
            assert action is not None
            assert not action.isEnabled()
