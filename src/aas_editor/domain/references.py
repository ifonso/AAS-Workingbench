"""Where references are stored, who refers to what, and what is dangling.

A reference of the SDK is immutable, so changing one means replacing it where
it is stored. `iter_slots` finds every place where an AAS object stores a
reference, without a list of fields: it reads the attributes of the SDK
objects, so a field that a later SDK version adds is found as well. A test
checks this against the signatures of all SDK classes.

`ReferenceIndex` answers the questions that edits need to ask about a whole
package: which objects share an id, which references point at an object or at
an element below it, and which references point at nothing.

A reference keeps the ids and idShorts of its path as keys. A `ModelReference`
is `[Submodel id, idShort, idShort, ...]`, and the key after a
`SubmodelElementList` is the position in the list (AASd-128). An
`ExternalReference` to a global id, such as the semantic id of an element that
points at a concept description, counts as a reference to the object with that
id.

Example:
    Finding what refers to a concept description::

        index = ReferenceIndex(package.objStore)
        for usage in index.usages_of([concept_description]):
            print(usage.slot.location)
"""

from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
import enum
import functools
import inspect
import typing
from typing import Any
from typing import cast

from basyx.aas import model

# Attributes that point back up or repeat what is held elsewhere, so a walk
# that followed them would leave the object or visit everything twice.
_NOT_CONTENT = frozenset({"parent", "namespace_element_sets"})

_CONTAINERS = (
    list,
    tuple,
    set,
    frozenset,
    model.NamespaceSet,
    model.ConstrainedList,
)

_MODEL_MODULE = "basyx.aas.model"
_DATATYPES_MODULE = "basyx.aas.model.datatypes"


@dataclass(frozen=True, eq=False)
class ReferenceSlot:
    """A place where an AAS object stores one reference.

    Attributes:
        owner: The object whose attribute holds the reference, or holds the
            list or set of references.
        attribute: The public name of that attribute, such as `semantic_id`.
        reference: The reference as stored.
        container: The list or set that holds the reference, or None if the
            attribute holds the reference itself.
        owner_container: The list or set that holds `owner`, if `owner` is an
            object that cannot be changed, such as a `SpecificAssetId`.
        anchor: The nearest element, or identifiable, at or above `owner`.
        root: The shell, submodel or concept description that holds it all.
    """

    owner: object
    attribute: str
    reference: model.Reference
    container: object | None
    owner_container: object | None
    anchor: model.Referable
    root: model.Identifiable

    @property
    def is_member(self) -> bool:
        """Whether the reference is a member of a list or set."""
        return self.container is not None

    @property
    def is_frozen(self) -> bool:
        """Whether the owner cannot be changed, so it must be replaced."""
        return type(self.owner).__setattr__ is not object.__setattr__

    @property
    def is_removable(self) -> bool:
        """Whether the reference can be taken away without breaking the owner.

        A member of a list or set always can. An attribute can if its type
        allows None, which is false for the first and second of a relationship
        and for the data specification of an embedded data specification.
        """
        if self.is_member:
            return True
        return _is_optional(type(self.owner), self.attribute)

    @property
    def location(self) -> str:
        """Tells where the reference is, for a message to the user."""
        return f"{describe_object(self.anchor)} / {self.attribute}"


@dataclass(frozen=True, eq=False)
class Usage:
    """A reference that points at an object or at something below it.

    Attributes:
        slot: Where the reference is stored.
        reference: The reference that matched. It is `slot.reference`, or one
            of its `referred_semantic_id`.
    """

    slot: ReferenceSlot
    reference: model.Reference

    @property
    def is_nested(self) -> bool:
        """Whether only a `referred_semantic_id` of the stored reference."""
        return self.reference is not self.slot.reference


