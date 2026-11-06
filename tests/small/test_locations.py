"""Tests for the stack of editing locations (F-EDT-01 AC10 and AC11)."""

import gc

from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.locations import LocationStack


class _Package:
    """Stands in for a package: any object that can be referred to weakly."""


def test_a_pushed_location_comes_back_with_its_expand_state() -> None:
    stack = LocationStack()
    package = _Package()
    submodel = make_submodel()
    stack.push(submodel, package, expanded=True)

    place = stack.pop()

    assert place is not None
    assert (place.target, place.package, place.expanded) == (
        submodel,
        package,
        True,
    )
    assert len(stack) == 0


def test_the_last_pushed_location_comes_first() -> None:
    stack = LocationStack()
    package = _Package()
    first, second = make_property("A"), make_property("B")
    stack.push(first, package, False)
    stack.push(second, package, False)

    places = [stack.pop(), stack.pop()]

    assert [p.target for p in places if p] == [second, first]


def test_pop_on_an_empty_stack_gives_nothing_and_does_not_fail() -> None:
    assert LocationStack().pop() is None


def test_a_location_of_a_deleted_object_is_skipped() -> None:
    stack = LocationStack()
    package = _Package()
    kept = make_property("Kept")
    stack.push(kept, package, False)
    stack.push(make_property("Gone"), package, False)
    gc.collect()

    place = stack.pop()

    assert place is not None and place.target is kept
    assert stack.pop() is None


def test_a_location_of_a_closed_package_is_skipped() -> None:
    stack = LocationStack()
    package = _Package()
    element = make_property("A")
    stack.push(element, package, False)
    del package
    gc.collect()

    assert stack.pop() is None


def test_the_oldest_location_is_dropped_beyond_the_limit() -> None:
    stack = LocationStack(limit=2)
    package = _Package()
    items = [make_property(n) for n in "ABC"]
    for item in items:
        stack.push(item, package, False)

    assert len(stack) == 2
    place = stack.pop()
    assert place is not None and place.target is items[2]
