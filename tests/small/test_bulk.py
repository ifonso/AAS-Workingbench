"""Tests for removing attributes from a submodel in bulk (F-EDT-03 AC11)."""

from basyx.aas import model
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.bulk import RemovableAttribute
from aas_editor.application.operations.bulk import available_attributes
from aas_editor.application.operations.bulk import plan_remove_attributes
from aas_editor.application.operations.bulk import removal_commands
from aas_editor.domain.walking import descendants


class _Owner:
    """Stands in for a package: something that scopes an observer."""


OWNER = _Owner()


def _qualifier(name: str) -> model.Qualifier:
    return model.Qualifier(name, model.datatypes.String, "v")


def _extension(name: str) -> model.Extension:
    return model.Extension(name, model.datatypes.String, "v")


def _submodel() -> model.Submodel:
    """A submodel with qualifiers, extensions and descriptions at all depths."""
    top = make_property("Top")
    top.qualifier.add(_qualifier("Q1"))
    top.qualifier.add(_qualifier("Q2"))
    top.description = model.MultiLanguageTextType({"en": "top"})
    deep = make_property("Deep")
    deep.qualifier.add(_qualifier("Q3"))
    deep.extension.add(_extension("E1"))
    deep.category = "PARAMETER"
    note = make_property("Note")
    note.qualifier.add(_qualifier("Q4"))
    annotated = make_annotated_relationship(annotations=(note,))
    item = make_property("ignored")
    item.extension.add(_extension("E2"))
    submodel = make_submodel(
        elements=[
            top,
            make_collection("Inner", [deep]),
            annotated,
            make_list("Items", [item]),
        ]
    )
    submodel.qualifier.add(_qualifier("Q0"))
    submodel.extension.add(_extension("E0"))
    submodel.display_name = model.MultiLanguageNameType({"en": "Sub"})
    return submodel


class TestPlan:
    def test_counts_qualifiers_of_the_submodel_and_every_descendant(
        self,
    ) -> None:
        submodel = _submodel()

        plan = plan_remove_attributes(submodel, {RemovableAttribute.QUALIFIERS})

        assert plan.count(RemovableAttribute.QUALIFIERS) == 5
        assert plan.count(RemovableAttribute.EXTENSIONS) == 0

    def test_annotations_and_list_items_are_included(self) -> None:
        plan = plan_remove_attributes(
            _submodel(),
            {RemovableAttribute.QUALIFIERS, RemovableAttribute.EXTENSIONS},
        )

        owners = {removal.owner.id_short for removal in plan.removals}

        assert "Note" in owners
        assert plan.count(RemovableAttribute.EXTENSIONS) == 3

    def test_single_value_attributes_count_owners(self) -> None:
        plan = plan_remove_attributes(
            _submodel(),
            {
                RemovableAttribute.DESCRIPTIONS,
                RemovableAttribute.DISPLAY_NAMES,
                RemovableAttribute.CATEGORIES,
            },
        )

        assert plan.count(RemovableAttribute.DESCRIPTIONS) == 1
        assert plan.count(RemovableAttribute.DISPLAY_NAMES) == 1
        assert plan.count(RemovableAttribute.CATEGORIES) == 1

    def test_only_the_chosen_attributes_are_in_the_plan(self) -> None:
        plan = plan_remove_attributes(
            _submodel(), {RemovableAttribute.DESCRIPTIONS}
        )

        assert {r.attribute for r in plan.removals} == {
            RemovableAttribute.DESCRIPTIONS
        }

    def test_nothing_to_remove_gives_an_empty_plan(self) -> None:
        plan = plan_remove_attributes(
            make_submodel(elements=[make_property("P")]),
            {RemovableAttribute.QUALIFIERS},
        )

        assert plan.is_empty
        assert plan.summary == "nothing"

    def test_the_summary_names_what_goes(self) -> None:
        plan = plan_remove_attributes(
            _submodel(),
            {RemovableAttribute.QUALIFIERS, RemovableAttribute.EXTENSIONS},
        )

        assert plan.summary == "5 qualifiers and 3 extensions"

    def test_the_question_names_what_goes_and_where(self) -> None:
        submodel = _submodel()
        plan = plan_remove_attributes(submodel, {RemovableAttribute.QUALIFIERS})

        question = plan.question

        assert "5 qualifiers" in question
        assert "Submodel 'Submodel'" in question
        assert "elements" in question
        assert "Undo" in question

    def test_a_single_item_uses_the_singular(self) -> None:
        plan = plan_remove_attributes(
            _submodel(), {RemovableAttribute.CATEGORIES}
        )

        assert plan.summary == "1 category"

    def test_available_attributes_counts_each_kind(self) -> None:
        counts = available_attributes(_submodel())

        assert counts[RemovableAttribute.QUALIFIERS] == 5
        assert counts[RemovableAttribute.EXTENSIONS] == 3

    def test_planning_changes_nothing(self) -> None:
        submodel = _submodel()
        store = make_store(submodel)
        before = snapshot(store)

        plan_remove_attributes(submodel, set(RemovableAttribute))

        assert snapshot(store) == before


class TestCommands:
    def test_removing_qualifiers_leaves_none_on_the_submodel_or_below(
        self,
    ) -> None:
        submodel = _submodel()
        plan = plan_remove_attributes(submodel, {RemovableAttribute.QUALIFIERS})
        stack = CommandStack()

        with stack.group(plan.description):
            for command in removal_commands(observer_for(OWNER), plan):
                stack.push(command)

        remaining = [len(submodel.qualifier)] + [
            len(element.qualifier) for element in _all_elements(submodel)
        ]
        assert remaining == [0] * len(remaining)

    def test_the_whole_removal_is_one_undo_step(self) -> None:
        submodel = _submodel()
        store = make_store(submodel)
        before = snapshot(store)
        plan = plan_remove_attributes(submodel, set(RemovableAttribute))
        stack = CommandStack()

        with stack.group(plan.description):
            for command in removal_commands(observer_for(OWNER), plan):
                stack.push(command)
        removed = snapshot(store)
        stack.undo()
        after_undo = snapshot(store)
        stack.redo()

        assert removed != before
        assert after_undo == before
        assert snapshot(store) == removed
        assert stack.undo_description == plan.description

    def test_descriptions_are_cleared_and_come_back_on_undo(self) -> None:
        submodel = _submodel()
        top = submodel.get_referable("Top")
        plan = plan_remove_attributes(
            submodel, {RemovableAttribute.DESCRIPTIONS}
        )
        stack = CommandStack()

        with stack.group(plan.description):
            for command in removal_commands(observer_for(OWNER), plan):
                stack.push(command)
        cleared = top.description
        stack.undo()

        assert not cleared
        assert top.description == {"en": "top"}

    def test_the_order_of_the_elements_survives_the_removal(self) -> None:
        submodel = _submodel()
        names = [e.id_short for e in submodel.submodel_element]
        plan = plan_remove_attributes(submodel, {RemovableAttribute.QUALIFIERS})
        stack = CommandStack()

        with stack.group(plan.description):
            for command in removal_commands(observer_for(OWNER), plan):
                stack.push(command)

        assert [e.id_short for e in submodel.submodel_element] == names


def _all_elements(submodel: model.Submodel) -> list[model.SubmodelElement]:

    return list(descendants(submodel))
