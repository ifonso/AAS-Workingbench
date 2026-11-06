"""Adding, removing, and replacing members of the containers of AAS objects.

BaSyx keeps the members of an object in different kinds of containers, and
each kind needs its own calls: a `NamespaceSet` (the elements of a submodel,
extensions, qualifiers), a `list` or a `ConstrainedList` (the supplemental
semantic ids), a plain `set` (the references of a
shell), an object store (the shells and submodels of a package), and a mapping
(a `LangStringSet`). The commands in `aas_editor.application.edits` work with
the functions here, so that they treat every container the same way and can
put a member back where it was.

Position matters only where the container has an order that is saved. A set
has none, so its functions report no position. A mapping member is a pair of
key and value, and its position is the position of the key.
"""

from collections.abc import Iterable
from collections.abc import MutableMapping
from collections.abc import MutableSequence
from collections.abc import MutableSet
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.domain import ordering
from aas_editor.domain.ordered_store import OrderedIdentifiableStore


def _is_mapping(container: object) -> bool:
    return isinstance(container, MutableMapping)


def is_list_like(container: object) -> bool:
    """Tells whether a container is an ordered list of members.

    Args:
        container: Any object.

    Returns:
        True for a `list` and for the SDK's `ConstrainedList`, which is a
        mutable sequence but no `list`. A `NamespaceSet` is not list-like here
        even though the SML's one is a sequence, because it has its own calls.
        Byte arrays are values, not containers.
    """
    return isinstance(container, MutableSequence) and not isinstance(
        container, (model.NamespaceSet, bytearray)
    )


def _members(container: object) -> list[Any]:
    """Returns the members of a container in order, as a new list."""
    return list(cast("Iterable[Any]", container))


def position_of(container: object, member: object) -> int | None:
    """Returns the position of a member, or None if it has none.

    Args:
        container: A `NamespaceSet`, a list (also the SDK's `ConstrainedList`), or a
            mapping. Other containers
            have no order.
        member: The object to look for, compared by identity. A mapping
            member is a pair, and its key is looked for.

    Returns:
        The position, or None when the container is unordered or does not hold
        the member.
    """
    if _is_mapping(container):
        key = cast("tuple[Any, Any]", member)[0]
        keys = _members(container)
        return keys.index(key) if key in keys else None
    if isinstance(container, OrderedIdentifiableStore):
        return container.position_of(cast("model.Identifiable", member))
    if isinstance(container, model.NamespaceSet) or is_list_like(container):
        held_members = _members(cast("object", container))
        for position, held in enumerate(held_members):
            if held is member:
                return position
        for position, held in enumerate(held_members):
            if held == member:
                return position
    return None


def add_member(
    container: object, member: object, index: int | None = None
) -> int | None:
    """Adds a member, at a position when the container has an order.

    Args:
        container: The container to add to.
        member: What to add. For a mapping, a pair of key and value.
        index: The wanted position, with the meaning of `list.insert`. None
            appends. A set ignores it.

    Returns:
        The position the member has now, or None for an unordered container.

    Raises:
        TypeError: If the container is of a kind this module does not know.
        ValueError: If a set already holds an equal member, because the add
            could not be taken back without removing the older member.
        Exception: Whatever the SDK raises when it refuses the member, such as
            a duplicate idShort. Nothing has changed then.
    """
    if _is_mapping(container):
        return _add_pair(
            cast("MutableMapping[Any, Any]", container), member, index
        )
    if isinstance(container, model.NamespaceSet):
        namespace_set = cast("model.NamespaceSet[Any]", container)
        if index is None:
            namespace_set.add(member)
        else:
            ordering.insert_at(namespace_set, member, index)
        return position_of(cast("object", container), member)
    if is_list_like(container):
        items = cast("MutableSequence[Any]", container)
        if index is None or index >= len(items):
            items.append(member)
            return len(items) - 1
        # A negative index counts from the end, as for list.insert.
        position = index if index >= 0 else max(0, len(items) + index)
        items.insert(position, member)
        return position
    if isinstance(container, OrderedIdentifiableStore):
        if member in container:
            raise ValueError(f"Already in the store: {member!r}")
        identifiable = cast("model.Identifiable", member)
        if index is None or index >= len(container):
            container.add(identifiable)
        else:
            container.insert(identifiable, index)
        return container.position_of(identifiable)
    if isinstance(container, MutableSet):
        members = cast("MutableSet[Any]", container)
        if member in members:
            raise ValueError(f"Already in the set: {member!r}")
        members.add(member)
        return None
    raise TypeError(f"Cannot add to a {type(container).__name__}")


def remove_member(container: object, member: object) -> int | None:
    """Removes a member and tells where it was.

    Args:
        container: The container to remove from.
        member: What to remove. For a mapping, a pair, of which the key counts.

    Returns:
        The position the member had, or None for an unordered container.

    Raises:
        TypeError: If the container is of a kind this module does not know.
        KeyError: If the container does not hold the member, or the SDK
            refuses to remove it, as for the last entry of a `LangStringSet`.
    """
    position = position_of(container, member)
    if _is_mapping(container):
        key = cast("tuple[Any, Any]", member)[0]
        del cast("MutableMapping[Any, Any]", container)[key]
    elif isinstance(container, model.NamespaceSet):
        cast("model.NamespaceSet[Any]", container).remove(member)
    elif is_list_like(container):
        if position is None:
            raise KeyError(f"Not in the list: {member!r}")
        del cast("MutableSequence[Any]", container)[position]
    elif isinstance(container, MutableSet):
        cast("MutableSet[Any]", container).remove(member)
    else:
        raise TypeError(f"Cannot remove from a {type(container).__name__}")
    return position


