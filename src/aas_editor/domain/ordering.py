"""Order of the elements in BaSyx namespaces (decisions D16 and D19).

A `NamespaceSet` keeps its objects in insertion order, and that order is saved
to files, but the SDK offers no way to choose a position. Adding an object
appends it, and renaming an idShort removes the object and adds it again,
which moves it to the end. This module snapshots and restores the order, so
that edits keep elements where the user put them.

The only way to reorder a `NamespaceSet` is `clear()` followed by `add()` for
each object, so every function here rolls back when the SDK refuses an object.
Reordering a `SubmodelElementList` regenerates the hidden idShorts of its
children. They are never serialized (D17), so this is harmless.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import Generic
from typing import TypeVar

from basyx.aas import model

_T = TypeVar(
    "_T",
    bound=model.Referable
    | model.Qualifier
    | model.HasSemantics
    | model.Extension,
)


class OrderRestoreError(RuntimeError):
    """The previous order could not be put back after a failed change.

    This is not expected, because the objects were valid in that order before.
    The namespace may be incomplete when it is raised.
    """


@dataclass(frozen=True, eq=False)
class OrderSnapshot(Generic[_T]):
    """The members of a namespace set in their order at one point in time.

    Attributes:
        namespace_set: The set that was captured.
        items: Its objects in order. They are compared by identity.
    """

    namespace_set: model.NamespaceSet[_T]
    items: tuple[_T, ...]


def snapshot_order(namespace_set: model.NamespaceSet[_T]) -> OrderSnapshot[_T]:
    """Captures the current order of a namespace set."""
    return OrderSnapshot(namespace_set, tuple(namespace_set))


def restore_order(snapshot: OrderSnapshot[_T]) -> None:
    """Puts the objects of a snapshot back into their captured order.

    Objects that left the set since the snapshot are skipped, and objects that
    joined it keep their relative order after all captured ones. So the call
    is safe after a rename, and after an object was replaced by another.

    Args:
        snapshot: What `snapshot_order` returned.

    Raises:
        OrderRestoreError: If the SDK refuses an object, and the order before
            the call could not be put back either.
    """
    namespace_set = snapshot.namespace_set
    current = tuple(namespace_set)
    present = {id(item) for item in current}
    kept = [item for item in snapshot.items if id(item) in present]
    kept_ids = {id(item) for item in kept}
    joined = [item for item in current if id(item) not in kept_ids]
    _rebuild(namespace_set, [*kept, *joined])


def reorder(namespace_set: model.NamespaceSet[_T], order: Sequence[_T]) -> None:
    """Changes the order of a namespace set, keeping its members.

    Args:
        namespace_set: The set to reorder.
        order: Every member of the set exactly once, in the new order.

    Raises:
        ValueError: If `order` is not a permutation of the members. Nothing
            changes.
        OrderRestoreError: If the SDK refuses an object, and the previous
            order could not be put back either.
        Exception: Whatever the SDK raised for a refused object, after the
            previous order was put back.
    """
    if not _same_members(tuple(namespace_set), order):
        raise ValueError(
            "Order must list every member of the set exactly once: "
            f"{len(order)} given, {len(namespace_set)} members"
        )
    _rebuild(namespace_set, order)


def insert_at(
    namespace_set: model.NamespaceSet[_T], item: _T, index: int
) -> None:
    """Adds an object at a position instead of at the end.

    Args:
        namespace_set: The set to add to.
        item: The object to add.
        index: The position in the new order, with the same meaning as for
            `list.insert`. A value beyond the end appends.

    Raises:
        Exception: Whatever the SDK raises when it refuses the object, such as
            a duplicate idShort. Nothing changes.
    """
    previous = tuple(namespace_set)
    namespace_set.add(item)
    wanted = list(previous)
    wanted.insert(index, item)
    try:
        _rebuild(namespace_set, wanted)
    except Exception:
        namespace_set.discard(item)
        raise


def move_to(
    namespace_set: model.NamespaceSet[_T], item: _T, index: int
) -> None:
    """Moves a member to another position.

    Args:
        namespace_set: The set that holds the object.
        item: The member to move.
        index: The position of the object in the new order, with the same
            meaning as for `list.insert` after the object was taken out.

    Raises:
        KeyError: If the object is not a member of the set.
    """
    members = [member for member in namespace_set if member is not item]
    if len(members) == len(namespace_set):
        raise KeyError(f"Object is not in the set: {item!r}")
    members.insert(index, item)
    _rebuild(namespace_set, members)


def replace_item(
    namespace_set: model.NamespaceSet[_T], old: _T, new: _T
) -> None:
    """Swaps a member for another object at the same position.

    Args:
        namespace_set: The set that holds `old`.
        old: The member to remove.
        new: The object that takes its place.

    Raises:
        KeyError: If `old` is not a member of the set.
        Exception: Whatever the SDK raises when it refuses `new`. Nothing
            changes.
    """
    if old not in namespace_set:
        raise KeyError(f"Object is not in the set: {old!r}")
    before = tuple(namespace_set)
    namespace_set.remove(old)
    try:
        namespace_set.add(new)
        _rebuild(
            namespace_set,
            [new if member is old else member for member in before],
        )
    except Exception:
        _refill(namespace_set, before)
        raise


def namespace_sets_of(element: object) -> list[model.NamespaceSet[Any]]:
    """Returns the namespace sets of its parent that hold an object."""
    parent = getattr(element, "parent", None)
    sets = getattr(parent, "namespace_element_sets", ())
    return [
        namespace_set
        for namespace_set in sets  # pyright: ignore[reportUnknownVariableType]
        if element in namespace_set
    ]


def set_attribute(element: object, name: str, value: object) -> None:
    """Sets an attribute of an object and keeps its position (D19).

    The SDK takes the object out of its namespace sets and adds it again when
    an attribute that the set indexes changes: the idShort, and also the
    semantic id. That moves the object to the end, so the order is restored.

    The SDK does not undo that when the check on adding fails, such as for an
    item of a list whose semantic id differs from its siblings (AASd-114). It
    leaves the object out of the list. This function puts it back with the old
    value.

    Args:
        element: The object, such as an element, qualifier or extension.
        name: The name of the attribute.
        value: The new value.

    Raises:
        Exception: Whatever the SDK raises for an invalid or taken value, such
            as `AASConstraintViolation`. The object and the order stay as they
            were.
    """
    snapshots = [
        snapshot_order(namespace_set)
        for namespace_set in namespace_sets_of(element)
    ]
    previous = getattr(element, name)
    try:
        setattr(element, name, value)
    except Exception:
        _put_back(element, name, previous, snapshots)
        raise
    finally:
        for snapshot in snapshots:
            restore_order(snapshot)


def _put_back(
    element: object,
    name: str,
    previous: object,
    snapshots: Sequence[OrderSnapshot[Any]],
) -> None:
    """Undoes a refused attribute change that left the object out of its sets."""
    left = [
        snapshot
        for snapshot in snapshots
        if element not in snapshot.namespace_set
    ]
    if not left:
        return
    fields = vars(element)
    # A property keeps its value in a field with a leading underscore.
    field = f"_{name}" if f"_{name}" in fields else name
    fields[field] = previous
    for snapshot in left:
        _refill(snapshot.namespace_set, snapshot.items)


def set_id_short(element: model.Referable, id_short: str | None) -> None:
    """Renames an element and keeps its position (D19).

    Args:
        element: The element to rename.
        id_short: The new idShort.

    Raises:
        Exception: Whatever the SDK raises for an invalid or taken idShort,
            such as `AASConstraintViolation`. The order stays as it was.
    """
    set_attribute(element, "id_short", id_short)


def _same_members(current: Sequence[object], order: Sequence[object]) -> bool:
    return len(current) == len(order) and {id(item) for item in current} == {
        id(item) for item in order
    }


def _rebuild(
    namespace_set: model.NamespaceSet[_T], order: Sequence[_T]
) -> None:
    """Replaces the contents with the objects in a given order.

    The previous order is put back when the SDK refuses an object.
    """
    previous = tuple(namespace_set)
    if len(previous) == len(order) and all(
        old is new for old, new in zip(previous, order, strict=True)
    ):
        return
    namespace_set.clear()
    try:
        for item in order:
            namespace_set.add(item)
    except Exception:
        _refill(namespace_set, previous)
        raise


def _refill(namespace_set: model.NamespaceSet[_T], items: Sequence[_T]) -> None:
    try:
        namespace_set.clear()
        for item in items:
            namespace_set.add(item)
    except Exception as error:
        raise OrderRestoreError(
            "Namespace order could not be restored"
        ) from error
