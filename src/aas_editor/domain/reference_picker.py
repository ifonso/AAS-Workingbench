"""What a user needs to fill a reference without typing ids (F-EDT-11).

A reference is entered in many places: the semantic id of an element, the
value id of a qualifier, `refers_to` of an extension, the value of a
ReferenceElement, the ends of a relationship, the Submodels of a shell. This
module holds the rules they share, without Qt:

- `rule_for_hint` reads the type hint of the field and says which kinds of
  reference and which targets it accepts.
- `candidates` lists what a reference may point at, filtered by target type.
- `reference_to` derives the keys of a reference to a target, as an external
  reference to its id or as a model reference to its path.
- `status_of` says whether a reference resolves in the package, is dangling,
  or points outside of it, and `explain` turns an SDK refusal (AASd-121 to
  AASd-128) into a sentence.

Example:
    Offering the concept descriptions that match a search::

        found = candidates(package.objStore, (ConceptDescription,), "temp")
        reference = reference_to(found[0].target, as_model=False)
"""

from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
import enum
import types
import typing
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import describe_object
from aas_editor.domain.references import path_of
from aas_editor.domain.walking import descendants

TargetClasses = tuple[type[model.Referable], ...]
"""The classes of object that a reference may point at."""

ANYTHING: TargetClasses = (model.Referable,)


class ReferenceTargetError(ValueError):
    """No reference of the wanted kind points at the target. For the user."""


@dataclass(frozen=True)
class TargetFilter:
    """A named choice in the filter of the picker.

    Attributes:
        name: The text of the choice.
        classes: The classes it lets through.
    """

    name: str
    classes: TargetClasses

    def accepts(self, target: model.Referable) -> bool:
        """Tells whether the target is of one of the classes."""
        return isinstance(target, self.classes)


FILTERS: tuple[TargetFilter, ...] = (
    TargetFilter("Anything", ANYTHING),
    TargetFilter(
        "Asset administration shells", (model.AssetAdministrationShell,)
    ),
    TargetFilter("Submodels", (model.Submodel,)),
    TargetFilter("Concept descriptions", (ConceptDescription,)),
    TargetFilter("Submodel elements", (model.SubmodelElement,)),
)
"""The filters that the picker offers, from the widest to the narrowest."""


@dataclass(frozen=True)
class ReferenceRule:
    """What a field accepts as a reference, found from its type hint.

    Attributes:
        allows_model: Whether a model reference is accepted.
        allows_external: Whether an external reference is accepted.
        targets: The classes a model reference may point at.
    """

    allows_model: bool
    allows_external: bool
    targets: TargetClasses

    def filters(self) -> tuple[TargetFilter, ...]:
        """Returns the filters that can show something for this field.

        A filter is offered when it lets through a class that the field
        accepts, or when the field accepts a class that the filter is made
        of. The widest filter stays when the field accepts anything.
        """
        offered = [
            candidate
            for candidate in FILTERS
            if any(
                issubclass(accepted, wanted) or issubclass(wanted, accepted)
                for accepted in self.targets
                for wanted in candidate.classes
            )
        ]
        return tuple(offered)


def _flatten(arguments: Iterable[Any]) -> Iterator[Any]:
    for argument in arguments:
        if typing.get_origin(argument) in (typing.Union, types.UnionType):
            yield from _flatten(typing.get_args(argument))
        else:
            yield argument


def rule_for_hint(hint: object) -> ReferenceRule:
    """Reads what a field accepts from its type hint.

    Args:
        hint: The hint of the field: `Reference`, `ExternalReference`, or
            `ModelReference[...]`, with the classes the target may have.
            Anything else is treated as `Reference`.

    Returns:
        The rule. `ModelReference[Submodel]` accepts model references to a
        Submodel only, a bare `ModelReference` any target, and `Reference` both
        kinds with any target.
    """
    origin = typing.get_origin(hint) or hint
    if origin is model.ExternalReference:
        return ReferenceRule(False, True, ())
    if origin is model.ModelReference:
        targets = tuple(
            argument
            for argument in _flatten(typing.get_args(hint))
            if isinstance(argument, type)
            and issubclass(argument, model.Referable)
        )
        return ReferenceRule(True, False, targets or ANYTHING)
    return ReferenceRule(True, True, ANYTHING)


