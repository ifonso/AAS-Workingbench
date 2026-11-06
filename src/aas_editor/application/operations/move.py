"""Moving members up, down, to the top and to the end (decision D16).

Elements of a submodel, a collection, a list, an entity or an annotated
relationship, the variables of an operation, qualifiers, extensions, and the
items of saved lists have an order that is written to the file. `plan_move`
works out the new order for one or several selected members of the same
container, without changing anything. `move_commands` builds the commands.

Items of a `SubmodelElementList` are named by their position in references
(AASd-128). Moving one gives the references through the items that changed
position their new keys, in the same step.

Example:
    Moving the selected elements one place up::

        plan = plan_move(container, selected, MoveKind.UP, package.objStore)
        if plan is not None:
            with stack.group(plan.description):
                for command in move_commands(observer, plan):
                    stack.push(command)
"""

from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
import enum
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import ReorderMembers
from aas_editor.application.edits import describe
from aas_editor.application.operations.references import KeyRename
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.references import reference_commands
from aas_editor.application.operations.references import rewrite_keys
from aas_editor.domain import containers
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import path_of


class MoveKind(enum.Enum):
    """Where to move the selected members."""

    UP = "up"
    DOWN = "down"
    TO_TOP = "top"
    TO_END = "end"


_TEXTS = {
    MoveKind.UP: "up",
    MoveKind.DOWN: "down",
    MoveKind.TO_TOP: "to the top",
    MoveKind.TO_END: "to the end",
}


@dataclass(frozen=True, eq=False)
class MovePlan:
    """What a move would do, found without changing anything.

    Attributes:
        container: The ordered container that holds the members.
        order: Its members in the new order.
        moved: The selected members that end at another position.
        shifts: The references that get the new position of a list item.
        description: Text for the undo step.
    """

    container: object
    order: tuple[object, ...]
    moved: tuple[object, ...]
    shifts: tuple[ReferenceChange, ...]
    description: str

    @property
    def reference_count(self) -> int:
        """How many references get a new position."""
        return len(self.shifts)


def new_order(
    members: Sequence[Any], selected: Collection[object], kind: MoveKind
) -> list[Any]:
    """Works out the order after a move.

    The selected members are taken out and put back next to each other, as
    Package Explorer does (F-EDT-09 AC3 and AC4, ADR 0020):

    * Up puts the block one place above the first selected member. When that
      member is at the top, nothing changes, even if others could move.
    * Down is the mirror of that: the block ends one place below the last
      selected member, and nothing changes when that member is at the bottom.
    * To top and to end put the block at the start or the end.

    Args:
        members: The members in their current order.
        selected: The members to move, compared by identity.
        kind: Where to move them.

    Returns:
        The members in the new order. The selected ones keep their order
        among themselves, which is their order in the container.
    """
    chosen = {id(item) for item in selected}
    order = list(members)
    block = [m for m in order if id(m) in chosen]
    rest = [m for m in order if id(m) not in chosen]
    if not block:
        return order
    positions = [n for n, m in enumerate(order) if id(m) in chosen]
    if kind is MoveKind.TO_TOP:
        start = 0
    elif kind is MoveKind.TO_END:
        start = len(rest)
    elif kind is MoveKind.UP:
        if positions[0] == 0:
            return order
        start = positions[0] - 1
    else:
        if positions[-1] == len(order) - 1:
            return order
        start = positions[-1] + 2 - len(block)
    return rest[:start] + block + rest[start:]


def can_move(
    container: object, selected: Collection[object], kind: MoveKind
) -> bool:
    """Tells whether a move would change the order.

    Args:
        container: The ordered container of the members.
        selected: The members to move.
        kind: Where to move them.

    Returns:
        False for an empty selection, for a member that is not in the
        container, and for a move that leaves the order as it is, such as
        Move Up on the first member.
    """
    try:
        members = containers.members_in_order(container)
    except TypeError:
        return False
    chosen = {id(item) for item in selected}
    if not chosen or not chosen <= {id(m) for m in members}:
        return False
    after = new_order(members, selected, kind)
    return any(a is not b for a, b in zip(members, after, strict=True))


def plan_move(
    container: object,
    selected: Iterable[object],
    kind: MoveKind,
    objects: Iterable[model.Identifiable],
) -> MovePlan | None:
    """Plans moving members of one container.

    Args:
        container: The `NamespaceSet` or list that holds the members.
        selected: The members to move. All must be in the container.
        kind: Where to move them.
        objects: The identifiables of the package, to find references through
            list items.

    Returns:
        The plan, or None when the order would not change.

    Raises:
        ValueError: If a selected object is not in the container.
    """
    chosen = list(selected)
    members = containers.members_in_order(container)
    if not {id(item) for item in chosen} <= {id(m) for m in members}:
        raise ValueError("A selected object is not in the container")
    order = new_order(members, chosen, kind)
    if all(a is b for a, b in zip(members, order, strict=True)):
        return None
    chosen_ids = {id(item) for item in chosen}
    moved = tuple(m for m in order if id(m) in chosen_ids)
    shifts = tuple(_position_changes(container, members, order, objects))
    name = describe(chosen[0]) if len(chosen) == 1 else f"{len(chosen)} items"
    return MovePlan(
        container,
        tuple(order),
        moved,
        shifts,
        f"Move {name} {_TEXTS[kind]}",
    )


def move_commands(
    observer: ModelChangeObserver, plan: MovePlan
) -> list[Command]:
    """Builds the commands of a move. Push them inside one group.

    Args:
        observer: Where the commands report.
        plan: What `plan_move` made.

    Returns:
        The reorder, then the commands that give references their new keys.
    """
    commands: list[Command] = [
        ReorderMembers(
            observer, plan.container, plan.order, description=plan.description
        )
    ]
    commands.extend(reference_commands(observer, plan.shifts))
    return commands


def _position_changes(
    container: object,
    members: Sequence[Any],
    order: Sequence[Any],
    objects: Iterable[model.Identifiable],
) -> list[ReferenceChange]:
    """Finds the references to list items that change position."""
    renames = position_renames(container, members, order)
    if not renames:
        return []
    changes, _ = rewrite_keys(ReferenceIndex(objects), renames)
    return list(changes)


def position_renames(
    container: object, members: Sequence[Any], order: Sequence[Any]
) -> list[KeyRename]:
    """Finds the new keys of the list items that change position (AASd-128).

    Args:
        container: The container of the members.
        members: The members in their current order.
        order: The members in the new order.

    Returns:
        One rename for each item of a `SubmodelElementList` that gets another
        position. Empty for every other container.
    """
    holder = _list_holder(members)
    if holder is None or not isinstance(container, model.NamespaceSet):
        return []
    renames: list[KeyRename] = []
    for new, item in enumerate(order):
        old = next(n for n, member in enumerate(members) if member is item)
        path = path_of(item)
        if old != new and path is not None:
            renames.append(KeyRename(path, str(new)))
    return renames


def _list_holder(
    members: Sequence[Any],
) -> model.SubmodelElementList[Any] | None:
    """Returns the list that holds the members, if it is a SubmodelElementList."""
    for member in members:
        parent = getattr(member, "parent", None)
        if isinstance(parent, model.SubmodelElementList):
            return cast("model.SubmodelElementList[Any]", parent)
        return None
    return None
