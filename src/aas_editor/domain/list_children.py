"""What a new child of a SubmodelElementList gets from the list.

A SubmodelElementList fixes the type of its children (`type_value_list_element`)
and may fix their semantic id (`semantic_id_list_element`) and, for a Property
or a Range, their value type (`value_type_list_element`). The SDK refuses any
other child: AASd-107, 108, 109, and 114. These attributes cannot change after
the list is made, so a new child has only one type it can have, and starts with
what the list says.
"""

from dataclasses import dataclass
import typing
from typing import Any

from basyx.aas import model

from aas_editor.domain.value_types import XsdType


@dataclass(frozen=True)
class ListChildDefaults:
    """What a new child of a list starts with.

    Attributes:
        element_type: The only class a child may have.
        value_type: The value type of a Property or Range child, fixed by the
            list. None if the list does not fix one.
        semantic_id: The semantic id that every child must have (AASd-107).
            None if the list fixes none.
        template: A blank element of `element_type` that has the semantic id
            and the value type, to fill a form from. None if the class cannot
            be made without values, like a BasicEventElement.
    """

    element_type: type[model.SubmodelElement]
    value_type: XsdType | None
    semantic_id: model.Reference | None
    template: model.SubmodelElement | None


def child_defaults(
    submodel_list: "model.SubmodelElementList[Any]",
) -> ListChildDefaults:
    """Returns what a new child of the list starts with.

    Args:
        submodel_list: The list to add a child to.

    Returns:
        The type, the value type, the semantic id, and a blank element that
        carries them.
    """
    element_type = typing.cast(
        "type[model.SubmodelElement]",
        submodel_list.type_value_list_element,  # pyright: ignore[reportUnknownMemberType]
    )
    value_type = submodel_list.value_type_list_element
    semantic_id = submodel_list.semantic_id_list_element
    template = _blank(element_type, value_type)
    if template is not None:
        template.semantic_id = semantic_id
    return ListChildDefaults(element_type, value_type, semantic_id, template)


def _blank(
    element_type: type[model.SubmodelElement], value_type: XsdType | None
) -> model.SubmodelElement | None:
    try:
        if element_type is model.Property and value_type is not None:
            return model.Property(None, value_type)
        if element_type is model.Range and value_type is not None:
            return model.Range(None, value_type)
        if element_type is model.Entity:
            return model.Entity(None, None)
        return element_type(None)  # pyright: ignore[reportCallIssue]
    except (TypeError, ValueError):
        return None
