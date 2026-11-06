"""Tells everyone who shows an AAS object when that object changed.

Several views can show the same object: the package tree, and one tab for each
opened object. When one of them edits it, the others must follow. The code that
changes an object reports what happened to a `ModelChangeObserver`, and every
view that subscribed updates itself. Objects are named by identity, never by a
row or an index of one view.

Reporting is the job of whoever mutates the object, which will be the commands
in `commands.py`. Subscribers only read the BaSyx objects again.
"""

from dataclasses import dataclass
import enum
from collections.abc import Callable
import weakref

from aas_editor.application.listeners import Listeners
from aas_editor.application.listeners import Subscription


class ChangeKind(enum.Enum):
    """What happened to an object."""

    ADDED = "added"
    REMOVED = "removed"
    MOVED = "moved"
    CHANGED = "changed"


@dataclass(frozen=True, eq=False)
class Change:
    """One change of the model.

    Create it with `Change.added`, `Change.removed`, `Change.moved`, or
    `Change.changed`.

    Attributes:
        kind: What happened.
        target: The BaSyx object that was added, removed, moved, or changed.
        parent: For added, removed, and moved objects, the container they
            are in: an owner such as a `Submodel`, the `NamespaceSet` or list
            that holds the objects, or the object store of a package. A
            subscriber accepts either form for an owner and its container.
        index: The position in the container after an add or a move, or the
            position before a remove. None when the position is not known.
        old_index: The position before a move.
        origin: The subscriber that reported the change and has updated
            itself already. It should ignore the change.
    """

    kind: ChangeKind
    target: object
    parent: object | None = None
    index: int | None = None
    old_index: int | None = None
    origin: object | None = None

    @classmethod
    def added(
        cls,
        parent: object,
        target: object,
        index: int | None = None,
        origin: object | None = None,
    ) -> "Change":
        """An object was added to a container."""
        return cls(ChangeKind.ADDED, target, parent, index, None, origin)

    @classmethod
    def removed(
        cls,
        parent: object,
        target: object,
        index: int | None = None,
        origin: object | None = None,
    ) -> "Change":
        """An object was removed from a container."""
        return cls(ChangeKind.REMOVED, target, parent, index, None, origin)

    @classmethod
    def moved(
        cls,
        parent: object,
        target: object,
        old_index: int,
        index: int,
        origin: object | None = None,
    ) -> "Change":
        """An object changed its position within its container."""
        return cls(ChangeKind.MOVED, target, parent, index, old_index, origin)

    @classmethod
    def changed(cls, target: object, origin: object | None = None) -> "Change":
        """An attribute of an object, or its value, changed."""
        return cls(ChangeKind.CHANGED, target, origin=origin)


ChangeListener = Callable[[Change], None]


class ModelChangeObserver:
    """Passes changes of one package's objects to everything that shows them.

    A bound method is held weakly, so subscribing a model's method does not
    keep the model alive. See `Listeners`.
    """

    def __init__(self) -> None:
        self._listeners: Listeners[[Change]] = Listeners()

    def subscribe(self, listener: ChangeListener) -> Subscription:
        """Registers a callback for all following changes.

        Args:
            listener: Called with each `Change`. A bound method is held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)

    def notify(self, change: Change) -> None:
        """Passes a change to every subscriber, in subscription order."""
        self._listeners.notify(change)


_observers: weakref.WeakKeyDictionary[object, ModelChangeObserver] = (
    weakref.WeakKeyDictionary()
)


def observer_for(owner: object) -> ModelChangeObserver:
    """Returns the observer that belongs to an owner, usually a package.

    The same owner always gets the same observer, and the observer lives as
    long as the owner does. The owner must be hashable and weak-referenceable.

    Args:
        owner: The object that scopes the changes, such as a `Package`.

    Returns:
        The observer for that owner. It is created on first use.
    """
    observer = _observers.get(owner)
    if observer is None:
        observer = ModelChangeObserver()
        _observers[owner] = observer
    return observer
