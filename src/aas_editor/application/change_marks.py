"""Which objects of a package differ from the saved file (F-EDT-01 AC3).

The tree shows an object that was changed since the last save in another
colour, and so it does for each object above it. The marks are not a property of
a row, because there is one row for each tab and tabs read their rows again
when an object changes. They belong to the package, and they follow its command
stack: a save clears them, and so does an undo that returns to the saved state.
Every tab and the package tree read the same marks.

Example:
    Marking by hand, and what clears the marks::

        marks = ChangeMarks(observer_for(package), package.commandStack)
        marks.mark_changed(element)
        marks.is_changed(element)  # True
        stack.mark_saved()
        marks.is_changed(element)  # False
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
import enum

from basyx.aas import model

from aas_editor.application.changes import Change
from aas_editor.application.changes import ChangeKind
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.listeners import Listeners
from aas_editor.application.listeners import Subscription

# Values that Python shares between objects. A mark names an object by its
# identity, so the text "x" of one property would mark every "x".
_SHARED_VALUES = (
    str,
    bytes,
    int,
    float,
    Decimal,
    tuple,
    frozenset,
    enum.Enum,
    type(None),
    type,
)


@dataclass(frozen=True, eq=False)
class MarkUpdate:
    """What a change of the marks touched.

    Attributes:
        objects: The objects that were marked or unmarked. Empty when
            `cleared` is true.
        cleared: True if all marks were taken away.
    """

    objects: tuple[object, ...] = ()
    cleared: bool = False


def is_markable(obj: object) -> bool:
    """Tells whether an object can carry a mark.

    Args:
        obj: Anything that a view shows.

    Returns:
        False for texts, numbers, enum members and the other values that
        Python shares between objects, which a mark by identity cannot tell
        apart.
    """
    return not isinstance(obj, _SHARED_VALUES)


class ChangeMarks:
    """The objects of one package that were changed or added since the save.

    The marks are made by the observer of the package, so every command marks
    its object and the objects above it. A view with more knowledge, such as
    the position of a qualifier in a tab, adds the objects it knows with
    `mark_changed`. The command stack clears them.
    """

    def __init__(
        self, observer: ModelChangeObserver, stack: CommandStack
    ) -> None:
        """Starts following a package.

        Args:
            observer: The change observer of the package.
            stack: The command stack of the package. Whoever creates the marks
                must keep them, because the subscriptions are weak.
        """
        self._stack = stack
        self._changed: dict[int, object] = {}
        self._new: dict[int, object] = {}
        # What was taken out of a container, by the container, because an
        # object that is gone carries no mark of its own.
        self._removed: dict[int, tuple[object, list[object]]] = {}
        self._listeners: Listeners[[MarkUpdate]] = Listeners()
        self._subscriptions = (
            observer.subscribe(self._on_change),
            stack.subscribe(self._on_history),
        )

    def is_changed(self, obj: object) -> bool:
        """Whether the object, or something below it, changed since the save."""
        return id(obj) in self._changed

    def is_new(self, obj: object) -> bool:
        """Whether the object was added since the save."""
        return id(obj) in self._new

    def removed_from(self, container: object) -> tuple[object, ...]:
        """The objects that were taken out of a container since the save.

        Args:
            container: What held them, such as the object store of a package.

        Returns:
            The removed objects, oldest first. A save, and an undo back to the
            saved state, empty the list.
        """
        entry = self._removed.get(id(container))
        return () if entry is None else tuple(entry[1])

    @property
    def is_empty(self) -> bool:
        """Whether nothing is marked."""
        return not self._changed and not self._new

    def mark_changed(self, *objects: object) -> None:
        """Marks objects as changed.

        Args:
            objects: The objects. Texts, numbers and other shared values are
                left out (see `is_markable`).
        """
        fresh = [
            obj
            for obj in objects
            if is_markable(obj) and id(obj) not in self._changed
        ]
        for obj in fresh:
            self._changed[id(obj)] = obj
        if fresh:
            self._listeners.notify(MarkUpdate(tuple(fresh)))

    def mark_new(self, obj: object) -> None:
        """Marks an object as added since the save."""
        if is_markable(obj) and id(obj) not in self._new:
            self._new[id(obj)] = obj
            self._listeners.notify(MarkUpdate((obj,)))

    def clear(self) -> None:
        """Takes all marks away."""
        if self.is_empty:
            return
        self._changed.clear()
        self._new.clear()
        self._removed.clear()
        self._listeners.notify(MarkUpdate(cleared=True))

    def subscribe(self, listener: Callable[[MarkUpdate], None]) -> Subscription:
        """Registers a callback for every change of the marks.

        Args:
            listener: Called with what was touched. A bound method is held
                weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)

    def _on_history(self) -> None:
        # A save, and an undo or redo that ends at the saved state.
        if self._stack.is_clean:
            self.clear()

    def _on_change(self, change: Change) -> None:
        if change.kind is ChangeKind.ADDED:
            self.mark_new(change.target)
        if change.kind is ChangeKind.REMOVED and change.parent is not None:
            container = change.parent
            self._removed.setdefault(id(container), (container, []))[1].append(
                change.target
            )
        owner = change.target if change.kind is ChangeKind.CHANGED else None
        if owner is None:
            owner = change.parent
        self.mark_changed(*with_ancestors(owner))


def with_ancestors(obj: object) -> list[object]:
    """Lists an object and the objects above it, as far as it knows them.

    Args:
        obj: A referable, a part of one such as a qualifier, or a container.

    Returns:
        The object first, then its parent, and so on. A part that knows its
        owner is followed to it.
    """
    found: list[object] = []
    seen: set[int] = set()
    current: object | None = obj
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        found.append(current)
        parent = (
            current.parent if isinstance(current, model.Referable) else None
        )
        if parent is None:
            parent = _container_owner(current)
        current = parent
    return found


def _container_owner(obj: object) -> object | None:
    # A namespace set, a list of qualifiers, and the like know their owner.
    owner = getattr(obj, "parent", None)
    return None if isinstance(owner, _SHARED_VALUES) else owner
