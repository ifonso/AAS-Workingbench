"""Renaming an id or an idShort and updating the references (decision D10).

A reference holds the ids and idShorts of its path as keys. Changing the id of
a shell, submodel or concept description, or the idShort of an element, leaves
every reference that goes through it pointing at nothing, unless the keys
change too. `plan_rename_id` and `plan_rename_id_short` find those references
without changing anything, so that a dialog can show them, and
`RenameCommand` makes the rename and the updates as one step.

Example:
    Renaming a submodel after showing the preview::

        plan = plan_rename_id(package.objStore, submodel, new_id)
        show(plan.changes)
        stack.push(RenameCommand(observer, plan))
        stack.undo()
"""

from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandGroup
from aas_editor.application.edits import ReplaceMember
from aas_editor.application.edits import SetAttribute
from aas_editor.application.edits import describe
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.references import reference_commands
from aas_editor.domain import ordering
from aas_editor.domain.ids import fix_id_short
from aas_editor.domain.ids import id_short_prefix
from aas_editor.domain.ids import is_valid_id_short
from aas_editor.domain.ids import unique_id_short
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import ReferenceSlot
from aas_editor.domain.references import Usage
from aas_editor.domain.references import is_model_reference
from aas_editor.domain.references import map_keys
from aas_editor.domain.references import path_of
from aas_editor.domain.references import starts_with

# The longest id the SDK accepts (Identifier).
MAX_ID_LENGTH = 2048

# Gives the key to use for a key of a reference at a position.
_KeySwap = Callable[[model.Reference, int, model.Key], model.Key]


class RenameError(ValueError):
    """A rename that cannot be made, with a message for the user."""


class DuplicateIdError(RenameError):
    """Another object of the package has the id already.

    Attributes:
        id: The id that is taken.
        other: The object that has it.
    """

    def __init__(self, id_: str, other: model.Identifiable) -> None:
        """Creates the error.

        Args:
            id_: The id that is taken.
            other: The object that has it.
        """
        super().__init__(
            f"The id '{id_}' belongs to another {type(other).__name__} of "
            "this package already. Two objects cannot share an id."
        )
        self.id = id_
        self.other = other


class InvalidIdError(RenameError):
    """The text is no id."""


class InvalidIdShortError(RenameError):
    """The text is no valid idShort, or a sibling has the idShort already.

    Attributes:
        text: What was entered.
        suggestion: A valid idShort that is free among the siblings and close
            to the text.
    """

    def __init__(self, message: str, text: str, suggestion: str) -> None:
        """Creates the error.

        Args:
            message: What is wrong, for the user.
            text: What was entered.
            suggestion: A valid idShort to use instead.
        """
        super().__init__(message)
        self.text = text
        self.suggestion = suggestion


@dataclass(frozen=True, eq=False)
class RenamePlan:
    """What a rename would change, found without changing anything.

    Attributes:
        target: The shell, submodel, concept description or element.
        attribute: `id` or `id_short`.
        old: The current value.
        new: The value to set.
        changes: The references that get other keys.
        not_updated: The references that would break a rule of references
            with the new keys, and so stay as they are. This is not expected.
    """

    target: model.Referable
    attribute: str
    old: str | None
    new: str
    changes: tuple[ReferenceChange, ...]
    not_updated: tuple[ReferenceSlot, ...] = ()

    @property
    def is_noop(self) -> bool:
        """Whether the target has the new value already."""
        return self.old == self.new


def plan_rename_id(
    objects: Iterable[model.Identifiable],
    target: model.Identifiable,
    new_id: str,
) -> RenamePlan:
    """Plans a new id for a shell, submodel or concept description.

    Args:
        objects: The identifiables of the package.
        target: The object to rename.
        new_id: The new id. Spaces around it are dropped.

    Returns:
        The plan. Its changes are the references that have the old id in a
        key, wherever they are stored.

    Raises:
        InvalidIdError: If the id is empty or too long.
        DuplicateIdError: If another object has the id.
    """
    new_id = new_id.strip()
    if not new_id:
        raise InvalidIdError("The id must not be empty.")
    if len(new_id) > MAX_ID_LENGTH:
        raise InvalidIdError(
            f"The id has {len(new_id)} characters, at most {MAX_ID_LENGTH} "
            "are allowed."
        )
    index = ReferenceIndex(objects)
    for other in index.with_id(new_id):
        if other is not target:
            raise DuplicateIdError(new_id, other)
    changes, failed = _id_changes(index, target, target.id, new_id)
    return RenamePlan(target, "id", target.id, new_id, changes, failed)


