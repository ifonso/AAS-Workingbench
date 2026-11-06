"""Adding a qualifier, extension, specific asset id or data specification to many."""

import json
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.attach import AttachPlan
from aas_editor.application.operations.attach import AttachStatus
from aas_editor.application.operations.attach import attach_commands
from aas_editor.application.operations.attach import can_hold
from aas_editor.application.operations.attach import plan_attach
from aas_editor.domain.clipboard_json import load_members
from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.member_json import clone_member

QUALIFIER = {"type": "Mark", "valueType": "xs:string", "value": "x"}


def _members(data: list[dict[str, Any]], kind: MemberKind) -> list[Any]:
    return load_members(json.dumps(data), kind)


def _factory(members: list[Any], kind: MemberKind):
    return lambda: [clone_member(m, kind) for m in members]


def _push(stack: CommandStack, owner: object, plan: AttachPlan) -> None:
    with stack.group(plan.description):
        for command in attach_commands(observer_for(owner), plan):
            stack.push(command)


def _plan(owners: list[Any], data: list[dict[str, Any]], kind: MemberKind):
    return plan_attach(owners, kind, _factory(_members(data, kind), kind))


def _types(owner: Any) -> list[str]:
    return [q.type for q in owner.qualifier]


def test_every_owner_gets_its_own_copy_in_one_undo_step() -> None:
    props = [make_property(n) for n in "ABC"]
    submodel = make_submodel(elements=props)
    plan = _plan(props, [QUALIFIER], MemberKind.QUALIFIER)
    stack = CommandStack()

    _push(stack, submodel, plan)
    after = [_types(p) for p in props]
    stack.undo()
    undone = [_types(p) for p in props]
    stack.redo()

    assert plan.can_apply
    assert after == [["Mark"]] * 3
    assert undone == [[]] * 3
    assert [_types(p) for p in props] == after
    qualifiers = [next(iter(p.qualifier)) for p in props]
    assert len({id(q) for q in qualifiers}) == 3
    assert all(q.parent is p for q, p in zip(qualifiers, props, strict=True))


def test_new_members_go_to_the_end() -> None:
    prop = make_property("A")
    prop.qualifier.add(
        model.Qualifier("First", value_type=model.datatypes.String)
    )
    submodel = make_submodel(elements=[prop])

    _push(
        CommandStack(),
        submodel,
        _plan([prop], [QUALIFIER], MemberKind.QUALIFIER),
    )

    assert _types(prop) == ["First", "Mark"]


def test_an_owner_with_the_type_is_skipped_and_the_others_get_it() -> None:
    has, lacks = make_property("A"), make_property("B")
    has.qualifier.add(
        model.Qualifier("Mark", value_type=model.datatypes.String, value="old")
    )
    submodel = make_submodel(elements=[has, lacks])

    plan = _plan([has, lacks], [QUALIFIER], MemberKind.QUALIFIER)
    _push(CommandStack(), submodel, plan)

    assert [e.status for e in plan.entries] == [
        AttachStatus.SKIPPED,
        AttachStatus.ADD,
    ]
    assert "AASd-021" in plan.entries[0].reason
    assert next(iter(has.qualifier)).value == "old"
    assert _types(lacks) == ["Mark"]


def test_two_members_of_one_batch_with_the_same_type_add_only_the_first() -> (
    None
):
    prop = make_property("A")
    second = {**QUALIFIER, "value": "second"}

    plan = _plan([prop], [QUALIFIER, second], MemberKind.QUALIFIER)

    assert [e.status for e in plan.entries] == [
        AttachStatus.ADD,
        AttachStatus.SKIPPED,
    ]
    assert "earlier" in plan.entries[1].reason


def test_nothing_to_add_cannot_be_applied() -> None:
    prop = make_property("A")
    prop.qualifier.add(
        model.Qualifier("Mark", value_type=model.datatypes.String)
    )

    plan = _plan([prop], [QUALIFIER], MemberKind.QUALIFIER)

    assert not plan.can_apply
    assert plan.skipped_count == 1
    with pytest.raises(ValueError, match="nothing to add"):
        attach_commands(observer_for(prop), plan)


def test_an_owner_that_cannot_have_the_kind_is_skipped() -> None:
    concept = make_concept_description()

    plan = _plan([concept], [QUALIFIER], MemberKind.QUALIFIER)

    assert plan.entries[0].status is AttachStatus.SKIPPED
    assert (
        "ConceptDescription cannot have a qualifier" in plan.entries[0].reason
    )
    assert not can_hold(concept, MemberKind.QUALIFIER)
    assert can_hold(make_property("P"), MemberKind.QUALIFIER)


