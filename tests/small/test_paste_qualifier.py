"""Pasting a qualifier into an existing qualifier (F-EDT-07 AC4 and AC5)."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.paste_qualifier import (
    PasteQualifierError,
)
from aas_editor.application.operations.paste_qualifier import (
    paste_qualifier_commands,
)
from aas_editor.application.operations.paste_qualifier import (
    plan_paste_into_qualifier,
)

String = model.datatypes.String
Int = model.datatypes.Int


def _owner(*qualifiers: model.Qualifier) -> model.Property:
    prop = make_property("Element")
    for qualifier in qualifiers:
        prop.qualifier.add(qualifier)
    return prop


def _paste(target: model.Qualifier, pasted: model.Qualifier) -> CommandStack:
    stack = CommandStack()
    plan = plan_paste_into_qualifier(target, pasted)
    with stack.group(plan.description):
        for command in paste_qualifier_commands(ModelChangeObserver(), plan):
            stack.push(command)
    return stack


def test_the_content_is_taken_over_and_the_kind_stays() -> None:
    target = model.Qualifier(
        "Cardinality",
        String,
        "One",
        kind=model.QualifierKind.TEMPLATE_QUALIFIER,
    )
    _owner(target)
    pasted = model.Qualifier(
        "Mark",
        Int,
        5,
        kind=model.QualifierKind.CONCEPT_QUALIFIER,
        value_id=make_external_reference("urn:value"),
        semantic_id=make_external_reference("urn:semantic"),
    )

    _paste(target, pasted)

    assert target.type == "Mark"
    assert target.value_type is Int
    assert target.value == 5
    assert isinstance(target.value, Int)
    assert target.kind is model.QualifierKind.TEMPLATE_QUALIFIER
    assert target.value_id == make_external_reference("urn:value")
    assert target.semantic_id == make_external_reference("urn:semantic")


def test_the_plan_says_that_the_kind_of_the_text_is_not_taken() -> None:
    target = model.Qualifier(
        "T", String, "x", kind=model.QualifierKind.TEMPLATE_QUALIFIER
    )
    _owner(target)

    different = model.Qualifier(
        "T", String, "y", kind=model.QualifierKind.VALUE_QUALIFIER
    )
    same = model.Qualifier(
        "T", String, "y", kind=model.QualifierKind.TEMPLATE_QUALIFIER
    )

    assert plan_paste_into_qualifier(target, different).keeps_kind
    assert not plan_paste_into_qualifier(target, same).keeps_kind


def test_supplemental_semantic_ids_are_replaced() -> None:
    target = model.Qualifier(
        "T",
        String,
        "x",
        semantic_id=make_external_reference("urn:semantic"),
        supplemental_semantic_id=[make_external_reference("urn:old")],
    )
    _owner(target)
    pasted = model.Qualifier(
        "T",
        String,
        "x",
        semantic_id=make_external_reference("urn:semantic"),
        supplemental_semantic_id=[
            make_external_reference("urn:a"),
            make_external_reference("urn:b"),
        ],
    )

    _paste(target, pasted)

    assert [r.key[0].value for r in target.supplemental_semantic_id] == [
        "urn:a",
        "urn:b",
    ]


def test_the_paste_is_one_undo_step_that_gives_the_old_content_back() -> None:
    target = model.Qualifier(
        "Cardinality",
        String,
        "One",
        kind=model.QualifierKind.TEMPLATE_QUALIFIER,
        semantic_id=make_external_reference("urn:old"),
    )
    prop = _owner(target)
    submodel = make_submodel(elements=[prop])
    store = model.DictIdentifiableStore([submodel])
    before = snapshot(store)
    pasted = model.Qualifier("Mark", Int, 5)

    stack = _paste(target, pasted)
    after = snapshot(store)
    stack.undo()

    assert after != before
    assert snapshot(store) == before
    assert not stack.can_undo
    assert target.value == "One"
    assert target.value_type is String


def test_a_value_type_change_works_when_the_old_value_does_not_fit() -> None:
    target = model.Qualifier("T", String, "not a number")
    _owner(target)

    _paste(target, model.Qualifier("T", Int, 7))

    assert (target.value_type, target.value) == (Int, 7)


def test_a_type_that_another_qualifier_has_is_refused_before_a_change() -> None:
    target = model.Qualifier("A", String, "a")
    other = model.Qualifier("B", String, "b")
    _owner(target, other)

    with pytest.raises(PasteQualifierError, match="AASd-021"):
        plan_paste_into_qualifier(target, model.Qualifier("B", String, "x"))

    assert (target.type, target.value) == ("A", "a")


def test_content_that_is_there_already_has_no_commands() -> None:
    target = model.Qualifier("A", String, "a")
    _owner(target)
    plan = plan_paste_into_qualifier(target, model.Qualifier("A", String, "a"))

    assert not plan.can_apply
    with pytest.raises(PasteQualifierError, match="already"):
        paste_qualifier_commands(ModelChangeObserver(), plan)


def test_pasting_the_own_type_is_no_conflict() -> None:
    target = model.Qualifier("A", String, "a")
    _owner(target, model.Qualifier("B", String, "b"))

    _paste(target, model.Qualifier("A", String, "changed"))

    assert target.value == "changed"
