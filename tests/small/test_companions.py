"""Tests for what travels with a copy between packages."""

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.companions import ConceptChoice
from aas_editor.application.operations.companions import concept_commands
from aas_editor.application.operations.companions import gather_companions
from aas_editor.application.operations.companions import plan_concepts
from aas_editor.application.operations.companions import (
    retarget_semantic_ids,
)


def _concept(id_: str, short: str, category: str | None = None):
    return model.ConceptDescription(
        id_=id_, id_short=short, category=category
    )


def _with_semantics(id_short: str, concept_id: str) -> model.Property:
    return model.Property(
        id_short=id_short,
        value_type=model.datatypes.String,
        semantic_id=make_external_reference(concept_id),
    )


def test_descriptions_of_an_element_and_its_children_are_found_once() -> None:
    inner = _with_semantics("inner", "urn:cd:1")
    outer = make_collection("C", [inner, _with_semantics("again", "urn:cd:1")])
    outer.semantic_id = make_external_reference("urn:cd:2")
    source = make_store(
        _concept("urn:cd:1", "One"),
        _concept("urn:cd:2", "Two"),
        _concept("urn:cd:3", "Three"),
        make_submodel(elements=[outer]),
    )

    found = gather_companions([outer], source)

    assert sorted(c.id for c in found.concept_descriptions) == [
        "urn:cd:1",
        "urn:cd:2",
    ]


def test_a_semantic_id_without_a_description_is_skipped() -> None:
    element = _with_semantics("p", "urn:cd:missing")
    source = make_store(make_submodel(elements=[element]))

    assert gather_companions([element], source).is_empty


def test_the_plan_adds_reuses_and_asks() -> None:
    new = _concept("urn:cd:new", "New")
    same = _concept("urn:cd:same", "Same")
    other = _concept("urn:cd:other", "Other", category="VALUE")
    source_elements = [
        _with_semantics("a", new.id),
        _with_semantics("b", same.id),
        _with_semantics("c", other.id),
    ]
    source = make_store(
        new,
        same,
        other,
        make_submodel(elements=source_elements),
    )
    target = make_store(
        _concept("urn:cd:same", "Same"),
        _concept("urn:cd:other", "Other", category="PROPERTY"),
    )

    plan = plan_concepts(gather_companions(source_elements, source), target)

    assert [c.id for c in plan.to_add] == ["urn:cd:new"]
    assert [c.id for c in plan.reused] == ["urn:cd:same"]
    assert [c.source.id for c in plan.conflicts] == ["urn:cd:other"]


def test_the_commands_add_copies_and_undo_removes_them() -> None:
    new = _concept("urn:cd:new", "New")
    element = _with_semantics("a", new.id)
    source = make_store(new, make_submodel(elements=[element]))
    target = make_store()
    plan = plan_concepts(gather_companions([element], source), target)
    stack = CommandStack()
    commands, renamed = concept_commands(
        ModelChangeObserver(), target, plan, {}
    )

    with stack.group("copy"):
        for command in commands:
            stack.push(command)
    added = [o.id for o in target]
    copy_is_new_object = next(iter(target)) is not new
    stack.undo()

    assert (added, renamed, copy_is_new_object) == (["urn:cd:new"], {}, True)
    assert len(target) == 0


def test_a_conflict_is_kept_or_added_under_a_new_id() -> None:
    mine = _concept("urn:cd:x", "X", category="VALUE")
    theirs = _concept("urn:cd:x", "X", category="PROPERTY")
    element = _with_semantics("a", mine.id)
    source = make_store(mine, make_submodel(elements=[element]))
    target = make_store(theirs)
    plan = plan_concepts(gather_companions([element], source), target)
    observer = ModelChangeObserver()

    kept, kept_map = concept_commands(observer, target, plan, {})
    added, added_map = concept_commands(
        observer, target, plan, {"urn:cd:x": ConceptChoice.ADD_WITH_NEW_ID}
    )

    assert (kept, kept_map) == ([], {})
    assert len(added) == 1
    assert added_map["urn:cd:x"].startswith("urn:uuid:")


def test_copies_are_pointed_at_the_description_under_its_new_id() -> None:
    element = make_collection(
        "C", [_with_semantics("in", "urn:cd:x")]
    )
    element.semantic_id = make_external_reference("urn:cd:x")
    element.supplemental_semantic_id.append(
        make_external_reference("urn:cd:x")
    )

    changed = retarget_semantic_ids([element], {"urn:cd:x": "urn:cd:y"})

    inner = element.get_referable("in")
    assert changed == 3
    assert element.semantic_id.key[0].value == "urn:cd:y"  # type: ignore[union-attr]
    assert inner.semantic_id.key[0].value == "urn:cd:y"  # type: ignore[attr-defined]
    assert element.supplemental_semantic_id[0].key[0].value == "urn:cd:y"


def test_nothing_changes_without_a_new_id() -> None:
    element = make_property("p")

    assert retarget_semantic_ids([element], {}) == 0
