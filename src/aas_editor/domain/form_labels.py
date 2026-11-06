"""What a generated form calls its fields.

A form is made from the constructor of a class of the SDK, so its fields come
with the names of Python: `value_type`, `semantic_id`, `type_`. A person who
knows the AAS looks for `valueType` and `semanticId`, as the tabs show them
(ADR 0022, ADR 0026). This module reads those words from the vocabulary of the
attributes.

It only builds text. It does not know Qt, and nothing that makes an object
reads it: the form finds and fills a field by the name of the parameter of the
SDK, which does not change.

Example:
    >>> from basyx.aas import model
    >>> label = field_label(model.Qualifier, "value_type", "value_type", True)
    >>> label.text
    'valueType*'
"""

from dataclasses import dataclass

from aas_editor.domain.attribute_vocabulary import attribute_info

REQUIRED_MARK = "*"
"""The mark behind the name of a field that the class cannot do without."""


@dataclass(frozen=True)
class FieldLabel:
    """The words next to one field of a form.

    Attributes:
        text: The name of the field, with a mark if it is required.
        name: The name of the field without the mark.
        tooltip: A short description of the attribute, or an empty text if the
            vocabulary has none.
    """

    text: str
    name: str
    tooltip: str


def field_label(
    owner: object, param: str, attribute: str, required: bool
) -> FieldLabel:
    """Returns the words for the field of a parameter of a constructor.

    Args:
        owner: The class that the form makes. Something that is not a class
            has no entries, and the field keeps the name of the parameter.
        param: The name of the parameter in the SDK, such as `type_`.
        attribute: The name of the attribute that holds the parameter in the
            object, such as `type`. The same as `param` if it is not known.
        required: Whether the class needs the parameter.

    Returns:
        The label. The parameter without its trailing underscore stands for
        a name the vocabulary does not have.
    """
    plain = param.strip("_")
    info = None
    if isinstance(owner, type):
        info = attribute_info(owner, attribute) or attribute_info(owner, plain)
    name = plain if info is None else info.name
    text = f"{name}{REQUIRED_MARK}" if required else name
    return FieldLabel(text, name, "" if info is None else info.description)
