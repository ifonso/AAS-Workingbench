"""Deleting objects and handling the references to them (decision D11)."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import Linked
from tests.reference_factories import make_linked
from tests.serialization import snapshot

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.delete import DeletePlan
from aas_editor.application.operations.delete import delete_commands
from aas_editor.application.operations.delete import plan_delete
from aas_editor.domain.references import ReferenceIndex


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


def _delete(
    stack: CommandStack,
    observer: ModelChangeObserver,
    linked: Linked,
    plan: DeletePlan,
    remove_references: bool,
) -> None:
    with stack.group("Delete"):
        for command in delete_commands(
            observer, plan, linked.store, remove_references
        ):
            stack.push(command)


def _owners(usages: tuple) -> list[object]:  # type: ignore[type-arg]
    return [usage.slot.owner for usage in usages]


class TestPlan:
    def test_plan_lists_the_semantic_ids_that_refer_to_a_concept(self) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [linked.concept])

        assert _owners(plan.usages) == [
            linked.name,
            linked.inner,
            linked.concept_link,
        ]
        assert plan.kept == ()
        assert len(plan.removals) == 3

    def test_plan_has_no_usages_when_nothing_refers_to_the_target(self) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [linked.pointer])

        assert not plan.has_usages
        assert plan.removals == ()

    def test_plan_keeps_a_reference_that_is_required(self) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [linked.inner])

        assert _owners(plan.kept) == [linked.relationship]
        assert [c.slot.owner for c in plan.removals] == [linked.link]

    def test_plan_leaves_out_references_stored_inside_the_target(self) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [linked.main])

        owners = _owners(plan.usages)
        assert linked.shell in owners
        assert linked.pointer in owners
        assert linked.relationship not in owners

    def test_plan_drops_a_target_that_is_below_another_target(self) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [linked.inner, linked.group])

        assert plan.targets == (linked.group,)

    def test_plan_keeps_a_semantic_id_while_a_supplemental_one_stays(
        self,
    ) -> None:
        linked = make_linked()
        linked.name.supplemental_semantic_id.append(
            make_external_reference("urn:other")
        )

        plan = plan_delete(linked.store, [linked.concept])

        assert linked.name in _owners(plan.kept)
        assert linked.name not in [c.slot.owner for c in plan.removals]

    def test_plan_removes_a_semantic_id_with_its_supplemental_ones(
        self,
    ) -> None:
        linked = make_linked()
        linked.name.supplemental_semantic_id.append(
            make_external_reference(CONCEPT_ID)
        )
        stack = CommandStack()
        plan = plan_delete(linked.store, [linked.concept])

        _delete(stack, ModelChangeObserver(), linked, plan, True)

        assert linked.name.semantic_id is None
        assert len(linked.name.supplemental_semantic_id) == 0

    @pytest.mark.parametrize(
        ("target", "destructive"),
        [
            ("pointer", False),
            ("name", True),
            ("group", True),
            ("main", True),
            ("concept", True),
        ],
    )
    def test_plan_is_destructive_for_what_has_content_or_usages(
        self, target: str, destructive: bool
    ) -> None:
        linked = make_linked()

        plan = plan_delete(linked.store, [getattr(linked, target)])

        assert plan.is_destructive is destructive

    def test_plan_is_not_destructive_for_a_property_nobody_refers_to(
        self,
    ) -> None:
        linked = make_linked()
        loose = make_property("Loose")
        linked.other.submodel_element.add(loose)

        assert not plan_delete(linked.store, [loose]).is_destructive

    def test_plan_cuts_a_nested_referred_semantic_id(self) -> None:
        linked = make_linked()
        element = make_property("Nested")
        element.semantic_id = model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:elsewhere"),),
            make_external_reference(CONCEPT_ID),
        )
        linked.other.submodel_element.add(element)
        stack = CommandStack()
        plan = plan_delete(linked.store, [linked.concept])

        _delete(stack, ModelChangeObserver(), linked, plan, True)

        assert element.semantic_id is not None
        assert element.semantic_id.key[0].value == "urn:elsewhere"
        assert element.semantic_id.referred_semantic_id is None


class TestDeleteCommands:
    def test_delete_removes_the_target_and_the_references(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.concept]),
            True,
        )

        assert linked.concept not in linked.store
        assert linked.name.semantic_id is None
        assert linked.inner.semantic_id is None
        assert linked.concept_link.value is None
        assert ReferenceIndex(linked.store).dangling() == []

    def test_delete_can_leave_the_references(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.concept]),
            False,
        )

        assert linked.concept not in linked.store
        assert linked.name.semantic_id is not None
        assert linked.concept_link.value is not None
        dangling = ReferenceIndex(linked.store).dangling()
        assert [item.slot.owner for item in dangling] == [linked.concept_link]

    def test_one_undo_brings_back_the_target_and_the_references(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.concept]),
            True,
        )
        deleted = snapshot(linked.store)
        stack.undo()
        undone = snapshot(linked.store)
        stack.redo()

        assert deleted != original
        assert undone == original
        assert snapshot(linked.store) == deleted
        assert not stack.can_redo

    def test_deleting_a_submodel_removes_the_reference_of_the_shell(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.main]),
            True,
        )

        assert len(linked.shell.submodel) == 1
        assert linked.pointer.value is None
        stack.undo()
        assert snapshot(linked.store) == original

    def test_deleting_several_objects_is_one_step(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.concept, linked.other]),
            True,
        )
        stack.undo()

        assert snapshot(linked.store) == original
        assert not stack.can_undo

    def test_deleting_an_element_puts_it_back_where_it_was(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.group]),
            True,
        )
        names = [e.id_short for e in linked.main.submodel_element]
        stack.undo()

        assert "Group" not in names
        assert [e.id_short for e in linked.main.submodel_element][1] == "Group"
        assert snapshot(linked.store) == original

    def test_the_required_reference_stays_and_dangles(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.inner]),
            True,
        )

        assert linked.link.value is None
        assert linked.relationship.second is not None
        dangling = ReferenceIndex(linked.store).dangling()
        assert [item.slot.owner for item in dangling] == [linked.relationship]


class TestListItems:
    def test_deleting_a_list_item_moves_the_references_to_the_next_items_up(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        first = next(iter(linked.items.value))
        original = snapshot(linked.store)
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [first]),
            True,
        )

        assert linked.list_link.value is not None
        assert [key.value for key in linked.list_link.value.key] == [
            MAIN_ID,
            "Items",
            "0",
        ]
        index = ReferenceIndex(linked.store)
        assert index.resolve(linked.list_link.value) is linked.second_item
        stack.undo()
        assert snapshot(linked.store) == original

    def test_references_move_up_even_when_the_references_stay(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.items.value.add(
            model.Property(
                id_short=None, value_type=model.datatypes.String, value="3"
            )
        )
        third = list(linked.items.value)[2]
        late = model.ReferenceElement(id_short="Late")
        linked.main.submodel_element.add(late)
        late.value = model.ModelReference.from_referable(third)
        first = next(iter(linked.items.value))

        stack = CommandStack()
        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [first]),
            False,
        )

        assert late.value is not None
        assert late.value.key[-1].value == "1"
        assert ReferenceIndex(linked.store).resolve(late.value) is third

    def test_deleting_the_referenced_item_takes_the_reference_away(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()

        _delete(
            stack,
            observer,
            linked,
            plan_delete(linked.store, [linked.second_item]),
            True,
        )

        assert linked.list_link.value is None
