"""What the package tree calls its nodes and the types of its rows.

The tree of a package has rows that are objects (a submodel, a property) and
rows that only group objects: the shells, submodels, concept descriptions and
files of a package, and the variables of an operation. The editor finds those
rows by the name of the attribute of the SDK (`concept_descriptions`,
`input_variable`), and that name does not change. This module gives the text
that a person reads instead: the words of the AAS.

It only builds text. It does not know Qt, and nothing that edits reads it.

Example:
    >>> from basyx.aas import model
    >>> node_name(model.Operation, "input_variable")
    'inputVariable'
    >>> type_name("Property", is_node=False)
    'Property'
"""

from aas_editor.domain.attribute_vocabulary import attribute_info

_PACKAGE = "Package"

_PACKAGE_NODES: dict[str, tuple[str, str]] = {
    "shells": (
        "Asset Administration Shells",
        "The Asset Administration Shells of the package.",
    ),
    "submodels": ("Submodels", "The submodels of the package."),
    "concept_descriptions": (
        "Concept Descriptions",
        "The concept descriptions of the package, which define what the "
        "semantic ids of the elements refer to.",
    ),
    "fileStore": (
        "Files",
        "The files that the package stores, such as thumbnails, documents "
        "and the content of File elements.",
    ),
}

_EDITOR_TYPES = {"StoredFile": "SupplementaryFile"}
"""The classes of the editor that the AAS has a word for."""


def node_name(owner: type, attribute: str) -> str:
    """Returns what the tree reads for a row that groups objects.

    Args:
        owner: The class of the object that has the attribute, such as the
            package or an operation.
        attribute: The name of the attribute in the SDK.

    Returns:
        The name of the group in the words of the AAS: `Submodels` for the
        submodels of a package, `inputVariable` for the input variables of an
        operation. The attribute itself if nothing names it.
    """
    if _is_package(owner) and attribute in _PACKAGE_NODES:
        return _PACKAGE_NODES[attribute][0]
    info = attribute_info(owner, attribute)
    return attribute if info is None else info.name


def node_description(owner: type, attribute: str) -> str:
    """Returns a sentence about what a row that groups objects holds.

    Args:
        owner: The class of the object that has the attribute.
        attribute: The name of the attribute in the SDK.

    Returns:
        The sentence, or an empty text if there is none.
    """
    if _is_package(owner) and attribute in _PACKAGE_NODES:
        return _PACKAGE_NODES[attribute][1]
    info = attribute_info(owner, attribute)
    return "" if info is None else info.description


def type_name(class_name: str, *, is_node: bool) -> str:
    """Returns what the type column of the tree reads.

    Args:
        class_name: The name of the class of the object of the row.
        is_node: Whether the row only groups objects. Such a row is not an
            object of the AAS, so it has no type.

    Returns:
        The name of the class in the metamodel, which is the name of the
        class in the SDK, an empty text for a row that groups objects, and a
        word of the AAS for a class that only the editor has.
    """
    if is_node:
        return ""
    return _EDITOR_TYPES.get(class_name, class_name)


def _is_package(owner: type) -> bool:
    return any(cls.__name__ == _PACKAGE for cls in owner.__mro__)
