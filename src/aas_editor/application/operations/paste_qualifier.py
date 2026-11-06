"""Pasting a qualifier from the clipboard into an existing qualifier.

"Add qualifier from clipboard" appends a new qualifier. This takes the content
of the qualifier on the clipboard into the qualifier that is selected, which is
what "Paste from clipboard" of a qualifier does in Package Explorer
(F-EDT-07 AC4 and AC5). The type, the value type, the value, the value id, the
semantic id, and the supplemental semantic ids are taken over. The kind stays
as the target has it, so a TemplateQualifier is not turned into a plain one
by text from somewhere else (the original does the same, and its
specification asks to keep it or document the difference).

The change is one group of commands, so it is one undo step. A type that
another qualifier of the owner has refuses the paste (AASd-021), before
anything changes.

Example:
    Pasting into the selected qualifier::

        plan = plan_paste_into_qualifier(target, pasted)
        with stack.group(plan.description):
            for command in paste_qualifier_commands(observer, plan):
                stack.push(command)
"""

from dataclasses import dataclass
from typing import Any

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import SetAttribute
from aas_editor.application.edits import describe
from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.member_json import clone_member


class PasteQualifierError(ValueError):
    """The paste cannot be done. The message is for the user."""


@dataclass(frozen=True, eq=False)
class QualifierPastePlan:
    """What a paste into a qualifier would do.

    Attributes:
        target: The qualifier that changes.
        source: A copy of the pasted qualifier, which belongs to the plan.
        changed: The names of the attributes that get another value. Empty
            when the qualifier has the pasted content already.
        keeps_kind: Whether the pasted qualifier has another kind than the
            target, which stays as it is.
    """

    target: model.Qualifier
    source: model.Qualifier
    changed: tuple[str, ...]
    keeps_kind: bool

    @property
    def description(self) -> str:
        """Text for the undo step."""
        return f"Paste into qualifier {describe(self.target)}"

    @property
    def can_apply(self) -> bool:
        """Whether the paste changes anything."""
        return bool(self.changed)


def plan_paste_into_qualifier(
    target: model.Qualifier, pasted: model.Qualifier
) -> QualifierPastePlan:
    """Plans taking the content of a qualifier into another.

    Args:
        target: The qualifier to change.
        pasted: The qualifier from the clipboard. It is copied, so it can be
            the one that the clipboard code made.

    Returns:
        The plan.

    Raises:
        PasteQualifierError: If another qualifier of the same owner has the
            pasted type.
    """
    source = clone_member(pasted, MemberKind.QUALIFIER)
    assert isinstance(source, model.Qualifier)
    owner: Any = getattr(target, "parent", None)
    for sibling in getattr(owner, "qualifier", ()):
        if sibling is not target and sibling.type == source.type:
            raise PasteQualifierError(
                f"Another qualifier of {describe(owner)} has the type "
                f"'{source.type}'. A type is used once (AASd-021)"
            )
    changed = tuple(
        name
        for name in (
            "type",
            "value_type",
            "value",
            "value_id",
            "semantic_id",
            "supplemental_semantic_id",
        )
        if _differs(target, source, name)
    )
    return QualifierPastePlan(
        target, source, changed, target.kind is not source.kind
    )


def paste_qualifier_commands(
    observer: ModelChangeObserver, plan: QualifierPastePlan
) -> list[Command]:
    """Builds the commands of a paste. Push them inside one group.

    Args:
        observer: Where the commands report.
        plan: What `plan_paste_into_qualifier` made.

    Returns:
        The commands, in the order the SDK accepts: the value is cleared
        before its type changes, and set after.

    Raises:
        PasteQualifierError: If the plan changes nothing.
    """
    if not plan.can_apply:
        raise PasteQualifierError(
            "The qualifier has the pasted content already"
        )
    target, source = plan.target, plan.source
    commands: list[Command] = []

    def set_(name: str, value: object) -> None:
        commands.append(SetAttribute(observer, target, name, value))

    if "value_type" in plan.changed:
        set_("value", None)
        set_("value_type", source.value_type)
        set_("value", source.value)
    elif "value" in plan.changed:
        set_("value", source.value)
    for name in ("type", "value_id", "semantic_id"):
        if name in plan.changed:
            set_(name, getattr(source, name))
    if "supplemental_semantic_id" in plan.changed:
        commands.extend(
            RemoveMember(observer, target.supplemental_semantic_id, held)
            for held in list(target.supplemental_semantic_id)
        )
        commands.extend(
            AddMember(observer, target.supplemental_semantic_id, added)
            for added in list(source.supplemental_semantic_id)
        )
    return commands


def _differs(
    target: model.Qualifier, source: model.Qualifier, name: str
) -> bool:
    if name == "supplemental_semantic_id":
        return list(target.supplemental_semantic_id) != list(
            source.supplemental_semantic_id
        )
    mine, theirs = getattr(target, name), getattr(source, name)
    return type(mine) is not type(theirs) or mine != theirs
