"""Converting a submodel element to another element type (F-EDT-04 Refactor).

The SDK cannot change the class of an element, so the new element is built
through the constructor of its class, from the attributes of the old one. The
original editor does this and drops attributes without a word. This module
finds what the new element would lack, before anything changes, so that the
editor can show it and ask (see ADR 0012).

Every conversion keeps what all elements share: idShort, display name,
category, description, semantic id, supplemental semantic ids, qualifiers,
extensions, and embedded data specifications. Beyond that, the types fall into
three groups, and the conversions inside a group carry their values over.
Any other pair, and a conversion to a Capability, carries nothing but the
shared attributes, and lists everything specific as lost.

=================  =====================================================
Group              What carries over
=================  =====================================================
Value elements     The value as text. A Property keeps its type for a
(Property, Range,  Range and the other way. A Range uses its minimum as
MultiLanguage-     the value, a Property's value as minimum and maximum.
Property, File,    A MultiLanguageProperty uses one text, preferably in
Blob)              English. A File's path is the text of a Blob.
Reference          The first reference. The second one only between
elements           relationships. The annotations only between annotated
                   relationships.
Containers         The items, as copies. Items without an idShort get one.
(Collection,       A list keeps the items that fit its settings. An
List, Entity,      Operation puts all items in its input variables.
Operation)
=================  =====================================================

A BasicEventElement can be converted to any type, but no type converts to it:
its observed reference is mandatory, and no other element has one to take.
The items of a list must all have the type of the list (AASd-108), so an item
of a list cannot be converted. Change what the list fixes instead
(`aas_workingbench.domain.list_settings`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import cast

from basyx.aas import model

from aas_workingbench.domain import blob_content
from aas_workingbench.domain import value_types
from aas_workingbench.domain.element_copy import GENERATED_PREFIX
from aas_workingbench.domain.element_copy import as_list
from aas_workingbench.domain.element_copy import common_arguments
from aas_workingbench.domain.element_copy import detached_copy
from aas_workingbench.domain.element_copy import is_set
from aas_workingbench.domain.element_copy import join_names
from aas_workingbench.domain.element_copy import members_of
from aas_workingbench.domain.element_copy import item_name
from aas_workingbench.domain.element_copy import names_of
from aas_workingbench.domain.element_copy import shown
from aas_workingbench.domain.ids import unique_id_short
from aas_workingbench.domain.list_settings import build_list
from aas_workingbench.domain.list_settings import derive_settings
from aas_workingbench.domain.list_settings import settings_of
from aas_workingbench.domain.replacement import ConversionRefused
from aas_workingbench.domain.replacement import Loss
from aas_workingbench.domain.replacement import Outcome
from aas_workingbench.domain.replacement import ReplacementPlan
from aas_workingbench.domain.value_types import XsdType

ElementType = type[model.SubmodelElement]

DEFAULT_LANGUAGE = "en"
"""The language of a text that a Property or a File gives a MultiLanguageProperty."""

VALUE_TYPES: tuple[ElementType, ...] = (
    model.Property,
    model.Range,
    model.MultiLanguageProperty,
    model.File,
    model.Blob,
)
REFERENCE_TYPES: tuple[ElementType, ...] = (
    model.ReferenceElement,
    model.RelationshipElement,
    model.AnnotatedRelationshipElement,
)
CONTAINER_TYPES: tuple[ElementType, ...] = (
    model.SubmodelElementCollection,
    model.SubmodelElementList,
    model.Entity,
    model.Operation,
)
TARGET_TYPES: tuple[ElementType, ...] = (
    *VALUE_TYPES,
    *REFERENCE_TYPES,
    *CONTAINER_TYPES,
    model.Capability,
)
"""The types an element can be converted to. A BasicEventElement is not one."""

_STRING = model.datatypes.String


@dataclass(frozen=True)
class _Options:
    file_content: bytes | None
    language: str


@dataclass(frozen=True)
class _Child:
    element: model.SubmodelElement
    key: str
    direction: str | None


def refusal_for(element: model.SubmodelElement) -> str | None:
    """Tells why an element cannot be converted at all.

    Args:
        element: The element to convert.

    Returns:
        A message for the user, or None if some conversion is possible.
    """
    parent = element.parent
    if isinstance(parent, model.SubmodelElementList):
        return (
            f"An item of the list '{parent.id_short}' must have the type "
            "the list fixes (AASd-108), so it cannot be converted. Use "
            "'Change list settings...' on the list to change that type."
        )
    if parent is None:
        return "The element is not in a submodel."
    return None


def targets_for(element: model.SubmodelElement) -> list[ElementType]:
    """Lists the types an element can be converted to.

    Args:
        element: The element to convert.

    Returns:
        The types, in the order of the editor's add dialog. Empty if
        `refusal_for` gives a reason. The annotations of a relationship can only
        become other data elements.
    """
    if refusal_for(element) is not None:
        return []
    allowed = [target for target in TARGET_TYPES if target is not type(element)]
    if isinstance(element.parent, model.AnnotatedRelationshipElement):
        allowed = [
            target
            for target in allowed
            if issubclass(target, model.DataElement)
        ]
    return cast("list[ElementType]", allowed)


def plan_conversion(
    element: model.SubmodelElement,
    target_type: ElementType,
    *,
    file_content: bytes | None = None,
    language: str = DEFAULT_LANGUAGE,
) -> ReplacementPlan:
    """Plans the conversion of an element to another type.

    Args:
        element: The element to convert. It is not changed.
        target_type: The class of the new element, one of `targets_for`.
        file_content: For a File converted to a Blob: the bytes of the stored
            file to copy into the Blob. None stores the path as text, as the
            original editor does when the user declines.
        language: The language for the text that a Property or a File gives a
            MultiLanguageProperty.

    Returns:
        The plan, with the losses. Nothing has changed.

    Raises:
        ConversionRefused: If the element cannot be converted to the type.
    """
    reason = refusal_for(element)
    if reason is not None:
        raise ConversionRefused(reason)
    if target_type not in targets_for(element):
        raise ConversionRefused(
            f"{type(element).__name__} cannot be converted to "
            f"{target_type.__name__}."
        )
    options = _Options(file_content, language)

    def build() -> Outcome:
        return _convert(element, target_type, options)

    outcome = build()
    return ReplacementPlan(
        source=element,
        target_type=target_type,
        preview=outcome.element,
        losses=outcome.losses,
        notes=outcome.notes,
        child_keys=outcome.child_keys,
        description=(f"Convert {item_name(element)} to {target_type.__name__}"),
        _builder=build,
    )


def _convert(
    source: model.SubmodelElement, target: ElementType, options: _Options
) -> Outcome:
    source_type = type(source)
    if source_type in VALUE_TYPES and target in VALUE_TYPES:
        return _value_to_value(source, target, options)
    if source_type in REFERENCE_TYPES and target in REFERENCE_TYPES:
        return _reference_to_reference(source, target)
    if source_type in CONTAINER_TYPES and target in CONTAINER_TYPES:
        return _container_to_container(source, target)
    return _common_only(source, target)


# Value elements


@dataclass
class _Parts:
    """The value of a value element as text, and what did not fit in it."""

    text: str | None = None
    raw: object = None
    value_type: XsdType | None = None
    content_type: str | None = None
    value_id: model.Reference | None = None
    data: bytes | None = None
    losses: list[Loss] | None = None

    def lost(self) -> list[Loss]:
        if self.losses is None:
            self.losses = []
        return self.losses


def _read_parts(source: model.SubmodelElement) -> _Parts:
    parts = _Parts()
    if isinstance(source, model.Property):
        parts.value_type = source.value_type
        parts.value_id = source.value_id
        parts.raw = source.value
        if source.value is not None:
            parts.text = value_types.format_value(source.value)
    elif isinstance(source, model.Range):
        parts.value_type = source.value_type
        parts.raw = source.min
        if source.min is not None:
            parts.text = value_types.format_value(source.min)
        if source.max is not None and source.max != source.min:
            parts.lost().append(
                Loss(
                    "maximum",
                    shown(value_types.format_value(source.max)),
                )
            )
    elif isinstance(source, model.MultiLanguageProperty):
        parts.value_id = source.value_id
        _read_texts(source, parts)
    elif isinstance(source, model.File):
        parts.text = source.value
        parts.content_type = source.content_type
    elif isinstance(source, model.Blob):
        parts.content_type = source.content_type
        parts.data = source.value
        _read_content(source, parts)
    return parts


def _read_texts(source: model.MultiLanguageProperty, parts: _Parts) -> None:
    texts = dict(source.value) if source.value else {}
    if not texts:
        return
    chosen = (
        DEFAULT_LANGUAGE if DEFAULT_LANGUAGE in texts else next(iter(texts))
    )
    parts.text = texts[chosen]
    parts.lost().append(Loss("language of the text", f"'{chosen}'"))
    others = {
        language: text for language, text in texts.items() if language != chosen
    }
    if others:
        parts.lost().append(
            Loss(
                "texts in other languages",
                "; ".join(
                    f"{language}: {shown(text)}"
                    for language, text in others.items()
                ),
            )
        )


def _read_content(source: model.Blob, parts: _Parts) -> None:
    data = source.value
    if data is None:
        return
    decoded = blob_content.as_text(data)
    if decoded is None:
        parts.lost().append(Loss("content", shown(data)))
        return
    parts.text = decoded.text.replace("\n", decoded.newline)


def _value_to_value(
    source: model.SubmodelElement, target: ElementType, options: _Options
) -> Outcome:
    parts = _read_parts(source)
    common = common_arguments(source)
    losses = list(parts.losses or [])
    notes: list[str] = []
    stringy = parts.value_type in (None, _STRING)
    if target in (model.Property, model.Range):
        new = _typed_element(target, parts, common)
        _lose_unless(losses, "content type", parts.content_type)
        if target is model.Range:
            _lose_unless(losses, "value id", parts.value_id)
    elif target is model.MultiLanguageProperty:
        new = _texts_element(parts, options, common, losses, notes)
        _lose_unless(losses, "content type", parts.content_type)
        _lose_type(losses, parts, stringy)
    elif target is model.File:
        new = _file_element(source, parts, common, losses, notes)
        _lose_type(losses, parts, stringy)
        _lose_unless(losses, "value id", parts.value_id)
    else:
        new = _blob_element(source, parts, options, common, losses, notes)
        _lose_type(losses, parts, stringy)
        _lose_unless(losses, "value id", parts.value_id)
    return Outcome(new, tuple(losses), tuple(notes))


def _typed_element(
    target: ElementType, parts: _Parts, common: dict[str, Any]
) -> model.SubmodelElement:
    value_type = parts.value_type or _STRING
    value = parts.raw
    if parts.text is not None and parts.value_type is None:
        value = value_types.parse(parts.text, value_type)
    if target is model.Property:
        return model.Property(
            value_type=value_type,
            value=cast("Any", value),
            value_id=parts.value_id,
            **common,
        )
    return model.Range(
        value_type=value_type,
        min=cast("Any", value),
        max=cast("Any", value),
        **common,
    )


def _texts_element(
    parts: _Parts,
    options: _Options,
    common: dict[str, Any],
    losses: list[Loss],
    notes: list[str],
) -> model.SubmodelElement:
    value = None
    if parts.text:
        value = model.MultiLanguageTextType({options.language: parts.text})
        notes.append(
            f"The text is stored in the language '{options.language}'."
        )
    elif parts.text == "":
        losses.append(Loss("value", "an empty text"))
    return model.MultiLanguageProperty(
        value=value, value_id=parts.value_id, **common
    )


def _file_element(
    source: model.SubmodelElement,
    parts: _Parts,
    common: dict[str, Any],
    losses: list[Loss],
    notes: list[str],
) -> model.SubmodelElement:
    path = parts.text
    if isinstance(source, model.Blob):
        # The bytes of a Blob are no path to a file.
        path = None
        if parts.text is not None:
            losses.append(Loss("content", shown(parts.text)))
    content_type = parts.content_type
    if content_type is None and path:
        content_type = blob_content.guess_content_type(path)
        if content_type:
            notes.append(
                f"The content type '{content_type}' was taken from the "
                "file name."
            )
    return model.File(content_type=content_type, value=path, **common)


def _blob_element(
    source: model.SubmodelElement,
    parts: _Parts,
    options: _Options,
    common: dict[str, Any],
    losses: list[Loss],
    notes: list[str],
) -> model.SubmodelElement:
    data: bytes | None = None
    if parts.text is not None:
        data = blob_content.from_text(parts.text)
    if isinstance(source, model.File) and options.file_content is not None:
        data = options.file_content
        losses.append(Loss("path", shown(parts.text or "")))
        notes.append(
            "The content of the file was copied into the Blob. The file "
            "stays in the package."
        )
    elif isinstance(source, model.File) and parts.text is not None:
        notes.append("The Blob holds the path of the file as text.")
    return model.Blob(content_type=parts.content_type, value=data, **common)


def _lose_unless(
    losses: list[Loss], what: str, value: object, text: str | None = None
) -> None:
    if is_set(value):
        losses.append(Loss(what, text or shown(value)))


def _lose_type(losses: list[Loss], parts: _Parts, stringy: bool) -> None:
    if not stringy and parts.value_type is not None:
        losses.append(
            Loss(
                "value type",
                f"{value_types.type_name(parts.value_type)} "
                "(the value becomes text)",
            )
        )


# Reference elements


def _reference_to_reference(
    source: model.SubmodelElement, target: ElementType
) -> Outcome:
    common = common_arguments(source)
    first: model.Reference | None
    second: model.Reference | None = None
    annotations: list[model.DataElement] = []
    if isinstance(source, model.ReferenceElement):
        first = source.value
    else:
        relationship = cast("model.RelationshipElement", source)
        first, second = relationship.first, relationship.second
    if isinstance(source, model.AnnotatedRelationshipElement):
        annotations = list(source.annotation)
    losses: list[Loss] = []
    keys: dict[str, str | None] = {}
    if target is model.ReferenceElement:
        new: model.SubmodelElement = model.ReferenceElement(
            value=first, **common
        )
        _lose_unless(losses, "second reference", second)
    elif target is model.RelationshipElement:
        new = model.RelationshipElement(first=first, second=second, **common)
    else:
        new = model.AnnotatedRelationshipElement(
            first=first, second=second, **common
        )
    if annotations and target is not model.AnnotatedRelationshipElement:
        losses.append(
            Loss("annotations", names_of(cast("list[Any]", annotations)))
        )
        keys.update(
            {
                str(annotation.id_short): None
                for annotation in annotations
                if annotation.id_short is not None
            }
        )
    return Outcome(new, tuple(losses), (), keys)


# Containers


def _children_of(source: model.SubmodelElement) -> list[_Child]:
    if isinstance(source, model.SubmodelElementList):
        members = cast(
            "Sequence[model.SubmodelElement]",
            as_list(cast("object", source)).value,
        )
        return [
            _Child(member, str(position), None)
            for position, member in enumerate(members)
        ]
    if isinstance(source, model.Operation):
        return [
            _Child(member, str(member.id_short), direction)
            for direction, members in (
                ("input", source.input_variable),
                ("output", source.output_variable),
                ("in-out", source.in_output_variable),
            )
            for member in members
        ]
    if isinstance(source, model.Entity):
        members = cast("Sequence[model.SubmodelElement]", source.statement)
    else:
        collection = cast("model.SubmodelElementCollection", source)
        members = cast("Sequence[model.SubmodelElement]", collection.value)
    return [_Child(member, str(member.id_short), None) for member in members]


def _container_to_container(
    source: model.SubmodelElement, target: ElementType
) -> Outcome:
    common = common_arguments(source)
    children = _children_of(source)
    losses = _container_losses(source, children)
    notes: list[str] = []
    keys: dict[str, str | None] = {}
    if target is model.SubmodelElementList:
        new = _list_element(source, children, common, losses, notes, keys)
        return Outcome(new, tuple(losses), tuple(notes), keys)
    copies = _named_copies(source, children, keys)
    if target is model.SubmodelElementCollection:
        new = model.SubmodelElementCollection(value=copies, **common)
    elif target is model.Entity:
        new = model.Entity(
            entity_type=model.EntityType.CO_MANAGED_ENTITY,
            statement=copies,
            **common,
        )
        notes.append("The entity type is CoManagedEntity.")
    else:
        new = model.Operation(input_variable=copies, **common)
        if copies:
            notes.append("All items are input variables.")
    return Outcome(new, tuple(losses), tuple(notes), keys)


def _container_losses(
    source: model.SubmodelElement, children: list[_Child]
) -> list[Loss]:
    losses: list[Loss] = []
    if isinstance(source, model.Entity):
        if source.entity_type == model.EntityType.SELF_MANAGED_ENTITY:
            losses.append(Loss("entity type", shown(source.entity_type)))
        _lose_unless(losses, "global asset id", source.global_asset_id)
        _lose_unless(
            losses, "specific asset ids", list(source.specific_asset_id)
        )
    if isinstance(source, model.SubmodelElementList):
        _list_settings_losses(as_list(cast("object", source)), children, losses)
    if isinstance(source, model.Operation):
        others = [child for child in children if child.direction != "input"]
        if others:
            losses.append(
                Loss(
                    "direction of the variables",
                    "; ".join(
                        f"{child.element.id_short}: {child.direction}"
                        for child in others
                    ),
                )
            )
    return losses


def _list_settings_losses(
    source: "model.SubmodelElementList[Any]",
    children: list[_Child],
    losses: list[Loss],
) -> None:
    settings = settings_of(source)
    _lose_unless(losses, "semantic id of the items", settings.semantic_id)
    if not settings.order_relevant:
        losses.append(Loss("order is relevant", "no"))
    default = (
        settings.element_type is model.Property
        and settings.value_type is _STRING
    )
    if not children and not default:
        kind = settings.element_type.__name__
        if settings.value_type is not None:
            kind += f" of {value_types.type_name(settings.value_type)}"
        losses.append(Loss("type of the items", kind))


def _named_copies(
    source: model.SubmodelElement,
    children: list[_Child],
    keys: dict[str, str | None],
) -> list[model.SubmodelElement]:
    """Copies the items for a container that names them by idShort."""
    from_list = isinstance(source, model.SubmodelElementList)
    taken: set[str] = set()
    copies: list[model.SubmodelElement] = []
    for position, child in enumerate(children):
        copy = detached_copy(child.element)
        if from_list:
            name = unique_id_short(f"Item_{position}", taken)
            copy.id_short = name
            keys[child.key] = name
        taken.add(str(copy.id_short))
        copies.append(copy)
    return copies


def _list_element(
    source: model.SubmodelElement,
    children: list[_Child],
    common: dict[str, Any],
    losses: list[Loss],
    notes: list[str],
    keys: dict[str, str | None],
) -> model.SubmodelElement:
    elements = [child.element for child in children]
    settings = derive_settings(elements)
    items = [(child.key, detached_copy(child.element)) for child in children]
    named = [
        str(child.element.id_short)
        for child in children
        if not isinstance(source, model.SubmodelElementList)
    ]
    placement = build_list(common, settings, items)
    for key, name, reason in placement.dropped:
        losses.append(Loss("item not kept", f"{name}: {reason}"))
        keys[key] = None
    kept_keys = {key for key, _ in placement.placed}
    for key, position in placement.placed:
        if key != str(position):
            keys[key] = str(position)
    kept_names = [name for name in named if name in kept_keys]
    if kept_names:
        losses.append(
            Loss(
                "idShorts of the items",
                f"{join_names(kept_names)} (the items of a list have none)",
            )
        )
    wanted = settings.normalized()
    kind = wanted.element_type.__name__
    if wanted.value_type is not None:
        kind += f" of {value_types.type_name(wanted.value_type)}"
    notes.append(
        f"The list holds {kind} items. Items of another kind are dropped."
    )
    return placement.new_list


# The rest


def _common_only(source: model.SubmodelElement, target: ElementType) -> Outcome:
    common = common_arguments(source)
    losses = [
        Loss(label, shown(value))
        for label, value in _specifics(source)
        if is_set(value)
    ]
    keys = {child.key: None for child in _children_of_any(source)}
    return Outcome(_empty(target, common), tuple(losses), (), keys)


def _children_of_any(source: model.SubmodelElement) -> list[_Child]:
    if isinstance(source, model.AnnotatedRelationshipElement):
        return [
            _Child(annotation, str(annotation.id_short), None)
            for annotation in source.annotation
        ]
    if type(source) in CONTAINER_TYPES:
        return _children_of(source)
    return []


def _specifics(source: model.SubmodelElement) -> list[tuple[str, object]]:
    """Lists the attributes beyond the shared ones, as label and value."""
    entries: list[tuple[str, object]]
    if isinstance(source, model.Property):
        entries = [("value", source.value), ("value id", source.value_id)]
        entries.append(_type_entry(source.value_type))
    elif isinstance(source, model.Range):
        entries = [("minimum", source.min), ("maximum", source.max)]
        entries.append(_type_entry(source.value_type))
    elif isinstance(source, model.MultiLanguageProperty):
        entries = [("texts", source.value), ("value id", source.value_id)]
    elif isinstance(source, (model.File, model.Blob)):
        label = "path" if isinstance(source, model.File) else "content"
        entries = [(label, source.value), ("content type", source.content_type)]
    elif isinstance(source, model.ReferenceElement):
        entries = [("reference", source.value)]
    elif isinstance(source, model.RelationshipElement):
        entries = [("first", source.first), ("second", source.second)]
        if isinstance(source, model.AnnotatedRelationshipElement):
            entries.append(("annotations", list(source.annotation)))
    elif isinstance(source, model.BasicEventElement):
        entries = [
            ("observed", source.observed),
            ("direction", source.direction),
            ("state", source.state),
            ("message topic", source.message_topic),
            ("message broker", cast("Any", source).message_broker),
            ("last update", source.last_update),
            ("minimum interval", source.min_interval),
            ("maximum interval", source.max_interval),
        ]
    else:
        entries = _container_entries(source)
    return entries


def _type_entry(value_type: XsdType) -> tuple[str, object]:
    # xs:string is what a new Property or Range has, so it is not news.
    return ("value type", None if value_type is _STRING else value_type)


def _container_entries(
    source: model.SubmodelElement,
) -> list[tuple[str, object]]:
    if isinstance(source, model.SubmodelElementCollection):
        return [("items", list(source.value))]
    if isinstance(source, model.SubmodelElementList):
        item_list = as_list(cast("object", source))
        settings = settings_of(item_list)
        return [
            ("items", members_of(item_list.value)),
            ("semantic id of the items", settings.semantic_id),
            ("order is relevant", None if settings.order_relevant else False),
        ]
    if isinstance(source, model.Entity):
        asset = source.entity_type == model.EntityType.SELF_MANAGED_ENTITY
        return [
            ("statements", list(source.statement)),
            ("entity type", source.entity_type if asset else None),
            ("global asset id", source.global_asset_id),
            ("specific asset ids", list(source.specific_asset_id)),
        ]
    if isinstance(source, model.Operation):
        return [
            ("input variables", list(source.input_variable)),
            ("output variables", list(source.output_variable)),
            ("in-output variables", list(source.in_output_variable)),
        ]
    return []


def _empty(
    target: ElementType, common: dict[str, Any]
) -> model.SubmodelElement:
    """Builds an element of a type with the shared attributes and no more."""
    if target is model.Property:
        return model.Property(value_type=_STRING, **common)
    if target is model.Range:
        return model.Range(value_type=_STRING, **common)
    if target is model.SubmodelElementList:
        return build_list(common, derive_settings([]), []).new_list
    if target is model.Entity:
        return model.Entity(
            entity_type=model.EntityType.CO_MANAGED_ENTITY, **common
        )
    return cast("Any", target)(**common)


__all__ = [
    "CONTAINER_TYPES",
    "DEFAULT_LANGUAGE",
    "GENERATED_PREFIX",
    "REFERENCE_TYPES",
    "TARGET_TYPES",
    "VALUE_TYPES",
    "plan_conversion",
    "refusal_for",
    "targets_for",
]
