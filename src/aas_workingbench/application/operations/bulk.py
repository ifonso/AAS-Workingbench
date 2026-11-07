"""Removing an attribute from a submodel and everything below it (F-EDT-03).

Package Explorer's "Remove attributes" asks which attributes to remove from
the submodel and all of its elements, then asks once more before it does.
`plan_remove_attributes` finds what would go without changing anything, so a
dialog can name it in the confirmation. `removal_commands` turns the plan into
commands, and all of them are one undo step.

Example:
    Removing all qualifiers and extensions::

        plan = plan_remove_attributes(
            submodel,
            {RemovableAttribute.QUALIFIERS, RemovableAttribute.EXTENSIONS},
        )
        with stack.group(plan.description):
            for command in removal_commands(observer, plan):
                stack.push(command)
"""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass
import enum
from typing import Any

from basyx.aas import model

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.edits import RemoveMember
from aas_workingbench.application.edits import SetAttribute
from aas_workingbench.domain.references import describe_object
from aas_workingbench.domain.walking import descendants


class RemovableAttribute(enum.Enum):
    """The attributes that can be removed from a submodel and its elements."""

    QUALIFIERS = ("qualifier", "qualifiers", "qualifier")
    EXTENSIONS = ("extension", "extensions", "extension")
    DESCRIPTIONS = ("description", "descriptions", "description")
    DISPLAY_NAMES = ("display_name", "display names", "display name")
    CATEGORIES = ("category", "categories", "category")

    @property
    def attribute(self) -> str:
        """The name of the attribute on the SDK objects."""
        return self.value[0]

    @property
    def plural(self) -> str:
        """The name for several of them, such as `qualifiers`."""
        return self.value[1]

    @property
    def singular(self) -> str:
        """The name for one of them, such as `qualifier`."""
        return self.value[2]

    @property
    def is_member_set(self) -> bool:
        """Whether the attribute is a set of members, not a single value."""
        return self in (
            RemovableAttribute.QUALIFIERS,
            RemovableAttribute.EXTENSIONS,
        )


@dataclass(frozen=True, eq=False)
class Removal:
    """One attribute of one object that the plan takes away.

    Attributes:
        owner: The submodel or element that has the attribute.
        attribute: Which attribute it is.
        members: For qualifiers and extensions, the ones to remove. Empty for
            a single value.
    """

    owner: model.Referable
    attribute: RemovableAttribute
    members: tuple[Any, ...] = ()

    @property
    def count(self) -> int:
        """How many items go: the members, or one for a single value."""
        return len(self.members) if self.attribute.is_member_set else 1


@dataclass(frozen=True, eq=False)
class RemovalPlan:
    """What a removal would take away, found without changing anything.

    Attributes:
        submodel: The submodel the removal starts at.
        removals: Every attribute of every object that goes.
        examined: How many objects were looked at: the submodel and the
            elements below it.
    """

    submodel: model.Submodel
    removals: tuple[Removal, ...]
    examined: int

    @property
    def is_empty(self) -> bool:
        """Whether nothing would be removed."""
        return not self.removals

    def count(self, attribute: RemovableAttribute) -> int:
        """Returns how many items of an attribute would go."""
        return sum(r.count for r in self.removals if r.attribute is attribute)

    def owners(self, attribute: RemovableAttribute) -> int:
        """Returns on how many objects an attribute would be removed."""
        return sum(1 for r in self.removals if r.attribute is attribute)

    @property
    def summary(self) -> str:
        """Names what goes, such as `3 qualifiers and 2 extensions`."""
        parts: list[str] = []
        for attribute in RemovableAttribute:
            number = self.count(attribute)
            if number:
                name = attribute.singular if number == 1 else attribute.plural
                parts.append(f"{number} {name}")
        if not parts:
            return "nothing"
        if len(parts) == 1:
            return parts[0]
        return f"{', '.join(parts[:-1])} and {parts[-1]}"

    @property
    def description(self) -> str:
        """The text of the undo step."""
        return f"Remove {self.summary} from {describe_object(self.submodel)}"

    @property
    def question(self) -> str:
        """The confirmation, naming what goes and where."""
        below = self.examined - 1
        elements = f"{below} element{'s' if below != 1 else ''}"
        return (
            f"Remove {self.summary} from {describe_object(self.submodel)} "
            f"and its {elements}? This is one step in the history, so Undo "
            "brings it all back."
        )


def _owned(
    owner: model.Referable, attribute: RemovableAttribute
) -> Removal | None:
    value = getattr(owner, attribute.attribute, None)
    if attribute.is_member_set:
        members = tuple(value) if value is not None else ()
        return Removal(owner, attribute, members) if members else None
    if value:
        return Removal(owner, attribute)
    return None


def plan_remove_attributes(
    submodel: model.Submodel, attributes: Collection[RemovableAttribute]
) -> RemovalPlan:
    """Finds what removing attributes from a submodel and below would take.

    Args:
        submodel: The submodel to start at.
        attributes: Which attributes to remove.

    Returns:
        The plan, in document order: the submodel first, then its elements,
        annotations and entity statements included.
    """
    owners: list[model.Referable] = [submodel, *descendants(submodel)]
    removals = [
        removal
        for owner in owners
        for attribute in RemovableAttribute
        if attribute in attributes
        if (removal := _owned(owner, attribute)) is not None
    ]
    return RemovalPlan(submodel, tuple(removals), len(owners))


def removal_commands(
    observer: ModelChangeObserver, plan: RemovalPlan
) -> list[Command]:
    """Builds the commands for a plan. Push them inside one group."""
    commands: list[Command] = []
    for removal in plan.removals:
        container: Any = getattr(removal.owner, removal.attribute.attribute)
        if removal.attribute.is_member_set:
            commands.extend(
                RemoveMember(observer, container, member)
                for member in removal.members
            )
        else:
            commands.append(
                SetAttribute(
                    observer,
                    removal.owner,
                    removal.attribute.attribute,
                    None,
                    description=(
                        f"Remove {removal.attribute.singular} of "
                        f"{describe_object(removal.owner)}"
                    ),
                )
            )
    return commands


def available_attributes(
    submodel: model.Submodel,
) -> dict[RemovableAttribute, int]:
    """Counts what each attribute would take, to show next to its check box."""
    everything: Iterable[RemovableAttribute] = tuple(RemovableAttribute)
    plan = plan_remove_attributes(submodel, set(everything))
    return {
        attribute: plan.count(attribute) for attribute in RemovableAttribute
    }
