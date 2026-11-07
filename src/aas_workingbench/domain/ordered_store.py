"""An object store that keeps the order in which objects were added.

The SDK's `SetIdentifiableStore` keeps its objects in a Python `set`. Its order
depends on the memory addresses of the objects, so it changes from run to run.
A package read from a file lists its shells, submodels, and concept
descriptions in the order of the file, and a package written from that store
wrote them in whatever order the set had. The order of a file could not
survive an open and a save, and the editor could not tell "the order of the
file" at all (ADR 0021).

`OrderedIdentifiableStore` is the same store with a `dict` as its backend, so
iteration follows the order of `add`. It keeps the property that the SDK
documents for the set store: objects are found by walking them, not by a key
that goes stale, so an object whose id changes stays findable.

Example:
    Reading a file into a store keeps the order of the file::

        store = OrderedIdentifiableStore()
        read_aas_json_file_into(store, path)
        [o.id for o in store]  # the order of the file
"""

from collections.abc import Iterable
from collections.abc import Iterator

from basyx.aas import model


class _OrderedBackend:
    """The part of a `set` that `SetIdentifiableStore` uses, in insertion order."""

    def __init__(self) -> None:
        self._items: dict[model.Identifiable, None] = {}

    def add(self, item: model.Identifiable) -> None:
        """Adds an object at the end. An object that is there stays in place."""
        self._items.setdefault(item, None)

    def discard(self, item: model.Identifiable) -> None:
        """Removes an object if it is there."""
        self._items.pop(item, None)

    def remove(self, item: model.Identifiable) -> None:
        """Removes an object.

        Raises:
            KeyError: If the object is not there.
        """
        del self._items[item]

    def replace_order(self, order: Iterable[model.Identifiable]) -> None:
        """Puts the objects into a new order. The caller checked it."""
        self._items = dict.fromkeys(order)

    def __contains__(self, item: object) -> bool:
        return item in self._items

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[model.Identifiable]:
        return iter(self._items)


class OrderedIdentifiableStore(model.SetIdentifiableStore[model.Identifiable]):
    """A `SetIdentifiableStore` whose iteration follows the order of `add`.

    Attributes:
        order: The ids of the objects, in the order of the store.
    """

    def __init__(self, objects: Iterable[model.Identifiable] = ()) -> None:
        """Makes a store.

        Args:
            objects: Objects to add, in this order.
        """
        # `SetIdentifiableStore` only adds, discards, removes, tests, counts,
        # and iterates its backend, which `_OrderedBackend` does in order.
        super().__init__()
        self._ordered = _OrderedBackend()
        self._backend = self._ordered  # pyright: ignore[reportAttributeAccessIssue]
        for item in objects:
            self.add(item)

    @property
    def order(self) -> tuple[str, ...]:
        """The ids of the objects in the order of the store."""
        return tuple(item.id for item in self)

    def position_of(self, item: model.Identifiable) -> int | None:
        """Returns the position of an object, compared by identity, or None."""
        for position, held in enumerate(self):
            if held is item:
                return position
        return None

    def insert(self, item: model.Identifiable, index: int) -> None:
        """Adds an object at a position, with the meaning of `list.insert`.

        Raises:
            KeyError: If the id is taken, as for `add`. Nothing changes then.
        """
        self.add(item)
        held = list(self)
        held.remove(item)
        held.insert(index, item)
        self._ordered.replace_order(held)

    def reorder(self, order: Iterable[model.Identifiable]) -> None:
        """Puts the objects into a new order.

        Args:
            order: Every object of the store once, in the new order.

        Raises:
            ValueError: If `order` is not a permutation of the objects. Nothing
                changes then.
        """
        wanted = list(order)
        if len(wanted) != len(self) or {id(o) for o in wanted} != {
            id(o) for o in self
        }:
            raise ValueError("Order must list every object exactly once")
        self._ordered.replace_order(wanted)