def plan_rename_id_short(
    objects: Iterable[model.Identifiable],
    target: model.Referable,
    new_id_short: str,
) -> RenamePlan:
    """Plans a new idShort for an element or an identifiable.

    Args:
        objects: The identifiables of the package.
        target: The object to rename.
        new_id_short: The new idShort.

    Returns:
        The plan. Its changes are the model references that go through the
        element: the key with its idShort gets the new one.

    Raises:
        RenameError: If the target is an item of a list, which has no idShort.
        InvalidIdShortError: If the text is not a valid idShort, or a sibling
            has it. The error suggests another one.
    """
    if isinstance(target.parent, model.SubmodelElementList):
        raise RenameError(
            "An item of a list has no idShort. Its position names it."
        )
    taken = _sibling_id_shorts(target)
    prefix = id_short_prefix(target)
    if not is_valid_id_short(new_id_short):
        raise InvalidIdShortError(
            f"'{new_id_short}' is not a valid idShort. It starts with a "
            "letter, has only letters, digits, underscores and hyphens, and "
            "does not end with a hyphen.",
            new_id_short,
            unique_id_short(fix_id_short(new_id_short, prefix), taken),
        )
    if new_id_short in taken:
        raise InvalidIdShortError(
            f"A sibling has the idShort '{new_id_short}' already.",
            new_id_short,
            unique_id_short(new_id_short, taken),
        )
    if isinstance(target, model.Identifiable):
        # References name an identifiable by its id, never by its idShort.
        return RenamePlan(target, "id_short", target.id_short, new_id_short, ())
    path = path_of(target)
    changes: tuple[ReferenceChange, ...] = ()
    failed: tuple[ReferenceSlot, ...] = ()
    if path is not None:
        changes, failed = _id_short_changes(
            ReferenceIndex(objects), target, path, new_id_short
        )
    return RenamePlan(
        target, "id_short", target.id_short, new_id_short, changes, failed
    )


def suggest_id_short(target: model.Referable, text: str) -> str:
    """Suggests a valid idShort that no sibling has, as close to a text as can be.

    Args:
        target: The element that would get the idShort.
        text: What the user typed.

    Returns:
        The text if it is valid and free, otherwise a repaired and numbered
        variant.
    """
    fixed = fix_id_short(text, id_short_prefix(target))
    return unique_id_short(fixed, _sibling_id_shorts(target))


def reference_changes_for_new_id(
    objects: Iterable[model.Identifiable],
    old: model.Identifiable,
    new_id: str,
) -> tuple[ReferenceChange, ...]:
    """Finds the references to change when an object is replaced by another.

    Args:
        objects: The identifiables of the package, with `old` in it.
        old: The object that goes away.
        new_id: The id of the object that takes its place.

    Returns:
        The references that have the id of `old` in a key.

    Raises:
        DuplicateIdError: If another object has the new id.
    """
    index = ReferenceIndex(objects)
    for other in index.with_id(new_id):
        if other is not old:
            raise DuplicateIdError(new_id, other)
    return _id_changes(index, old, old.id, new_id)[0]


class RenameCommand(CommandGroup):
    """The rename of an id or idShort and the updates of its references.

    It is one step: undo restores the old value and the old references.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        plan: RenamePlan,
        origin: object | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where the commands report.
            plan: What `plan_rename_id` or `plan_rename_id_short` made.
            origin: The subscriber that updates itself when it pushes the
                command.
        """
        rename = SetAttribute(
            observer, plan.target, plan.attribute, plan.new, origin=origin
        )
        # The rename comes first, so a refused value changes nothing.
        super().__init__(
            f"Rename {describe(plan.target)}",
            [rename, *reference_commands(observer, plan.changes)],
        )
        self._plan = plan

    @property
    def plan(self) -> RenamePlan:
        """What the command does."""
        return self._plan

    @property
    def owner(self) -> object:
        """The object that is renamed."""
        return self._plan.target

    @property
    def name(self) -> str:
        """The attribute that is renamed."""
        return self._plan.attribute


