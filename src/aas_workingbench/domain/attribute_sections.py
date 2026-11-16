"""The sections that the attributes of an object are read in.

A tab listed every attribute of an object in the order of the SDK, each with
the same weight, and four of them were usually empty. The detail now reads in
sections, in this order (proposal 3.2 of `design/ui-proposals.md`):

* Value: what the object holds, such as the value and the value type of a
  Property, which is what a person reads first.
* Identification: the names of the object, such as idShort, displayName and
  description.
* Semantics: what the object means, such as its semanticId.
* Advanced: what few people read, such as qualifiers and extensions.

In Read mode the attributes that hold nothing leave their sections for one more
section, Empty attributes, which starts closed (proposal 3.3). In Edit mode they
stay where they are, because that is where they are filled in.

The table is keyed by the name of a class and looked up along the base classes
of the object, as the vocabulary of `attribute_vocabulary` is, and a test fails
for an attribute of the vocabulary without a section.
"""

from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Sized
from enum import StrEnum
from typing import Final


class Section(StrEnum):
    """A section of the detail of an object."""

    VALUE = "value"
    IDENTIFICATION = "identification"
    SEMANTICS = "semantics"
    ADVANCED = "advanced"
    EMPTY = "empty"


SECTION_ORDER: Final = (
    Section.VALUE,
    Section.IDENTIFICATION,
    Section.SEMANTICS,
    Section.ADVANCED,
    Section.EMPTY,
)
"""The order of the sections, from what is read first."""

SECTION_TITLES: Final = {
    Section.VALUE: "Value",
    Section.IDENTIFICATION: "Identification",
    Section.SEMANTICS: "Semantics",
    Section.ADVANCED: "Advanced",
    Section.EMPTY: "Empty attributes",
}
"""What the header of each section reads."""

CLOSED_AT_FIRST: Final = frozenset({Section.ADVANCED, Section.EMPTY})
"""The sections that can start closed: they name their attributes in the
header, and a click opens them (see `starts_open`)."""

LIST_INDEX_NAME: Final = "index"
"""The name of the row with the position of an item in its list, which the
editor adds and the SDK does not have."""

_V = Section.VALUE
_I = Section.IDENTIFICATION
_S = Section.SEMANTICS
_A = Section.ADVANCED

_SECTIONS: Final[dict[str, dict[str, Section]]] = {
    "Referable": {
        "id_short": _I,
        "category": _I,
        "display_name": _I,
        "description": _I,
    },
    "HasExtension": {"extension": _A},
    "Identifiable": {"id": _I, "administration": _I},
    "HasSemantics": {"semantic_id": _S, "supplemental_semantic_id": _S},
    "Qualifiable": {"qualifier": _A},
    "HasDataSpecification": {"embedded_data_specifications": _A},
    "HasKind": {"kind": _I},
    "AdministrativeInformation": {
        "version": _V,
        "revision": _V,
        "creator": _V,
        "template_id": _V,
    },
    "Extension": {
        "name": _I,
        "value_type": _V,
        "value": _V,
        "refers_to": _S,
    },
    "Qualifier": {
        "kind": _I,
        "type": _I,
        "value_type": _V,
        "value": _V,
        "value_id": _V,
    },
    "Reference": {"key": _V, "referred_semantic_id": _S},
    "ModelReference": {"type": _V},
    "Key": {"type": _V, "value": _V},
    "EmbeddedDataSpecification": {
        "data_specification": _V,
        "data_specification_content": _V,
    },
    "AssetAdministrationShell": {
        "derived_from": _S,
        "asset_information": _V,
        "submodel": _V,
    },
    "AssetInformation": {
        "asset_kind": _V,
        "global_asset_id": _V,
        "specific_asset_id": _V,
        "asset_type": _V,
        "default_thumbnail": _V,
    },
    "Resource": {"path": _V, "content_type": _V},
    "SpecificAssetId": {
        "name": _V,
        "value": _V,
        "external_subject_id": _S,
    },
    "Submodel": {"submodel_element": _V},
    "Property": {"value_type": _V, "value": _V, "value_id": _V},
    "MultiLanguageProperty": {"value": _V, "value_id": _V},
    "Range": {"value_type": _V, "min": _V, "max": _V},
    "Blob": {"value": _V, "content_type": _V},
    "File": {"value": _V, "content_type": _V},
    "ReferenceElement": {"value": _V},
    "RelationshipElement": {"first": _V, "second": _V},
    "AnnotatedRelationshipElement": {"annotation": _V},
    "SubmodelElementCollection": {"value": _V},
    "SubmodelElementList": {
        "order_relevant": _V,
        "value": _V,
        "semantic_id_list_element": _V,
        "type_value_list_element": _V,
        "value_type_list_element": _V,
    },
    "Entity": {
        "statement": _V,
        "entity_type": _V,
        "global_asset_id": _V,
        "specific_asset_id": _V,
    },
    "Operation": {
        "input_variable": _V,
        "output_variable": _V,
        "in_output_variable": _V,
    },
    "BasicEventElement": {
        "observed": _V,
        "direction": _V,
        "state": _V,
        "message_topic": _V,
        "message_broker": _V,
        "last_update": _V,
        "min_interval": _V,
        "max_interval": _V,
    },
    "ConceptDescription": {"is_case_of": _S},
    "DataSpecificationIEC61360": {
        "preferred_name": _V,
        "short_name": _V,
        "unit": _V,
        "unit_id": _V,
        "source_of_definition": _V,
        "symbol": _V,
        "data_type": _V,
        "definition": _V,
        "value_format": _V,
        "value_list": _V,
        "value": _V,
        "level_types": _V,
    },
    "ValueReferencePair": {"value": _V, "value_id": _V},
    "DictItem": {"key": _V, "value": _V},
    "Package": {
        "name": _V,
        "file": _V,
        "changed": _V,
        "partial": _V,
        "numOfShells": _V,
        "numOfSubmodels": _V,
        "numOfConceptDescriptions": _V,
        "files": _V,
        "missingFiles": _V,
        "thumbnail": _V,
        "coreProperties": _V,
    },
    "StoredFile": {"name": _V, "mime_type": _V, "value": _V},
}


