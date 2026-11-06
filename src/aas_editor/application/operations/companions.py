"""What goes with a copy between packages: its concept descriptions.

An element refers to concept descriptions through its semantic ids. Copied into
another package, it would refer to nothing there. `gather_companions` finds
what belongs to a copy in the package it comes from, and `plan_concepts`
compares that with the target package:

- A description that the target lacks is added.
- One with the same id and the same content is reused.
- One with the same id and other content is a conflict, which the user
  decides: keep the description of the target, or add the copied one under a
  new id and point the copies at it.

`Companions` is the seam for other things that travel with a copy. It holds
the references of the copies to the files of their package too. The commands
that copy those files, and number a name that the target has taken, are in
`aas_editor.application.file_transfer`.

Example:
    Copying an element to another package::

        companions = gather_companions([element], source.objStore)
        plan = plan_concepts(companions, target.objStore)
        for command in concept_commands(observer, target.objStore, plan, {}):
            stack.push(command)
"""

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
import enum
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import AddMember
from aas_editor.domain import containers
from aas_editor.domain.clipboard_json import clone
from aas_editor.domain.clipboard_json import dump_objects
from aas_editor.domain.file_references import FileReference
from aas_editor.domain.file_references import references_in
from aas_editor.domain.ids import new_identifier
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import iter_slots
from aas_editor.domain.references import map_keys

_SEMANTIC_ATTRIBUTES = ("semantic_id", "supplemental_semantic_id")


@dataclass(frozen=True, eq=False)
class Companions:
    """What belongs to copied objects, found in their package.

    Attributes:
        concept_descriptions: The descriptions that the semantic ids of the
            objects and of everything below them refer to, each once.
        files: The references of the objects, and of everything below them,
            to files of their package. Their holders are the objects that
            were passed in, so pass the copies that are inserted.
    """

    concept_descriptions: tuple[ConceptDescription, ...] = ()
    files: tuple[FileReference, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether nothing needs to travel with the copy."""
        return not self.concept_descriptions and not self.files


class ConceptChoice(enum.Enum):
    """What to do with a description whose id the target has, with other content."""

    KEEP_EXISTING = "keep"
    """Use the description of the target for the copies."""
    ADD_WITH_NEW_ID = "new_id"
    """Add the copied description under a new id, and point the copies at it."""


@dataclass(frozen=True, eq=False)
class ConceptConflict:
    """A description whose id is taken by one with other content.

    Attributes:
        source: The description of the package the copy comes from.
        existing: The description of the target with the same id.
    """

    source: ConceptDescription
    existing: model.Identifiable


@dataclass(frozen=True, eq=False)
class ConceptPlan:
    """What copying the descriptions to a package would do.

    Attributes:
        to_add: Descriptions the target does not have.
        reused: Descriptions the target has with the same id and content.
        conflicts: Descriptions that need a decision.
    """

    to_add: tuple[ConceptDescription, ...]
    reused: tuple[ConceptDescription, ...]
    conflicts: tuple[ConceptConflict, ...]


def gather_companions(
    objects: Iterable[model.Referable],
    source_objects: Iterable[model.Identifiable],
    with_files: bool = False,
) -> Companions:
    """Finds the concept descriptions and files that copied objects refer to.

    Args:
        objects: The objects that are copied. Elements and everything below
            them count, with their semantic ids.
        source_objects: The identifiables of the package they come from.
        with_files: Also list the references to files of the package.

    Returns:
        The descriptions found in that package. A semantic id that names no
        description of the package is skipped.
    """
    objects = list(objects)
    index = ReferenceIndex(source_objects)
    found: dict[str, ConceptDescription] = {}
    for obj in objects:
        # iter_slots only reads attributes, so an element without an
        # identifiable above it is walked as well.
        for slot in iter_slots(cast("model.Identifiable", obj)):
            if slot.attribute not in _SEMANTIC_ATTRIBUTES:
                continue
            for key in slot.reference.key:
                for candidate in index.with_id(key.value):
                    if isinstance(candidate, ConceptDescription):
                        found.setdefault(candidate.id, candidate)
    references: list[FileReference] = []
    if with_files:
        for obj in objects:
            if isinstance(obj, model.Identifiable | model.SubmodelElement):
                references.extend(references_in(obj))
    return Companions(tuple(found.values()), tuple(references))


def plan_concepts(
    companions: Companions, target_objects: Iterable[model.Identifiable]
) -> ConceptPlan:
    """Compares the descriptions of a copy with the target package.

    Args:
        companions: What `gather_companions` found.
        target_objects: The identifiables of the package that receives the
            copy.

    Returns:
        The plan. Nothing changes.
    """
    index = ReferenceIndex(target_objects)
    to_add: list[ConceptDescription] = []
    reused: list[ConceptDescription] = []
    conflicts: list[ConceptConflict] = []
    for concept in companions.concept_descriptions:
        (existing, *_) = index.with_id(concept.id) or (None,)
        if existing is None:
            to_add.append(concept)
        elif isinstance(existing, ConceptDescription) and (
            dump_objects([existing]) == dump_objects([concept])
        ):
            reused.append(concept)
        else:
            conflicts.append(ConceptConflict(concept, existing))
    return ConceptPlan(tuple(to_add), tuple(reused), tuple(conflicts))


def concept_commands(
    observer: ModelChangeObserver,
    store: object,
    plan: ConceptPlan,
    choices: Mapping[str, ConceptChoice],
) -> tuple[list[Command], dict[str, str]]:
    """Builds the commands that add the descriptions to the target.

    Args:
        observer: Where the commands report.
        store: The object store of the target package.
        plan: What `plan_concepts` made.
        choices: For the id of each conflict, what to do. A conflict without
            a choice keeps the existing description.

    Returns:
        The commands, which add copies of the descriptions, and a mapping from
        the old id to the new id for the descriptions that were added under
        another id. Use `retarget_semantic_ids` on the pasted copies.
    """
    commands: list[Command] = []
    renamed: dict[str, str] = {}
    for concept in plan.to_add:
        copied = clone(concept)
        commands.append(AddMember(observer, store, copied))
    for conflict in plan.conflicts:
        if choices.get(conflict.source.id) is ConceptChoice.ADD_WITH_NEW_ID:
            copied = cast("ConceptDescription", clone(conflict.source))
            copied.id = new_identifier()
            renamed[conflict.source.id] = copied.id
            commands.append(AddMember(observer, store, copied))
    return commands, renamed


def retarget_semantic_ids(
    copies: Iterable[model.Referable], renamed: Mapping[str, str]
) -> int:
    """Points the semantic ids of detached copies at renamed descriptions.

    The copies are not part of a package yet, so no command is needed.

    Args:
        copies: The objects that a paste inserts.
        renamed: The old id and the new id of descriptions.

    Returns:
        The number of references that were changed.
    """
    if not renamed:
        return 0

    def swap(
        reference: model.Reference, position: int, key: model.Key
    ) -> model.Key:
        del reference, position
        new = renamed.get(key.value)
        return key if new is None else model.Key(key.type, new)

    changed = 0
    for obj in copies:
        for slot in list(iter_slots(cast("model.Identifiable", obj))):
            if slot.attribute not in _SEMANTIC_ATTRIBUTES:
                continue
            after = map_keys(slot.reference, swap)
            if after is slot.reference:
                continue
            if slot.container is None:
                setattr(slot.owner, slot.field, after)
            else:
                containers.replace_member(slot.container, slot.reference, after)
            changed += 1
    return changed
