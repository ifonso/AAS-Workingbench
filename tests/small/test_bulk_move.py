"""Moving a selection that reaches into several containers."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.operations.bulk_move import bulk_move_commands
from aas_workingbench.application.operations.bulk_move import can_bulk_move
from aas_workingbench.application.operations.bulk_move import plan_bulk_move
from aas_workingbench.application.operations.move import MoveKind
from aas_workingbench.domain.references import ReferenceIndex


def _names(container: object) -> list[str]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


def _two_collections() -> tuple[
    model.Submodel,
    model.SubmodelElementCollection,
    model.SubmodelElementCollection,
]:
    first = make_collection("First", [make_property(n) for n in "ABC"])
    second = make_collection("Second", [make_property(n) for n in "XYZ"])
    return make_submodel(elements=[first, second]), first, second


def _pairs(*members: model.SubmodelElement) -> list[tuple[object, object]]:
    return [(m.parent.value, m) for m in members]  # type: ignore[union-attr]


def _run(stack: CommandStack, submodel: model.Submodel, plan: object) -> None:
    observer = observer_for(submodel)
    with stack.group("Move"):
        for command in bulk_move_commands(observer, plan):  # type: ignore[arg-type]
            stack.push(command)


def test_each_container_moves_its_own_selected_members() -> None:
    submodel, first, second = _two_collections()
    b = first.get_referable("B")
    z = second.get_referable("Z")

    plan = plan_bulk_move(_pairs(b, z), MoveKind.UP, [submodel])
    assert plan is not None
    _run(CommandStack(), submodel, plan)

    assert _names(first.value) == ["B", "A", "C"]
    assert _names(second.value) == ["X", "Z", "Y"]


def test_a_container_whose_order_would_not_change_is_left_out() -> None:
    submodel, first, second = _two_collections()
    a = first.get_referable("A")
    z = second.get_referable("Z")

    plan = plan_bulk_move(_pairs(a, z), MoveKind.UP, [submodel])

    assert plan is not None
    assert len(plan.steps) == 1
    assert plan.steps[0].container is second.value


def test_nothing_to_move_gives_no_plan() -> None:
    submodel, first, second = _two_collections()
    selection = _pairs(first.get_referable("A"), second.get_referable("X"))

    assert plan_bulk_move(selection, MoveKind.UP, [submodel]) is None
    assert not can_bulk_move(selection, MoveKind.UP)


def test_the_move_is_possible_when_one_container_can_move() -> None:
    submodel, first, second = _two_collections()
    selection = _pairs(first.get_referable("A"), second.get_referable("Z"))

    assert can_bulk_move(selection, MoveKind.UP)
    assert can_bulk_move(selection, MoveKind.DOWN)
    assert not can_bulk_move([], MoveKind.UP)


def test_one_undo_takes_back_the_moves_of_every_container() -> None:
    submodel, first, second = _two_collections()
    plan = plan_bulk_move(
        _pairs(first.get_referable("C"), second.get_referable("X")),
        MoveKind.TO_END,
        [submodel],
    )
    assert plan is not None
    stack = CommandStack()

    _run(stack, submodel, plan)
    moved = (_names(first.value), _names(second.value))
    stack.undo()
    undone = (_names(first.value), _names(second.value))
    stack.redo()
    redone = (_names(first.value), _names(second.value))

    assert moved == (list("ABC"), ["Y", "Z", "X"])
    assert undone == (list("ABC"), list("XYZ"))
    assert redone == moved
    assert not stack.can_redo


def test_the_description_names_the_count() -> None:
    submodel, first, second = _two_collections()
    plan = plan_bulk_move(
        _pairs(first.get_referable("B"), second.get_referable("Z")),
        MoveKind.UP,
        [submodel],
    )

    assert plan is not None
    assert plan.description == "Move 2 items up"


def test_a_member_that_is_not_in_its_container_is_refused() -> None:
    submodel, first, _ = _two_collections()
    stranger = make_property("Stranger")

    with pytest.raises(ValueError, match="not in the container"):
        plan_bulk_move([(first.value, stranger)], MoveKind.UP, [submodel])


def test_a_failure_in_a_later_container_undoes_the_earlier_ones() -> None:
    submodel, first, second = _two_collections()
    plan = plan_bulk_move(
        _pairs(first.get_referable("C"), second.get_referable("Z")),
        MoveKind.TO_TOP,
        [submodel],
    )
    assert plan is not None
    # The package changes between the plan and the move.
    second.value.remove(second.get_referable("Y"))
    stack = CommandStack()

    with pytest.raises(ValueError):
        _run(stack, submodel, plan)

    assert _names(first.value) == list("ABC")
    assert _names(second.value) == ["X", "Z"]
    assert not stack.can_undo


def _item(value: str) -> model.Property:
    return model.Property(
        id_short=None, value_type=model.datatypes.String, value=value
    )


def _reference_elements(
    items: list[model.Property],
) -> list[model.ReferenceElement]:
    return [
        model.ReferenceElement(
            id_short=f"RefTo{item.value}",
            value=model.ModelReference.from_referable(item),
        )
        for item in items
    ]


def _resolved(
    objects: list[model.Submodel], holder: model.Submodel
) -> dict[str, str | None]:
    index = ReferenceIndex(objects)
    return {
        ref.id_short: getattr(index.resolve(ref.value), "value", None)  # type: ignore[union-attr,arg-type]
        for ref in holder.submodel_element
        if isinstance(ref, model.ReferenceElement)
    }


def test_references_through_the_items_of_two_lists_follow_their_items() -> None:
    first = make_list("L1", [_item(f"L1{n}") for n in range(3)])
    second = make_list("L2", [_item(f"L2{n}") for n in range(3)])
    target = make_submodel(elements=[first, second])
    holder = make_submodel(
        id_="urn:example:holder",
        id_short="Holder",
        elements=_reference_elements([*first.value, *second.value]),  # type: ignore[list-item]
    )
    objects = [target, holder]
    before = _resolved(objects, holder)
    moving = [list(first.value)[2], list(second.value)[0]]
    plan = plan_bulk_move(_pairs(*moving), MoveKind.TO_END, objects)
    assert plan is not None

    _run(CommandStack(), target, plan)

    assert _resolved(objects, holder) == before
    assert [p.value for p in first.value] == ["L10", "L11", "L12"]  # type: ignore[attr-defined]
    assert [p.value for p in second.value] == ["L21", "L22", "L20"]  # type: ignore[attr-defined]


def test_a_list_in_a_list_is_rewritten_once_per_reference() -> None:
    inner = [
        make_list(None, [_item(f"I{n}{m}") for m in range(3)])  # type: ignore[arg-type]
        for n in range(2)
    ]
    outer = model.SubmodelElementList(
        id_short="Outer",
        type_value_list_element=model.SubmodelElementList,
        value=inner,
    )
    leaves = [item for sml in inner for item in sml.value]
    target = make_submodel(elements=[outer])
    holder = make_submodel(
        id_="urn:example:holder",
        id_short="Holder",
        elements=_reference_elements(leaves),  # type: ignore[arg-type]
    )
    objects = [target, holder]
    before = _resolved(objects, holder)
    # The outer item 0 goes to the end, and an item of the other list moves.
    selection = [
        (outer.value, inner[0]),
        (inner[1].value, list(inner[1].value)[0]),
    ]
    plan = plan_bulk_move(selection, MoveKind.TO_END, objects)
    assert plan is not None
    stack = CommandStack()

    _run(stack, target, plan)
    after = _resolved(objects, holder)
    stack.undo()

    assert after == before
    assert _resolved(objects, holder) == before
