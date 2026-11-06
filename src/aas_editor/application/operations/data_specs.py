"""Editing the data specification records of concept descriptions.

- `add_record_commands` and `replace_record_commands` put an IEC 61360 record
  made from a draft (`aas_editor.domain.data_specifications`) on a concept
  description, or in place of its record.
- `plan_fix_keys` finds records whose reference does not name the IEC 61360
  template, which is what the original calls `Fix data specs wrt. content`.
  Content decides, as it does in the original: a record with IEC 61360 content
  gets the key of the template. The original repairs only the first record of
  each description per run; this repairs all of them.
- `clear_empty_commands` takes away the attributes that are present but empty,
  which the SDK accepts and the schema does not (`Delete invalid (empty)`).
- `plan_value_list_import` adds pairs to a value list without repeating one
  that is there.

Example:
    Importing pairs that were read from the clipboard::

        plan = plan_value_list_import(content, parse.pairs)
        with stack.group("Import value list"):
            for command in import_commands(observer, plan):
                stack.push(command)
"""

from collections.abc import Iterable
from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import ReplaceMember
from aas_editor.application.edits import SetAttribute
from aas_editor.domain.data_specifications import TemplateMatch
from aas_editor.domain.data_specifications import empty_attributes
from aas_editor.domain.data_specifications import iec_content_of
from aas_editor.domain.data_specifications import match_template
from aas_editor.domain.data_specifications import template_reference
from aas_editor.domain.references import describe_object

PairKey = tuple[str, tuple[tuple[str, str], ...]]


def iec_records(
    concept: ConceptDescription,
) -> list[
    tuple[model.EmbeddedDataSpecification, model.DataSpecificationIEC61360]
]:
    """Returns the records of a description that have IEC 61360 content."""
    found: list[
        tuple[model.EmbeddedDataSpecification, model.DataSpecificationIEC61360]
    ] = []
    for record in concept.embedded_data_specifications:
        content = iec_content_of(record)
        if content is not None:
            found.append((record, content))
    return found


def add_record_commands(
    observer: ModelChangeObserver,
    concept: ConceptDescription,
    record: model.EmbeddedDataSpecification,
) -> list[Command]:
    """Builds the command that adds a record to a description."""
    return [
        AddMember(
            observer,
            concept.embedded_data_specifications,
            record,
            description=f"Add IEC 61360 record to {describe_object(concept)}",
        )
    ]


def replace_record_commands(
    observer: ModelChangeObserver,
    concept: ConceptDescription,
    old: model.EmbeddedDataSpecification,
    new: model.EmbeddedDataSpecification,
) -> list[Command]:
    """Builds the command that puts a new record in the place of an old one."""
    return [
        ReplaceMember(
            observer,
            concept.embedded_data_specifications,
            old,
            new,
            description=f"Edit IEC 61360 record of {describe_object(concept)}",
        )
    ]


@dataclass(frozen=True, eq=False)
class FixKeysPlan:
    """The records whose reference does not name the IEC 61360 template.

    Attributes:
        unknown: Records with IEC 61360 content and a reference to something
            else, with the description that holds them.
        other_spelling: Records whose reference names the template in another
            spelling or version, such as `http` or `3/0`.
        correct: How many records have the key already.
    """

    unknown: tuple[
        tuple[ConceptDescription, model.EmbeddedDataSpecification], ...
    ]
    other_spelling: tuple[
        tuple[ConceptDescription, model.EmbeddedDataSpecification], ...
    ]
    correct: int

    @property
    def is_empty(self) -> bool:
        """Whether there is nothing to fix at all."""
        return not (self.unknown or self.other_spelling)