@dataclass(frozen=True, eq=False)
class Candidate:
    """An object that a reference can point at.

    Attributes:
        target: The shell, submodel, concept description, or element.
        kind: The name of its class.
        label: Its idShort path, or its id for an identifiable without an
            idShort.
        owner: The identifiable it belongs to, as a short text, or empty for
            an identifiable.
        depth: How far below its identifiable it is.
    """

    target: model.Referable
    kind: str
    label: str
    owner: str
    depth: int

    @property
    def search_text(self) -> str:
        """The text a search looks in, in lower case."""
        ids = (
            self.target.id
            if isinstance(self.target, model.Identifiable)
            else ""
        )
        return f"{self.kind} {self.label} {self.owner} {ids}".lower()


def _label_of(target: model.Referable) -> str:
    if isinstance(target, model.Identifiable):
        return target.id_short or target.id
    path = path_of(target)
    if path is None:
        return target.id_short or type(target).__name__
    return "/".join(path[1:])


def _root_order(root: model.Identifiable) -> tuple[int, str]:
    rank = {
        model.AssetAdministrationShell: 0,
        model.Submodel: 1,
        ConceptDescription: 2,
    }
    for cls, number in rank.items():
        if isinstance(root, cls):
            return number, _label_of(root).lower()
    return len(rank), _label_of(root).lower()


def candidates(
    objects: Iterable[model.Identifiable],
    classes: TargetClasses = ANYTHING,
    text: str = "",
) -> list[Candidate]:
    """Lists what a reference may point at, in document order.

    Args:
        objects: The shells, submodels, and concept descriptions of a package.
        classes: Only targets of these classes are listed.
        text: Only targets whose class, path, owner, or id contain this text,
            ignoring case. Empty lists everything.

    Returns:
        The candidates. A shell, a submodel, or a concept description comes
        before the elements below it.
    """
    wanted = text.strip().lower()
    found: list[Candidate] = []
    # Shells, submodels and concept descriptions live in sets, so their order
    # changes from run to run. The list shows them in a fixed one.
    for root in sorted(objects, key=_root_order):
        owner = ""
        for target in (root, *descendants(root)):
            if target is not root:
                owner = describe_object(root)
            if not isinstance(target, classes):
                continue
            candidate = Candidate(
                target=target,
                kind=type(target).__name__,
                label=_label_of(target),
                owner=owner,
                depth=0 if target is root else len(path_of(target) or ()) - 1,
            )
            if wanted in candidate.search_text:
                found.append(candidate)
    return found


def key_type_of(target: model.Referable) -> model.KeyTypes:
    """Returns the key type for an object, such as `PROPERTY` for a Property.

    Raises:
        ReferenceTargetError: If no key type fits the object.
    """
    try:
        cls = model.resolve_referable_class_in_key_types(target)
    except TypeError as error:
        raise ReferenceTargetError(
            f"No key type exists for {type(target).__name__}"
        ) from error
    return model.KEY_TYPES_CLASSES[cls]


def class_for_key_type(
    key_type: model.KeyTypes,
) -> type[model.Referable] | None:
    """Returns the class for a key type, or None for `GlobalReference` etc."""
    for cls, known in model.KEY_TYPES_CLASSES.items():
        if known is key_type:
            return cls
    return None


def reference_to(target: model.Referable, as_model: bool) -> model.Reference:
    """Derives the reference to a target.

    Args:
        target: The object to point at.
        as_model: True for a model reference through the path of the object,
            False for an external reference to its id.

    Returns:
        A `ModelReference` with the keys of the path, or an
        `ExternalReference` with one `GlobalReference` key that holds the id.

    Raises:
        ReferenceTargetError: If the target has no id for an external
            reference, or is not part of an identifiable for a model
            reference. The message tells the user what to do.
    """
    if not as_model:
        if not isinstance(target, model.Identifiable):
            raise ReferenceTargetError(
                "An external reference can only point at an AAS, a Submodel or "
                "a concept description, by its id. Use a model reference for "
                f"{describe_object(target)}"
            )
        return model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, target.id),)
        )
    try:
        return cast(
            "model.ModelReference[Any]",
            model.ModelReference.from_referable(target),  # pyright: ignore[reportUnknownMemberType]
        )
    except (ValueError, AttributeError, KeyError, StopIteration) as error:
        raise ReferenceTargetError(
            f"{describe_object(target)} is not part of a shell, a submodel "
            "or a concept description, so no model reference can point at it"
        ) from error


