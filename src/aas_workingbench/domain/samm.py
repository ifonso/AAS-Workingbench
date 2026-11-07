"""Concept descriptions that carry a SAMM element (F-EDT-05 AC18).

The Semantic Aspect Meta Model (SAMM, formerly BAMM) describes data models
with elements such as an Aspect, a Property, or a Characteristic. Package
Explorer stores each element in one concept description, as an `Extension`
whose semantic id is the URN of the element type and whose value is JSON (see
F-SMT-05 of its design documents). This module only *recognizes* such a
description and reads the links between elements. It does not edit them: the
modeling of SAMM is a feature of its own, and the extension stays an ordinary
extension in the editor.

What the editor uses it for:

- a description with a SAMM element lists its identification before its
  referable attributes, and has no hint about missing data specifications,
  because it defines nothing through them (`attribute_order`),
- the "Structured" order of concept descriptions follows the links from the
  Aspects down (`structured_ranks` in `concept_order`).

Recognition follows Package Explorer: the semantic id of the extension is one
external reference whose key is the URN of a known element type, in one of
the three supported versions, 1.0.0 with the prefix `bamm` and 2.0.0 and 2.1.0
with the prefix `samm`. The JSON of the value is read leniently: a value that
is not JSON, or has other fields, has no links, and nothing is raised.

Example:
    Telling a SAMM description from another::

        element = samm_element_of(concept)
        if element is not None:
            print(element.type_name, element.version)
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
import json
import re
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

_URN = re.compile(
    r"urn:(?P<prefix>bamm:io\.openmanufacturing|samm:org\.eclipse\.esmf\.samm)"
    r":(?P<space>meta-model|characteristic):(?P<version>\d+\.\d+\.\d+)"
    r"#(?P<name>[A-Za-z]+)"
)
_VERSIONS = {
    "bamm:io.openmanufacturing": ("1.0.0",),
    "samm:org.eclipse.esmf.samm": ("2.0.0", "2.1.0"),
}

# The element types, by the namespace of their URN (F-SMT-05, section 4).
_META_MODEL = frozenset(
    {"Aspect", "Property", "Entity", "Unit", "Characteristic"}
)
_CONSTRAINTS = frozenset(
    {
        "Constraint",
        "LanguageConstraint",
        "LocaleConstraint",
        "RangeConstraint",
        "EncodingConstraint",
        "LengthConstraint",
        "RegularExpressionConstraint",
        "FixedPointConstraint",
    }
)
_CHARACTERISTICS = frozenset(
    {
        "Trait",
        "Quantifiable",
        "Measurement",
        "Enumeration",
        "State",
        "Duration",
        "Collection",
        "List",
        "Set",
        "SortedSet",
        "TimeSeries",
        "Code",
        "Either",
        "SingleEntity",
        "StructuredValue",
    }
)
_CHARACTERISTIC_SPACE = _CHARACTERISTICS | _CONSTRAINTS

# What each kind of element points at, as the keys of its JSON (F-SMT-05,
# "Graph rules"). Each key holds a reference `{"Value": id}` or a list of
# them. A characteristic that is no trait points at its data type.
_LINK_FIELDS: dict[str, tuple[str, ...]] = {
    "Aspect": ("Properties",),
    "Property": ("Characteristic",),
    "Entity": ("Properties",),
    "Trait": ("BaseCharacteristic", "Constraint"),
}
_NO_LINKS = frozenset({"Unit"}) | _CONSTRAINTS


@dataclass(frozen=True, eq=False)
class SammElement:
    """The SAMM element that a concept description carries.

    Attributes:
        type_name: The type, such as `Aspect`, `Property` or `Trait`.
        version: The SAMM version of the URN, such as `2.1.0`.
        extension: The extension that holds the element.
    """

    type_name: str
    version: str
    extension: model.Extension


def _element_of(extension: model.Extension) -> SammElement | None:
    reference = extension.semantic_id
    if reference is None or len(reference.key) != 1:
        return None
    match = _URN.fullmatch(reference.key[0].value)
    if match is None:
        return None
    name, version = match["name"], match["version"]
    if version not in _VERSIONS[match["prefix"]]:
        return None
    known = (
        _META_MODEL if match["space"] == "meta-model" else _CHARACTERISTIC_SPACE
    )
    if name not in known:
        return None
    return SammElement(name, version, extension)


def samm_elements_of(concept: ConceptDescription) -> tuple[SammElement, ...]:
    """Lists the SAMM elements in the extensions of a description.

    Args:
        concept: The concept description.

    Returns:
        One element for each extension whose semantic id is the URN of a known
        element type, in the order of the extensions.
    """
    found = (_element_of(extension) for extension in concept.extension)
    return tuple(element for element in found if element is not None)


def samm_element_of(concept: ConceptDescription) -> SammElement | None:
    """Returns the first SAMM element of a description, or None."""
    elements = samm_elements_of(concept)
    return elements[0] if elements else None


def is_samm(obj: object) -> bool:
    """Tells whether an object is a concept description with a SAMM element."""
    return isinstance(obj, ConceptDescription) and bool(samm_elements_of(obj))


def _values(node: Any) -> list[str]:
    """Collects the `Value` of a reference or of a list of references."""
    if isinstance(node, dict):
        value = cast("dict[str, Any]", node).get("Value")
        return [value] if isinstance(value, str) and value else []
    if isinstance(node, list):
        return [v for item in cast("list[Any]", node) for v in _values(item)]
    return []


def samm_links(element: SammElement) -> tuple[str, ...]:
    """Lists the ids that an element points at, in the order of its JSON.

    Args:
        element: What `samm_element_of` found.

    Returns:
        The ids of the properties of an Aspect or Entity, the characteristic
        of a Property, the base characteristic and constraints of a Trait, and
        the data type of any other characteristic. A unit or a constraint
        points at nothing. A value that is not JSON gives no links.
    """
    if element.type_name in _NO_LINKS:
        return ()
    value = element.extension.value
    if not isinstance(value, str) or not value.strip():
        return ()
    try:
        data = json.loads(value)
    except ValueError:
        return ()
    if not isinstance(data, dict):
        return ()
    fields = _LINK_FIELDS.get(element.type_name, ("DataType",))
    found: list[str] = []
    for name in fields:
        found.extend(_values(cast("dict[str, Any]", data).get(name)))
    return tuple(found)


# The attributes that a SAMM description lists first (F-EDT-05 section 3.2).
_IDENTIFIABLE_FIRST = ("id", "administration")


def attribute_order(obj: object, attributes: Sequence[str]) -> list[str]:
    """Orders the attributes that a tab shows for an object.

    A concept description with a SAMM element lists the Identifiable attributes
    (`id`, `administration`) before the Referable ones, as Package Explorer
    does. Every other object keeps the order it was given.

    Args:
        obj: The object that the tab shows.
        attributes: The attributes in their usual order.

    Returns:
        The attributes in the order to show.
    """
    if not is_samm(obj):
        return list(attributes)
    first = [name for name in _IDENTIFIABLE_FIRST if name in attributes]
    return [*first, *(name for name in attributes if name not in first)]


def referenced_ids(
    concepts: Iterable[ConceptDescription],
) -> dict[str, tuple[str, ...]]:
    """Maps the id of each SAMM description to the ids its element points at."""
    links: dict[str, tuple[str, ...]] = {}
    for concept in concepts:
        element = samm_element_of(concept)
        if element is not None:
            links[concept.id] = samm_links(element)
    return links
