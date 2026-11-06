"""Reporting model changes to every subscriber, without Qt."""

import gc
import logging

import pytest
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import Change
from aas_editor.application.changes import ChangeKind
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.changes import observer_for
from aas_editor.application.listeners import Subscription


class _Recorder:
    def __init__(self) -> None:
        self.received: list[Change] = []

    def on_change(self, change: Change) -> None:
        self.received.append(change)


def test_notify_passes_the_change_to_every_subscriber() -> None:
    observer = ModelChangeObserver()
    first, second = _Recorder(), _Recorder()
    observer.subscribe(first.on_change)
    observer.subscribe(second.on_change)
    prop = make_property("a")
    change = Change.changed(prop)

    observer.notify(change)

    assert first.received == [change]
    assert second.received == [change]


def test_notify_calls_subscribers_in_the_order_they_subscribed() -> None:
    observer = ModelChangeObserver()
    calls: list[str] = []
    observer.subscribe(lambda change: calls.append("first"))
    observer.subscribe(lambda change: calls.append("second"))

    observer.notify(Change.changed(make_property("a")))

    assert calls == ["first", "second"]


def test_cancel_stops_calls_to_that_subscriber_only() -> None:
    observer = ModelChangeObserver()
    kept, cancelled = _Recorder(), _Recorder()
    observer.subscribe(kept.on_change)
    subscription = observer.subscribe(cancelled.on_change)

    subscription.cancel()
    observer.notify(Change.changed(make_property("a")))

    assert len(kept.received) == 1
    assert cancelled.received == []


def test_cancel_does_nothing_when_called_twice() -> None:
    observer = ModelChangeObserver()
    recorder = _Recorder()
    subscription = observer.subscribe(recorder.on_change)

    subscription.cancel()
    subscription.cancel()
    observer.notify(Change.changed(make_property("a")))

    assert recorder.received == []


def test_subscriber_may_cancel_itself_while_it_is_called() -> None:
    observer = ModelChangeObserver()
    received: list[Change] = []
    holder: list[Subscription] = []

    def once(change: Change) -> None:
        received.append(change)
        holder[0].cancel()

    holder.append(observer.subscribe(once))
    other = _Recorder()
    observer.subscribe(other.on_change)

    observer.notify(Change.changed(make_property("a")))
    observer.notify(Change.changed(make_property("b")))

    assert len(received) == 1
    assert len(other.received) == 2


def test_notify_reaches_other_subscribers_when_one_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = ModelChangeObserver()
    after = _Recorder()

    def failing(change: Change) -> None:
        raise ValueError("broken view")

    observer.subscribe(failing)
    observer.subscribe(after.on_change)

    with caplog.at_level(logging.ERROR):
        observer.notify(Change.changed(make_property("a")))

    assert len(after.received) == 1
    assert "broken view" in caplog.text


def test_bound_method_is_dropped_when_its_object_is_gone() -> None:
    observer = ModelChangeObserver()
    recorder = _Recorder()
    observer.subscribe(recorder.on_change)
    received = recorder.received

    del recorder
    gc.collect()
    observer.notify(Change.changed(make_property("a")))

    assert received == []


def test_function_stays_subscribed_without_other_references() -> None:
    observer = ModelChangeObserver()
    received: list[Change] = []
    observer.subscribe(received.append)
    gc.collect()

    observer.notify(Change.changed(make_property("a")))

    assert len(received) == 1


def test_added_describes_parent_target_and_position() -> None:
    submodel = make_submodel()
    prop = make_property("a")

    change = Change.added(submodel.submodel_element, prop, 2)

    assert change.kind is ChangeKind.ADDED
    assert change.parent is submodel.submodel_element
    assert change.target is prop
    assert change.index == 2
    assert change.old_index is None


def test_removed_describes_parent_target_and_former_position() -> None:
    submodel = make_submodel()
    prop = make_property("a")

    change = Change.removed(submodel, prop, 1)

    assert change.kind is ChangeKind.REMOVED
    assert change.parent is submodel
    assert change.target is prop
    assert change.index == 1


def test_moved_describes_both_positions() -> None:
    submodel = make_submodel()
    prop = make_property("a")

    change = Change.moved(submodel, prop, old_index=0, index=3)

    assert change.kind is ChangeKind.MOVED
    assert change.old_index == 0
    assert change.index == 3


def test_changed_has_no_parent_and_keeps_its_origin() -> None:
    prop = make_property("a")
    origin = object()

    change = Change.changed(prop, origin=origin)

    assert change.kind is ChangeKind.CHANGED
    assert change.target is prop
    assert change.parent is None
    assert change.origin is origin


def test_observer_for_gives_the_same_observer_to_the_same_owner() -> None:
    owner = _Recorder()

    assert observer_for(owner) is observer_for(owner)


def test_observer_for_gives_different_observers_to_different_owners() -> None:
    assert observer_for(_Recorder()) is not observer_for(_Recorder())