@dataclass(frozen=True, eq=False)
class DanglingReference:
    """A model reference whose target is not in the package.

    Attributes:
        slot: Where the reference is stored.
        reference: The reference that points at nothing.
        reason: Why it does not resolve, as a sentence.
    """

    slot: ReferenceSlot
    reference: model.ModelReference[Any]
    reason: str


def describe_object(obj: object) -> str:
    """Returns a short text for an AAS object, such as `Property 'Pump'`.

    Args:
        obj: Any object. Identifiables are named by their id.

    Returns:
        The class name and the idShort, path or id when there is one.
    """
    kind = type(obj).__name__
    if isinstance(obj, model.Identifiable):
        name = obj.id_short or obj.id
        return f"{kind} '{name}'"
    if isinstance(obj, model.Referable):
        try:
            return f"{kind} '{obj.get_id_short_path()}'"
        except (ValueError, AttributeError):
            return f"{kind} '{obj.id_short}'" if obj.id_short else kind
    return kind


def describe_reference(reference: model.Reference) -> str:
    """Returns the keys of a reference as one line.

    Args:
        reference: The reference to describe.

    Returns:
        For example `Submodel urn:x > Property Pump`.
    """
    return " > ".join(
        f"{key.type.name.title().replace('_', '')} {key.value}"
        for key in reference.key
    )


def keys_equal(first: model.Reference, second: model.Reference) -> bool:
    """Tells whether two references have the same keys, at every level.

    Args:
        first: One reference.
        second: Another reference.

    Returns:
        True if the keys match one by one, and so do the keys of the
        `referred_semantic_id` of both.
    """
    return type(first) is type(second) and first == second


def with_keys(
    reference: model.Reference,
    keys: Sequence[model.Key],
    referred_semantic_id: model.Reference | None,
) -> model.Reference:
    """Builds a reference of the same kind with other keys.

    Args:
        reference: The reference to take the kind and type from.
        keys: The keys of the new reference.
        referred_semantic_id: The `referred_semantic_id` of the new reference.

    Returns:
        A new `ModelReference` with the same target type, or a new
        `ExternalReference`.

    Raises:
        AASConstraintViolation: If the keys break a rule of the reference.
    """
    if isinstance(reference, model.ModelReference):
        typed = cast("model.ModelReference[Any]", reference)
        return model.ModelReference(
            tuple(keys), typed.type, referred_semantic_id
        )
    return model.ExternalReference(tuple(keys), referred_semantic_id)


def map_keys(
    reference: model.Reference,
    change: Callable[[model.Reference, int, model.Key], model.Key],
) -> model.Reference:
    """Builds a reference with changed keys, at every level.

    Args:
        reference: The reference to rebuild.
        change: Called with each reference of the chain, the position of a
            key, and the key. It returns the key to use, which is the same
            object when nothing changes.

    Returns:
        `reference` itself if no key changed, otherwise a new reference.

    Raises:
        AASConstraintViolation: If the new keys break a rule of a reference.
    """
    inner = reference.referred_semantic_id
    new_inner = None if inner is None else map_keys(inner, change)
    keys = tuple(
        change(reference, position, key)
        for position, key in enumerate(reference.key)
    )
    if new_inner is inner and all(
        new is old for new, old in zip(keys, reference.key, strict=True)
    ):
        return reference
    return with_keys(reference, keys, new_inner)


def without_nested(
    reference: model.Reference, nested: model.Reference
) -> model.Reference:
    """Builds a reference without one of its `referred_semantic_id`.

    Args:
        reference: The stored reference.
        nested: A reference in the chain of `referred_semantic_id` below it.
            The chain is cut at this reference.

    Returns:
        A new reference. Everything above `nested` is kept.

    Raises:
        AASConstraintViolation: If the keys break a rule, which cannot happen
            for keys that were valid before.
    """
    if reference is nested:
        raise ValueError("The stored reference itself is not nested")
    inner = reference.referred_semantic_id
    new_inner = (
        None
        if inner is nested or inner is None
        else without_nested(inner, nested)
    )
    return with_keys(reference, reference.key, new_inner)


