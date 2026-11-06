"""Deleting objects, and what to do with the references to them (D11).

Deleting a submodel, a concept description or an element leaves every
reference to it pointing at nothing. `plan_delete` finds those references
without changing anything. The user then chooses between taking the references
away and leaving them, and `delete_commands` builds the commands for the
choice, so that one undo brings back the objects and the references.

Deleting a child of a `SubmodelElementList` also moves the items behind it up
by one, and a reference to such an item names it by its position (AASd-128).
Those references get the new position, whatever the user chose.

Example:
    Deleting with a look at the usages::

        plan = plan_delete(package.objStore, [submodel])
        if plan.usages:
            remove = ask_user(plan)
        with stack.group("Delete Pump"):
            for command in delete_commands(
                observer, plan, package.objStore, remove
            ):
                stack.push(command)
"""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass
import enum
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import RemoveMember
from aas_editor.application.operations.references import KeyRename
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.references import reference_commands
from aas_editor.application.operations.references import rewrite_keys
from aas_editor.domain import ordering
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import Usage
from aas_editor.domain.references import chain
from aas_editor.domain.references import path_of
from aas_editor.domain.references import without_nested


class DeletePrompt(enum.Enum):
    """What to ask the user before a delete."""

    NONE = "none"
    """Delete at once."""
    CONFIRM = "confirm"
    """Ask whether to delete, because the delete is destructive."""
    USAGES = "usages"
    """Show the references, and ask what to do with them."""


@dataclass(frozen=True, eq=False)
class DeletePlan:
    """What a delete would do, found without changing anything.

    Attributes:
        targets: The objects to delete. An object below another target is
            not listed, because it goes with its parent.
        usages: The references to the targets from objects that stay.
        removals: What taking the references away would do. A reference that
            is a member of a list or set, or an optional attribute, is taken
            away, and a `referred_semantic_id` is cut off.
        kept: The usages that cannot be taken away, because the attribute is
            required, such as the first end of a relationship. They stay.
        shifts: The references to the items behind a deleted list item, which
            get the new position.
    """

    targets: tuple[model.Referable, ...]
    usages: tuple[Usage, ...]
    removals: tuple[ReferenceChange, ...]
    kept: tuple[Usage, ...]
    shifts: tuple[ReferenceChange, ...] = ()

    @property
    def has_usages(self) -> bool:
        """Whether something that stays refers to a target."""
        return bool(self.usages)

    @property
    def is_destructive(self) -> bool:
        """Whether the delete takes away more than a user may expect.

        That is a shell, submodel or concept description, an element with
        elements below it, or anything that is referred to.
        """
        return (
            self.has_usages
            or any(
                isinstance(target, model.Identifiable)
                for target in self.targets
            )
            or any(_has_children(target) for target in self.targets)
        )


def prompt_for(
    plan: DeletePlan, skip_confirmation: bool = False
) -> DeletePrompt:
    """Decides what to ask the user before a delete.

    Args:
        plan: What `plan_delete` made.
        skip_confirmation: True when the user asked to delete without a
            question. That skips the confirmation, but never the references:
            the user should see what would point at nothing.

    Returns:
        The question to ask.
    """
    if plan.has_usages:
        return DeletePrompt.USAGES
    if plan.is_destructive and not skip_confirmation:
        return DeletePrompt.CONFIRM
    return DeletePrompt.NONE


def plan_delete(
    objects: Iterable[model.Identifiable],
    targets: Iterable[model.Referable],
) -> DeletePlan:
    """Finds the references to the objects that are about to be deleted.

    Args:
        objects: The identifiables of the package.
        targets: The shells, submodels, concept descriptions and elements to
            delete.

    Returns:
        The plan. Nothing changes.
    """
    top = _top_level(targets)
    index = ReferenceIndex(objects)
    usages = index.usages_of(top)
    removals, kept = _removals(usages)
    return DeletePlan(
        tuple(top),
        tuple(usages),
        tuple(removals),
        tuple(kept),
        tuple(_shifts(index, top)),
    )


def delete_commands(
    observer: ModelChangeObserver,
    plan: DeletePlan,
    store: object,
    remove_references: bool,
) -> list[Command]:
    """Builds the commands that delete the targets.

    Args:
        observer: Where the commands report.
        plan: What `plan_delete` made.
        store: The object store of the package, which holds the shells,
            submodels and concept descriptions.
        remove_references: Whether to take the references away. Otherwise they
            stay and point at nothing.

    Returns:
        The commands in the order to apply them: the references first, so
        that undo puts the objects back before the references to them. Push
        them inside one group.
    """
    commands = cleanup_commands(observer, plan, remove_references)
    commands.extend(
        RemoveMember(observer, container_of(target, store), target)
        for target in plan.targets
    )
    return commands


