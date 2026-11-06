"""What a SubmodelElementList fixes, and rebuilding a list with other settings.

A list fixes four things when it is made: the type of its items, the value type
of its Property or Range items, the semantic id its items share, and whether
their order matters. The SDK has no setters for them (see ADR 0008). To change
one, the list is made again through the constructor, and the items go into the
new list one by one. The SDK decides which items fit by refusing the others
(AASd-107, 108, 109, 114), and the items that do not fit are reported, never
dropped silently.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.domain import typed_values
from aas_editor.domain.element_copy import common_arguments
from aas_editor.domain.element_copy import detached_copy
from aas_editor.domain.element_copy import item_name
from aas_editor.domain.references import keys_equal
from aas_editor.domain.replacement import ConversionRefused
from aas_editor.domain.replacement import Loss
from aas_editor.domain.replacement import Outcome
from aas_editor.domain.replacement import ReplacementPlan
from aas_editor.domain.value_types import InvalidValueError
from aas_editor.domain.value_types import XsdType

ElementType = type[model.SubmodelElement]

# A list needs a type, and a Property item needs a value type.
DEFAULT_ITEM_TYPE: ElementType = model.Property
DEFAULT_VALUE_TYPE: XsdType = model.datatypes.String

# The types that the SDK accepts for the items of a list, and the abstract
# ones that it accepts but that no item can have (AASd-108 compares exactly).
LIST_ITEM_TYPES: tuple[ElementType, ...] = (
    model.Property,
    model.MultiLanguageProperty,
    model.Range,
    model.Blob,
    model.File,
    model.ReferenceElement,
    model.RelationshipElement,
    model.AnnotatedRelationshipElement,
    model.SubmodelElementCollection,
    model.SubmodelElementList,
    model.Entity,
    model.Operation,
    model.Capability,
    model.BasicEventElement,
)

_NEEDS_VALUE_TYPE = (model.Property, model.Range)


@dataclass(frozen=True)
class ListSettings:
    """The four things a list fixes.

    Attributes:
        element_type: The class every item must have (AASd-108).
        value_type: The value type of every item, for a list of Property or
            Range items, otherwise None (AASd-109).
        semantic_id: The semantic id every item with one must have
            (AASd-107). None fixes none.
        order_relevant: Whether the order of the items matters.
    """

    element_type: ElementType
    value_type: XsdType | None
    semantic_id: model.Reference | None
    order_relevant: bool

    def normalized(self) -> "ListSettings":
        """Returns the settings the SDK can build.

        A list of Property or Range items needs a value type, so the default
        is filled in. A list of other items has none.
        """
        if self.element_type in _NEEDS_VALUE_TYPE:
            return replace(
                self, value_type=self.value_type or DEFAULT_VALUE_TYPE
            )
        return replace(self, value_type=None)

    def differs_from(self, other: "ListSettings") -> bool:
        """Tells whether any of the four things differs."""
        return (
            self.element_type is not other.element_type
            or self.value_type is not other.value_type
            or self.order_relevant != other.order_relevant
            or not _same_reference(self.semantic_id, other.semantic_id)
        )


def settings_of(item_list: "model.SubmodelElementList[Any]") -> ListSettings:
    """Reads what a list fixes."""
    return ListSettings(
        cast(ElementType, item_list.type_value_list_element),  # pyright: ignore[reportUnknownMemberType]
        item_list.value_type_list_element,
        item_list.semantic_id_list_element,
        item_list.order_relevant,
    )


def derive_settings(items: Sequence[model.SubmodelElement]) -> ListSettings:
    """Chooses the settings of a list that is to hold some items.

    The most common type of the items wins, the first one on a tie. Among the
    items of that type, the most common value type wins for Property and
    Range, and the most common semantic id. The order is relevant, as it is
    by default in the SDK. For no items the default is a list of Property
    items of `xs:string`.

    Args:
        items: The items in their order.

    Returns:
        The settings. Items that do not fit them are for the rebuild to find.
    """
    if not items:
        return ListSettings(DEFAULT_ITEM_TYPE, DEFAULT_VALUE_TYPE, None, True)
    element_type = _most_common([type(item) for item in items])
    of_type = [item for item in items if type(item) is element_type]
    value_type: XsdType | None = None
    if element_type in _NEEDS_VALUE_TYPE:
        value_type = _most_common(
            [cast("XsdType", cast("Any", item).value_type) for item in of_type]
        )
    semantic_ids = [
        item.semantic_id for item in of_type if item.semantic_id is not None
    ]
    semantic_id = _most_common_reference(semantic_ids)
    return ListSettings(
        cast(ElementType, element_type), value_type, semantic_id, True
    )


def detect_settings(
    item_list: "model.SubmodelElementList[Any]",
) -> ListSettings | None:
    """Derives the settings of a list from the items it holds.

    The SDK makes every item fit the list already, so the type and the value
    type come out as they are. What can differ is the semantic id: a list that
    states none, with items that share one, gets that one.

    Args:
        item_list: The list.

    Returns:
        The detected settings, which keep the order flag of the list. None if
        the list has no items to detect from.
    """
    items = list(cast("Sequence[model.SubmodelElement]", item_list.value))
    if not items:
        return None
    derived = derive_settings(items)
    return replace(derived, order_relevant=item_list.order_relevant)


def plan_list_rebuild(
    item_list: "model.SubmodelElementList[Any]", settings: ListSettings
) -> ReplacementPlan:
    """Plans a new list with other settings, and the items that stay in it.

    Args:
        item_list: The list to rebuild. It is not changed.
        settings: What the new list fixes.

    Returns:
        The plan. The items that do not fit are in its losses.

    Raises:
        ConversionRefused: If the settings change nothing.
    """
    wanted = settings.normalized()
    if not wanted.differs_from(settings_of(item_list)):
        raise ConversionRefused("The list has these settings already.")

    def build() -> Outcome:
        return _rebuild(item_list, wanted)

    outcome = build()
    return ReplacementPlan(
        source=item_list,
        target_type=model.SubmodelElementList,
        preview=outcome.element,
        losses=outcome.losses,
        notes=outcome.notes,
        child_keys=outcome.child_keys,
        description=f"Change what {item_name(item_list)} fixes",
        _builder=build,
    )


@dataclass(frozen=True, eq=False)
class Placement:
    """The result of putting items into a new list.

    Attributes:
        new_list: The new list, holding the items that fit.
        placed: For each kept item, its key in the old element and its
            position in the new list.
        dropped: The items that do not fit, with the reason.
    """

    new_list: "model.SubmodelElementList[Any]"
    placed: tuple[tuple[str, int], ...]
    dropped: tuple[tuple[str, str, str], ...]


def build_list(
    common: dict[str, Any],
    settings: ListSettings,
    items: Sequence[tuple[str, model.SubmodelElement]],
) -> Placement:
    """Makes a list through the SDK and adds the items that it accepts.

    Args:
        common: The keyword arguments for the attributes every element has.
            The idShort is dropped when the list is itself an item of a list.
        settings: What the list fixes.
        items: Copies of the items, each with its key in the old element.
            They are changed: they lose their idShort, and the value type of
            a Property or Range follows the list.

    Returns:
        The list, the positions of the kept items, and for each item that does
        not fit its key, its name, and the reason.
    """
    wanted = settings.normalized()
    new_list = model.SubmodelElementList(
        type_value_list_element=wanted.element_type,
        semantic_id_list_element=wanted.semantic_id,
        value_type_list_element=wanted.value_type,
        order_relevant=wanted.order_relevant,
        **common,
    )
    placed: list[tuple[str, int]] = []
    dropped: list[tuple[str, str, str]] = []
    for key, item in items:
        name = _described(item)
        try:
            _follow_value_type(item, wanted)
            item.id_short = None
            new_list.value.add(item)
        except (model.AASConstraintViolation, InvalidValueError) as error:
            dropped.append((key, name, _reason(error)))
        else:
            placed.append((key, len(new_list.value) - 1))
    return Placement(new_list, tuple(placed), tuple(dropped))


def _rebuild(
    item_list: "model.SubmodelElementList[Any]", wanted: ListSettings
) -> Outcome:
    keep_name = not isinstance(item_list.parent, model.SubmodelElementList)
    common = common_arguments(item_list, keep_id_short=keep_name)
    members = list(cast("Sequence[model.SubmodelElement]", item_list.value))
    copies = [
        (str(position), detached_copy(member))
        for position, member in enumerate(members)
    ]
    placement = build_list(common, wanted, copies)
    keys: dict[str, str | None] = {}
    for key, position in placement.placed:
        if key != str(position):
            keys[key] = str(position)
    for key, _, _ in placement.dropped:
        keys[key] = None
    losses = tuple(
        Loss("item not kept", f"{name}: {reason}")
        for _, name, reason in placement.dropped
    )
    return Outcome(placement.new_list, losses, (), keys)


def _follow_value_type(
    item: model.SubmodelElement, wanted: ListSettings
) -> None:
    """Converts the values of a Property or Range item to the list's type."""
    if wanted.value_type is None or type(item) not in _NEEDS_VALUE_TYPE:
        return
    current = cast("Any", item).value_type
    if current is wanted.value_type:
        return
    values = typed_values.type_change_values(item, wanted.value_type)
    cast("Any", item).value_type = wanted.value_type
    for name, value in values.items():
        setattr(item, name, value)


