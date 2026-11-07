"""Deleting parts of an IEC 61360 record through the record dialog.

F-EDT-05 AC7: deleting a value list as a whole, or its last pair, leaves the
record without a value list. AC4: choosing "(none)" for the data type removes
it. Each change is one step, undone, redone, saved, and read again.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.medium.concept_lab import build_lab_class
from tests.serialization import snapshot

from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY

CONCEPTS = "concept_descriptions"


def _concept(**content: Any) -> model.ConceptDescription:
    return model.ConceptDescription(
        "urn:cd:colour",
        id_short="Colour",
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                make_external_reference(IEC_61360_TEMPLATE_KEY),
                model.DataSpecificationIEC61360(
                    model.PreferredNameTypeIEC61360({"en": "Colour"}),
                    **content,
                ),
            )
        ],
    )


def _pairs(*values: str) -> set[model.ValueReferencePair]:
    return {
        model.ValueReferencePair(v, make_external_reference(f"urn:v:{v}"))
        for v in values
    }


@pytest.fixture
def lab(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    return build_lab_class(views, monkeypatch, tmp_path)


def _content(lab: Any) -> model.DataSpecificationIEC61360:
    record = lab.concept("urn:cd:colour").embedded_data_specifications[0]
    content = record.data_specification_content
    assert isinstance(content, model.DataSpecificationIEC61360)
    return content


def _edit(lab: Any, fill: Any) -> None:
    from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog

    lab.select((CONCEPTS, "Colour"))
    lab.fill(Iec61360Dialog, fill)
    lab.act("concepts.edit_record")


def _saved_content(lab: Any, tmp_path: Path) -> model.DataSpecificationIEC61360:
    from aas_workingbench.package import Package

    path = tmp_path / "again.aasx"
    lab.package.write(path)
    concept = Package(path).objStore.get_item("urn:cd:colour")
    assert isinstance(concept, model.ConceptDescription)
    content = concept.embedded_data_specifications[0].data_specification_content
    assert isinstance(content, model.DataSpecificationIEC61360)
    return content


class TestValueList:
    def test_the_dialog_lists_the_pairs_and_offers_to_remove_them(
        self, lab
    ) -> None:
        from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog
        from aas_workingbench.domain.data_specifications import draft_of

        lab = lab(_concept(value_list=_pairs("Red", "Blue")))
        dialog = Iec61360Dialog(draft_of(_content(lab)))

        assert [
            dialog.pairs_list.item(n).text()
            for n in range(dialog.pairs_list.count())
        ] == [
            "Blue  =  GlobalReference urn:v:Blue",
            "Red  =  GlobalReference urn:v:Red",
        ]
        assert not dialog.remove_list_button.isHidden()

    def test_removing_the_only_pair_leaves_no_value_list(
        self, lab, tmp_path: Path
    ) -> None:
        lab = lab(_concept(value_list=_pairs("Red")))
        before = snapshot(lab.store)

        _edit(lab, lambda d: d.remove_pair(0))
        done = snapshot(lab.store)

        assert _content(lab).value_list is None
        assert _saved_content(lab, tmp_path).value_list is None
        lab.stack.undo()
        assert snapshot(lab.store) == before
        assert len(_content(lab).value_list or ()) == 1
        lab.stack.redo()
        assert snapshot(lab.store) == done

    def test_remove_value_list_takes_every_pair_away(self, lab) -> None:
        lab = lab(_concept(value_list=_pairs("Red", "Green", "Blue")))

        _edit(lab, lambda d: d.remove_value_list())

        assert _content(lab).value_list is None
        assert dict(_content(lab).preferred_name) == {"en": "Colour"}

    def test_removing_one_of_two_pairs_keeps_the_other(self, lab) -> None:
        lab = lab(_concept(value_list=_pairs("Red", "Blue")))

        # The list shows Blue first.
        _edit(lab, lambda d: d.remove_pair(0))

        assert [p.value for p in _content(lab).value_list or ()] == ["Red"]

    def test_the_buttons_do_the_same_as_the_methods(self, lab) -> None:
        from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog
        from aas_workingbench.domain.data_specifications import draft_of

        lab = lab(_concept(value_list=_pairs("Red", "Blue")))
        dialog = Iec61360Dialog(draft_of(_content(lab)))

        dialog.pairs_list.setCurrentRow(0)
        dialog.remove_pair_button.click()
        assert [p.value for p in dialog.draft.value_list or ()] == ["Red"]
        dialog.remove_list_button.click()

        assert dialog.draft.value_list is None
        assert dialog.pairs_list.isHidden()
        assert "No pairs" in dialog.value_list_label.text()

    def test_a_pair_number_that_does_not_exist_changes_nothing(
        self, lab
    ) -> None:
        lab = lab(_concept(value_list=_pairs("Red")))

        _edit(lab, lambda d: d.remove_pair(5))

        assert len(_content(lab).value_list or ()) == 1

    def test_without_a_value_list_the_remove_buttons_are_hidden(
        self, lab
    ) -> None:
        from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog
        from aas_workingbench.domain.data_specifications import draft_of

        lab = lab(_concept())
        dialog = Iec61360Dialog(draft_of(_content(lab)))

        assert dialog.remove_list_button.isHidden()
        assert dialog.remove_pair_button.isHidden()


class TestDataType:
    def test_a_chosen_data_type_is_stored_as_the_literal(
        self, lab, tmp_path: Path
    ) -> None:
        lab = lab(_concept())

        _edit(
            lab,
            lambda d: d.set_data_type(
                model.DataTypeIEC61360.STRING_TRANSLATABLE
            ),
        )

        assert (
            _content(lab).data_type
            is model.DataTypeIEC61360.STRING_TRANSLATABLE
        )
        assert (
            _saved_content(lab, tmp_path).data_type
            is model.DataTypeIEC61360.STRING_TRANSLATABLE
        )

    def test_choosing_none_removes_the_data_type(
        self, lab, tmp_path: Path
    ) -> None:
        lab = lab(_concept(data_type=model.DataTypeIEC61360.INTEGER_COUNT))
        before = snapshot(lab.store)

        _edit(lab, lambda d: d.set_data_type(None))
        done = snapshot(lab.store)

        assert _content(lab).data_type is None
        assert _saved_content(lab, tmp_path).data_type is None
        lab.stack.undo()
        assert _content(lab).data_type is model.DataTypeIEC61360.INTEGER_COUNT
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert snapshot(lab.store) == done