def chain(reference: model.Reference) -> Iterator[model.Reference]:
    """Yields a reference and the references in its `referred_semantic_id`."""
    current: model.Reference | None = reference
    while current is not None:
        yield current
        current = current.referred_semantic_id


def iter_slots(root: model.Identifiable) -> Iterator[ReferenceSlot]:
    """Finds every reference that an identifiable stores, anywhere below it.

    The walk reads the attributes of the SDK objects, so it needs no list of
    fields. It covers semantic ids, supplemental semantic ids, value ids,
    `refers_to`, data specifications, the references of a shell, relationships,
    annotations and every other field of the SDK, including those of the
    qualifiers, extensions, and data specification content.

    Args:
        root: The shell, submodel or concept description to search.

    Yields:
        One slot for each stored reference, in document order. A
        `referred_semantic_id` is not a slot of its own, but part of the slot
        of the reference that holds it.
    """
    stack: list[tuple[object, model.Referable, object | None]] = [
        (root, root, None)
    ]
    seen: set[int] = set()
    while stack:
        owner, anchor, owner_container = stack.pop()
        if id(owner) in seen:
            continue
        seen.add(id(owner))
        pending: list[tuple[object, model.Referable, object | None]] = []
        for name, value in vars(owner).items():
            if name in _NOT_CONTENT:
                continue
            attribute = _public_name(type(owner), name)
            if isinstance(value, model.Reference):
                yield ReferenceSlot(
                    owner, attribute, value, None, owner_container, anchor, root
                )
            elif isinstance(value, _CONTAINERS):
                container = cast("object", value)
                for member in cast("Iterable[object]", value):
                    if isinstance(member, model.Reference):
                        yield ReferenceSlot(
                            owner,
                            attribute,
                            member,
                            container,
                            owner_container,
                            anchor,
                            root,
                        )
                    elif _is_content(member):
                        pending.append(_child(member, anchor, container))
            elif _is_content(value):
                pending.append(_child(value, anchor, None))
        stack.extend(reversed(pending))


