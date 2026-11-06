"""Moving a selection that reaches into several containers.

`plan_move` moves the selected members of one container. A selection of
elements from several collections, lists, or submodels is common, and moving
it means moving the members of each container within that container: up, down,
to the top, or to the end of their own. Nothing moves from one container to
another, because that would change the path of the element and every
reference through it.

`plan_bulk_move` makes one plan for the whole selection, and
`bulk_move_commands` builds its commands, which belong in one group. The new
keys that references get for moved list items are found once for all the
containers, so a reference through two lists (a list inside a list) is
rewritten once, with both changes.

Example:
    Moving the selected elements of several collections up::

        plan = plan_bulk_move(placements, MoveKind.UP, package.objStore)
        if plan is not None:
            with stack.group(plan.description):
                for command in bulk_move_commands(observer, plan):
                    stack.push(command)
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import ReorderMembers
from aas_editor.application.edits import describe
from aas_editor.application.operations.move import MoveKind
from aas_editor.application.operations.move import new_order
from aas_editor.application.operations.move import position_renames
from aas_editor.application.operations.references import KeyRename
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.references import reference_commands
from aas_editor.application.operations.references import rewrite_keys
from aas_editor.domain import containers
from aas_editor.domain.references import ReferenceIndex

Placement = tuple[object, object]
"""A selected member and the ordered container that holds it."""

_TEXTS = {
    MoveKind.UP: "up",
    MoveKind.DOWN: "down",
    MoveKind.TO_TOP: "to the top",
    MoveKind.TO_END: "to the end",
}


@dataclass(frozen=True, eq=False)
class MoveStep:
    """The new order of one container.

    Attributes:
        container: The ordered container.
        order: Its members in the new order.
        moved: The selected members, in the new order.
    """

    container: object
    order: tuple[object, ...]
    moved: tuple[object, ...]


@dataclass(frozen=True, eq=False)
class BulkMovePlan:
    """What a move of a selection would do, found without changing anything.

    Attributes:
        steps: The containers whose order changes.
        shifts: The references that get the new position of a list item.
        description: Text for the undo step.
    """

    steps: tuple[MoveStep, ...]
    shifts: tuple[ReferenceChange, ...]
    description: str

    @property
    def reference_count(self) -> int:
        """How many references get a new position."""
        return len(self.shifts)


def _group(
    selection: Iterable[Placement],
) -> list[tuple[object, list[object]]]:
    """Groups the selected members by container, in order of first use."""
    groups: list[tuple[object, list[object]]] = []
    for container, member in selection:
        for held, members in groups:
            if held is container:
                members.append(member)
                break
        else:
            groups.append((container, [member]))
    return groups


def can_bulk_move(selection: Iterable[Placement], kind: MoveKind) -> bool:
    """Tells whether a move would change the order of any container.

    Args:
        selection: Each selected member with its container.
        kind: Where to move.

    Returns:
        False for an empty selection, and when every container would keep
        its order, such as Move Up for the first member of each.
    """
    for container, selected in _group(selection):
        try:
            members: list[Any] = containers.members_in_order(container)
        except TypeError:
            return False
        chosen = {id(item) for item in selected}
        if not chosen <= {id(m) for m in members}:
            return False
        after = new_order(members, selected, kind)
        if any(a is not b for a, b in zip(members, after, strict=True)):
            return True
    return False


def plan_bulk_move(
    selection: Iterable[Placement],
    kind: MoveKind,
    objects: Iterable[model.Identifiable],
) -> BulkMovePlan | None:
    """Plans moving the selected members within their containers.

    Args:
        selection: Each selected member with its ordered container.
        kind: Where to move them.
        objects: The identifiables of the package, to find references through
            list items.

    Returns:
        The plan, or None when no container would change its order.

    Raises:
        ValueError: If a selected member is not in its container.
    """
    placements = list(selection)
    steps: list[MoveStep] = []
    renames: list[KeyRename] = []
    for container, selected in _group(placements):
        members: list[Any] = containers.members_in_order(container)
        if not {id(item) for item in selected} <= {id(m) for m in members}:
            raise ValueError("A selected object is not in the container")
        order = new_order(members, selected, kind)
        if all(a is b for a, b in zip(members, order, strict=True)):
            continue
        chosen = {id(item) for item in selected}
        steps.append(
            MoveStep(
                container,
                tuple(order),
                tuple(m for m in order if id(m) in chosen),
            )
        )
        renames.extend(position_renames(container, members, order))
    if not steps:
        return None
    shifts: tuple[ReferenceChange, ...] = ()
    if renames:
        shifts, _ = rewrite_keys(ReferenceIndex(objects), renames)
    first = placements[0][1]
    name = (
        describe(first) if len(placements) == 1 else f"{len(placements)} items"
    )
    return BulkMovePlan(tuple(steps), shifts, f"Move {name} {_TEXTS[kind]}")


def bulk_move_commands(
    observer: ModelChangeObserver, plan: BulkMovePlan
) -> list[Command]:
    """Builds the commands of a move. Push them inside one group.

    Args:
        observer: Where the commands report.
        plan: What `plan_bulk_move` made.

    Returns:
        A reorder for each container, then the commands that give references
        their new keys.
    """
    commands: list[Command] = [
        ReorderMembers(
            observer, step.container, step.order, description=plan.description
        )
        for step in plan.steps
    ]
    commands.extend(reference_commands(observer, plan.shifts))
    return commands
