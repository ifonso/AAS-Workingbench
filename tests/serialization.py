"""Compares the content of packages through the SDK's JSON serialization.

Tests that edit and then undo compare state with this, so they do not depend on
which attributes of an object a test remembers to check.
"""

import io
import json
from typing import Any

from basyx.aas import model
from basyx.aas.adapter.json import write_aas_json_file


def snapshot(objects: model.AbstractObjectStore[Any, Any]) -> str:
    """Serializes the objects of a package with the SDK, as text.

    The order inside every object is kept, because it is saved. The shells,
    submodels and concept descriptions of a package live in a set, so their
    order is not part of the content, and the lists and their keys are sorted.

    Args:
        objects: The object store of a package.

    Returns:
        The same text for the same content.
    """
    buffer = io.StringIO()
    write_aas_json_file(buffer, objects)
    document = json.loads(buffer.getvalue())
    ordered = {
        key: sorted(document[key], key=lambda entry: entry["id"])
        for key in sorted(document)
    }
    return json.dumps(_sort_sets(ordered), indent=1)


# JSON arrays that the SDK builds from a Python set, so their order is
# arbitrary and can differ between two reads of the same file.
_SET_KEYS = ("submodels", "specificAssetIds", "valueReferencePairs")


def _sort_sets(node: Any) -> Any:
    if isinstance(node, list):
        return [_sort_sets(item) for item in node]
    if isinstance(node, dict):
        return {
            key: _sorted_if_set(key, _sort_sets(child))
            for key, child in node.items()
        }
    return node


def _sorted_if_set(key: str, value: Any) -> Any:
    if key in _SET_KEYS and isinstance(value, list):
        return sorted(value, key=json.dumps)
    return value
