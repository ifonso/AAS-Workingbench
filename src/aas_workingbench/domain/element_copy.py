"""Copies of elements and their parts, and how to name them for the user.

`copy.deepcopy` of an element copies everything it can reach, and an element
reaches its parent, so it copies the whole submodel. `detached_copy` stops at
the parent. The copy has no parent and shares nothing with the original.
"""

import copy
from collections.abc import Iterable
from collections.abc import Sized
from enum import Enum
from typing import Any
from typing import TypeVar
from typing import cast

from basyx.aas import model

from aas_workingbench.domain import blob_content
from aas_workingbench.domain import value_types
from aas_workingbench.domain.references import describe_reference

_T = TypeVar("_T")

# The first part of the idShort the SDK gives to an item of a list.
GENERATED_PREFIX = "generated_submodel_list_hack_"

_MAX_SHOWN = 60
_MAX_NAMES = 8


def detached_copy(obj: _T) -> _T:
    """Copies an element, or a part of it, without its parent.

    Args:
        obj: An element, qualifier, or extension.

    Returns:
        A deep copy whose `parent` is None. Everything below it is copied.
    """
    parent = getattr(obj, "parent", None)
    memo: dict[int, Any] = {}
    if parent is not None:
        memo[id(parent)] = None
    return copy.deepcopy(obj, memo)


def common_arguments(
    element: model.SubmodelElement, keep_id_short: bool = True
) -> dict[str, Any]:
    """Collects the attributes that every element type has, as copies.

    Args:
        element: The element to take the attributes from.
        keep_id_short: Whether to give the idShort. An item of a list has
            none, so the new element of a list item is made without it.

    Returns:
        The keyword arguments for the constructor of any element class:
        `id_short`, `display_name`, `category`, `description`, `semantic_id`,
        `supplemental_semantic_id`, `qualifier`, `extension`, and
        `embedded_data_specifications`.
    """
    display_name = element.display_name
    description = element.description
    return {
        "id_short": element.id_short if keep_id_short else None,
        "display_name": None
        if display_name is None
        else model.MultiLanguageNameType(dict(display_name)),
        "category": element.category,
        "description": None
        if description is None
        else model.MultiLanguageTextType(dict(description)),
        "semantic_id": element.semantic_id,
        "supplemental_semantic_id": list(element.supplemental_semantic_id),
        "qualifier": [detached_copy(item) for item in element.qualifier],
        "extension": [detached_copy(item) for item in element.extension],
        "embedded_data_specifications": [
            copy.deepcopy(item) for item in element.embedded_data_specifications
        ],
    }


def is_set(value: object) -> bool:
    """Tells whether an attribute holds something worth reporting.

    Args:
        value: An attribute value.

    Returns:
        False for None and for an empty container, text, or bytes. An empty
        text counts as set, because it differs from no text.
    """
    if value is None:
        return False
    if isinstance(value, (str, bytes)):
        return True
    if isinstance(value, (list, set, tuple, dict, model.NamespaceSet)):
        return len(cast("Sized", value)) > 0
    return True


def shorten(text: str, limit: int = _MAX_SHOWN) -> str:
    """Cuts text to a length, and marks the cut."""
    return text if len(text) <= limit else text[: limit - 3] + "..."


def shown(value: object) -> str:
    """Writes a value for a message to the user.

    Args:
        value: An attribute value of an element.

    Returns:
        Text values in quotes, bytes as text when they are text and as a size
        otherwise, references by their keys, language texts by language, and
        containers by the names of their items.
    """
    if isinstance(value, bytes):
        decoded = blob_content.as_text(value)
        if decoded is None:
            return f"{len(value)} bytes"
        return f"'{shorten(decoded.text)}'"
    if isinstance(value, str):
        return f"'{shorten(value)}'"
    if isinstance(value, model.Reference):
        return describe_reference(value)
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, type):
        return _type_text(cast("type[Any]", value))
    if isinstance(value, model.LangStringSet):
        pairs = dict(value)
        return "; ".join(
            f"{language}: '{shorten(text)}'" for language, text in pairs.items()
        )
    if isinstance(value, (model.NamespaceSet, list, set, tuple)):
        return names_of(members_of(cast("object", value)))
    if isinstance(value, bool):
        return "yes" if value else "no"
    return shorten(str(value))


def members_of(container: object) -> list[Any]:
    """Returns the members of a set, list, or tuple as a new list."""
    return list(cast("Iterable[Any]", container))


def as_list(element: object) -> "model.SubmodelElementList[Any]":
    """Types an element that is known to be a list, for the checker."""
    return cast("model.SubmodelElementList[Any]", element)


def names_of(items: list[Any]) -> str:
    """Lists the names of some objects, and how many more there are."""
    return join_names([item_name(item) for item in items])


def join_names(names: list[str]) -> str:
    """Joins names with commas, and says how many more than a few there are."""
    shown_names = names[:_MAX_NAMES]
    more = len(names) - len(shown_names)
    text = ", ".join(shown_names)
    return f"{text} and {more} more" if more > 0 else text


def item_name(item: object) -> str:
    """Names an element or part for the user: its idShort or its class."""
    id_short = getattr(item, "id_short", None)
    if isinstance(id_short, str) and not id_short.startswith(GENERATED_PREFIX):
        return id_short
    name = getattr(item, "name", None)
    if isinstance(name, str):
        return name
    return type(item).__name__


def _type_text(value_type: type[Any]) -> str:
    try:
        return value_types.type_name(value_type)
    except value_types.InvalidValueError:
        return value_type.__name__
