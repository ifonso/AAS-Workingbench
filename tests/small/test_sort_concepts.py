"""Sorting the concept descriptions for good (F-EDT-05 AC11, AC12)."""

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.operations.sort_concepts import NOTHING_TO_SORT
from aas_editor.application.operations.sort_concepts import SortRefused
from aas_editor.application.operations.sort_concepts import plan_sort
from aas_editor.application.operations.sort_concepts import sort_command
from aas_editor.domain.concept_order import CANNOT_SORT
from aas_editor.domain.concept_order import ConceptOrder
from aas_editor.domain.ordered_store import OrderedIdentifiableStore


def _store() -> OrderedIdentifiableStore:
    store = make_store(
        make_concept_description("urn:cd:c", "Charlie"),
        make_shell(),
        make_concept_description("urn:cd:a", "alpha"),
        make_submodel(),
        make_concept_description("urn:cd:b", "Bravo"),
    )
    assert isinstance(store, OrderedIdentifiableStore)
    return store


def _ids(store: OrderedIdentifiableStore) -> list[str]:
    return [o.id for o in store]


def test_sorting_by_id_short_puts_the_descriptions_in_order_in_the_store() -> (
    None
):
    store = _store()
    stack = CommandStack()

    plan = plan_sort(store, ConceptOrder.ID_SHORT)
    stack.push(sort_command(ModelChangeObserver(), store, plan))

    concepts = [o.id for o in store if isinstance(o, model.ConceptDescription)]
    assert concepts == ["urn:cd:a", "urn:cd:b", "urn:cd:c"]


def test_the_shell_and_the_submodel_keep_their_places() -> None:
    store = _store()
    before = [type(o).__name__ for o in store]

    plan = plan_sort(store, ConceptOrder.ID)
    CommandStack().push(sort_command(ModelChangeObserver(), store, plan))

    assert [type(o).__name__ for o in store] == before


def test_one_undo_gives_the_old_order_back_and_a_redo_sorts_again() -> None:
    store = _store()
    stack = CommandStack()
    original = _ids(store)

    stack.push(
        sort_command(
            ModelChangeObserver(), store, plan_sort(store, ConceptOrder.ID)
        )
    )
    sorted_ids = _ids(store)
    stack.undo()
    undone = _ids(store)
    stack.redo()

    assert undone == original
    assert _ids(store) == sorted_ids
    assert sorted_ids != original


def test_sorting_by_first_use_follows_the_submodels() -> None:
    first = make_property("First")
    first.semantic_id = make_external_reference("urn:cd:b")
    store = make_store(
        make_submodel(elements=[first]),
        make_concept_description("urn:cd:a", "alpha"),
        make_concept_description("urn:cd:b", "Bravo"),
    )

    plan = plan_sort(store, ConceptOrder.FIRST_USE)

    ids = [
        o.id for o in plan.new_order if isinstance(o, model.ConceptDescription)
    ]
    assert ids == ["urn:cd:b", "urn:cd:a"]


@pytest.mark.parametrize(
    "order",
    [
        ConceptOrder.LIST_INDEX,
        ConceptOrder.BY_ELEMENTS,
        ConceptOrder.STRUCTURED,
    ],
)
def test_the_three_orders_that_cannot_sort_say_so_and_change_nothing(
    order: ConceptOrder,
) -> None:
    store = _store()
    before = _ids(store)

    with pytest.raises(SortRefused) as refused:
        plan_sort(store, order)

    assert (
        str(refused.value) == CANNOT_SORT == "Cannot apply selected sort order!"
    )
    assert _ids(store) == before


def test_a_package_without_descriptions_has_nothing_to_sort() -> None:
    with pytest.raises(SortRefused, match="No concept descriptions found"):
        plan_sort(make_store(make_shell()), ConceptOrder.ID)

    assert NOTHING_TO_SORT.startswith("No concept descriptions found")


def test_a_sorted_store_is_a_plan_that_changes_nothing() -> None:
    store = make_store(
        make_concept_description("urn:cd:a", "A"),
        make_concept_description("urn:cd:b", "B"),
    )

    assert not plan_sort(store, ConceptOrder.ID).changes
    assert plan_sort(_store(), ConceptOrder.ID).changes


def test_a_deleted_description_comes_back_at_its_place_on_undo() -> None:
    store = _store()
    middle = next(o for o in store if o.id == "urn:cd:a")
    stack = CommandStack()
    observer = ModelChangeObserver()

    stack.push(RemoveMember(observer, store, middle))
    assert "urn:cd:a" not in _ids(store)
    stack.undo()

    assert _ids(store)[2] == "urn:cd:a"


def test_a_description_added_by_redo_lands_where_it_was_first() -> None:
    store = _store()
    late = make_concept_description("urn:cd:late", "Late")
    stack = CommandStack()

    stack.push(AddMember(ModelChangeObserver(), store, late))
    stack.undo()
    stack.redo()

    assert _ids(store)[-1] == "urn:cd:late"
