"""What the tabs call a value, a null attribute, and the entries of a list.

The attribute vocabulary names the attributes (`attribute_vocabulary`). This
module names the rest of what a row shows, in words of the AAS and not of
Python:

* the type of a value, such as `xs:double` for a float and `list` for a
  `NamespaceSet`,
* what a null attribute reads, so that it is not `None` or `NoneType`,
* the name of an entry of a list: the idShort of an element, the language of
  a text, the type of a qualifier, and the position of anything else.

It only builds text. What the editor edits, and by which name, does not
depend on it.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sized
from enum import Enum
import inspect

from basyx.aas import model
from basyx.aas.model import datatypes

from aas_editor.additional.classes import DictItem
from aas_editor.domain.attribute_vocabulary import AttributeInfo
from aas_editor.domain.attribute_vocabulary import VALUE_DATA_TYPE

NOT_SET = "(not set)"
"""What an attribute without a value reads."""

EMPTY = "(empty)"
"""What a list, a set, or a mapping without entries reads."""

LIST_TYPE = "list"
"""The type of a container whose entries are the rows below it."""

_XSD_NAMES: Mapping[type, str] = datatypes.XSD_TYPE_NAMES
_LANG_STRING = "LangString"
_NO_LANGUAGE = "(no language)"
_GENERATED_ID_SHORT_PREFIX = "generated_submodel_list_hack_"


def value_type_name(value: object) -> str:
    """Returns the AAS name of the type of a value.

    Args:
        value: Anything that a row can show.

    Returns:
        `xs:double`, `xs:string` and so on for a value of an XSD type, the
        name of the class for an AAS object or an enumeration, `LangString`
        for a text of a language, `list` for a container, and `not set` for
        None.
    """
    if value is None:
        return "not set"
    if isinstance(value, DictItem):
        return _LANG_STRING
    if isinstance(value, bytes):
        return "xs:base64Binary"
    xsd_name = _XSD_NAMES.get(type(value))
    if xsd_name is not None:
        return xsd_name
    if isinstance(value, Enum):
        return type(value).__name__
    if inspect.isclass(value):
        return "type"
    if _is_container(value):
        return LIST_TYPE
    return type(value).__name__


def _is_container(value: object) -> bool:
    return isinstance(value, Iterable) and not isinstance(
        value, (str, bytes, Mapping, model.LangStringSet)
    )


def type_column_text(info: AttributeInfo | None, value: object) -> str:
    """Returns what the type column of a row reads.

    The type of an attribute is the one that the metamodel declares. Only a
    value that follows the value type of its owner is named by the value
    itself, and a reference by the kind of reference it is. An attribute
    without an entry, such as an entry of a list, is named by its value.

    Args:
        info: The vocabulary entry of the attribute, if it has one.
        value: The value of the attribute.

    Returns:
        The text of the cell, which is never a Python type.
    """
    if info is None:
        return value_type_name(value)
    if value is None:
        return info.type_name
    if info.type_name == VALUE_DATA_TYPE:
        return value_type_name(value)
    if isinstance(value, model.Reference) and info.type_name.endswith(
        "Reference"
    ):
        return type(value).__name__
    return info.type_name


def value_text(value: object) -> str | None:
    """Returns the text for a value that Python would show badly.

    Args:
        value: The value of a row.

    Returns:
        `(not set)` for None, `(empty)` for a container without entries, the
        name of the XSD type for a value type, and None for any other value,
        which is shown as it always was.
    """
    if value is None:
        return NOT_SET
    if inspect.isclass(value) and value in _XSD_NAMES:
        return _XSD_NAMES[value]
    if _is_empty(value):
        return EMPTY
    return None


def _is_empty(value: object) -> bool:
    # Only what knows its size is asked: iterating a generator would use it up.
    return (
        isinstance(value, Sized)
        and not isinstance(value, (str, bytes))
        and len(value) == 0
    )


def entry_label(entry: object, position: int) -> str:
    """Returns the name of an entry of a list, a set, or a mapping.

    Args:
        entry: The entry.
        position: Its place in the list, counted from 0.

    Returns:
        The key that tells the entry apart, if it has one: the language of a
        text, the idShort of an element, the type of a qualifier, or the name
        of an extension or a specific asset id. Otherwise its position, in
        brackets.
    """
    key = _entry_key(entry)
    if isinstance(entry, DictItem):
        return key or _NO_LANGUAGE
    if isinstance(entry, model.Key):
        return f"[{position}] {entry.type.name}"
    return key or f"[{position}]"


def _entry_key(entry: object) -> str:
    if isinstance(entry, DictItem):
        return str(entry.key)
    if isinstance(entry, model.Referable):
        id_short = entry.id_short
        if id_short and not id_short.startswith(_GENERATED_ID_SHORT_PREFIX):
            return id_short
        return ""
    if isinstance(entry, model.Qualifier):
        return entry.type
    if isinstance(entry, (model.Extension, model.SpecificAssetId)):
        return entry.name
    return ""