def test_extensions_need_a_name_the_owner_does_not_have() -> None:
    first, second = make_property("A"), make_property("B")
    second.extension.add(model.Extension("Note"))
    submodel = make_submodel(elements=[first, second])

    plan = _plan([first, second], [{"name": "Note"}], MemberKind.EXTENSION)
    _push(CommandStack(), submodel, plan)

    assert plan.entries[1].status is AttachStatus.SKIPPED
    assert "AASd-077" in plan.entries[1].reason
    assert [e.name for e in first.extension] == ["Note"]
    assert [e.name for e in second.extension] == ["Note"]


def test_every_referable_can_have_an_extension() -> None:
    shell_owner = make_concept_description()

    plan = _plan([shell_owner], [{"name": "Note"}], MemberKind.EXTENSION)
    _push(CommandStack(), shell_owner, plan)

    assert [e.name for e in shell_owner.extension] == ["Note"]


def test_specific_asset_ids_go_to_asset_information_and_self_managed_entities() -> (
    None
):
    information = make_asset_information()
    self_managed = model.Entity(
        "Self", model.EntityType.SELF_MANAGED_ENTITY, global_asset_id="urn:a"
    )
    co_managed = model.Entity("Co", model.EntityType.CO_MANAGED_ENTITY)
    prop = make_property("P")
    submodel = make_submodel(elements=[self_managed, co_managed, prop])
    data = [{"name": "BPN", "value": "BPNL1"}]

    plan = _plan(
        [information, self_managed, co_managed, prop],
        data,
        MemberKind.SPECIFIC_ASSET_ID,
    )
    _push(CommandStack(), submodel, plan)

    assert [e.status for e in plan.entries] == [
        AttachStatus.ADD,
        AttachStatus.ADD,
        AttachStatus.SKIPPED,
        AttachStatus.SKIPPED,
    ]
    assert "AASd-014" in plan.entries[2].reason
    assert [s.name for s in information.specific_asset_id] == ["BPN"]
    assert [s.value for s in self_managed.specific_asset_id] == ["BPNL1"]
    assert len(co_managed.specific_asset_id) == 0


def test_the_same_specific_asset_id_is_not_added_twice() -> None:
    information = make_asset_information()
    information.specific_asset_id.append(model.SpecificAssetId("BPN", "1"))

    plan = _plan(
        [information],
        [{"name": "BPN", "value": "1"}],
        MemberKind.SPECIFIC_ASSET_ID,
    )

    assert plan.entries[0].status is AttachStatus.SKIPPED
    assert "this specific asset id already" in plan.entries[0].reason


def test_data_specifications_go_to_every_owner_without_that_specification() -> (
    None
):
    iec = "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3/0"
    data = {
        "dataSpecification": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": iec}],
        },
        "dataSpecificationContent": {
            "modelType": "DataSpecificationIec61360",
            "preferredName": [{"language": "en", "text": "Name"}],
        },
    }
    fresh = make_concept_description("urn:cd:1")
    has = make_concept_description("urn:cd:2")
    has.embedded_data_specifications.append(
        _members([data], MemberKind.EMBEDDED_DATA_SPECIFICATION)[0]
    )
    submodel = make_submodel()

    plan = _plan([fresh, has], [data], MemberKind.EMBEDDED_DATA_SPECIFICATION)
    _push(CommandStack(), submodel, plan)

    assert [e.status for e in plan.entries] == [
        AttachStatus.ADD,
        AttachStatus.SKIPPED,
    ]
    assert len(fresh.embedded_data_specifications) == 1
    assert len(has.embedded_data_specifications) == 1
    assert fresh.embedded_data_specifications[0].data_specification == (
        make_external_reference(iec)
    )


def test_a_failure_while_adding_undoes_what_was_added() -> None:
    first, second = make_property("A"), make_property("B")
    submodel = make_submodel(elements=[first, second])
    plan = _plan([first, second], [QUALIFIER], MemberKind.QUALIFIER)
    # The package changes between the plan and the apply.
    second.qualifier.add(
        model.Qualifier("Mark", value_type=model.datatypes.String)
    )
    stack = CommandStack()

    with pytest.raises(model.AASConstraintViolation):
        _push(stack, submodel, plan)

    assert _types(first) == []
    assert _types(second) == ["Mark"]
    assert not stack.can_undo


def test_the_description_counts_what_is_added() -> None:
    props = [make_property(n) for n in "AB"]

    plan = _plan(props, [QUALIFIER], MemberKind.QUALIFIER)

    assert plan.description == "Add qualifier to 2 items"
    single = _plan(props[:1], [QUALIFIER], MemberKind.QUALIFIER)
    assert single.description == "Add qualifier to A"


def test_collections_take_qualifiers_like_any_element() -> None:
    assert can_hold(make_collection("C"), MemberKind.QUALIFIER)
    assert can_hold(make_collection("C"), MemberKind.EXTENSION)
    assert can_hold(
        make_collection("C"), MemberKind.EMBEDDED_DATA_SPECIFICATION
    )
    assert not can_hold(make_collection("C"), MemberKind.SPECIFIC_ASSET_ID)