_NO_KEYS = "A reference must have at least one key!"


def explain(error: BaseException) -> str:
    """Turns the refusal of the SDK into a sentence for the user.

    Args:
        error: What the SDK raised while a reference was made, for example an
            `AASConstraintViolation` of AASd-121 to AASd-128.

    Returns:
        The message, which names the rule, without the traceback.
    """
    text = " ".join(str(error).split())
    if text == _NO_KEYS:
        return (
            "A reference needs at least one key. Add a key, or choose the "
            "target from the package."
        )
    return text


class ReferenceState(enum.Enum):
    """How a reference stands against the package."""

    RESOLVED = "resolved"
    """It points at an object of the package."""
    PARTIAL = "partial"
    """Its first keys resolve, and a later key does not."""
    DANGLING = "dangling"
    """A model reference whose first key matches no object."""
    OUTSIDE = "outside"
    """An external reference that no object of the package has the id of."""


@dataclass(frozen=True, eq=False)
class ReferenceStatus:
    """What the package says about a reference.

    Attributes:
        state: How the reference stands.
        text: A sentence for the user.
        target: The object it points at, if it resolves.
        reached: The deepest object that its keys lead to. The target when it
            resolves, an ancestor of the missing one for a partial one, and
            None when nothing is found.
        missing: The key values that were not found, for a partial reference.
    """

    state: ReferenceState
    text: str
    target: model.Referable | None = None
    reached: model.Referable | None = None
    missing: tuple[str, ...] = ()

    @property
    def is_dangling(self) -> bool:
        """Whether a model reference points at nothing, wholly or in part."""
        return self.state in (ReferenceState.PARTIAL, ReferenceState.DANGLING)


def _walk(
    root: model.Identifiable, values: list[str]
) -> tuple[model.Referable, int]:
    """Follows key values below an identifiable as far as they lead."""
    item: model.Referable = root
    for number, value in enumerate(values):
        try:
            item = model.UniqueIdShortNamespace.get_referable(
                cast("model.UniqueIdShortNamespace", item), [value]
            )
        except (KeyError, ValueError, TypeError, IndexError, AttributeError):
            return item, number
    return item, len(values)


def status_of(
    index: ReferenceIndex, reference: model.Reference
) -> ReferenceStatus:
    """Says whether a reference resolves, dangles, or points outside.

    Args:
        index: The index of the package the reference is stored in.
        reference: The reference to check.

    Returns:
        The status. An external reference is never dangling, because its
        target may well be elsewhere. If its first key holds the id of an
        object of the package, the status names that object, so the user can
        jump to it.
    """
    keys = [
        key
        for key in reference.key
        if key.type is not model.KeyTypes.FRAGMENT_REFERENCE
    ]
    first = keys[0].value
    roots = index.with_id(first)
    if not isinstance(reference, model.ModelReference):
        if roots:
            return ReferenceStatus(
                ReferenceState.RESOLVED,
                f"Points at {describe_object(roots[0])} of this package",
                roots[0],
                roots[0],
            )
        return ReferenceStatus(
            ReferenceState.OUTSIDE,
            "External reference: its target is outside of this package",
        )
    if not roots:
        why = index.why(cast("model.ModelReference[Any]", reference))
        return ReferenceStatus(ReferenceState.DANGLING, f"Dangling: {why}")
    root = roots[0]
    if len(keys) == 1:
        return ReferenceStatus(
            ReferenceState.RESOLVED,
            f"Resolves to {describe_object(root)}",
            root,
            root,
        )
    reached, followed = _walk(root, [key.value for key in keys[1:]])
    if followed == len(keys) - 1:
        return ReferenceStatus(
            ReferenceState.RESOLVED,
            f"Resolves to {describe_object(reached)}",
            reached,
            reached,
        )
    missing = tuple(key.value for key in keys[1 + followed :])
    return ReferenceStatus(
        ReferenceState.PARTIAL,
        f"Dangling: {describe_object(reached)} exists, but has nothing at "
        f"{' > '.join(missing)}",
        None,
        reached,
        missing,
    )