def cleanup_commands(
    observer: ModelChangeObserver,
    plan: DeletePlan,
    remove_references: bool,
) -> list[Command]:
    """Builds the commands for the references, without deleting anything.

    For a caller that deletes the objects itself, such as a view that also has
    to follow the rows of its model.

    Args:
        observer: Where the commands report.
        plan: What `plan_delete` made.
        remove_references: Whether to take the references away.

    Returns:
        The commands that give the references to list items their new
        position, and that take the references away if asked to.
    """
    removals = plan.removals if remove_references else ()
    removed = {id(change.slot) for change in removals}
    # A reference that is taken away needs no new position.
    shifts = [c for c in plan.shifts if id(c.slot) not in removed]
    return reference_commands(observer, [*shifts, *removals])


def container_of(target: model.Referable, store: object) -> object:
    """Returns the container that holds a target.

    Args:
        target: A shell, submodel, concept description or element.
        store: The object store of the package.

    Returns:
        The store for an identifiable, otherwise the namespace set of its
        parent that holds it.

    Raises:
        KeyError: If the target is held by nothing.
    """
    if isinstance(target, model.Identifiable):
        return store
    sets = ordering.namespace_sets_of(target)
    if not sets:
        raise KeyError(f"{target!r} is not held by any container")
    return sets[0]


def _top_level(targets: Iterable[model.Referable]) -> list[model.Referable]:
    """Drops the targets that are below another target, and repeats."""
    unique: dict[int, model.Referable] = {}
    for target in targets:
        unique.setdefault(id(target), target)
    chosen = set(unique)
    top: list[model.Referable] = []
    for target in unique.values():
        parent = getattr(target, "parent", None)
        while parent is not None and id(parent) not in chosen:
            parent = getattr(parent, "parent", None)
        if parent is None:
            top.append(target)
    return top


def _has_children(target: model.Referable) -> bool:
    sets = cast(
        "Iterable[Iterable[object]]",
        getattr(target, "namespace_element_sets", ()),
    )
    return any(
        isinstance(member, model.SubmodelElement)
        for namespace_set in sets
        for member in namespace_set
    )


def _removals(
    usages: Collection[Usage],
) -> tuple[list[ReferenceChange], list[Usage]]:
    by_slot: dict[int, list[Usage]] = {}
    for usage in usages:
        by_slot.setdefault(id(usage.slot), []).append(usage)
    candidates: dict[int, ReferenceChange] = {}
    kept: list[Usage] = []
    for found in by_slot.values():
        slot = found[0].slot
        whole = [usage for usage in found if not usage.is_nested]
        if whole:
            if slot.is_removable:
                candidates[id(slot)] = ReferenceChange(slot, None)
            else:
                kept.extend(whole)
        else:
            matched = {id(usage.reference) for usage in found}
            outermost = next(
                node for node in chain(slot.reference) if id(node) in matched
            )
            candidates[id(slot)] = ReferenceChange(
                slot, without_nested(slot.reference, outermost)
            )
    changes = list(candidates.values())
    kept.extend(_blocked_semantic_ids(changes))
    blocked = {id(usage.slot) for usage in kept}
    return [c for c in changes if id(c.slot) not in blocked], kept


def _blocked_semantic_ids(changes: list[ReferenceChange]) -> list[Usage]:
    """Finds semantic ids that must stay while a supplemental one stays.

    Constraint AASd-118 forbids a supplemental semantic id without a semantic
    id. The change is dropped from `changes` by the caller.
    """
    gone = {
        id(change.slot.reference) for change in changes if change.is_removal
    }
    blocked: list[Usage] = []
    for change in changes:
        slot = change.slot
        if not change.is_removal or slot.attribute != "semantic_id":
            continue
        supplemental = cast(
            "Iterable[model.Reference]",
            getattr(slot.owner, "supplemental_semantic_id", ()),
        )
        if any(id(reference) not in gone for reference in supplemental):
            blocked.append(Usage(slot, slot.reference))
    return blocked


def _shifts(
    index: ReferenceIndex, targets: Collection[model.Referable]
) -> list[ReferenceChange]:
    """Finds the references to list items that move up after a delete."""
    # The items of each list that loses a child, by the list, with the ones
    # that go away.
    items_by_list: dict[int, list[model.Referable]] = {}
    gone: set[int] = set()
    for target in targets:
        if isinstance(target.parent, model.SubmodelElementList):
            parent = cast(
                "model.SubmodelElementList[Any]",
                target.parent,  # pyright: ignore[reportUnknownMemberType]
            )
            gone.add(id(target))
            items_by_list.setdefault(
                id(parent),
                list(cast("Iterable[model.Referable]", parent.value)),
            )
    renames: list[KeyRename] = []
    for items in items_by_list.values():
        removed_before = 0
        for position, item in enumerate(items):
            if id(item) in gone:
                removed_before += 1
            elif removed_before:
                path = path_of(item)
                if path is not None:
                    renames.append(
                        KeyRename(path, str(position - removed_before))
                    )
    changes, _ = rewrite_keys(index, renames)
    return list(changes)