class ReferenceIndex:
    """Ids and references of the objects of one package, built when needed.

    Build one for a single operation and drop it: it does not follow changes.
    Finding the objects by id is cheap, and the references are collected on
    first use by walking the objects once.

    Attributes:
        objects: The shells, submodels and concept descriptions, in the order
            they were given.
    """

    def __init__(self, objects: Iterable[model.Identifiable]) -> None:
        """Indexes the ids of the objects.

        Args:
            objects: The identifiables of the package, such as its object
                store.
        """
        self.objects = tuple(objects)
        self._by_id: dict[str, list[model.Identifiable]] = {}
        for obj in self.objects:
            self._by_id.setdefault(obj.id, []).append(obj)
        self._slots: tuple[ReferenceSlot, ...] | None = None
        # Every key value, with the reference that has the key and the
        # position of the key, to find the references to an id quickly.
        self._by_value: dict[
            str, list[tuple[ReferenceSlot, model.Reference, int]]
        ] = {}

    # Ids

    def with_id(self, id_: str) -> tuple[model.Identifiable, ...]:
        """Returns the objects that have an id."""
        return tuple(self._by_id.get(id_, ()))

    def is_taken(
        self, id_: str, ignoring: model.Identifiable | None = None
    ) -> bool:
        """Tells whether an id belongs to an object of the package.

        Args:
            id_: The id to look for.
            ignoring: An object that does not count, usually the one that
                gets the id.

        Returns:
            True if another object has this id.
        """
        return any(obj is not ignoring for obj in self._by_id.get(id_, ()))

    def duplicate_ids(self) -> dict[str, tuple[model.Identifiable, ...]]:
        """Finds ids that more than one object has.

        Returns:
            For each id that is shared, the objects that share it.
        """
        return {
            id_: tuple(objs)
            for id_, objs in self._by_id.items()
            if len(objs) > 1
        }

    # References

    @property
    def slots(self) -> tuple[ReferenceSlot, ...]:
        """Every stored reference in the package, in document order."""
        return self._build()

    def _build(self) -> tuple[ReferenceSlot, ...]:
        if self._slots is None:
            self._slots = tuple(
                slot for obj in self.objects for slot in iter_slots(obj)
            )
            for slot in self._slots:
                for node in chain(slot.reference):
                    for position, key in enumerate(node.key):
                        self._by_value.setdefault(key.value, []).append(
                            (slot, node, position)
                        )
        return self._slots

    def resolve(self, reference: model.Reference) -> model.Referable | None:
        """Follows a model reference in the package.

        Args:
            reference: The reference to follow. An external reference points
                outside the package and never resolves.

        Returns:
            The object it points at, whatever its type, or None if there is
            no such object. A trailing fragment key is ignored.
        """
        if _model_reference(reference) is None:
            return None
        keys = [
            key
            for key in reference.key
            if key.type is not model.KeyTypes.FRAGMENT_REFERENCE
        ]
        found = self._by_id.get(keys[0].value)
        if not found:
            return None
        item: model.Referable = found[0]
        path = [key.value for key in keys[1:]]
        if not path:
            return item
        try:
            return model.UniqueIdShortNamespace.get_referable(
                cast("model.UniqueIdShortNamespace", item), path
            )
        except (KeyError, ValueError, TypeError, IndexError):
            return None

    def usages_of(
        self,
        targets: Iterable[model.Referable],
        include_inside: bool = False,
    ) -> list[Usage]:
        """Finds the references that point at objects or at elements below them.

        A reference to an identifiable is a model reference whose first key
        has its id, or any reference with a key of that id, such as the
        semantic id that points at a concept description. A reference to an
        element is a model reference whose path starts with the path of the
        element, so it also covers the elements below.

        References that are stored inside a target do not count, unless
        `include_inside` asks for them, as a rename does.

        Args:
            targets: The objects that are about to change or go away.
            include_inside: Whether to include the references that are stored
                in a target or below it.

        Returns:
            The usages, in document order, each reference once.
        """
        wanted = list(targets)
        inside = {id(target) for target in wanted}
        slots = self.slots
        found: dict[tuple[int, int], Usage] = {}
        for target in wanted:
            for slot, node in self._candidates(target):
                if not include_inside and _is_within(slot, inside):
                    continue
                found.setdefault(
                    (id(slot), id(node)),
                    Usage(slot, node),
                )
        order = {id(slot): number for number, slot in enumerate(slots)}
        return sorted(
            found.values(),
            key=lambda usage: (
                order[id(usage.slot)],
                id(usage.reference) != id(usage.slot.reference),
            ),
        )

    def dangling(
        self, roots: Collection[model.Identifiable] | None = None
    ) -> list[DanglingReference]:
        """Finds the model references that point at nothing.

        An external reference never counts, because its target is outside the
        package.

        Args:
            roots: Only the references stored in these objects. None checks
                the whole package.

        Returns:
            The references that do not resolve, in document order.
        """
        found: list[DanglingReference] = []
        only = None if roots is None else {id(root) for root in roots}
        for slot in self.slots:
            if only is not None and id(slot.root) not in only:
                continue
            for node in chain(slot.reference):
                typed = _model_reference(node)
                if typed is not None and self.resolve(typed) is None:
                    found.append(
                        DanglingReference(slot, typed, self.why(typed))
                    )
        return found

    def why(self, reference: model.ModelReference[Any]) -> str:
        """Says why a model reference does not resolve, as a sentence."""
        first = reference.key[0].value
        if first not in self._by_id:
            return f"No object has the id '{first}'"
        return f"'{first}' has nothing at {describe_reference(reference)}"

    def _candidates(
        self, target: model.Referable
    ) -> Iterator[tuple[ReferenceSlot, model.Reference]]:
        if isinstance(target, model.Identifiable):
            for slot, node, position in self._by_value.get(target.id, ()):
                if position == 0 or _model_reference(node) is None:
                    yield slot, node
            return
        path = path_of(target)
        if path is not None:
            for usage in self.through(path):
                yield usage.slot, usage.reference

    def through(self, path: Sequence[str]) -> list[Usage]:
        """Finds the model references whose keys begin with a path.

        Args:
            path: The key values from an identifiable down to an element, as
                `path_of` gives them.

        Returns:
            The references that go through the element or end at it, with the
            reference of the chain that matched.
        """
        self._build()
        return [
            Usage(slot, node)
            for slot, node, position in self._by_value.get(path[0], ())
            if position == 0
            and _model_reference(node) is not None
            and starts_with(node, path)
        ]


