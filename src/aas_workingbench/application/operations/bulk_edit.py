"""Changing one attribute of many objects, and removing extensions from many.

`plan_change_attribute` applies a pattern (see
`aas_workingbench.domain.rename_pattern`) to an attribute of each selected object,
without changing anything, and says for each object what would happen:

- `CHANGE`: the attribute gets the new text.
- `UNCHANGED`: the pattern gives the text it has.
- `SKIPPED`: the object has nothing to change, such as no text in the chosen
  language. The others still change, and the dialog says which were skipped.
- `REFUSED`: the new text is not allowed, such as an idShort that is invalid
  or taken. One refused object stops the whole change, so the package never
  holds half of a rename. The reason names the problem.

A rename of an idShort updates the references through the elements in the
same step, with `plan_rename_id_short`'s rules (`rewrite_keys`), and several
renames at once are checked against the names they leave, so that two
elements may swap names. `change_commands` builds the commands, which belong
in one group, so that the change is one undo step and a failure undoes what
was done.

Example:
    Putting a prefix before the idShort of the selected elements::

        plan = plan_change_attribute(
            package.objStore, selected, BulkAttribute.ID_SHORT, "ABC_{old}"
        )
        if plan.can_apply:
            with stack.group(plan.description):
                for command in change_commands(observer, plan):
                    stack.push(command)
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import replace
import enum
from typing import Any
from typing import cast
import uuid

from basyx.aas import model

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.edits import RemoveMember
from aas_workingbench.application.edits import ReplaceMember
from aas_workingbench.application.edits import SetAttribute
from aas_workingbench.application.edits import describe
from aas_workingbench.application.operations.references import KeyRename
from aas_workingbench.application.operations.references import ReferenceChange
from aas_workingbench.application.operations.references import (
    reference_commands,
)
from aas_workingbench.application.operations.references import rewrite_keys
from aas_workingbench.domain import ordering
from aas_workingbench.domain import value_types
from aas_workingbench.domain.ids import is_valid_id_short
from aas_workingbench.domain.references import ReferenceIndex
from aas_workingbench.domain.references import ReferenceSlot
from aas_workingbench.domain.references import path_of
from aas_workingbench.domain.rename_pattern import Pattern
from aas_workingbench.domain.rename_pattern import PatternContext
from aas_workingbench.domain.rename_pattern import PatternError
from aas_workingbench.domain.rename_pattern import compile_pattern
from aas_workingbench.domain.rename_pattern import render
from aas_workingbench.domain.typed_values import prepare_edit


class BulkAttribute(enum.Enum):
    """The attributes that a pattern can change."""

    ID_SHORT = "idShort"
    DESCRIPTION = "description"
    DISPLAY_NAME = "display name"
    VALUE = "value as text"

    @property
    def label(self) -> str:
        """The name for the user."""
        return str(self.value)

    @property
    def uses_language(self) -> bool:
        """Whether the attribute is a text per language."""
        return self is not BulkAttribute.ID_SHORT


class EntryStatus(enum.Enum):
    """What would happen to one selected object."""

    CHANGE = "change"
    UNCHANGED = "unchanged"
    SKIPPED = "skipped"
    REFUSED = "refused"


@dataclass(frozen=True, eq=False)
class BulkEntry:
    """One selected object and what the pattern does to it.

    Attributes:
        target: The object.
        old: The text of the attribute now, or None if it has none.
        new: The text it would get, or None if there is none.
        status: What happens to it.
        reason: Why it is skipped or refused, or empty.
        prepared: The value to assign for a typed value, or None.
    """

    target: model.Referable
    old: str | None
    new: str | None
    status: EntryStatus
    reason: str = ""
    prepared: object = None


@dataclass(frozen=True, eq=False)
class BulkPlan:
    """What a change of an attribute would do, found without changing it.

    Attributes:
        attribute: The attribute that changes.
        language: The language of a text attribute.
        pattern: The pattern as typed.
        entries: One entry for each selected object, in selection order.
        changes: The references that get other keys after an idShort rename.
        not_updated: References that would break a rule with the new keys.
            None is expected.
        pattern_error: Why the pattern cannot be read, or None.
    """

    attribute: BulkAttribute
    language: str
    pattern: str
    entries: tuple[BulkEntry, ...]
    changes: tuple[ReferenceChange, ...] = ()
    not_updated: tuple[ReferenceSlot, ...] = ()
    pattern_error: str | None = None

    def with_status(self, status: EntryStatus) -> list[BulkEntry]:
        """Returns the entries that have a status."""
        return [entry for entry in self.entries if entry.status is status]

    @property
    def to_change(self) -> list[BulkEntry]:
        """The entries that would change."""
        return self.with_status(EntryStatus.CHANGE)

    @property
    def refused(self) -> list[BulkEntry]:
        """The entries whose new text is not allowed."""
        return self.with_status(EntryStatus.REFUSED)

    @property
    def skipped(self) -> list[BulkEntry]:
        """The entries that have nothing to change."""
        return self.with_status(EntryStatus.SKIPPED)

    @property
    def can_apply(self) -> bool:
        """Whether the change can be made: something changes, nothing is refused."""
        return (
            self.pattern_error is None
            and not self.not_updated
            and not self.refused
            and bool(self.to_change)
        )

    @property
    def reference_count(self) -> int:
        """How many references get other keys."""
        return len(self.changes)

    @property
    def description(self) -> str:
        """Text for the undo step."""
        changing = self.to_change
        if len(changing) == 1:
            return f"Change {self.attribute.label} of {describe(changing[0].target)}"
        return f"Change {self.attribute.label} of {len(changing)} items"


def plan_change_attribute(
    objects: Iterable[model.Identifiable],
    targets: Iterable[model.Referable],
    attribute: BulkAttribute,
    pattern: str,
    language: str = "en",
) -> BulkPlan:
    """Plans a change of one attribute of the selected objects.

    Args:
        objects: The identifiables of the package, to find references.
        targets: The selected objects, in the order of the selection. An
            object listed twice counts once.
        attribute: What to change.
        pattern: The pattern for the new text.
        language: The language of a text attribute. An object without a text
            in this language is skipped.

    Returns:
        The plan. A pattern that cannot be read gives a plan with
        `pattern_error` and no entries.
    """
    try:
        compiled = compile_pattern(pattern)
    except PatternError as error:
        return BulkPlan(
            attribute, language, pattern, (), pattern_error=str(error)
        )
    chosen = _unique(targets)
    entries = [
        _plan_entry(compiled, target, attribute, language, number, len(chosen))
        for number, target in enumerate(chosen, start=1)
    ]
    if attribute is BulkAttribute.ID_SHORT:
        entries = _check_siblings(entries)
    plan = BulkPlan(attribute, language, pattern, tuple(entries))
    if attribute is BulkAttribute.ID_SHORT and not plan.refused:
        changes, failed = _reference_changes(objects, plan.to_change)
        plan = replace(plan, changes=changes, not_updated=failed)
    return plan


def change_commands(
    observer: ModelChangeObserver, plan: BulkPlan
) -> list[Command]:
    """Builds the commands of a change. Push them inside one group.

    Args:
        observer: Where the commands report.
        plan: What `plan_change_attribute` made.

    Returns:
        The commands: the new texts, then the new keys of references.

    Raises:
        ValueError: If the plan cannot be applied.
    """
    if not plan.can_apply:
        raise ValueError("The change cannot be applied")
    if plan.attribute is BulkAttribute.ID_SHORT:
        commands = _id_short_commands(observer, plan.to_change)
        commands.extend(reference_commands(observer, plan.changes))
        return commands
    return [_text_command(observer, plan, entry) for entry in plan.to_change]


def _unique(targets: Iterable[model.Referable]) -> list[model.Referable]:
    seen: set[int] = set()
    found: list[model.Referable] = []
    for target in targets:
        if id(target) not in seen:
            seen.add(id(target))
            found.append(target)
    return found


def _plan_entry(
    pattern: Pattern,
    target: model.Referable,
    attribute: BulkAttribute,
    language: str,
    number: int,
    count: int,
) -> BulkEntry:
    old, skip = _read_old(target, attribute, language)
    if skip:
        return BulkEntry(target, old, None, EntryStatus.SKIPPED, skip)
    text = old or ""
    parent = getattr(target.parent, "id_short", None)
    context = PatternContext(
        old=text,
        number=number,
        count=count,
        id_short=target.id_short or "",
        parent=parent if isinstance(parent, str) else "",
        type_name=type(target).__name__,
    )
    try:
        new = render(pattern, context)
    except PatternError as error:
        return BulkEntry(target, old, None, EntryStatus.REFUSED, str(error))
    if new == old:
        return BulkEntry(target, old, new, EntryStatus.UNCHANGED)
    return _checked(target, attribute, language, old, new)


def _read_old(
    target: model.Referable, attribute: BulkAttribute, language: str
) -> tuple[str | None, str]:
    """Returns the text now, and why there is nothing to change, or empty."""
    if attribute is BulkAttribute.ID_SHORT:
        if isinstance(target.parent, model.SubmodelElementList):
            return (
                None,
                "An item of a list has no idShort. Its position names it.",
            )
        return target.id_short or "", ""
    texts = _texts_of(target, attribute)
    if texts is None:
        return None, (
            f"A {type(target).__name__} has no text value that can be changed here"
            if attribute is BulkAttribute.VALUE
            and not isinstance(
                target, (model.Property, model.MultiLanguageProperty)
            )
            else f"It has no text in the language '{language}'"
        )
    if isinstance(texts, str):
        return texts, ""
    if language not in texts:
        return None, f"It has no text in the language '{language}'"
    return str(texts[language]), ""


def _texts_of(
    target: model.Referable, attribute: BulkAttribute
) -> "model.LangStringSet | str | None":
    """Returns the language texts, the text of a Property value, or None."""
    if attribute is BulkAttribute.DESCRIPTION:
        return target.description
    if attribute is BulkAttribute.DISPLAY_NAME:
        return target.display_name
    if isinstance(target, model.MultiLanguageProperty):
        return target.value
    if isinstance(target, model.Property):
        value = target.value
        return "" if value is None else value_types.format_value(value)
    return None


def _checked(
    target: model.Referable,
    attribute: BulkAttribute,
    language: str,
    old: str | None,
    new: str,
) -> BulkEntry:
    """Checks that the SDK accepts the new text."""
    prepared: object = None
    try:
        if attribute is BulkAttribute.ID_SHORT:
            if not is_valid_id_short(new):
                raise ValueError(
                    f"'{new}' is not a valid idShort. It starts with a "
                    "letter, has only letters, digits, underscores and "
                    "hyphens, and does not end with a hyphen."
                )
        elif attribute is BulkAttribute.VALUE and isinstance(
            target, model.Property
        ):
            prepared = prepare_edit(target, "value", new)
        else:
            texts = cast("model.LangStringSet", _texts_of(target, attribute))
            type(texts)({language: new})
    except (ValueError, model.AASConstraintViolation) as error:
        return BulkEntry(target, old, new, EntryStatus.REFUSED, str(error))
    return BulkEntry(target, old, new, EntryStatus.CHANGE, prepared=prepared)


def _check_siblings(entries: list[BulkEntry]) -> list[BulkEntry]:
    """Refuses new idShorts that another element of the same parent has.

    The names are those after the whole change, so two elements can swap.
    """
    final: dict[int, str] = {
        id(entry.target): entry.new
        for entry in entries
        if entry.status is EntryStatus.CHANGE and entry.new is not None
    }
    result: list[BulkEntry] = []
    for entry in entries:
        if entry.status is not EntryStatus.CHANGE or entry.new is None:
            result.append(entry)
            continue
        reason = _clash(entry.target, entry.new, final)
        if reason:
            entry = replace(entry, status=EntryStatus.REFUSED, reason=reason)
        result.append(entry)
    return result


def _clash(target: model.Referable, new: str, final: dict[int, str]) -> str:
    for namespace_set in ordering.namespace_sets_of(target):
        for other in cast("Iterable[model.Referable]", namespace_set):
            if other is target:
                continue
            if id(other) in final:
                if final[id(other)] == new:
                    return (
                        f"Another selected element gets the idShort '{new}' "
                        "as well."
                    )
            elif other.id_short == new:
                return f"A sibling has the idShort '{new}' already."
    return ""


def _reference_changes(
    objects: Iterable[model.Identifiable], entries: Sequence[BulkEntry]
) -> tuple[tuple[ReferenceChange, ...], tuple[ReferenceSlot, ...]]:
    renames: list[KeyRename] = []
    for entry in entries:
        if isinstance(entry.target, model.Identifiable) or entry.new is None:
            # References name an identifiable by its id, never by its idShort.
            continue
        path = path_of(entry.target)
        if path is not None:
            renames.append(KeyRename(path, entry.new))
    if not renames:
        return (), ()
    return rewrite_keys(ReferenceIndex(objects), renames)


def _id_short_commands(
    observer: ModelChangeObserver, entries: Sequence[BulkEntry]
) -> list[Command]:
    """Renames the elements, through temporary names if they overlap."""
    current = {entry.old for entry in entries if entry.old is not None}
    needs_detour = any(
        entry.new in current and entry.new != entry.old for entry in entries
    )
    commands: list[Command] = []
    if needs_detour:
        for entry in entries:
            temporary = f"Bulk{uuid.uuid4().hex[:12]}"
            commands.append(_rename(observer, entry, temporary))
    for entry in entries:
        commands.append(_rename(observer, entry, cast("str", entry.new)))
    return commands


def _rename(
    observer: ModelChangeObserver, entry: BulkEntry, name: str
) -> Command:
    return SetAttribute(
        observer,
        entry.target,
        "id_short",
        name,
        description=f"Rename {describe(entry.target)}",
    )


def _text_command(
    observer: ModelChangeObserver, plan: BulkPlan, entry: BulkEntry
) -> Command:
    new = cast("str", entry.new)
    if plan.attribute is BulkAttribute.VALUE and isinstance(
        entry.target, model.Property
    ):
        return SetAttribute(
            observer,
            entry.target,
            "value",
            entry.prepared,
            description=f"Edit value of {describe(entry.target)}",
        )
    texts = cast("Any", _texts_of(entry.target, plan.attribute))
    return ReplaceMember(
        observer,
        texts,
        (plan.language, entry.old),
        (plan.language, new),
        description=f"Edit {plan.attribute.label} of {describe(entry.target)}",
    )


class ExtensionKey(enum.Enum):
    """What extensions are grouped by."""

    NAME = "name"
    SEMANTIC_ID = "semantic id"


@dataclass(frozen=True, eq=False)
class ExtensionGroup:
    """The extensions of the selection that share a name or semantic id.

    Attributes:
        key: The name, or the values of the keys of the semantic id.
        entries: Each extension with the object that has it.
    """

    key: str
    entries: tuple[tuple[model.HasExtension, model.Extension], ...]

    @property
    def count(self) -> int:
        """How many extensions the group has."""
        return len(self.entries)

    @property
    def label(self) -> str:
        """The text for a list, such as `Animate.Args (3)`."""
        return f"{self.key} ({self.count})"


def group_extensions(
    owners: Iterable[object], by: ExtensionKey
) -> list[ExtensionGroup]:
    """Groups the extensions of the selected objects.

    Args:
        owners: The selected objects. Those without extensions are ignored,
            and one listed twice counts once.
        by: Whether to group by the name or by the semantic id.

    Returns:
        The groups sorted by key. An extension with no name, or no semantic
        id when grouping by that, is left out.
    """
    groups: dict[str, list[tuple[model.HasExtension, model.Extension]]] = {}
    seen: set[int] = set()
    for owner in owners:
        if not isinstance(owner, model.HasExtension) or id(owner) in seen:
            continue
        seen.add(id(owner))
        for extension in owner.extension:
            key = _key_of(extension, by)
            if key:
                groups.setdefault(key, []).append((owner, extension))
    return [
        ExtensionGroup(key, tuple(groups[key]))
        for key in sorted(groups, key=str.casefold)
    ]


def remove_extension_commands(
    observer: ModelChangeObserver, group: ExtensionGroup
) -> list[Command]:
    """Builds the commands that remove the extensions of a group.

    Args:
        observer: Where the commands report.
        group: What `group_extensions` returned.

    Returns:
        One removal for each extension. Push them inside one group.
    """
    return [
        RemoveMember(
            observer,
            owner.extension,
            extension,
            description=f"Remove extension {extension.name} of {describe(owner)}",
        )
        for owner, extension in group.entries
    ]


def _key_of(extension: model.Extension, by: ExtensionKey) -> str:
    if by is ExtensionKey.NAME:
        return extension.name
    reference = extension.semantic_id
    if reference is None:
        return ""
    return " > ".join(key.value for key in reference.key)


def languages_in(
    targets: Iterable[model.Referable], attribute: BulkAttribute
) -> list[str]:
    """Lists the languages that the selected objects have texts in.

    Args:
        targets: The selected objects.
        attribute: A text attribute. The others have no languages.

    Returns:
        The language tags, the most common first.
    """
    counts: dict[str, int] = {}
    if attribute.uses_language:
        for target in targets:
            texts = _texts_of(target, attribute)
            if texts is None or isinstance(texts, str):
                continue
            for language in texts:
                counts[language] = counts.get(language, 0) + 1
    return sorted(counts, key=lambda language: (-counts[language], language))
