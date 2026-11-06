"""AAS objects as JSON text for the clipboard, and back.

Copying puts a JSON array of the objects on the system clipboard, in the
serialization of the metamodel, and pasting reads such text. Only the JSON
adapter of the BaSyx SDK reads and writes it. The text may come from any
program, so it is never evaluated, and a text that is not a valid AAS object
is refused with a message instead of an exception.

The same round trip makes a copy of an object that is detached from its
parent and from the package, which is what a paste inserts.

Example:
    Copying a property and pasting a duplicate of it::

        text = dump_objects([prop])
        (copy,) = load_objects(text)
"""

from collections.abc import Iterable
import json
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from basyx.aas.adapter.json import StrictAASFromJsonDecoder

# Text beyond this size is not a copied element. It is a file or a mistake.
MAX_CLIPBOARD_CHARS = 20_000_000


class ClipboardError(ValueError):
    """The text is not AAS objects. The message is meant for the user."""


def dump_objects(objects: Iterable[model.Referable]) -> str:
    """Serializes objects to a JSON array.

    Args:
        objects: Shells, submodels, concept descriptions or elements.

    Returns:
        Indented JSON text with one entry for each object.
    """
    return json.dumps(list(objects), cls=AASToJsonEncoder, indent=2)


def looks_like_json(text: str) -> bool:
    """Tells whether a text may be a JSON object or array.

    A cheap test that tells ordinary text on the clipboard from JSON, before
    anything is parsed.
    """
    stripped = text.lstrip()
    return stripped[:1] in ("{", "[")


def load_objects(text: str) -> list[model.Referable]:
    """Reads AAS objects from JSON text.

    Args:
        text: A JSON object, or an array of objects, in the serialization of
            the metamodel.

    Returns:
        The objects, detached from any parent.

    Raises:
        ClipboardError: If the text is not JSON, is too large, holds a value
            that is not an AAS object, or holds an object that the SDK
            refuses.
    """
    if len(text) > MAX_CLIPBOARD_CHARS:
        raise ClipboardError("The clipboard text is too large to be an element")
    if not looks_like_json(text):
        raise ClipboardError("The clipboard does not hold AAS JSON")
    try:
        loaded = json.loads(text, cls=StrictAASFromJsonDecoder)
    except json.JSONDecodeError as error:
        raise ClipboardError(
            f"The clipboard text is not valid JSON: {error}"
        ) from error
    except RecursionError as error:
        raise ClipboardError(
            "The clipboard JSON is nested too deeply"
        ) from error
    except (
        KeyError,
        TypeError,
        ValueError,
        AttributeError,
        model.AASConstraintViolation,
    ) as error:
        raise ClipboardError(
            f"The clipboard JSON is not a valid AAS object: {error}"
        ) from error
    objects = cast(
        "list[Any]", loaded if isinstance(loaded, list) else [loaded]
    )
    if not objects:
        raise ClipboardError("The clipboard JSON holds no object")
    if not all(isinstance(entry, model.Referable) for entry in objects):
        raise ClipboardError(
            "The clipboard JSON holds something that is not an AAS object"
        )
    return cast("list[model.Referable]", objects)


def clone(obj: model.Referable) -> model.Referable:
    """Makes a copy of an object that has no parent.

    Args:
        obj: The object to copy. It is not changed.

    Returns:
        A new object with the same content, made by the SDK's JSON adapter.

    Raises:
        ClipboardError: If the SDK cannot read back what it wrote.
    """
    (copied,) = load_objects(dump_objects([obj]))
    return copied
