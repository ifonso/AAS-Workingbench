"""The dialogs for renames, deletes and repairs, with `exec` stubbed."""

from collections.abc import Callable

from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from pytestqt.qtbot import QtBot
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import make_linked

from aas_workingbench.application.operations.delete import plan_delete
from aas_workingbench.application.operations.rename import plan_rename_id
from aas_workingbench.application.operations.rename import plan_rename_id_short
from aas_workingbench.application.operations.rename import suggest_id_short


@pytest.fixture
def dialogs(qapp: object):
    from aas_workingbench.ui import reference_dialogs

    return reference_dialogs


def _rename_dialog(dialogs, qtbot: QtBot, text: str = "urn:test:cd"):
    linked = make_linked()
    objects = list(linked.store)
    dialog = dialogs.RenameDialog(
        "Rename id",
        "New id",
        linked.concept.id,
        lambda value: plan_rename_id(objects, linked.concept, value),
        generate=lambda: "urn:uuid:generated",
    )
    qtbot.addWidget(dialog)
    return linked, dialog


class TestRenameDialog:
    def test_the_dialog_starts_with_the_current_id_and_no_change(
        self, dialogs, qtbot: QtBot
    ) -> None:
        _, dialog = _rename_dialog(dialogs, qtbot)

        assert dialog.value == CONCEPT_ID
        assert "current value" in dialog.preview_label.text()
        assert not dialog.accept_button.isEnabled()

    def test_typing_an_id_previews_the_references_that_change(
        self, dialogs, qtbot: QtBot
    ) -> None:
        _, dialog = _rename_dialog(dialogs, qtbot)

        dialog.edit.setText("urn:test:cd2")

        assert dialog.accept_button.isEnabled()
        assert dialog.preview_label.text() == (
            "3 references will be updated, in the same undo step."
        )
        assert [row[1:] for row in dialog.table.texts()] == [
            [
                f"GlobalReference {CONCEPT_ID}",
                "GlobalReference urn:test:cd2",
            ]
        ] * 2 + [
            [
                f"ConceptDescription {CONCEPT_ID}",
                "ConceptDescription urn:test:cd2",
            ]
        ]

    def test_an_id_of_another_object_shows_why_and_disables_accept(
        self, dialogs, qtbot: QtBot
    ) -> None:
        _, dialog = _rename_dialog(dialogs, qtbot)

        dialog.edit.setText(MAIN_ID)

        assert MAIN_ID in dialog.error_label.text()
        assert dialog.plan is None
        assert dialog.table.rowCount() == 0
        assert not dialog.accept_button.isEnabled()

    def test_an_empty_id_disables_accept(self, dialogs, qtbot: QtBot) -> None:
        _, dialog = _rename_dialog(dialogs, qtbot)

        dialog.edit.setText("")

        assert dialog.error_label.text() == "The id must not be empty."
        assert not dialog.accept_button.isEnabled()

    def test_generate_puts_a_new_id_in_the_field(
        self, dialogs, qtbot: QtBot
    ) -> None:
        _, dialog = _rename_dialog(dialogs, qtbot)

        dialog.generate_button.click()

        assert dialog.value == "urn:uuid:generated"
        assert dialog.accept_button.isEnabled()

    def test_a_reference_count_of_one_uses_the_singular(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        objects = list(linked.store)
        dialog = dialogs.RenameDialog(
            "Rename id",
            "New id",
            linked.other.id,
            lambda value: plan_rename_id(objects, linked.other, value),
        )
        qtbot.addWidget(dialog)

        dialog.edit.setText("urn:test:o2")

        assert dialog.preview_label.text() == (
            "1 reference will be updated, in the same undo step."
        )
        assert dialog.generate_button is None
        assert dialog.fix_button is None

    def test_fix_replaces_text_that_is_no_idshort(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        objects = list(linked.store)
        dialog = dialogs.RenameDialog(
            "Rename idShort",
            "New idShort",
            "Name",
            lambda value: plan_rename_id_short(objects, linked.name, value),
            suggest=lambda value: suggest_id_short(linked.name, value),
        )
        qtbot.addWidget(dialog)

        dialog.edit.setText("my motor!")
        refused = dialog.plan is None
        enabled_before = dialog.fix_button.isEnabled()
        dialog.fix_button.click()

        assert refused
        assert enabled_before
        assert dialog.value == "My_motor"
        assert dialog.plan is not None
        assert dialog.accept_button.isEnabled()
        assert not dialog.fix_button.isEnabled()

    def test_ask_rename_returns_the_plan_when_accepted(
        self, dialogs, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        linked = make_linked()
        objects = list(linked.store)

        def answer(dialog: QDialog) -> int:
            dialog.edit.setText("urn:test:cd2")  # type: ignore[attr-defined]
            dialog.accept()
            return dialog.result()

        monkeypatch.setattr(QDialog, "exec", answer)

        plan = dialogs.ask_rename(
            "Rename id",
            "New id",
            CONCEPT_ID,
            lambda value: plan_rename_id(objects, linked.concept, value),
        )

        assert plan is not None
        assert plan.new == "urn:test:cd2"
        assert len(plan.changes) == 3

    def test_ask_rename_returns_none_when_cancelled(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        objects = list(linked.store)

        plan = dialogs.ask_rename(
            "Rename id",
            "New id",
            CONCEPT_ID,
            lambda value: plan_rename_id(objects, linked.concept, value),
        )

        assert plan is None

    def test_ask_rename_returns_none_when_the_value_is_unchanged(
        self, dialogs, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        linked = make_linked()
        objects = list(linked.store)
        monkeypatch.setattr(
            QDialog, "exec", lambda self: (self.accept(), self.result())[1]
        )

        plan = dialogs.ask_rename(
            "Rename id",
            "New id",
            CONCEPT_ID,
            lambda value: plan_rename_id(objects, linked.concept, value),
        )

        assert plan is None


class TestChangesDialog:
    def test_changes_are_listed_with_where_before_and_after(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id(list(linked.store), linked.other, "urn:test:o2")

        dialog = dialogs.ReferenceChangesDialog(
            "Rename id", "These change:", plan.changes, ["A note"]
        )
        qtbot.addWidget(dialog)

        assert dialog.table.texts() == [
            [
                "AssetAdministrationShell 'Shell' / submodel",
                f"Submodel {OTHER_ID}",
                "Submodel urn:test:o2",
            ]
        ]
        assert dialog.intro_label.text() == "These change:"
        assert dialog.notes_label.text() == "A note"
        assert not dialog.notes_label.isHidden()

    def test_notes_are_hidden_when_there_are_none(
        self, dialogs, qtbot: QtBot
    ) -> None:
        dialog = dialogs.ReferenceChangesDialog("T", "Intro", [])
        qtbot.addWidget(dialog)

        assert dialog.notes_label.isHidden()

    def test_confirm_returns_true_only_when_accepted(
        self, dialogs, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        declined = dialogs.confirm_reference_changes("T", "Intro", [])
        monkeypatch.setattr(
            QDialog, "exec", lambda self: (self.accept(), self.result())[1]
        )
        accepted = dialogs.confirm_reference_changes("T", "Intro", [])

        assert not declined
        assert accepted

    def test_confirm_rename_needs_no_dialog_without_changes(
        self, dialogs
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id(list(linked.store), linked.shell, "urn:test:s2")

        assert dialogs.confirm_rename(plan)


OTHER_ID = "urn:test:other"


class TestDeleteDialog:
    def test_the_dialog_lists_the_usages_and_offers_both_choices(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.concept])

        dialog = dialogs.DeleteDialog(plan)
        qtbot.addWidget(dialog)

        assert "Concept" in dialog.summary_label.text()
        assert "3 references refer" in dialog.summary_label.text()
        assert [row[0] for row in dialog.table.texts()] == [
            "Property 'Name' of Submodel 'Main' / semantic_id",
            "Property 'Group.Inner' of Submodel 'Main' / semantic_id",
            "ReferenceElement 'ConceptLink' of Submodel 'Main' / value",
        ]
        assert dialog.remove_button.isChecked()
        assert dialog.remove_button.text() == "Delete and remove 3 references"
        assert dialog.kept_label.isHidden()

    def test_required_references_are_listed_as_staying(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.inner])

        dialog = dialogs.DeleteDialog(plan)
        qtbot.addWidget(dialog)

        assert not dialog.kept_label.isHidden()
        assert "second" in dialog.kept_label.text()
        assert dialog.remove_button.text() == "Delete and remove 1 reference"

    def test_without_removable_references_the_choice_is_to_leave_them(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        linked.link.value = None
        plan = plan_delete(list(linked.store), [linked.inner])

        dialog = dialogs.DeleteDialog(plan)
        qtbot.addWidget(dialog)

        assert not dialog.remove_button.isEnabled()
        assert not dialog.remove_references

    def test_the_cancel_button_is_the_default(
        self, dialogs, qtbot: QtBot
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.concept])
        dialog = dialogs.DeleteDialog(plan)
        qtbot.addWidget(dialog)

        defaults = [
            button.text()
            for button in dialog.buttons.buttons()
            if button.isDefault()
        ]

        assert defaults == ["Cancel"]

    def test_many_objects_are_summed_up(self, dialogs, qtbot: QtBot) -> None:
        linked = make_linked()
        targets = [linked.name, linked.group, linked.items, linked.link]
        targets += [linked.list_link, linked.concept_link, linked.relationship]
        plan = plan_delete(list(linked.store), targets)

        dialog = dialogs.DeleteDialog(plan)
        qtbot.addWidget(dialog)

        assert "and 2 more" in dialog.summary_label.text()

    @pytest.mark.parametrize(
        ("choose", "expected"),
        [
            (lambda dialog: dialog.accept(), True),
            (
                lambda dialog: (
                    dialog.keep_button.setChecked(True),
                    dialog.accept(),
                ),
                False,
            ),
            (lambda dialog: dialog.reject(), None),
        ],
        ids=["remove", "keep", "cancel"],
    )
    def test_ask_delete_returns_the_choice(
        self,
        dialogs,
        monkeypatch: pytest.MonkeyPatch,
        choose: Callable[[QDialog], object],
        expected: bool | None,
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.concept])

        def answer(dialog: QDialog) -> int:
            choose(dialog)
            return dialog.result()

        monkeypatch.setattr(QDialog, "exec", answer)

        assert dialogs.ask_delete(plan) is expected


class TestMessageBoxes:
    @staticmethod
    def _click(monkeypatch: pytest.MonkeyPatch, text: str) -> list[QMessageBox]:
        shown: list[QMessageBox] = []

        def answer(box: QMessageBox) -> int:
            shown.append(box)
            for button in box.buttons():
                if button.text() == text:
                    button.click()
            return 0

        monkeypatch.setattr(QMessageBox, "exec", answer)
        return shown

    def test_confirm_delete_names_the_objects_and_defaults_to_cancel(
        self, dialogs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.other])
        shown = self._click(monkeypatch, "Delete")

        confirmed = dialogs.confirm_delete(plan)

        assert confirmed
        assert shown[0].text() == "Delete Submodel 'Other'?"
        assert shown[0].defaultButton().text() == "Cancel"

    def test_confirm_delete_is_false_when_cancelled(
        self, dialogs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.other])
        self._click(monkeypatch, "Cancel")

        assert not dialogs.confirm_delete(plan)

    def test_confirm_delete_is_false_when_the_box_is_dismissed(
        self, dialogs
    ) -> None:
        linked = make_linked()
        plan = plan_delete(list(linked.store), [linked.other])

        assert not dialogs.confirm_delete(plan)

    def test_confirm_suggested_id_short_offers_the_suggestion(
        self, dialogs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        linked = make_linked()
        try:
            plan_rename_id_short(list(linked.store), linked.name, "my motor!")
        except Exception as error:
            refusal = error
        shown = self._click(monkeypatch, "Use suggestion")

        used = dialogs.confirm_suggested_id_short(refusal)  # type: ignore[arg-type]

        assert used
        assert "My_motor" in shown[0].informativeText()
