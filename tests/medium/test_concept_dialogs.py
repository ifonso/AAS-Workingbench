"""The dialogs of the concept description actions, driven through their widgets."""

from basyx.aas import model
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_external_reference

from aas_workingbench.application.operations.data_specs import ImportPlan
from aas_workingbench.application.operations.data_specs import plan_fix_keys
from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_workingbench.domain.data_specifications import Iec61360Draft
from aas_workingbench.domain.data_specifications import build_content


@pytest.fixture
def iec(qapp: object):
    from aas_workingbench.ui import iec61360_dialog

    return iec61360_dialog


@pytest.fixture
def pairs_dialog(qapp: object):
    from aas_workingbench.ui import value_list_dialog

    return value_list_dialog


@pytest.fixture
def dialogs(qapp: object):
    from aas_workingbench.ui import concept_dialogs

    return concept_dialogs


def _accept_enabled(dialog) -> bool:
    from aas_workingbench.ui.concept_dialogs import accept_button

    button = accept_button(dialog.buttons)
    assert button is not None
    return button.isEnabled()


class TestIec61360Dialog:
    def _dialog(self, iec, qtbot: QtBot, draft: Iec61360Draft | None = None):
        dialog = iec.Iec61360Dialog(draft or Iec61360Draft())
        qtbot.addWidget(dialog)
        return dialog

    def test_it_starts_with_a_blank_english_row_and_says_what_is_missing(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(iec, qtbot)

        assert dialog.preferred_name.rows() == [("en", "")]
        assert not _accept_enabled(dialog)
        assert "preferred name" in dialog.problems_label.text().lower()

    def test_a_name_makes_the_record_acceptable(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(iec, qtbot)

        _, text = dialog.preferred_name.row_edits(0)
        text.setText("Maximum speed")

        assert _accept_enabled(dialog)
        assert dialog.problems_label.text() == ""
        assert dialog.draft.preferred_name == [("en", "Maximum speed")]

    def test_a_short_name_over_18_characters_shows_why_and_blocks(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en", "Speed")])
        )

        dialog.short_name.add_row("en", "x" * 19)

        assert not _accept_enabled(dialog)
        assert "19 characters" in dialog.problems_label.text()
        dialog.short_name.set_rows([("en", "x" * 18)])
        assert _accept_enabled(dialog)

    def test_a_bad_language_tag_shows_its_reason(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en_US", "Speed")])
        )

        assert not _accept_enabled(dialog)
        assert "hyphen" in dialog.problems_label.text()

    def test_a_row_can_be_added_and_removed(self, iec, qtbot: QtBot) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en", "Speed")])
        )

        dialog.preferred_name.add_row("de", "Geschwindigkeit")
        assert len(dialog.preferred_name.rows()) == 2
        dialog.preferred_name.set_rows([("en", "Speed")])

        assert dialog.preferred_name.rows() == [("en", "Speed")]

    def test_the_list_offers_every_data_type_and_none(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(iec, qtbot)

        assert sorted(dialog.data_types(), key=lambda t: t.value) == sorted(
            model.DataTypeIEC61360, key=lambda t: t.value
        )
        assert dialog.data_type.itemText(0) == "(none)"
        assert dialog.draft.data_type is None

    @pytest.mark.parametrize("data_type", list(model.DataTypeIEC61360))
    def test_each_data_type_can_be_chosen(
        self, iec, qtbot: QtBot, data_type: model.DataTypeIEC61360
    ) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en", "Speed")])
        )

        dialog.set_data_type(data_type)

        assert dialog.draft.data_type is data_type

    def test_group_headers_cannot_be_chosen(self, iec, qtbot: QtBot) -> None:
        dialog = self._dialog(iec, qtbot)
        headers = [
            dialog.data_type.itemText(n)
            for n in range(dialog.data_type.count())
            if dialog.data_type.itemText(n).startswith("--")
        ]

        assert headers == [
            "-- Property or value --",
            "-- Reference --",
            "-- Document --",
        ]

    def test_a_measure_without_unit_shows_the_constraint_but_can_be_saved(
        self, iec, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en", "Speed")])
        )

        dialog.set_data_type(model.DataTypeIEC61360.REAL_MEASURE)

        assert "AASc-3a-009" in dialog.advisories_label.text()
        assert _accept_enabled(dialog)
        dialog.unit.setText("m/s")
        assert "AASc-3a-009" not in dialog.advisories_label.text()

    def test_every_field_ends_up_in_the_draft(self, iec, qtbot: QtBot) -> None:
        dialog = self._dialog(
            iec, qtbot, Iec61360Draft(preferred_name=[("en", "Speed")])
        )

        dialog.definition.add_row("en", "How fast")
        dialog.unit.setText("m/s")
        dialog.unit_id.setText("urn:unit")
        dialog.symbol.setText("v")
        dialog.source_of_definition.setText("ISO")
        dialog.value_format.setText("NR1")
        dialog.value.setText("5")
        dialog.set_data_type(model.DataTypeIEC61360.INTEGER_MEASURE)
        for level, check in dialog.level_checks.items():
            check.setChecked(level is model.IEC61360LevelType.MIN)
        content = build_content(dialog.draft)

        assert dict(content.definition or {}) == {"en": "How fast"}
        assert content.unit == "m/s"
        assert content.unit_id == make_external_reference("urn:unit")
        assert content.symbol == "v"
        assert content.source_of_definition == "ISO"
        assert content.value_format == "NR1"
        assert content.value == "5"
        assert content.data_type is model.DataTypeIEC61360.INTEGER_MEASURE
        assert content.level_types == {model.IEC61360LevelType.MIN}

    def test_the_value_list_of_a_record_is_kept_and_counted(
        self, iec, qtbot: QtBot
    ) -> None:
        pair = model.ValueReferencePair("Red", make_external_reference("urn:r"))
        dialog = self._dialog(
            iec,
            qtbot,
            Iec61360Draft(
                preferred_name=[("en", "Colour")], value_list=(pair,)
            ),
        )

        assert "1 pair" in dialog.value_list_label.text()
        assert dialog.draft.value_list == (pair,)

    def test_the_template_key_is_shown(self, iec, qtbot: QtBot) -> None:
        from PyQt6.QtWidgets import QLineEdit

        dialog = self._dialog(iec, qtbot)

        keys = [
            e.text() for e in dialog.findChildren(QLineEdit) if e.isReadOnly()
        ]
        assert keys == [IEC_61360_TEMPLATE_KEY]

    def test_ask_returns_the_draft_when_accepted_and_none_when_cancelled(
        self, iec, monkeypatch: pytest.MonkeyPatch, qtbot: QtBot
    ) -> None:
        def accept(dialog) -> None:
            dialog.preferred_name.row_edits(0)[1].setText("Speed")
            dialog.accept()

        monkeypatch.setattr(iec.Iec61360Dialog, "exec", accept)
        accepted = iec.ask_iec61360(Iec61360Draft())
        monkeypatch.setattr(iec.Iec61360Dialog, "exec", lambda d: d.reject())
        cancelled = iec.ask_iec61360(Iec61360Draft())

        assert accepted is not None
        assert accepted.preferred_name == [("en", "Speed")]
        assert cancelled is None


class TestValueListDialog:
    def _content(self, *pairs: model.ValueReferencePair):
        return model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360({"en": "Colour"}),
            value_list=set(pairs) or None,
        )

    def _dialog(self, pairs_dialog, qtbot: QtBot, text: str, *old):
        dialog = pairs_dialog.ValueListImportDialog(self._content(*old), text)
        qtbot.addWidget(dialog)
        return dialog

    def test_lines_are_previewed_with_what_happens_to_each(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(
            pairs_dialog, qtbot, "Red, urn:red\nGreen\nBlue\turn:blue"
        )

        assert dialog.table.texts() == [
            ["Line 1", "Red", "GlobalReference urn:red", "will be added"],
            ["Line 2", "Green", "", dialog.table.texts()[1][3]],
            ["Line 3", "Blue", "GlobalReference urn:blue", "will be added"],
        ]
        assert dialog.table.texts()[1][3].startswith("skipped: has no valueId")
        assert (
            dialog.summary_label.text() == "2 pairs will be added, 1 skipped."
        )
        assert _accept_enabled(dialog)

    def test_a_pair_the_list_has_is_marked(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        old = model.ValueReferencePair(
            "Red", make_external_reference("urn:red")
        )
        dialog = self._dialog(
            pairs_dialog, qtbot, "Red, urn:red\nBlue, urn:blue", old
        )

        assert [row[3] for row in dialog.table.texts()] == [
            "already in the value list",
            "will be added",
        ]
        assert "1 already in the list" in dialog.summary_label.text()

    def test_text_that_cannot_be_read_shows_the_reason_and_blocks(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(pairs_dialog, qtbot, '[{"value": "A",')

        assert "cannot be read" in dialog.error_label.text()
        assert dialog.table.rowCount() == 0
        assert not _accept_enabled(dialog)

    def test_empty_text_is_refused_with_a_message(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(pairs_dialog, qtbot, "   \n")

        assert dialog.error_label.text() == "There is no text to read."
        assert not _accept_enabled(dialog)

    def test_only_skipped_entries_block_the_import(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(pairs_dialog, qtbot, "lonely")

        assert not _accept_enabled(dialog)
        assert dialog.plan is not None
        assert dialog.plan.added == ()

    def test_editing_the_text_updates_the_preview(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        dialog = self._dialog(pairs_dialog, qtbot, "lonely")

        dialog.text_edit.setPlainText("Red, urn:red")

        assert _accept_enabled(dialog)
        assert dialog.table.rowCount() == 1

    def test_code_in_the_text_is_data_and_never_runs(
        self, pairs_dialog, qtbot: QtBot, tmp_path
    ) -> None:
        marker = tmp_path / "owned"
        code = f"__import__('pathlib').Path({str(marker)!r}).write_text('x')"

        dialog = self._dialog(pairs_dialog, qtbot, f"{code}\n[{code}]")

        assert not marker.exists()
        assert not _accept_enabled(dialog)

    def test_a_long_list_previews_only_the_first_rows(
        self, pairs_dialog, qtbot: QtBot
    ) -> None:
        text = "\n".join(f"V{n}, urn:v:{n}" for n in range(800))

        dialog = self._dialog(pairs_dialog, qtbot, text)

        assert dialog.table.rowCount() == pairs_dialog.MAX_PREVIEW_ROWS
        assert "800 pairs will be added" in dialog.summary_label.text()
        assert "first 500" in dialog.summary_label.text()

    def test_ask_returns_the_plan_when_accepted(
        self, pairs_dialog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            pairs_dialog.ValueListImportDialog, "exec", lambda d: d.accept()
        )

        plan = pairs_dialog.ask_value_list(self._content(), "Red, urn:red")

        assert isinstance(plan, ImportPlan)
        assert [p.value for p in plan.added] == ["Red"]

    def test_ask_returns_none_when_cancelled_or_nothing_to_add(
        self, pairs_dialog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            pairs_dialog.ValueListImportDialog, "exec", lambda d: d.reject()
        )
        cancelled = pairs_dialog.ask_value_list(self._content(), "Red, urn:r")
        monkeypatch.setattr(
            pairs_dialog.ValueListImportDialog, "exec", lambda d: d.accept()
        )
        empty = pairs_dialog.ask_value_list(self._content(), "lonely")

        assert cancelled is None
        assert empty is None


class TestPickerAndPreview:
    def _concepts(self) -> list[model.ConceptDescription]:
        content = build_content(
            Iec61360Draft(preferred_name=[("en", "Maximum speed")])
        )
        return [
            model.ConceptDescription(
                "urn:cd:speed",
                id_short="Speed",
                embedded_data_specifications=[
                    model.EmbeddedDataSpecification(
                        make_external_reference("k"), content
                    )
                ],
            ),
            model.ConceptDescription("urn:cd:weight", id_short="Weight"),
        ]

    def test_the_picker_lists_idshort_name_and_id(
        self, dialogs, qtbot: QtBot
    ) -> None:
        dialog = dialogs.ConceptPickerDialog(
            self._concepts(), "No semantic id."
        )
        qtbot.addWidget(dialog)

        assert dialog.table.texts() == [
            ["Speed", "Maximum speed", "urn:cd:speed"],
            ["Weight", "", "urn:cd:weight"],
        ]
        assert dialog.selected is None
        assert not _accept_enabled(dialog)

    def test_choosing_a_row_enables_assign(self, dialogs, qtbot: QtBot) -> None:
        concepts = self._concepts()
        dialog = dialogs.ConceptPickerDialog(concepts, "")
        qtbot.addWidget(dialog)

        dialog.table.selectRow(1)

        assert dialog.selected is concepts[1]
        assert _accept_enabled(dialog)

    def test_the_filter_hides_rows_that_do_not_match(
        self, dialogs, qtbot: QtBot
    ) -> None:
        dialog = dialogs.ConceptPickerDialog(self._concepts(), "")
        qtbot.addWidget(dialog)

        dialog.filter_edit.setText("maxi")

        assert [dialog.table.isRowHidden(row) for row in range(2)] == [
            False,
            True,
        ]

    def test_a_hidden_selection_does_not_count(
        self, dialogs, qtbot: QtBot
    ) -> None:
        dialog = dialogs.ConceptPickerDialog(self._concepts(), "")
        qtbot.addWidget(dialog)
        dialog.table.selectRow(1)

        dialog.filter_edit.setText("maxi")

        assert dialog.table.isRowHidden(1)
        assert dialog.selected is None
        assert not _accept_enabled(dialog)

    def test_a_preview_with_choice_starts_with_everything_selected(
        self, dialogs, qtbot: QtBot
    ) -> None:
        dialog = dialogs.PreviewDialog(
            "T", "intro", ["a", "b"], [["1", "x"], ["2", "y"]], selectable=True
        )
        qtbot.addWidget(dialog)

        assert dialog.chosen() == [0, 1]
        dialog.table.clearSelection()
        assert dialog.chosen() == []
        assert not _accept_enabled(dialog)

    def test_choose_rows_returns_the_kept_rows_or_none(
        self, dialogs, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(dialogs.PreviewDialog, "exec", lambda d: d.accept())
        kept = dialogs.choose_rows("T", "i", ["a"], [["1"], ["2"]])
        monkeypatch.setattr(dialogs.PreviewDialog, "exec", lambda d: d.reject())
        cancelled = dialogs.choose_rows("T", "i", ["a"], [["1"]])

        assert kept == [0, 1]
        assert cancelled is None

    def test_the_fix_keys_dialog_lists_unknown_keys_and_asks_about_the_rest(
        self, dialogs, qtbot: QtBot
    ) -> None:
        def concept(id_: str, key: str) -> model.ConceptDescription:
            return model.ConceptDescription(
                id_,
                id_short=id_,
                embedded_data_specifications=[
                    model.EmbeddedDataSpecification(
                        make_external_reference(key),
                        build_content(
                            Iec61360Draft(preferred_name=[("en", "n")])
                        ),
                    )
                ],
            )

        plan = plan_fix_keys(
            [
                concept("Wrong", "nonsense"),
                concept(
                    "Older",
                    "http://admin-shell.io/DataSpecificationTemplates/"
                    "DataSpecificationIEC61360/3/0",
                ),
            ]
        )
        dialog = dialogs.FixKeysDialog(plan)
        qtbot.addWidget(dialog)
        dialog.show()

        assert dialog.table.texts() == [
            ["Wrong", "GlobalReference nonsense", "template key"]
        ]
        assert dialog.other_check.isVisible()
        assert not dialog.include_other
        dialog.other_check.setChecked(True)
        assert dialog.include_other

    def test_the_fix_keys_dialog_hides_the_checkbox_without_other_spellings(
        self, dialogs, qtbot: QtBot
    ) -> None:
        plan = plan_fix_keys([])
        dialog = dialogs.FixKeysDialog(plan)
        qtbot.addWidget(dialog)
        dialog.show()

        assert not dialog.other_check.isVisible()
        assert not _accept_enabled(dialog)