def _described(item: model.SubmodelElement) -> str:
    name = item_name(item)
    return f"{name} ({type(item).__name__})"


def _reason(error: Exception) -> str:
    if isinstance(error, model.AASConstraintViolation):
        # The SDK appends the representation of the whole item to its message.
        text = error.message.rsplit(" (Constraint", 1)[0]
        cut = text.find(", got ")
        text = text[:cut] if cut > 0 else text
        return f"{text} (AASd-{error.constraint_id:03d})"
    return str(error).strip()


def _most_common(values: Sequence[Any]) -> Any:
    counts = Counter(values)
    best = max(counts.values())
    return next(value for value in values if counts[value] == best)


def _most_common_reference(
    references: Sequence[model.Reference],
) -> model.Reference | None:
    if not references:
        return None
    unique: list[model.Reference] = []
    for reference in references:
        if not any(_same_reference(reference, known) for known in unique):
            unique.append(reference)
    counts = [
        sum(_same_reference(reference, other) for other in references)
        for reference in unique
    ]
    return unique[counts.index(max(counts))]


def _same_reference(
    first: model.Reference | None, second: model.Reference | None
) -> bool:
    if first is None or second is None:
        return first is second
    return keys_equal(first, second)


__all__ = [
    "DEFAULT_ITEM_TYPE",
    "DEFAULT_VALUE_TYPE",
    "LIST_ITEM_TYPES",
    "ListSettings",
    "Placement",
    "build_list",
    "derive_settings",
    "detect_settings",
    "plan_list_rebuild",
    "settings_of",
]
