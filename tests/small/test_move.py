"""Tests for moving members of ordered containers (D16)."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_list
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.operations.move import MoveKind
from aas_workingbench.application.operations.move import can_move
from aas_workingbench.application.operations.move import move_commands
from aas_workingbench.application.operations.move import new_order
from aas_workingbench.application.operations.move import plan_move
from aas_workingbench.domain.references import ReferenceIndex


def _names(container: object) -> list[str]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


def _submodel_of(*names: str) -> model.Submodel:
    return make_submodel(elements=[make_property(n) for n in names])


def _push(stack: CommandStack, observer: object, plan: object) -> None:
    with stack.group("move"):
        for command in move_commands(observer, plan):  # type: ignore[arg-type]
            stack.push(command)


class TestNewOrder:
    @pytest.mark.parametrize(
        ("kind", "selected", "expected"),
        [
            (MoveKind.UP, "C", "A C B D"),
            (MoveKind.UP, "A", "A B C D"),
            (MoveKind.DOWN, "B", "A C B D"),
            (MoveKind.DOWN, "D", "A B C D"),
            (MoveKind.TO_TOP, "C", "C A B D"),
            (MoveKind.TO_END, "B", "A C D B"),
            (MoveKind.UP, "BC", "B C A D"),
            (MoveKind.UP, "AC", "A B C D"),
            (MoveKind.DOWN, "BC", "A D B C"),
            (MoveKind.DOWN, "BD", "A B C D"),
            (MoveKind.TO_TOP, "BD", "B D A C"),
            (MoveKind.TO_END, "AC", "B D A C"),
        ],
    )
    def test_the_selection_moves_as_a_block_or_not_at_all(
        self, kind: MoveKind, selected: str, expected: str
    ) -> None:
        items = [make_property(n) for n in "ABCD"]
        chosen = [i for i in items if i.id_short in selected]

        result = new_order(items, chosen, kind)

        assert " ".join(i.id_short for i in result) == expected

    @pytest.mark.parametrize(
        ("kind", "selected", "expected"),
        [
            # F-EDT-09 AC3: indices 2 and 4 of 6 end at 1 and 2.
            (MoveKind.UP, "CE", "A C E B D F"),
            # F-EDT-09 AC4: the first selected row is at the top, no change.
            (MoveKind.UP, "AD", "A B C D E F"),
            (MoveKind.UP, "ABE", "A B C D E F"),
            # Down is the mirror: the block ends one place below the last row.
            (MoveKind.DOWN, "BD", "A C E B D F"),
            (MoveKind.DOWN, "CF", "A B C D E F"),
            (MoveKind.DOWN, "AB", "C A B D E F"),
            # Selected rows keep their order in the container.
            (MoveKind.TO_TOP, "FC", "C F A B D E"),
            (MoveKind.TO_END, "DB", "A C E F B D"),
        ],
    )
    def test_selected_rows_become_adjacent_as_in_package_explorer(
        self, kind: MoveKind, selected: str, expected: str
    ) -> None:
        items = [make_property(n) for n in "ABCDEF"]
        chosen = [i for i in items if i.id_short in selected]

        result = new_order(items, chosen, kind)

        assert " ".join(i.id_short for i in result) == expected

    def test_a_move_that_changes_nothing_is_not_possible(self) -> None:
        items = [make_property(n) for n in "ABCDEF"]
        top = [items[0], items[3]]

        assert not can_move(items, top, MoveKind.UP)
        assert can_move(items, top, MoveKind.DOWN)


class TestCanMove:
    def test_up_is_not_possible_on_the_first_member(self) -> None:
        submodel = _submodel_of("A", "B")
        first = next(iter(submodel.submodel_element))

        assert not can_move(submodel.submodel_element, [first], MoveKind.UP)
        assert not can_move(submodel.submodel_element, [first], MoveKind.TO_TOP)
        assert can_move(submodel.submodel_element, [first], MoveKind.DOWN)

    def test_a_member_of_another_container_cannot_move(self) -> None:
        submodel = _submodel_of("A", "B")
        stranger = make_property("X")

        assert not can_move(
            submodel.submodel_element, [stranger], MoveKind.DOWN
        )

    def test_a_set_has_no_order_to_move(self) -> None:
        shell = make_shell()
        assert not can_move(shell.submodel, [object()], MoveKind.UP)


class TestMoveCommands:
    def test_moving_changes_the_order_and_undo_restores_it(self) -> None:
        submodel = _submodel_of("A", "B", "C")
        elements = submodel.submodel_element
        third = list(elements)[2]
        stack = CommandStack()
        observer = observer_for(submodel)
        plan = plan_move(elements, [third], MoveKind.TO_TOP, [submodel])
        assert plan is not None

        _push(stack, observer, plan)
        moved = _names(elements)
        stack.undo()
        undone = _names(elements)
        stack.redo()

        assert (moved, undone, _names(elements)) == (
            ["C", "A", "B"],
            ["A", "B", "C"],
            ["C", "A", "B"],
        )

    def test_a_move_is_one_undo_step_for_the_whole_selection(self) -> None:
        submodel = _submodel_of("A", "B", "C", "D")
        elements = submodel.submodel_element
        chosen = [m for m in elements if m.id_short in ("B", "D")]
        stack = CommandStack()
        plan = plan_move(elements, chosen, MoveKind.UP, [submodel])
        assert plan is not None

        _push(stack, observer_for(submodel), plan)
        stack.undo()

        assert _names(elements) == ["A", "B", "C", "D"]
        assert not stack.can_undo

    def test_no_plan_when_nothing_changes(self) -> None:
        submodel = _submodel_of("A", "B")
        first = next(iter(submodel.submodel_element))

        assert (
            plan_move(
                submodel.submodel_element, [first], MoveKind.UP, [submodel]
            )
            is None
        )

    def test_each_moved_member_is_reported_at_its_final_row(self) -> None:
        submodel = _submodel_of("A", "B", "C")
        elements = submodel.submodel_element
        observer = observer_for(submodel)
        seen: list[tuple[str, int | None]] = []
        subscription = observer.subscribe(
            lambda change: seen.append((change.target.id_short, change.index))  # type: ignore[attr-defined]
        )
        third = list(elements)[2]
        plan = plan_move(elements, [third], MoveKind.TO_TOP, [submodel])
        assert plan is not None

        _push(CommandStack(), observer, plan)

        assert seen == [("C", 0), ("A", 1), ("B", 2)]
        subscription.cancel()

    def test_the_variables_of_an_operation_move_within_their_direction(
        self,
    ) -> None:
        operation = make_operation(
            input_variables=[make_property("I1"), make_property("I2")],
            output_variables=[make_property("O1")],
        )
        submodel = make_submodel(elements=[operation])
        second = list(operation.input_variable)[1]
        plan = plan_move(
            operation.input_variable, [second], MoveKind.UP, [submodel]
        )
        assert plan is not None

        _push(CommandStack(), observer_for(submodel), plan)

        assert _names(operation.input_variable) == ["I2", "I1"]
        assert _names(operation.output_variable) == ["O1"]


class TestReferencesThroughListItems:
    def _build(
        self,
    ) -> tuple[model.Submodel, model.SubmodelElementList, model.Submodel]:
        items = [
            make_property("a", "1"),
            make_property("b", "2"),
            make_property("c", "3"),
        ]
        sml = make_list("List", items)
        target = make_submodel(elements=[sml])
        holder = make_submodel(
            id_="urn:example:holder",
            id_short="Holder",
            elements=[
                model.ReferenceElement(
                    id_short=f"RefTo{item.value}",
                    value=model.ModelReference.from_referable(item),
                )
                for item in items
            ],
        )
        return target, sml, holder

    def _targets(self, holder: model.Submodel) -> dict[str, str]:
        return {
            ref.id_short: ref.value.key[-1].value  # type: ignore[union-attr]
            for ref in holder.submodel_element
            if isinstance(ref, model.ReferenceElement)
        }

    def test_references_follow_the_items_to_their_new_positions(self) -> None:
        target, sml, holder = self._build()
        objects = [target, holder]
        last = list(sml.value)[2]
        plan = plan_move(sml.value, [last], MoveKind.TO_TOP, objects)
        assert plan is not None

        _push(CommandStack(), observer_for(target), plan)

        # c moved from 2 to 0, so its reference names position 0 now.
        assert self._targets(holder) == {
            "RefTo1": "1",
            "RefTo2": "2",
            "RefTo3": "0",
        }
        resolved = {
            ref.id_short: ReferenceIndex(objects).resolve(ref.value)  # type: ignore[arg-type]
            for ref in holder.submodel_element
            if isinstance(ref, model.ReferenceElement)
        }
        assert [
            resolved[f"RefTo{value}"].value  # type: ignore[union-attr]
            for value in ("1", "2", "3")
        ] == ["1", "2", "3"]

    def test_undo_gives_the_references_their_old_positions(self) -> None:
        target, sml, holder = self._build()
        before = self._targets(holder)
        stack = CommandStack()
        plan = plan_move(
            sml.value,
            [list(sml.value)[0]],
            MoveKind.TO_END,
            [target, holder],
        )
        assert plan is not None
        _push(stack, observer_for(target), plan)

        stack.undo()

        assert self._targets(holder) == before

    def test_moving_elements_of_a_collection_leaves_references_alone(
        self,
    ) -> None:
        inner = [make_property("a"), make_property("b")]
        collection = make_collection(elements=inner)
        target = make_submodel(elements=[collection])
        holder = make_submodel(
            id_="urn:example:holder",
            id_short="Holder",
            elements=[
                model.ReferenceElement(
                    id_short="Ref",
                    value=model.ModelReference.from_referable(inner[0]),
                )
            ],
        )
        plan = plan_move(
            collection.value, [inner[0]], MoveKind.TO_END, [target, holder]
        )

        assert plan is not None
        assert plan.reference_count == 0

    def test_a_store_of_shell_and_submodel_is_accepted_as_objects(self) -> None:
        submodel = _submodel_of("A", "B")
        store = make_store(submodel, make_shell(submodels=[submodel]))
        first = next(iter(submodel.submodel_element))

        plan = plan_move(
            submodel.submodel_element, [first], MoveKind.DOWN, store
        )

        assert plan is not None
