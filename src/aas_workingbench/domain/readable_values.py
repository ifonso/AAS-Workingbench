"""What a cell reads for a value that Python shows as a repr.

The cells of a tab and of the columns of the package tree showed
`Extension(name=Origin)`, `{Qualifier(type=Cardinality)}` and
`(Key(type=SUBMODEL, value=urn:x),)`. A person reads the name of an extension,
the number of qualifiers, and the last key of a reference.

This module only builds the text of a cell. What the editor edits, copies, and
shows in the form of an edit dialog is the value itself, and does not depend
on it.

Example:
    >>> from basyx.aas import model
    >>> from basyx.aas.model import datatypes
    >>> readable_text(model.Extension("Origin", datatypes.String, "datasheet"))
    'Origin'
"""

from collections.abc import Iterable
from collections.abc import Sized
import datetime
from decimal import Decimal
from enum import Enum
import inspect
import itertools
import re
from typing import cast

from basyx.aas import model
from basyx.aas.model import datatypes
from dateutil.relativedelta import relativedelta

from aas_workingbench.additional.classes import DictItem
from aas_workingbench.domain.attribute_display import EMPTY
from aas_workingbench.domain.attribute_display import GENERATED_ID_SHORT_TEXT
from aas_workingbench.domain.attribute_display import is_generated_id_short
from aas_workingbench.domain.attribute_display import value_text

_CAMEL_WORD = re.compile(r"[A-Z][a-z]*|[0-9]+")
_IRREGULAR_PLURALS = {"entity": "entities", "property": "properties"}
_MOST_ENTRIES_INSPECTED = 100
_REPR_LIKE = re.compile(r"^\w+[(\[]")


def readable_text(value: object) -> str | None:
    """Returns what a person reads for a value that Python shows as a repr.

    Args:
        value: The value of a row.

    Returns:
        `(not set)` for None, `(empty)` for a container without entries, the
        name of an object that has one (an extension, a qualifier), a count
        such as `2 qualifiers` for a container, and a size for bytes. None
        for a value that the program has always shown well: text, numbers,
        enumerations, texts of languages, and references, which the caller
        shows by their last key.
    """
    if isinstance(value, relativedelta):
        return datatypes.xsd_repr(value)
    if is_generated_id_short(value):
        return GENERATED_ID_SHORT_TEXT
    text = value_text(value)
    if text is not None or _shown_as_it_is(value):
        return text
    if isinstance(value, bytes):
        return f"{len(value)} bytes"
    named = _object_text(value)
    if named is not None:
        return named
    if _is_counted(value):
        return count_text(cast("Sized", value))
    return _repr_free_text(value)


def content_text(content: bytes, owner: object) -> str:
    """Returns what the cell of a binary content reads.

    Args:
        content: The bytes of a Blob or of a stored file.
        owner: The object that has the content. Its content type, or media
            type, is named if it has one.

    Returns:
        The size and the content type, such as `8 bytes, image/png`. The
        bytes themselves are what the editor edits and copies.
    """
    size = f"{len(content)} bytes"
    kind = getattr(owner, "content_type", None) or getattr(
        owner, "mime_type", None
    )
    return f"{size}, {kind}" if isinstance(kind, str) and kind else size


def count_text(entries: Sized) -> str:
    """Returns the number of entries with the word for what they are.

    Args:
        entries: A container with entries.

    Returns:
        For example `1 extension`, `2 qualifiers`, `3 embedded data
        specifications`, or `4 items` when the entries are of mixed kinds.
    """
    count = len(entries)
    noun = _entries_noun(entries)
    return f"{count} {noun if count == 1 else _plural(noun)}"


def _shown_as_it_is(value: object) -> bool:
    return isinstance(
        value,
        (
            str,
            int,
            float,
            Enum,
            DictItem,
            model.Reference,
            model.Key,
            model.LangStringSet,
            Decimal,
            datetime.date,
            datetime.time,
            datetime.timedelta,
            relativedelta,
        ),
    ) or inspect.isclass(value)


def _is_counted(value: object) -> bool:
    return isinstance(value, Sized) and isinstance(value, Iterable)


def _entries_noun(entries: object) -> str:
    kinds = {
        _kind_of(entry)
        for entry in itertools.islice(
            cast("Iterable[object]", entries), _MOST_ENTRIES_INSPECTED
        )
    }
    if len(kinds) == 1:
        (kind,) = kinds
        return _words(kind.__name__)
    if kinds and all(issubclass(k, model.SubmodelElement) for k in kinds):
        return "element"
    return "item"


def _kind_of(entry: object) -> type:
    # The kind of a reference does not matter to a person who counts them.
    if isinstance(entry, model.Reference):
        return model.Reference
    return type(entry)


def _words(class_name: str) -> str:
    if class_name == "StoredFile":
        return "file"
    return " ".join(word.lower() for word in _CAMEL_WORD.findall(class_name))


def _plural(noun: str) -> str:
    head, space, word = noun.rpartition(" ")
    if word in _IRREGULAR_PLURALS:
        word = _IRREGULAR_PLURALS[word]
    elif word.endswith(("s", "x")):
        word += "es"
    elif word.endswith("y") and word[-2:-1] not in ("a", "e", "i", "o", "u"):
        word = word[:-1] + "ies"
    else:
        word += "s"
    return head + space + word


def _object_text(value: object) -> str | None:
    """Returns the name of an AAS object that a cell shows instead of a repr."""
    if isinstance(value, model.Extension):
        return _pair(value.name, value.value)
    if isinstance(value, model.Qualifier):
        return _pair(value.type, value.value)
    if isinstance(value, model.SpecificAssetId):
        return _pair(value.name, value.value)
    if isinstance(value, model.Resource):
        return value.path
    if isinstance(value, model.AssetInformation):
        return _asset_information_text(value)
    if isinstance(value, model.AdministrativeInformation):
        return _administration_text(value)
    if isinstance(value, model.EmbeddedDataSpecification):
        return _data_specification_text(value)
    if isinstance(value, model.Identifiable):
        return value.id_short or value.id
    if isinstance(value, model.Referable):
        return value.id_short or None
    return None


def _pair(name: str, value: object) -> str:
    if value is None:
        return name
    shown = readable_text(value) if isinstance(value, relativedelta) else value
    return f"{name}: {shown}"


def _asset_information_text(info: model.AssetInformation) -> str:
    kind = info.asset_kind.name
    return f"{kind}: {info.global_asset_id}" if info.global_asset_id else kind


def _administration_text(info: model.AdministrativeInformation) -> str:
    parts: list[str] = []
    if info.version:
        parts.append(f"version {info.version}")
    if info.revision:
        parts.append(f"revision {info.revision}")
    if info.creator is not None:
        parts.append(f"creator {_last_key(info.creator)}")
    if info.template_id:
        parts.append(f"template {info.template_id}")
    return ", ".join(parts) if parts else EMPTY


def _data_specification_text(spec: model.EmbeddedDataSpecification) -> str:
    content = spec.data_specification_content
    if isinstance(content, model.DataSpecificationIEC61360):
        return "IEC 61360"
    return _last_key(spec.data_specification)


def _last_key(reference: model.Reference) -> str:
    return reference.key[-1].value if reference.key else EMPTY


def _repr_free_text(value: object) -> str | None:
    """Names an object whose text is a Python repr, such as `Name(a=1)`."""
    if _REPR_LIKE.match(str(value)):
        return type(value).__name__
    return None