def is_model_reference(reference: model.Reference) -> bool:
    """Tells whether a reference is a `ModelReference`, not an external one."""
    return isinstance(reference, model.ModelReference)


def path_of(element: model.Referable) -> tuple[str, ...] | None:
    """Returns the key values that lead to an element.

    Args:
        element: An element below a shell, submodel or concept description.

    Returns:
        The id of the identifiable, then the idShort of each element on the
        way, or the position for an element in a list. None if the element
        is not below an identifiable.
    """
    try:
        reference = cast(
            "model.ModelReference[Any]",
            model.ModelReference.from_referable(element),  # pyright: ignore[reportUnknownMemberType]
        )
    except (ValueError, AttributeError, KeyError, StopIteration):
        return None
    return tuple(key.value for key in reference.key)


def starts_with(reference: model.Reference, path: Sequence[str]) -> bool:
    """Tells whether the keys of a reference begin with the given values."""
    keys = reference.key
    return len(keys) >= len(path) and all(
        key.value == value for key, value in zip(keys, path, strict=False)
    )


def _is_within(slot: ReferenceSlot, targets: Collection[int]) -> bool:
    current: object | None = slot.anchor
    while current is not None:
        if id(current) in targets:
            return True
        current = getattr(current, "parent", None)
    return False


def _child(
    obj: object, anchor: model.Referable, container: object | None
) -> tuple[object, model.Referable, object | None]:
    new_anchor = obj if isinstance(obj, model.Referable) else anchor
    return obj, new_anchor, container


def _is_content(value: object) -> bool:
    """Tells whether an object can hold references, and so must be walked."""
    if isinstance(value, (str, bytes, int, float, type, enum.Enum, model.Key)):
        return False
    if isinstance(value, (Mapping, model.Reference)):
        return False
    module = type(value).__module__
    return module.startswith(_MODEL_MODULE) and module != _DATATYPES_MODULE


def _model_reference(
    reference: model.Reference,
) -> "model.ModelReference[Any] | None":
    if isinstance(reference, model.ModelReference):
        return cast("model.ModelReference[Any]", reference)
    return None


def _public_name(cls: type, name: str) -> str:
    if name.startswith("_") and hasattr(cls, name[1:]):
        return name[1:]
    return name


@functools.cache
def _is_optional(cls: type, attribute: str) -> bool:
    # The SDK lets a relationship go without ends, which the metamodel does not.
    if issubclass(cls, model.RelationshipElement) and attribute in {
        "first",
        "second",
    }:
        return False
    # The annotation of the constructor parameter is read as it was written,
    # because resolving all hints of a class fails for forward references to
    # modules, such as the ones of `BasicEventElement`.
    try:
        parameter = inspect.signature(cast("type[Any]", cls)).parameters.get(
            attribute
        )
    except (TypeError, ValueError):
        return False
    if parameter is None:
        return False
    annotation = cast("object", parameter.annotation)
    if isinstance(annotation, str):
        return "Optional[" in annotation or "None" in annotation
    return type(None) in typing.get_args(annotation)
