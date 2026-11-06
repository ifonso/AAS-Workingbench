"""Values that follow a value type: of a Property, a Range, and more.

A Property has a `value_type` and a `value` of that type. So do a Range, with a
`min` and a `max`, a Qualifier, and an Extension. The BaSyx classes cast a
value when it is set, but only trivially: text is not parsed, and changing the
`value_type` leaves the value as it was, in the old type. This module makes
the rules of editing such an attribute:

* Text becomes a value of the type, or is refused with a message.
* A Range keeps its minimum at or below its maximum.
* Changing the type converts the values through their text. When one of them
  does not fit the new type, the change is refused and nothing changes.
* A Property in a SubmodelElementList keeps the value type of the list (AASd-109).
"""

from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.domain import value_types
from aas_editor.domain.value_types import InvalidValueError
from aas_editor.domain.value_types import XsdType

# The attributes that hold a value, by the class of their owner.
_VALUE_ATTRS: tuple[tuple[type, tuple[str, ...]], ...] = (
    (model.Property, ("value",)),
    (model.Range, ("min", "max")),
    (model.Qualifier, ("value",)),
    (model.Extension, ("value",)),
)
# The attributes that name the type of a value.
_TYPE_ATTRS = ("value_type",)


def value_attrs(owner: object) -> tuple[str, ...]:
    """Returns the names of the attributes of an object that hold values.

    Args:
        owner: Any object.

    Returns:
        `("value",)` for a Property, a Qualifier, and an Extension, `("min",
        "max")` for a Range, and an empty tuple for any other object.
    """
    for owner_type, names in _VALUE_ATTRS:
        if isinstance(owner, owner_type):
            return names
    return ()


def is_value_attr(owner: object, name: str) -> bool:
    """Tells whether an attribute holds a value that follows `value_type`."""
    return name in value_attrs(owner)


def is_value_type_attr(owner: object, name: str) -> bool:
    """Tells whether an attribute names the value type of the owner's values."""
    return bool(value_attrs(owner)) and name in _TYPE_ATTRS


def value_type_of(owner: object) -> XsdType | None:
    """Returns the type that the values of the owner follow, if it has one."""
    if not value_attrs(owner):
        return None
    return cast("XsdType | None", getattr(owner, "value_type", None))


def prepare_edit(owner: object, name: str, value: object) -> Any:
    """Makes the value for an edit of a typed attribute, or refuses it.

    Args:
        owner: A Property, Range, Qualifier, or Extension.
        name: The attribute to set, one of `value_attrs(owner)`.
        value: Text to parse, a value of the type, or None to clear.

    Returns:
        What to assign. Text for a type other than `xs:string` that is empty
        gives None, so that clearing the field clears the value.

    Raises:
        InvalidValueError: If the value does not fit the type, or a Range
            would get a minimum above its maximum.
    """
    value_type = value_type_of(owner)
    typed = _coerce(value, value_type)
    if isinstance(owner, model.Range) and name in ("min", "max"):
        low = typed if name == "min" else owner.min
        high = typed if name == "max" else owner.max
        problem = value_types.check_range(low, high, owner.value_type)
        if problem:
            raise InvalidValueError(problem)
    return typed


def check_new_object(obj: object) -> None:
    """Refuses a freshly made object whose values contradict each other.

    Args:
        obj: An object that a dialog made, like a Range.

    Raises:
        InvalidValueError: If a Range has a minimum above its maximum.
    """
    if isinstance(obj, model.Range):
        problem = value_types.check_range(obj.min, obj.max, obj.value_type)
        if problem:
            raise InvalidValueError(problem)


def type_change_values(
    owner: object, new_type: XsdType | None
) -> dict[str, Any]:
    """Plans what changing the value type does to the values of the owner.

    Args:
        owner: A Property, Range, Qualifier, or Extension.
        new_type: The value type to change to. Only an Extension may have
            none, and only without a value.

    Returns:
        The new value of each attribute that has a value, converted through
        its text. Attributes without a value are not in the result.

    Raises:
        InvalidValueError: If a value does not fit the new type, or if the
            owner is a Property or Range in a list that fixes the value type.
            Nothing has changed in this case.
    """
    if new_type is None:
        if any(getattr(owner, name) is not None for name in value_attrs(owner)):
            raise InvalidValueError(
                "The value type cannot be removed while there is a value. "
                "Clear the value first"
            )
        return {}
    value_types.type_name(new_type)
    _check_list_fixes_type(owner, new_type)
    converted: dict[str, Any] = {}
    for name in value_attrs(owner):
        current = getattr(owner, name)
        if current is None:
            continue
        try:
            converted[name] = value_types.convert(current, new_type)
        except InvalidValueError as error:
            raise InvalidValueError(
                f"The value type cannot change to "
                f"{value_types.type_name(new_type)}: "
                f"the {name} {error}. Clear or change the {name} first"
            ) from None
    if isinstance(owner, model.Range):
        problem = value_types.check_range(
            converted.get("min"), converted.get("max"), new_type
        )
        if problem:
            raise InvalidValueError(problem)
    return converted


def _check_list_fixes_type(owner: object, new_type: XsdType) -> None:
    parent = getattr(owner, "parent", None)
    if not isinstance(parent, model.SubmodelElementList):
        return
    fixed = parent.value_type_list_element
    if fixed is not None and fixed is not new_type:
        raise InvalidValueError(
            f"The value type cannot change to "
            f"{value_types.type_name(new_type)}: the list "
            f"'{parent.id_short}' needs {value_types.type_name(fixed)} for "
            "all items (AASd-109)"
        )


def _coerce(value: object, value_type: XsdType | None) -> Any:
    if value is None:
        return None
    if value_type is None:
        raise InvalidValueError("Choose a value type before giving a value")
    if isinstance(value, str) and not isinstance(value, value_type):
        if not value and not value_types.keeps_whitespace(value_type):
            return None
        return value_types.parse(value, value_type)
    return value_types.cast_value(value, value_type)