def plan_fix_keys(concepts: Iterable[ConceptDescription]) -> FixKeysPlan:
    """Finds the records that need the key of the IEC 61360 template.

    Args:
        concepts: The descriptions to look at.

    Returns:
        The plan. Nothing changes.
    """
    unknown: list[
        tuple[ConceptDescription, model.EmbeddedDataSpecification]
    ] = []
    other: list[tuple[ConceptDescription, model.EmbeddedDataSpecification]] = []
    correct = 0
    for concept in concepts:
        for record, _ in iec_records(concept):
            match = match_template(record.data_specification)
            if match is TemplateMatch.CURRENT:
                correct += 1
            elif match is TemplateMatch.OTHER_SPELLING:
                other.append((concept, record))
            else:
                unknown.append((concept, record))
    return FixKeysPlan(tuple(unknown), tuple(other), correct)


def fix_keys_commands(
    observer: ModelChangeObserver, plan: FixKeysPlan, include_other: bool
) -> list[Command]:
    """Builds the commands that set the key of the template.

    Args:
        observer: Where the commands report.
        plan: What `plan_fix_keys` made.
        include_other: Whether to fix records with another spelling of the
            key too. A file written for an older version keeps them.

    Returns:
        One command for each record. Push them inside one group.
    """
    records = [*plan.unknown, *(plan.other_spelling if include_other else ())]
    return [
        SetAttribute(
            observer,
            record,
            "data_specification",
            template_reference(),
            description=f"Fix data specification key of {describe_object(concept)}",
        )
        for concept, record in records
    ]


def clear_empty_commands(
    observer: ModelChangeObserver, content: model.DataSpecificationIEC61360
) -> list[Command]:
    """Builds the commands that take away empty attributes.

    The preferred name stays: the SDK cannot make it empty, and it is
    required.
    """
    return [
        SetAttribute(
            observer,
            content,
            name,
            None,
            description=f"Remove empty {name}",
        )
        for name in empty_attributes(content)
    ]


def pair_key(pair: model.ValueReferencePair) -> PairKey:
    """Returns what makes two pairs the same: the value and the value id keys."""
    keys = (
        ()
        if pair.value_id is None
        else tuple((k.type.name, k.value) for k in pair.value_id.key)
    )
    return pair.value, keys


@dataclass(frozen=True, eq=False)
class ImportPlan:
    """Pairs to add to a value list.

    Attributes:
        content: The IEC 61360 content that gets the pairs.
        added: The pairs that are new.
        duplicates: The pairs that the list has already, or that appear twice
            in the input.
    """

    content: model.DataSpecificationIEC61360
    added: tuple[model.ValueReferencePair, ...]
    duplicates: tuple[model.ValueReferencePair, ...]

    @property
    def merged(self) -> set[model.ValueReferencePair]:
        """The value list after the import: the old pairs and the new ones."""
        return {*(self.content.value_list or ()), *self.added}


def plan_value_list_import(
    content: model.DataSpecificationIEC61360,
    pairs: Iterable[model.ValueReferencePair],
) -> ImportPlan:
    """Plans adding pairs to the value list of IEC 61360 content.

    Two pairs are the same when they have the same value and value id keys.
    The SDK compares pairs by identity, so without this a second import of
    the same text would double the list.

    Args:
        content: The content that gets the pairs.
        pairs: The pairs that were read.

    Returns:
        The plan. Nothing changes.
    """
    known = {pair_key(p) for p in content.value_list or ()}
    added: list[model.ValueReferencePair] = []
    duplicates: list[model.ValueReferencePair] = []
    for pair in pairs:
        key = pair_key(pair)
        if key in known:
            duplicates.append(pair)
        else:
            known.add(key)
            added.append(pair)
    return ImportPlan(content, tuple(added), tuple(duplicates))


def import_commands(
    observer: ModelChangeObserver, plan: ImportPlan
) -> list[Command]:
    """Builds the command that sets the merged value list.

    A new set replaces the old one, so undo gives the old list back.
    """
    if not plan.added:
        return []
    return [
        SetAttribute(
            observer,
            plan.content,
            "value_list",
            plan.merged,
            description=(
                f"Import {len(plan.added)} value"
                f"{'' if len(plan.added) == 1 else 's'}"
            ),
        )
    ]
