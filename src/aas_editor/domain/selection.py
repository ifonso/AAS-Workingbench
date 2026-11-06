"""What a selection of several rows is, and what can be done with it.

Package Explorer shows a panel when several tree nodes are selected. It names
the selection, and offers the actions that apply to all of it. This module has
the facts that panel needs, without Qt: how many objects are selected, of which
kinds, in how many parents, and whether the selection holds variables of an
Operation in different directions, where the original offers neither Move nor
Delete (F-EDT-09 AC19).

Example:
    Describing a selection of two properties::

        summary = summarize([(first, collection), (second, collection)])
        summary.header  # "Multiple selected elements"
        summary.kinds_text  # "2 Property"
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass

from basyx.aas import model

from aas_editor.domain.references import describe_object

MULTIPLE_HEADER = "Multiple selected elements"
"""The header of the panel, as in Package Explorer."""

_DIRECTIONS = (
    ("input", "input_variable"),
    ("output", "output_variable"),
    ("inoutput", "in_output_variable"),
)


def variable_direction(obj: object) -> str | None:
    """Tells which kind of variable of an Operation an object is.

    Args:
        obj: Any object.

    Returns:
        "input", "output", or "inoutput" for an element that sits in one of
        the variable sets of an Operation, and None for anything else.
    """
    parent = getattr(obj, "parent", None)
    if not isinstance(parent, model.Operation):
        return None
    for direction, attribute in _DIRECTIONS:
        held = getattr(parent, attribute)
        if any(member is obj for member in held):
            return direction
    return None


def has_mixed_variable_directions(objects: Iterable[object]) -> bool:
    """Tells whether variables of different directions are selected.

    Package Explorer offers neither Move nor Delete for such a selection,
    because the variables of an Operation are three separate lists. Cut and
    Copy stay (F-EDT-09 AC19).

    Args:
        objects: The selected objects.

    Returns:
        True when the selection holds variables of more than one direction.
        Objects that are no variables do not count.
    """
    directions = {variable_direction(obj) for obj in objects}
    directions.discard(None)
    return len(directions) > 1


@dataclass(frozen=True)
class SelectionSummary:
    """The facts about a selection that the panel shows.

    Attributes:
        count: How many rows are selected.
        kinds: The class names and how many of each, most frequent first.
        parents: How many different parents the rows have.
        parent_text: The one parent, when all rows share it.
        mixed_directions: Whether variables of different directions are
            selected.
    """

    count: int
    kinds: tuple[tuple[str, int], ...]
    parents: int
    parent_text: str | None
    mixed_directions: bool

    @property
    def is_multiple(self) -> bool:
        """Whether the selection has more than one row."""
        return self.count > 1

    @property
    def header(self) -> str:
        """The title of the panel."""
        if self.count == 0:
            return "Nothing selected"
        if self.count == 1:
            return "One element selected"
        return MULTIPLE_HEADER

    @property
    def kinds_text(self) -> str:
        """The kinds with their counts, such as `2 Property, 1 File`."""
        return ", ".join(f"{count} {kind}" for kind, count in self.kinds)

    @property
    def parent_line(self) -> str:
        """Tells where the rows are."""
        if self.count == 0:
            return ""
        if self.parent_text is not None:
            return f"All in {self.parent_text}."
        return (
            f"In {self.parents} different parents. Move works inside each "
            "parent."
        )


def summarize(
    selection: Sequence[tuple[object, object | None]],
) -> SelectionSummary:
    """Describes a selection.

    Args:
        selection: Each selected object with the object that holds it in the
            tree. An AAS object that has a parent of its own is grouped by
            that parent, and the second value is used for the rest, such as
            a stored file or a shell.

    Returns:
        The summary. An empty selection has a count of zero.
    """
    counts: dict[str, int] = {}
    parents: list[object | None] = []
    for obj, fallback in selection:
        own = getattr(obj, "parent", None)
        parent = own if own is not None else fallback
        name = type(obj).__name__
        counts[name] = counts.get(name, 0) + 1
        if not any(parent is held for held in parents):
            parents.append(parent)
    kinds = tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
    shared = parents[0] if len(parents) == 1 else None
    return SelectionSummary(
        count=len(selection),
        kinds=kinds,
        parents=len(parents),
        parent_text=_parent_text(shared) if len(parents) == 1 else None,
        mixed_directions=has_mixed_variable_directions(
            obj for obj, _ in selection
        ),
    )


def _parent_text(parent: object | None) -> str | None:
    if isinstance(parent, model.Referable):
        return describe_object(parent)
    return "the same place"
