"""Tests for planning a paste (D12, D13)."""

import pytest
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.paste import PasteError
from aas_editor.application.operations.paste import PastePlan
from aas_editor.application.operations.paste import paste_commands
from aas_editor.application.operations.paste import plan_paste


def _ids(container: object) -> list[str | None]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


def _paste(stack: CommandStack, owner: object, plan: PastePlan) -> None:
    with stack.group(plan.description):
        for command in paste_commands(observer_for(owner), plan):
            stack.push(command)


class TestElements:
    def test_a_copy_is_inserted_below_with_a_numbered_idshort(self) -> None:
        submodel = make_submodel(
            elements=[make_property("Pump"), make_property("Other")]
        )
        elements = submodel.submodel_element
        source = next(iter(elements))

        plan = plan_paste(elements, [source], index=1)
        _paste(CommandStack(), submodel, plan)

        assert _ids(elements) == ["Pump", "Pump_1", "Other"]
        assert source in elements

    def test_the_source_is_not_changed_or_added(self) -> None:
        source = make_property("Pump")
        submodel = make_submodel(elements=[make_property("Pump")])

        plan = plan_paste(submodel.submodel_element, [source], index=0)

        assert source.parent is None
        assert plan.items[0].copy is not source
        assert plan.items[0].original_name == "Pump"

    def test_pasting_twice_gives_two_different_duplicates(self) -> None:
        submodel = make_submodel(elements=[make_property("Pump")])
        elements = submodel.submodel_element
        buffer = [make_property("Pump")]
        stack = CommandStack()

        _paste(stack, submodel, plan_paste(elements, buffer))
        _paste(stack, submodel, plan_paste(elements, buffer))

        assert _ids(elements) == ["Pump", "Pump_1", "Pump_2"]

    def test_several_items_keep_their_order_and_names_are_unique(self) -> None:
        submodel = make_submodel(
            elements=[make_property("A"), make_property("Z")]
        )
        elements = submodel.submodel_element
        buffer = [make_property("A"), make_property("B"), make_property("A")]

        _paste(CommandStack(), submodel, plan_paste(elements, buffer, index=1))

        assert _ids(elements) == ["A", "A_1", "B", "A_2", "Z"]

    def test_undo_removes_all_copies_in_one_step(self) -> None:
        submodel = make_submodel(elements=[make_property("A")])
        stack = CommandStack()
        buffer = [make_property("B"), make_property("C")]

        _paste(
            stack, submodel, plan_paste(submodel.submodel_element, buffer, 0)
        )
        stack.undo()

        assert _ids(submodel.submodel_element) == ["A"]
        assert not stack.can_undo

    def test_a_free_name_is_kept(self) -> None:
        submodel = make_submodel(elements=[make_property("A")])

        plan = plan_paste(submodel.submodel_element, [make_property("B")])

        assert plan.renamed == ()

    def test_annotations_take_a_paste_above(self) -> None:
        relationship = make_annotated_relationship(
            annotations=[make_property("N1"), make_property("N2")]
        )
        make_submodel(elements=[relationship])

        plan = plan_paste(
            relationship.annotation, [make_property("N3")], index=1
        )
        _paste(CommandStack(), relationship, plan)

        assert _ids(relationship.annotation) == ["N1", "N3", "N2"]

    def test_list_children_get_no_idshort_of_their_own(self) -> None:
        sml = make_list("L", [make_property("x", "1")])
        make_submodel(elements=[sml])

        plan = plan_paste(sml.value, [make_property("y", "2")], index=0)
        _paste(CommandStack(), sml, plan)

        assert [m.value for m in sml.value] == ["2", "1"]  # type: ignore[attr-defined]

    def test_a_collection_copy_keeps_its_children(self) -> None:
        submodel = make_submodel(elements=[])
        source = make_collection("C", [make_property("a"), make_property("b")])

        _paste(
            CommandStack(),
            submodel,
            plan_paste(submodel.submodel_element, [source]),
        )

        copy = submodel.get_referable("C")
        assert _ids(copy.value) == ["a", "b"]  # type: ignore[attr-defined]

    def test_a_submodel_cannot_be_pasted_among_elements(self) -> None:
        submodel = make_submodel()

        with pytest.raises(PasteError):
            plan_paste(submodel.submodel_element, [make_submodel(id_="urn:x")])

    def test_an_empty_buffer_is_refused(self) -> None:
        with pytest.raises(PasteError):
            plan_paste(make_submodel().submodel_element, [])


class TestIdentifiables:
    def test_a_copied_submodel_gets_a_new_id(self) -> None:
        original = make_submodel(elements=[make_property("P")])
        store = make_store(original)

        plan = plan_paste(store, [original], taken_ids={original.id})
        _paste(CommandStack(), original, plan)

        ids = {o.id for o in store}
        assert len(ids) == 2
        assert all(i.startswith("urn:uuid:") for i in ids - {original.id})

    def test_a_cut_submodel_keeps_its_id(self) -> None:
        cut = make_submodel(id_="urn:cut")
        store = make_store()

        plan = plan_paste(store, [cut], keep_ids=True, taken_ids=set())
        _paste(CommandStack(), cut, plan)

        assert [o.id for o in store] == ["urn:cut"]

    def test_a_cut_gets_a_new_id_if_its_id_is_taken(self) -> None:
        cut = make_submodel(id_="urn:cut")
        store = make_store(make_submodel(id_="urn:cut"))

        plan = plan_paste(store, [cut], keep_ids=True, taken_ids={"urn:cut"})

        assert plan.items[0].copy.id != "urn:cut"  # type: ignore[attr-defined]
        assert plan.items[0].original_name == "urn:cut"

    def test_a_concept_description_copy_gets_a_new_id(self) -> None:
        concept = make_concept_description()
        store = make_store(concept)

        plan = plan_paste(store, [concept], taken_ids={concept.id})

        assert plan.items[0].copy.id != concept.id  # type: ignore[attr-defined]

    def test_an_element_cannot_be_pasted_among_identifiables(self) -> None:
        with pytest.raises(PasteError):
            plan_paste(make_store(), [make_property("P")])
