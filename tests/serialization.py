"""Compares the content of packages through the SDK's JSON serialization.

Tests that edit and then undo compare state with this, so they do not depend on
which attributes of an object a test remembers to check.
"""

import io
import json

from basyx.aas import model
from basyx.aas.adapter.json import write_aas_json_file


def snapshot(
    objects: model.AbstractObjectStore[str, model.Identifiable],
) -> str:
    """Serializes the objects of a package with the SDK, as text.

    The order inside every object is kept, because it is saved. The shells,
    submodels and concept descriptions of a package live in a set, so their
    order is not part of the content and the lists are sorted by id.

    Args:
        objects: The object store of a package.

    Returns:
        The same text for the same content.
    """
    buffer = io.StringIO()
    write_aas_json_file(buffer, objects)
    document = json.loads(buffer.getvalue())
    for key, entries in document.items():
        document[key] = sorted(entries, key=lambda entry: entry["id"])
    return json.dumps(document, indent=1)
