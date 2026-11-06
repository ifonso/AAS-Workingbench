"""Editing locations: places in the package tree to come back to.

Package Explorer has Push location and Pop location (F-EDT-01 AC10, AC11).
Push stores the selected node and whether it is expanded. Pop takes the last
one back off the stack and selects that node again. The original never clears
the stack, so it can point to objects that are gone. Here a location holds its
object and package by weak reference, so closing a package or deleting an
object does not keep it alive, and Pop skips the locations that are gone.

The stack is plain Python and has no Qt, so it is tested without a window.

Example:
    Remembering a place and coming back to it::

        stack = LocationStack()
        stack.push(submodel, package, expanded=True)
        ...
        place = stack.pop()
        if place is not None:
            show(place.target, place.package, place.expanded)
"""

from dataclasses import dataclass
from typing import Any
from typing import Generic
from typing import TypeVar
import weakref

T = TypeVar("T")

DEFAULT_LIMIT = 100
"""How many locations the stack keeps. The oldest is dropped beyond that."""


@dataclass(frozen=True)
class Place:
    """A location that is still alive.

    Attributes:
        target: The object of the node.
        package: The package that holds it.
        expanded: Whether the node was expanded when it was pushed.
    """

    target: Any
    package: Any
    expanded: bool


class _Slot(Generic[T]):
    """A weak reference that also works for None."""

    def __init__(self, value: T | None) -> None:
        self._ref = None if value is None else weakref.ref(value)
        self._none = value is None

    def get(self) -> T | None:
        """Returns the object, or None if it is gone or was None."""
        return None if self._ref is None else self._ref()

    @property
    def is_gone(self) -> bool:
        """Whether an object was held and has been freed."""
        return not self._none and self.get() is None


@dataclass(frozen=True)
class _Entry:
    target: _Slot[Any]
    package: _Slot[Any]
    expanded: bool


class LocationStack:
    """The stack of pushed locations."""

    def __init__(self, limit: int = DEFAULT_LIMIT) -> None:
        """Creates an empty stack.

        Args:
            limit: How many locations it keeps.
        """
        self._limit = limit
        self._entries: list[_Entry] = []

    def __len__(self) -> int:
        return len(self._entries)

    def push(self, target: object, package: object, expanded: bool) -> None:
        """Stores a location.

        Args:
            target: The object of the selected node.
            package: The package that holds it.
            expanded: Whether the node is expanded.

        Raises:
            TypeError: If the object cannot be referred to weakly.
        """
        self._entries.append(_Entry(_Slot(target), _Slot(package), expanded))
        del self._entries[: -self._limit]

    def pop(self) -> Place | None:
        """Takes the last location that is still alive off the stack.

        Locations whose object or package is gone are dropped on the way.

        Returns:
            The place, or None when the stack is empty or holds nothing alive.
        """
        while self._entries:
            entry = self._entries.pop()
            target = entry.target.get()
            package = entry.package.get()
            if target is None or entry.package.is_gone:
                continue
            return Place(target, package, entry.expanded)
        return None

    def clear(self) -> None:
        """Forgets every location."""
        self._entries.clear()


_default = LocationStack()


def default_stack() -> LocationStack:
    """Returns the stack of the running editor."""
    return _default
