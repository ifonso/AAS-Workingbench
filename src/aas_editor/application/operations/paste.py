"""Pasting copies of AAS objects at a position (decisions D12 and D13).

A paste inserts copies, never the objects of the buffer, so the same buffer
can be pasted again and gives a further duplicate. `plan_paste` makes the
copies and names them without changing the package:

- An element whose idShort is taken among its new siblings gets a numeric
  suffix (`Pump` becomes `Pump_1`), through `domain.ids.unique_id_short`.
- A copied shell, submodel or concept description gets a new id, through
  `new_identifier`. A cut keeps its id, because the references to it would
  dangle with another one. It gets a new id only if the id is taken.

`paste_commands` turns the plan into commands. Push them in one group.

Example:
    Pasting below the second element::

        plan = plan_paste(container, items, index=2)
        with stack.group(plan.description):
            for command in paste_commands(observer, plan):
                stack.push(command)
"""

from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import describe
from aas_editor.domain.clipboard_json import clone
from aas_editor.domain.ids import new_identifier
from aas_editor.domain.ids import unique_id_short


class PasteError(ValueError):
    """The buffer cannot be pasted here. The message is for the user."""


@dataclass(frozen=True, eq=False)
class PastedItem:
    """One copy that a paste inserts.

    Attributes:
        copy: The new object, detached until the command adds it.
        original_name: The idShort or id the object had before it was
            renamed, or None if it kept its name.
    """

    copy: model.Referable
    original_name: str | None = None

    @property
    def renamed(self) -> bool:
        """Whether the copy got another idShort or id."""
        return self.original_name is not None


@dataclass(frozen=True, eq=False)
class PastePlan:
    """What a paste would add, found without changing anything.

    Attributes:
        container: The namespace set or object store to add to.
        items: The copies in the order they are inserted.
        index: The position of the first copy, or None to append.
        description: Text for the undo step.
    """

    container: object
    items: tuple[PastedItem, ...]
    index: int | None
    description: str

    @property
    def renamed(self) -> tuple[PastedItem, ...]:
        """The copies that got another idShort or id."""
        return tuple(item for item in self.items if item.renamed)


def plan_paste(
    container: object,
    items: Sequence[model.Referable],
    index: int | None = None,
    keep_ids: bool = False,
    taken_ids: Collection[str] = (),
) -> PastePlan:
    """Makes the copies for a paste and gives them free names.

    Args:
        container: The `NamespaceSet` to paste elements into, or the object
            store of the package to paste shells, submodels and concept
            descriptions into.
        items: The objects of the buffer, in the order to insert them. They are
            not changed or added.
        index: The position of the first copy in a namespace set. None
            appends. Ignored for an object store.
        keep_ids: True for the objects of a cut. They keep their id if it is
            free.
        taken_ids: The ids of the identifiables of the package, for pasting
            into the object store.

    Returns:
        The plan.

    Raises:
        PasteError: If nothing is to be pasted or an object does not belong in
            the container.
    """
    if not items:
        raise PasteError("There is nothing to paste")
    if isinstance(container, model.NamespaceSet):
        return _plan_elements(
            cast("model.NamespaceSet[model.Referable]", container),
            items,
            index,
        )
    return _plan_identifiables(container, items, keep_ids, set(taken_ids))


def paste_commands(
    observer: ModelChangeObserver, plan: PastePlan
) -> list[Command]:
    """Builds the commands that add the copies. Push them inside one group."""
    commands: list[Command] = []
    for number, item in enumerate(plan.items):
        position = None if plan.index is None else plan.index + number
        commands.append(
            AddMember(
                observer,
                plan.container,
                item.copy,
                position,
                description=f"Paste {describe(item.copy)}",
            )
        )
    return commands


def _plan_elements(
    container: "model.NamespaceSet[model.Referable]",
    items: Sequence[model.Referable],
    index: int | None,
) -> PastePlan:
    if not all(isinstance(item, model.SubmodelElement) for item in items):
        raise PasteError(
            "No (valid) information for SubmodelElements in the paste buffer"
        )
    in_list = isinstance(container, model.OrderedNamespaceSet)
    taken: set[str] = {
        member.id_short for member in container if member.id_short is not None
    }
    pasted: list[PastedItem] = []
    for item in items:
        copied = clone(item)
        original: str | None = None
        if in_list:
            # The children of a list have no idShort of their own.
            copied.id_short = None
        elif copied.id_short is not None:
            free = unique_id_short(copied.id_short, taken)
            if free != copied.id_short:
                original = copied.id_short
                copied.id_short = free
            taken.add(free)
        pasted.append(PastedItem(copied, original))
    return PastePlan(container, tuple(pasted), index, _describe(pasted))


def _plan_identifiables(
    container: object,
    items: Sequence[model.Referable],
    keep_ids: bool,
    taken: set[str],
) -> PastePlan:
    if not all(isinstance(item, model.Identifiable) for item in items):
        raise PasteError(
            "No (valid) information for Identifiables in the paste buffer"
        )
    pasted: list[PastedItem] = []
    for item in items:
        copied = cast("model.Identifiable", clone(item))
        original: str | None = None
        if not keep_ids or copied.id in taken:
            original = copied.id
            copied.id = new_identifier()
        taken.add(copied.id)
        pasted.append(PastedItem(copied, original))
    return PastePlan(container, tuple(pasted), None, _describe(pasted))


def _describe(pasted: Iterable[PastedItem]) -> str:
    copies = [item.copy for item in pasted]
    if len(copies) == 1:
        return f"Paste {describe(copies[0])}"
    return f"Paste {len(copies)} items"
