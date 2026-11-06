"""Replacing an element by a new one, and keeping the references to it valid.

A conversion to another element type (`aas_editor.domain.conversion`) and the
rebuild of a list with other settings (`aas_editor.domain.list_settings`) both
swap an element for a newly built one. A reference to the element names its
class in the last key, and in `ModelReference.type`, and the SDK refuses to
resolve a reference whose type the target no longer has. A reference to an item
names it by idShort, or by position in a list. So the references have to change
with the element. `plan_reference_updates` finds them without changing anything,
and `replacement_command` makes the swap and the updates as one step.

References to an item that is gone stay as they are, and `ReferenceUpdates`
lists them, so that the user is told before they point at nothing.

Example:
    Converting after the user confirmed::

        plan = plan_conversion(element, model.Range)
        updates = plan_reference_updates(package.objStore, plan)
        stack.push(replacement_command(observer, plan, updates))
        stack.undo()
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from basyx.aas import model

from aas_editor.application.changes import Change
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandGroup
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.references import reference_commands
from aas_editor.domain import containers
from aas_editor.domain import ordering
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import ReferenceSlot
from aas_editor.domain.references import Usage
from aas_editor.domain.references import is_model_reference
from aas_editor.domain.references import path_of
from aas_editor.domain.references import starts_with
from aas_editor.domain.references import with_keys
from aas_editor.domain.replacement import ReplacementPlan


@dataclass(frozen=True, eq=False)
class ReferenceUpdates:
    """What a replacement does to the references of the package.

    Attributes:
        changes: The references that get other keys: the key of the element
            has the type of the new element, and the key of an item has its
            new idShort or position. Their `ModelReference.type` follows.
        orphaned: The references to items that the new element does not
            have. They stay as they are and point at nothing afterwards.
        not_updated: References that would break a rule of references with
            the new keys, and so stay as they are. None is expected.
    """

    changes: tuple[ReferenceChange, ...] = ()
    orphaned: tuple[Usage, ...] = ()
    not_updated: tuple[ReferenceSlot, ...] = ()


def plan_reference_updates(
    objects: Iterable[model.Identifiable], plan: ReplacementPlan
) -> ReferenceUpdates:
    """Finds the references that a replacement changes or leaves dangling.

    Args:
        objects: The identifiables of the package.
        plan: The plan of the conversion or the list rebuild.

    Returns:
        The updates. Nothing has changed.
    """
    path = path_of(plan.source)
    if path is None:
        return ReferenceUpdates()
    index = ReferenceIndex(objects)
    key_type = model.Key.from_referable(plan.preview).type
    rewriter = _Rewriter(path, key_type, plan)
    slots: dict[int, ReferenceSlot] = {}
    for usage in index.through(path):
        slots.setdefault(id(usage.slot), usage.slot)
    changes: list[ReferenceChange] = []
    orphaned: list[Usage] = []
    failed: list[ReferenceSlot] = []
    for slot in slots.values():
        try:
            after = rewriter.rewrite(slot.reference)
        except model.AASConstraintViolation:
            failed.append(slot)
            continue
        if after is not slot.reference:
            changes.append(ReferenceChange(slot, after))
    for usage in index.through(path):
        if rewriter.is_orphaned(usage.reference) and not _inside_lost_item(
            usage.slot, path, plan
        ):
            orphaned.append(usage)
    return ReferenceUpdates(tuple(changes), tuple(orphaned), tuple(failed))


class ReplaceElement(Command):
    """Swaps an element for a new one in place, and back on undo.

    The new element is built when the command is applied the first time, so
    that it copies the items after the references inside them were updated.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        container: object,
        plan: ReplacementPlan,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            container: The namespace set of the parent that holds the element.
            plan: What `plan_conversion` or `plan_list_rebuild` made.
            description: Text for Undo and Redo.
        """
        self.description = description or plan.description
        self._observer = observer
        self._container = container
        self._plan = plan
        self._new: model.SubmodelElement | None = None

    @property
    def new(self) -> model.SubmodelElement | None:
        """The new element, once the command was applied."""
        return self._new

    def apply(self) -> None:
        """Puts the new element in the place of the old one."""
        if self._new is None:
            self._new = self._plan.build()
        containers.replace_member(self._container, self._plan.source, self._new)
        self._observer.notify(Change.changed(self._container))

    def revert(self) -> None:
        """Puts the old element back, with its items."""
        if self._new is None:
            return
        containers.replace_member(self._container, self._new, self._plan.source)
        self._observer.notify(Change.changed(self._container))


class ReplacementStep(CommandGroup):
    """The swap of an element and the updates of its references, as one step."""

    def __init__(
        self, description: str, commands: list[Command], swap: ReplaceElement
    ) -> None:
        """Creates the step from commands that include the swap.

        Args:
            description: Text for Undo and Redo.
            commands: The commands in the order to apply them.
            swap: The command in `commands` that swaps the element.
        """
        super().__init__(description, commands)
        self._swap = swap

    @property
    def new(self) -> model.SubmodelElement | None:
        """The new element, once the step was applied."""
        return self._swap.new


def replacement_command(
    observer: ModelChangeObserver,
    plan: ReplacementPlan,
    updates: ReferenceUpdates,
) -> ReplacementStep:
    """Builds the one step that swaps the element and updates the references.

    The references change first, so that the copies of the items carry the new
    references, and undo restores them after the old element is back.

    Args:
        observer: Where the commands report.
        plan: What `plan_conversion` or `plan_list_rebuild` made.
        updates: What `plan_reference_updates` found.

    Returns:
        A command to push on the stack of the package.

    Raises:
        KeyError: If no container of the parent holds the element.
    """
    sets = ordering.namespace_sets_of(plan.source)
    if not sets:
        raise KeyError(f"{plan.source!r} is not held by any container")
    swap = ReplaceElement(observer, sets[0], plan)
    commands = [*reference_commands(observer, updates.changes), swap]
    return ReplacementStep(plan.description, commands, swap)


class _Rewriter:
    """Gives the references through an element the keys of its replacement."""

    def __init__(
        self,
        path: tuple[str, ...],
        key_type: model.KeyTypes,
        plan: ReplacementPlan,
    ) -> None:
        self._path = path
        self._key_type = key_type
        self._plan = plan

    def rewrite(self, reference: model.Reference) -> model.Reference:
        """Returns the reference with new keys, or itself if nothing changes."""
        inner = reference.referred_semantic_id
        new_inner = None if inner is None else self.rewrite(inner)
        keys = list(reference.key)
        target_type: Any = getattr(reference, "type", None)
        if self._goes_through(reference) and not self.is_orphaned(reference):
            keys, target_type = self._new_keys(reference, keys, target_type)
        if new_inner is inner and all(
            new is old for new, old in zip(keys, reference.key, strict=True)
        ):
            return reference
        if target_type is not None and target_type is not getattr(
            reference, "type", None
        ):
            return model.ModelReference(tuple(keys), target_type, new_inner)
        return with_keys(reference, keys, new_inner)

    def is_orphaned(self, reference: model.Reference) -> bool:
        """Tells whether a reference goes into an item that is gone."""
        if not self._goes_through(reference):
            return False
        depth = len(self._path)
        keys = reference.key
        return len(keys) > depth and (
            keys[depth].value in self._plan.child_keys
            and self._plan.child_keys[keys[depth].value] is None
        )

    def _goes_through(self, reference: model.Reference) -> bool:
        return is_model_reference(reference) and starts_with(
            reference, self._path
        )

    def _new_keys(
        self,
        reference: model.Reference,
        keys: list[model.Key],
        target_type: Any,
    ) -> tuple[list[model.Key], Any]:
        depth = len(self._path)
        element = keys[depth - 1]
        if element.type != self._key_type:
            keys[depth - 1] = model.Key(self._key_type, element.value)
        if len(keys) == depth:
            new_class = self._plan.target_type
            if target_type is None or not issubclass(new_class, target_type):
                target_type = new_class
            return keys, target_type
        moved = self._plan.child_keys.get(keys[depth].value)
        if moved is not None and moved != keys[depth].value:
            keys[depth] = model.Key(keys[depth].type, moved)
        return keys, target_type


def _inside_lost_item(
    slot: ReferenceSlot, path: tuple[str, ...], plan: ReplacementPlan
) -> bool:
    """Tells whether a reference is stored in an item that is gone."""
    anchor_path = path_of(slot.anchor)
    if anchor_path is None or len(anchor_path) <= len(path):
        return False
    if anchor_path[: len(path)] != path:
        return False
    return plan.child_keys.get(anchor_path[len(path)], "kept") is None
