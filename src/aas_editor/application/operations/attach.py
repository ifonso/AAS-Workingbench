"""Adding a qualifier, extension, specific asset id or data specification to many.

The member comes from a preset or from the clipboard (see
`aas_editor.domain.presets` and `aas_editor.domain.clipboard_json`). Each
owner needs a member of its own, because the SDK lets a qualifier or extension
belong to one owner only, so the caller gives `plan_attach` a factory that
makes new members for each call.

`plan_attach` decides for each owner and member, without changing anything:

- `ADD`: the member is added at the end.
- `SKIPPED`: the owner cannot have this kind, or has the member already, such
  as a qualifier of the same type (AASd-021) or an extension of the same name
  (AASd-077). The other owners still get theirs, and the dialog names the
  skipped ones with the reason.

Nothing replaces an existing member. `attach_commands` builds the commands,
which belong in one group: one undo step, and a failure undoes what was done.

Example:
    Adding a qualifier preset to the selected elements::

        plan = plan_attach(
            selected, MemberKind.QUALIFIER, lambda: [preset.make()]
        )
        if plan.can_apply:
            with stack.group(plan.description):
                for command in attach_commands(observer, plan):
                    stack.push(command)
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
import enum
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import describe
from aas_editor.domain.member_json import Member
from aas_editor.domain.member_json import MemberKind


class AttachStatus(enum.Enum):
    """What happens to one member for one owner."""

    ADD = "add"
    SKIPPED = "skipped"


@dataclass(frozen=True, eq=False)
class AttachEntry:
    """One owner and what it gets.

    Attributes:
        owner: The object that would get the member.
        member: The new member, or None if the owner cannot have the kind.
        status: Whether it is added.
        reason: Why it is skipped, or empty.
    """

    owner: object
    member: Member | None
    status: AttachStatus
    reason: str = ""


@dataclass(frozen=True, eq=False)
class AttachPlan:
    """What adding members to the owners would do.

    Attributes:
        kind: What is added.
        entries: One entry for each owner and member.
    """

    kind: MemberKind
    entries: tuple[AttachEntry, ...]

    @property
    def to_add(self) -> list[AttachEntry]:
        """The entries that add a member."""
        return [e for e in self.entries if e.status is AttachStatus.ADD]

    @property
    def skipped(self) -> list[AttachEntry]:
        """The entries that add nothing."""
        return [e for e in self.entries if e.status is AttachStatus.SKIPPED]

    @property
    def skipped_count(self) -> int:
        """How many entries add nothing."""
        return len(self.skipped)

    @property
    def can_apply(self) -> bool:
        """Whether anything is added."""
        return bool(self.to_add)

    @property
    def description(self) -> str:
        """Text for the undo step."""
        owners: list[object] = []
        for entry in self.to_add:
            if not any(entry.owner is held for held in owners):
                owners.append(entry.owner)
        label = self.kind.label
        if len(owners) == 1:
            return f"Add {label} to {describe(owners[0])}"
        return f"Add {label} to {len(owners)} items"


def refusal(owner: object, kind: MemberKind) -> str | None:
    """Tells why an owner cannot have the kind of member.

    Args:
        owner: The object that would get the member.
        kind: What would be added.

    Returns:
        A message for the user, or None if the owner can have it.
    """
    if kind is MemberKind.SPECIFIC_ASSET_ID:
        if isinstance(owner, model.Entity):
            if owner.entity_type is model.EntityType.CO_MANAGED_ENTITY:
                return (
                    "A co-managed entity has neither a globalAssetId nor a "
                    "specificAssetId (AASd-014)"
                )
            return None
        if isinstance(owner, model.AssetInformation):
            return None
    elif isinstance(owner, _OWNER_TYPES[kind]):
        return None
    return f"A {type(owner).__name__} cannot have a {kind.label}"


def can_hold(owner: object, kind: MemberKind) -> bool:
    """Tells whether an owner can have members of the kind."""
    return refusal(owner, kind) is None


def plan_attach(
    owners: Iterable[object],
    kind: MemberKind,
    make: Callable[[], Sequence[Member]],
) -> AttachPlan:
    """Plans adding members to each owner.

    Args:
        owners: The selected objects, in selection order. One listed twice
            counts once.
        kind: What is added.
        make: Gives new members, without a parent, for one owner. It is
            called once for each owner that can have the kind.

    Returns:
        The plan.
    """
    entries: list[AttachEntry] = []
    seen: set[int] = set()
    for owner in owners:
        if id(owner) in seen:
            continue
        seen.add(id(owner))
        reason = refusal(owner, kind)
        if reason is not None:
            entries.append(
                AttachEntry(owner, None, AttachStatus.SKIPPED, reason)
            )
            continue
        taken = _taken(owner, kind)
        for member in make():
            problem = _conflict(member, kind, taken)
            if problem:
                entries.append(
                    AttachEntry(owner, member, AttachStatus.SKIPPED, problem)
                )
                continue
            taken.append(member)
            entries.append(AttachEntry(owner, member, AttachStatus.ADD))
    return AttachPlan(kind, tuple(entries))


def attach_commands(
    observer: ModelChangeObserver, plan: AttachPlan
) -> list[Command]:
    """Builds the commands that add the members. Push them inside one group.

    Args:
        observer: Where the commands report.
        plan: What `plan_attach` made.

    Returns:
        One add for each member that is added.

    Raises:
        ValueError: If the plan has nothing to add.
    """
    if not plan.can_apply:
        raise ValueError("There is nothing to add")
    return [
        AddMember(
            observer,
            getattr(entry.owner, plan.kind.attribute),
            entry.member,
            description=f"Add {plan.kind.label} to {describe(entry.owner)}",
        )
        for entry in plan.to_add
    ]


_OWNER_TYPES: dict[MemberKind, type | tuple[type, ...]] = {
    MemberKind.QUALIFIER: model.Qualifiable,
    MemberKind.EXTENSION: model.HasExtension,
    MemberKind.SPECIFIC_ASSET_ID: (model.AssetInformation, model.Entity),
    MemberKind.EMBEDDED_DATA_SPECIFICATION: model.HasDataSpecification,
}


def _taken(owner: object, kind: MemberKind) -> list[Member]:
    """Returns the members the owner has, which new ones must not repeat."""
    held = getattr(owner, kind.attribute)
    return list(cast("Iterable[Member]", held))


def _conflict(member: Member, kind: MemberKind, taken: list[Member]) -> str:
    """Tells why the member cannot be added next to the taken ones."""
    if isinstance(member, model.Qualifier):
        if any(cast("Any", t).type == member.type for t in taken):
            return (
                f"It has a qualifier of the type '{member.type}' already, or "
                "gets one from an earlier entry (AASd-021)"
            )
    elif isinstance(member, model.Extension):
        if any(cast("Any", t).name == member.name for t in taken):
            return (
                f"It has an extension named '{member.name}' already, or gets "
                "one from an earlier entry (AASd-077)"
            )
    elif isinstance(member, model.SpecificAssetId):
        if any(t == member for t in taken):
            return "It has this specific asset id already"
    elif any(
        cast("Any", t).data_specification == member.data_specification
        for t in taken
    ):
        return "It has this data specification already"
    return ""
