"""Replacing and removing the references stored in AAS objects.

References are immutable, so a change to a reference replaces it where it is
stored. `ReferenceChange` says which stored reference becomes which, and
`reference_commands` turns changes into commands. A reference can be:

- an attribute of an object, such as `semantic_id`, which is set,
- a member of a list or set, such as a supplemental semantic id or a
  reference of a shell to a submodel, which is replaced in place, or
- a field of an object that cannot be changed, such as a `SpecificAssetId`,
  which is replaced as a whole by a copy with the new reference.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import ReplaceMember
from aas_editor.application.edits import SetAttribute
from aas_editor.domain.references import ReferenceSlot


@dataclass(frozen=True, eq=False)
class ReferenceChange:
    """One stored reference that is replaced or taken away.

    Attributes:
        slot: Where the reference is stored.
        before: The reference as stored, which is `slot.reference`.
        after: The reference to store instead, or None to take it away.
    """

    slot: ReferenceSlot
    after: model.Reference | None

    @property
    def before(self) -> model.Reference:
        """The reference as it is stored now."""
        return self.slot.reference

    @property
    def is_removal(self) -> bool:
        """Whether the reference is taken away instead of replaced."""
        return self.after is None


def reference_commands(
    observer: ModelChangeObserver, changes: Sequence[ReferenceChange]
) -> list[Command]:
    """Builds the commands that make the changes.

    Members that are taken away come before attributes that are cleared, so
    that a semantic id is never cleared while a supplemental one is left.

    Args:
        observer: Where the commands report.
        changes: The references to replace or remove, each slot once.

    Returns:
        The commands, in the order to apply them.

    Raises:
        ValueError: If a reference is stored in an object that cannot be
            changed or replaced, which only `SpecificAssetId` can be.
    """
    members: list[Command] = []
    attributes: list[Command] = []
    frozen: dict[int, list[ReferenceChange]] = {}
    for change in changes:
        slot = change.slot
        if slot.is_frozen:
            frozen.setdefault(id(slot.owner), []).append(change)
        elif slot.is_member:
            members.append(_member_command(observer, change))
        else:
            attributes.append(
                SetAttribute(
                    observer,
                    slot.owner,
                    slot.attribute,
                    change.after,
                    description=f"Edit {slot.attribute}",
                )
            )
    replaced = [_frozen_command(observer, owned) for owned in frozen.values()]
    return [*members, *replaced, *attributes]


def _member_command(
    observer: ModelChangeObserver, change: ReferenceChange
) -> Command:
    container = cast("Any", change.slot.container)
    if change.after is None or _already_holds(container, change.after):
        # The same reference is there already, so only the old one goes.
        return RemoveMember(observer, container, change.before)
    return ReplaceMember(observer, container, change.before, change.after)


def _already_holds(container: object, reference: model.Reference) -> bool:
    return isinstance(container, set) and reference in container


def _frozen_command(
    observer: ModelChangeObserver, changes: Sequence[ReferenceChange]
) -> Command:
    slot = changes[0].slot
    owner = slot.owner
    if not isinstance(owner, model.SpecificAssetId) or (
        slot.owner_container is None
    ):
        raise ValueError(
            f"Cannot change the references of a {type(owner).__name__}"
        )
    replacement = _rebuilt_specific_asset_id(owner, changes)
    return ReplaceMember(observer, slot.owner_container, owner, replacement)


def _rebuilt_specific_asset_id(
    owner: model.SpecificAssetId, changes: Sequence[ReferenceChange]
) -> model.SpecificAssetId:
    """Copies a specific asset id with its references replaced."""
    after = {id(change.before): change.after for change in changes}

    def swap(reference: model.Reference | None) -> model.Reference | None:
        if reference is None or id(reference) not in after:
            return reference
        return after[id(reference)]

    subject = swap(owner.external_subject_id)
    semantic_id = swap(owner.semantic_id)
    supplemental = [
        replaced
        for reference in owner.supplemental_semantic_id
        if (replaced := swap(reference)) is not None
    ]
    return model.SpecificAssetId(
        owner.name,
        owner.value,
        cast("model.ExternalReference | None", subject),
        semantic_id,
        supplemental,
    )