class ReplaceIdentifiable(CommandGroup):
    """Replaces a shell, submodel or concept description by another object.

    The references to the old id get the id of the new object, in one step.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        objects: Iterable[model.Identifiable],
        container: object,
        old: model.Identifiable,
        new: model.Identifiable,
        origin: object | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where the commands report.
            objects: The identifiables of the package.
            container: The object store of the package.
            old: The object to replace.
            new: The object that takes its place.
            origin: The subscriber that updates itself when it pushes the
                command.

        Raises:
            DuplicateIdError: If another object has the id of `new`.
        """
        changes = reference_changes_for_new_id(objects, old, new.id)
        commands: list[Command] = [
            ReplaceMember(observer, container, old, new, origin=origin)
        ]
        commands.extend(reference_commands(observer, changes))
        super().__init__(f"Edit {describe(old)}", commands)
        self._new = new
        self._changes = changes

    @property
    def new(self) -> model.Identifiable:
        """The object that takes the place of the old one."""
        return self._new

    @property
    def changes(self) -> tuple[ReferenceChange, ...]:
        """The references that get the id of the new object."""
        return self._changes


def _sibling_id_shorts(target: model.Referable) -> Collection[str]:
    """Returns the idShorts of the other members of the namespaces of target."""
    names: set[str] = set()
    for namespace_set in ordering.namespace_sets_of(target):
        for member in cast("Iterable[model.Referable]", namespace_set):
            if member is not target and member.id_short:
                names.add(member.id_short)
    return names


def _id_changes(
    index: ReferenceIndex,
    target: model.Identifiable,
    old_id: str,
    new_id: str,
) -> tuple[tuple[ReferenceChange, ...], tuple[ReferenceSlot, ...]]:
    def swap(
        reference: model.Reference, position: int, key: model.Key
    ) -> model.Key:
        # A model reference names its identifiable in the first key only.
        is_id_position = position == 0 or not is_model_reference(reference)
        if key.value == old_id and is_id_position:
            return model.Key(key.type, new_id)
        return key

    if old_id == new_id:
        return (), ()
    usages = index.usages_of([target], include_inside=True)
    return _rewrite(_slots_of(usages), swap)


def _id_short_changes(
    index: ReferenceIndex,
    target: model.Referable,
    path: tuple[str, ...],
    new_id_short: str,
) -> tuple[tuple[ReferenceChange, ...], tuple[ReferenceSlot, ...]]:
    last = len(path) - 1

    def swap(
        reference: model.Reference, position: int, key: model.Key
    ) -> model.Key:
        if (
            position == last
            and is_model_reference(reference)
            and starts_with(reference, path)
        ):
            return model.Key(key.type, new_id_short)
        return key

    usages = index.usages_of([target], include_inside=True)
    return _rewrite(_slots_of(usages), swap)


def _slots_of(usages: Iterable[Usage]) -> list[ReferenceSlot]:
    slots: dict[int, ReferenceSlot] = {}
    for usage in usages:
        slots.setdefault(id(usage.slot), usage.slot)
    return list(slots.values())


def _rewrite(
    slots: Iterable[ReferenceSlot],
    swap: _KeySwap,
) -> tuple[tuple[ReferenceChange, ...], tuple[ReferenceSlot, ...]]:
    changes: list[ReferenceChange] = []
    failed: list[ReferenceSlot] = []
    for slot in slots:
        try:
            after = map_keys(slot.reference, swap)
        except model.AASConstraintViolation:
            failed.append(slot)
            continue
        if after is not slot.reference:
            changes.append(ReferenceChange(slot, after))
    return tuple(changes), tuple(failed)
