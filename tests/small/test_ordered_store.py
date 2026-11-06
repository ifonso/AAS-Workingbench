"""The store of a package keeps the order in which objects were added."""

from basyx.aas import model
import pytest

from aas_editor.domain.ordered_store import OrderedIdentifiableStore


def _concept(id_: str) -> model.ConceptDescription:
    return model.ConceptDescription(
        id_, id_short="C_" + id_.removeprefix("urn:")
    )


def test_objects_come_back_in_the_order_they_were_added() -> None:
    store = OrderedIdentifiableStore()
    for name in ("urn:z", "urn:a", "urn:m", "urn:b", "urn:c"):
        store.add(_concept(name))

    assert store.order == ("urn:z", "urn:a", "urn:m", "urn:b", "urn:c")


def test_a_removed_object_is_gone_and_a_new_one_comes_last() -> None:
    store = OrderedIdentifiableStore()
    first, second, third = (_concept(n) for n in ("urn:1", "urn:2", "urn:3"))
    for obj in (first, second, third):
        store.add(obj)

    store.remove(second)
    store.add(second)

    assert store.order == ("urn:1", "urn:3", "urn:2")
    assert len(store) == 3


def test_adding_an_object_again_keeps_its_place() -> None:
    store = OrderedIdentifiableStore()
    first, second = _concept("urn:1"), _concept("urn:2")
    store.add(first)
    store.add(second)

    store.add(first)

    assert store.order == ("urn:1", "urn:2")


def test_an_id_that_is_taken_is_refused_as_in_the_sdk() -> None:
    store = OrderedIdentifiableStore()
    store.add(_concept("urn:1"))

    with pytest.raises(KeyError):
        store.add(_concept("urn:1"))


def test_an_object_is_found_after_its_id_changed() -> None:
    store = OrderedIdentifiableStore()
    concept = _concept("urn:old")
    store.add(concept)

    concept.id = "urn:new"

    assert store.get_item("urn:new") is concept
    assert concept in store


def test_discard_ignores_an_object_that_is_not_there() -> None:
    store = OrderedIdentifiableStore([_concept("urn:1")])

    store.discard(_concept("urn:2"))

    assert store.order == ("urn:1",)