def replace_member(container: object, old: object, new: object) -> None:
    """Replaces a member by another object at the same position.

    Args:
        container: The container that holds `old`.
        old: The member to replace. For a mapping, a pair.
        new: The object that takes its place. For a mapping, a pair.

    Raises:
        TypeError: If the container is of a kind this module does not know.
        KeyError: If the container does not hold `old`.
        ValueError: If a mapping already has the key of `new`.
        Exception: Whatever the SDK raises when it refuses `new`. Nothing has
            changed then.
    """
    if _is_mapping(container):
        _replace_pair(cast("MutableMapping[Any, Any]", container), old, new)
    elif isinstance(container, model.NamespaceSet):
        ordering.replace_item(
            cast("model.NamespaceSet[Any]", container), old, new
        )
    elif is_list_like(container):
        position = position_of(container, old)
        if position is None:
            raise KeyError(f"Not in the list: {old!r}")
        cast("MutableSequence[Any]", container)[position] = new
    elif isinstance(container, MutableSet):
        members = cast("MutableSet[Any]", container)
        if old not in members:
            raise KeyError(f"Not in the set: {old!r}")
        members.remove(old)
        try:
            members.add(new)
        except Exception:
            members.add(old)
            raise
    else:
        raise TypeError(f"Cannot replace in a {type(container).__name__}")


def members_in_order(container: object) -> list[Any]:
    """Returns the members of an ordered container, as a new list.

    Args:
        container: A `NamespaceSet` or a list (also the SDK's
            `ConstrainedList`).

    Raises:
        TypeError: If the container has no order that is saved.
    """
    if isinstance(
        container, (model.NamespaceSet, OrderedIdentifiableStore)
    ) or is_list_like(container):
        return _members(cast("object", container))
    raise TypeError(f"A {type(container).__name__} has no order")


def reorder_members(container: object, order: list[Any]) -> None:
    """Puts the members of an ordered container into a new order.

    Args:
        container: A `NamespaceSet` or a list (also the SDK's
            `ConstrainedList`).
        order: Every member exactly once, in the new order. Members are
            compared by identity.

    Raises:
        TypeError: If the container has no order that is saved.
        ValueError: If `order` is not a permutation of the members. Nothing
            changes then.
        Exception: Whatever the SDK raises for a refused member, after the
            previous order was put back.
    """
    if isinstance(container, model.NamespaceSet):
        ordering.reorder(cast("model.NamespaceSet[Any]", container), order)
        return
    if isinstance(container, OrderedIdentifiableStore):
        container.reorder(cast("list[model.Identifiable]", order))
        return
    if is_list_like(container):
        items = cast("MutableSequence[Any]", container)
        current = _members(container)
        if len(current) != len(order) or {id(m) for m in current} != {
            id(m) for m in order
        }:
            raise ValueError("Order must list every member exactly once")
        items[:] = order
        return
    raise TypeError(f"A {type(container).__name__} has no order")


def reorder_keys(mapping: object, order: list[Any]) -> None:
    """Puts the entries of a mapping into a new order, by their keys.

    The SDK's `LangStringSet` is a mapping whose order is saved in the file.
    It has no insert, so each entry is taken out and added again at the end,
    in the new order. An entry is only taken out while another one is left,
    because the set must never be empty.

    Args:
        mapping: A mutable mapping, such as a `LangStringSet`.
        order: Every key exactly once, in the new order.

    Raises:
        TypeError: If the container is no mapping.
        ValueError: If `order` is not a permutation of the keys. Nothing
            changes then.
    """
    if not _is_mapping(mapping):
        raise TypeError(f"A {type(mapping).__name__} is no mapping")
    entries = cast("MutableMapping[Any, Any]", mapping)
    if sorted(order, key=repr) != sorted(entries, key=repr) or len(
        set(order)
    ) != len(order):
        raise ValueError("Order must list every key exactly once")
    if len(order) < 2:
        return
    for key in order:
        value = entries[key]
        del entries[key]
        entries[key] = value


def _add_pair(
    mapping: MutableMapping[Any, Any], pair: object, index: int | None
) -> int:
    key, value = cast("tuple[Any, Any]", pair)
    if key in mapping:
        raise ValueError(f"Key already used: {key!r}")
    mapping[key] = value
    if index is not None and 0 <= index < len(mapping) - 1:
        _move_last_key_to(mapping, index)
    return list(mapping).index(key)


def _replace_pair(
    mapping: MutableMapping[Any, Any], old: object, new: object
) -> None:
    old_key = cast("tuple[Any, Any]", old)[0]
    new_key, new_value = cast("tuple[Any, Any]", new)
    if old_key not in mapping:
        raise KeyError(f"Key not found: {old_key!r}")
    if new_key == old_key:
        mapping[old_key] = new_value
        return
    if new_key in mapping:
        raise ValueError(f"Key already used: {new_key!r}")
    position = list(mapping).index(old_key)
    # The new key goes in first, so a LangStringSet is never empty.
    mapping[new_key] = new_value
    _move_last_key_to(mapping, position)
    del mapping[old_key]


def _move_last_key_to(mapping: MutableMapping[Any, Any], position: int) -> None:
    """Moves the newest entry to a position, by re-adding the ones behind it.

    A dict has no insert, so the entries that must follow the moved one are
    taken out and added again.
    """
    keys = list(mapping)
    for key in keys[position:-1]:
        value = mapping[key]
        del mapping[key]
        mapping[key] = value
