"""Walks the elements of a submodel, including the annotations.

`basyx.aas.util.traversal.walk_submodel` skips the annotations of an
`AnnotatedRelationshipElement`. The SDK reader and writer rely on it to find
File elements, so a File under an annotation is silently lost. Code that must
see every element uses this module instead.
"""

from collections.abc import Iterator

from basyx.aas import model
from basyx.aas.util import traversal


def walk_elements(
    submodel: model.Submodel,
) -> Iterator[model.SubmodelElement]:
    """Yields every element of a submodel, recursively.

    This is what `walk_submodel` yields, plus the annotations of each
    `AnnotatedRelationshipElement`. Do not add, remove, or move elements while
    iterating.

    Args:
        submodel: The submodel to walk.

    Yields:
        Each element, children before their parent, as the SDK does. The
        annotations of a relationship element follow it.
    """
    for element in traversal.walk_submodel(submodel):
        yield element
        if isinstance(element, model.AnnotatedRelationshipElement):
            yield from element.annotation


def is_annotation(element: model.SubmodelElement) -> bool:
    """Tells whether an element is an annotation of a relationship element.

    Args:
        element: Any submodel element.

    Returns:
        True if the parent of the element is an `AnnotatedRelationshipElement`.
    """
    return isinstance(element.parent, model.AnnotatedRelationshipElement)