def starts_open(section: Section, *, has_content: bool) -> bool:
    """Tells whether a section shows its rows before the user opens it.

    Empty attributes start closed. Advanced starts closed while it holds
    nothing, as qualifiers and extensions usually do, and open when one of its
    attributes has content, which a reader should not miss. The others start
    open.

    Args:
        section: The section.
        has_content: Whether one of its attributes holds something.
    """
    if section is Section.EMPTY:
        return False
    if section is Section.ADVANCED:
        return has_content
    return True


def section_classes() -> tuple[str, ...]:
    """Lists the names of the classes that the table has sections for."""
    return tuple(_SECTIONS)


def section_of(owner: type, sdk_name: str) -> Section | None:
    """Finds the section of an attribute.

    Args:
        owner: The class of the object that has the attribute. The table is
            read along its base classes, so `Property` finds the sections of
            `Referable` too.
        sdk_name: The name of the attribute in the SDK, such as `value_type`.

    Returns:
        Its section, or None for an attribute that the table does not know,
        such as an entry of a list.
    """
    if sdk_name == LIST_INDEX_NAME:
        return Section.IDENTIFICATION
    for cls in owner.__mro__:
        sections = _SECTIONS.get(cls.__name__)
        if sections is not None and sdk_name in sections:
            return sections[sdk_name]
    return None


def holds_nothing(value: object) -> bool:
    """Tells whether an attribute is empty: not set, or an empty list or text.

    Args:
        value: The value of the attribute.

    Returns:
        True for None, an empty string, and an empty collection. A number or
        a bool is never empty, so a 0 and a False are read.
    """
    if value is None:
        return True
    if isinstance(value, (bool, int, float)):
        return False
    if isinstance(value, Sized):
        try:
            return len(value) == 0
        except TypeError:
            return False
    return False


def place_of(
    owner: type, sdk_name: str, *, is_empty: bool, editing: bool
) -> Section | None:
    """Finds where an attribute is shown.

    Args:
        owner: The class of the object that has the attribute.
        sdk_name: The name of the attribute in the SDK.
        is_empty: Whether it holds nothing (see `holds_nothing`).
        editing: Whether the editor is in Edit mode.

    Returns:
        Its section, `Section.EMPTY` for an empty attribute in Read mode, or
        None for an attribute that the table does not know.
    """
    section = section_of(owner, sdk_name)
    if section is None:
        return None
    if is_empty and not editing:
        return Section.EMPTY
    return section


def rank(section: Section | None) -> int:
    """Gives the place of a section in the order, and the end for None."""
    if section is None:
        return len(SECTION_ORDER)
    return SECTION_ORDER.index(section)


def in_reading_order(
    owner: type,
    sdk_names: Iterable[str],
    empty: Collection[str],
    *,
    editing: bool,
) -> list[str]:
    """Puts the attributes of an object in the order of their sections.

    Inside a section the attributes keep the order that was given, so the
    order of the SDK, or of a concept description with a SAMM element, stays.
    Only the description follows the display name, as a person reads a name
    before what it means (`idShort`, `displayName`, `description`).

    Args:
        owner: The class of the object.
        sdk_names: Its attributes, in the order they would be shown.
        empty: The attributes that hold nothing.
        editing: Whether the editor is in Edit mode.

    Returns:
        The same names, in sections.
    """
    names = list(sdk_names)
    ordered = sorted(
        names,
        key=lambda name: rank(
            place_of(owner, name, is_empty=name in empty, editing=editing)
        ),
    )
    return _description_after_display_name(ordered)


def _description_after_display_name(names: list[str]) -> list[str]:
    """Moves the description right after the display name, when both are in
    the same place and the description came first."""
    if "description" not in names or "display_name" not in names:
        return names
    first, second = names.index("description"), names.index("display_name")
    if first > second:
        return names
    moved = [name for name in names if name != "description"]
    moved.insert(moved.index("display_name") + 1, "description")
    return moved


def header_text(
    section: Section, names: list[str], *, is_open: bool
) -> tuple[str, str, str]:
    """Gives what the header of a section reads.

    Args:
        section: The section.
        names: The names of its attributes, as the metamodel says them.
        is_open: Whether the section shows its rows.

    Returns:
        The title, the count, and the names of a closed section that starts
        closed, which tell what a click opens, such as `qualifier, extension`.
        The names are empty for a section that is open or usually open.
    """
    listed = ""
    if not is_open and section in CLOSED_AT_FIRST:
        listed = ", ".join(names)
    return SECTION_TITLES[section], str(len(names)), listed
