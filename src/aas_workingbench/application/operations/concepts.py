"""Creating, assigning, detecting and deleting concept descriptions.

Every operation first makes a plan without changing anything. The plan says
what would happen, including what is skipped and why, and a function builds
the commands for it. A caller pushes the commands inside one group, so a
single undo takes the whole operation back.

- `plan_create` makes descriptions for semantic ids that name none (one
  element, or everything below a selection).
- `plan_assign` points the semantic id of an element at a description. It
  never replaces a semantic id without saying so: the plan carries the old one.
- `plan_detect` finds the description of elements that have no semantic id.
- `plan_from_pairs` makes one description for each pair of a value list.
- `plan_invalid` lists the descriptions that say nothing, with how many
  references would be left pointing at nothing. The delete itself goes through
  `ui.delete_flow`, so the usages are shown.

Example:
    Creating the descriptions for the semantic ids below a submodel::

        plan = plan_create(package.objStore, [submodel], adaptive=True)
        with stack.group("Create concept descriptions"):
            for command in create_commands(observer, package.objStore, plan):
                stack.push(command)
"""

from collections.abc import Iterable
from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.edits import AddMember
from aas_workingbench.application.edits import SetAttribute
from aas_workingbench.application.operations.fix import concept_of
from aas_workingbench.domain.concepts import SemanticHolder
from aas_workingbench.domain.concepts import concept_for_pair
from aas_workingbench.domain.concepts import concept_id_of
from aas_workingbench.domain.concepts import concept_reference
from aas_workingbench.domain.concepts import concepts_by_id_short
from aas_workingbench.domain.concepts import empty_concepts
from aas_workingbench.domain.concepts import holders_of
from aas_workingbench.domain.concepts import new_concept_for
from aas_workingbench.domain.concepts import usage_count
from aas_workingbench.domain.data_specifications import DEFAULT_LANGUAGE
from aas_workingbench.domain.data_specifications import iec_content_of
from aas_workingbench.domain.references import ReferenceIndex
from aas_workingbench.domain.references import describe_object


@dataclass(frozen=True, eq=False)
class CreatePlan:
    """The descriptions that semantic ids ask for.

    Attributes:
        new: The descriptions to add, one for each id.
        sources: The holder that each new description was made from, in the
            same order.
        existing: Holders whose semantic id names a description of the
            package already, with that description.
        conflicts: Holders whose id is used by an object that is not a
            description, with that object.
        without_semantic_id: How many holders had no semantic id.
    """

    new: tuple[ConceptDescription, ...]
    sources: tuple[SemanticHolder, ...]
    existing: tuple[tuple[SemanticHolder, ConceptDescription], ...]
    conflicts: tuple[tuple[SemanticHolder, model.Identifiable], ...]
    without_semantic_id: int

    @property
    def summary(self) -> str:
        """One sentence for the user about what the plan does."""
        parts = [
            f"{_count(len(self.new), 'concept description')} will be added"
        ]
        if self.existing:
            parts.append(f"{len(self.existing)} already exist")
        if self.conflicts:
            parts.append(
                f"{_count(len(self.conflicts), 'semantic id')} cannot be "
                "used because another kind of object has the id"
            )
        if self.without_semantic_id:
            parts.append(f"{self.without_semantic_id} have no semantic id")
        return ", ".join(parts) + "."


def _count(number: int, noun: str) -> str:
    return f"{number} {noun}{'' if number == 1 else 's'}"


def plan_create(
    objects: Iterable[model.Identifiable],
    roots: Iterable[model.Referable],
    adaptive: bool,
    below: bool = True,
    language: str = DEFAULT_LANGUAGE,
) -> CreatePlan:
    """Plans the descriptions for the semantic ids of a selection.

    Args:
        objects: The identifiables of the package.
        roots: The selected submodels and elements.
        adaptive: Whether the new descriptions get an IEC 61360 record with
            the preferred name and definition of the element.
        below: Whether to include everything below the roots.
        language: The language of names taken from an idShort.

    Returns:
        The plan. Nothing changes.
    """
    index = ReferenceIndex(objects)
    new: dict[str, ConceptDescription] = {}
    sources: dict[str, SemanticHolder] = {}
    existing: list[tuple[SemanticHolder, ConceptDescription]] = []
    conflicts: list[tuple[SemanticHolder, model.Identifiable]] = []
    without = 0
    for holder in holders_of(roots, below):
        if holder.reference is None:
            without += 1
            continue
        found = concept_of(index, holder.owner)
        if found is not None:
            existing.append((holder, found))
            continue
        id_ = concept_id_of(holder.reference)
        taken = index.with_id(id_)
        if taken:
            conflicts.append((holder, taken[0]))
        elif id_ not in new:
            new[id_] = new_concept_for(holder, adaptive, language)
            sources[id_] = holder
    return CreatePlan(
        tuple(new.values()),
        tuple(sources[id_] for id_ in new),
        tuple(existing),
        tuple(conflicts),
        without,
    )


def create_commands(
    observer: ModelChangeObserver, store: object, plan: CreatePlan
) -> list[Command]:
    """Builds the commands that add the new descriptions.

    Args:
        observer: Where the commands report.
        store: The object store of the package.
        plan: What `plan_create` made.

    Returns:
        One command for each description. Push them inside one group.
    """
    return [
        AddMember(
            observer,
            store,
            concept,
            description=f"Create concept description {concept.id_short or concept.id}",
        )
        for concept in plan.new
    ]


@dataclass(frozen=True, eq=False)
class AssignPlan:
    """Pointing the semantic id of one holder at a description.

    Attributes:
        holder: The submodel or element.
        concept: The description to use.
        previous: The semantic id the holder has now, or None.
    """

    holder: SemanticHolder
    concept: ConceptDescription
    previous: model.Reference | None

    @property
    def replaces(self) -> bool:
        """Whether the holder has another semantic id, which would be lost."""
        return self.previous is not None and (
            self.previous != concept_reference(self.concept)
        )

    @property
    def is_noop(self) -> bool:
        """Whether the holder points at the description already."""
        return self.previous is not None and not self.replaces


def plan_assign(
    holder: SemanticHolder, concept: ConceptDescription
) -> AssignPlan:
    """Plans giving a holder the semantic id of a description.

    The caller asks the user when `replaces` is true.
    """
    return AssignPlan(holder, concept, holder.reference)


def assign_commands(
    observer: ModelChangeObserver, plans: Iterable[AssignPlan]
) -> list[Command]:
    """Builds the commands that set the semantic ids.

    Args:
        observer: Where the commands report.
        plans: The assignments. Those that are no-ops are skipped.

    Returns:
        One command for each holder that changes.
    """
    return [
        SetAttribute(
            observer,
            plan.holder.owner,
            "semantic_id",
            concept_reference(plan.concept),
            description=(
                f"Assign concept description to {describe_object(plan.holder.owner)}"
            ),
        )
        for plan in plans
        if not plan.is_noop
    ]


@dataclass(frozen=True, eq=False)
class DetectPlan:
    """The result of looking for the description of elements.

    Attributes:
        assign: Holders without a semantic id, and the one description whose
            idShort matches.
        linked: Holders whose semantic id names a description by id.
        ambiguous: Holders without a semantic id that match several
            descriptions, and those descriptions.
        unmatched: Holders without a semantic id that match none.
        unresolved: Holders whose semantic id names no description of the
            package. They keep it.
    """

    assign: tuple[AssignPlan, ...]
    linked: tuple[SemanticHolder, ...]
    ambiguous: tuple[tuple[SemanticHolder, tuple[ConceptDescription, ...]], ...]
    unmatched: tuple[SemanticHolder, ...]
    unresolved: tuple[SemanticHolder, ...]

    @property
    def summary(self) -> str:
        """One sentence for the user about what was found."""
        parts = [f"{_count(len(self.assign), 'element')} will get a concept"]
        if self.linked:
            parts.append(f"{len(self.linked)} are linked already")
        if self.ambiguous:
            parts.append(f"{len(self.ambiguous)} match several (skipped)")
        if self.unmatched:
            parts.append(f"{len(self.unmatched)} match none")
        if self.unresolved:
            parts.append(
                f"{len(self.unresolved)} have a semantic id that names no "
                "concept description (kept)"
            )
        return ", ".join(parts) + "."


def plan_detect(
    objects: Iterable[model.Identifiable],
    roots: Iterable[model.Referable],
    below: bool = True,
) -> DetectPlan:
    """Finds the concept descriptions of elements by id and by idShort.

    The rule, for each submodel or element below the roots:

    1. **By id.** If its semantic id has the id of a description, it is
       linked already and nothing changes.
    2. A semantic id that names no description stays as it is. A semantic id
       is never replaced.
    3. **By idShort.** Without a semantic id, the element takes the one
       description with the same idShort. A description that differs only in
       case counts when no other matches exactly. Several matches are
       reported and skipped, and so is an item of a list, which has no
       idShort.

    Args:
        objects: The identifiables of the package.
        roots: The selected submodels and elements.
        below: Whether to include everything below the roots.

    Returns:
        The plan. Nothing changes.
    """
    all_objects = list(objects)
    index = ReferenceIndex(all_objects)
    assign: list[AssignPlan] = []
    linked: list[SemanticHolder] = []
    ambiguous: list[tuple[SemanticHolder, tuple[ConceptDescription, ...]]] = []
    unmatched: list[SemanticHolder] = []
    unresolved: list[SemanticHolder] = []
    for holder in holders_of(roots, below):
        if holder.reference is not None:
            if concept_of(index, holder.owner) is not None:
                linked.append(holder)
            else:
                unresolved.append(holder)
            continue
        matches = (
            concepts_by_id_short(all_objects, holder.id_short)
            if holder.id_short
            else []
        )
        if len(matches) == 1:
            assign.append(plan_assign(holder, matches[0]))
        elif matches:
            ambiguous.append((holder, tuple(matches)))
        else:
            unmatched.append(holder)
    return DetectPlan(
        tuple(assign),
        tuple(linked),
        tuple(ambiguous),
        tuple(unmatched),
        tuple(unresolved),
    )


@dataclass(frozen=True, eq=False)
class PairsPlan:
    """The descriptions that the pairs of a value list ask for.

    Attributes:
        new: Each pair that gets a description, and the description.
        existing: Pairs whose value id is the id of an object of the package.
        skipped: Pairs that cannot get one, and the reason.
    """

    new: tuple[tuple[model.ValueReferencePair, ConceptDescription], ...]
    existing: tuple[tuple[model.ValueReferencePair, model.Identifiable], ...]
    skipped: tuple[tuple[model.ValueReferencePair, str], ...]

    @property
    def summary(self) -> str:
        """One sentence for the user about what the plan does."""
        parts = [
            f"{_count(len(self.new), 'concept description')} will be added"
        ]
        if self.existing:
            parts.append(f"{len(self.existing)} exist already")
        if self.skipped:
            parts.append(f"{len(self.skipped)} are skipped")
        return ", ".join(parts) + "."


def value_pairs_of(
    concept: ConceptDescription,
) -> list[model.ValueReferencePair]:
    """Returns the pairs of the value lists of a description, by value.

    A value list is a set, so its order is not saved. The pairs are sorted by
    value and by value id, so every call lists them alike.
    """
    pairs: list[model.ValueReferencePair] = []
    for record in concept.embedded_data_specifications:
        content = iec_content_of(record)
        if content is not None and content.value_list:
            pairs.extend(content.value_list)
    return sorted(
        pairs,
        key=lambda p: (
            p.value,
            "" if p.value_id is None else concept_id_of(p.value_id),
        ),
    )


def plan_from_pairs(
    objects: Iterable[model.Identifiable],
    concept: ConceptDescription,
    language: str = DEFAULT_LANGUAGE,
) -> PairsPlan:
    """Plans one description for each pair of the value list of a description.

    The input is the value list of the IEC 61360 record of `concept`. A pair
    needs a value id, which becomes the id of the new description. The
    original editor made a description without an id for a pair without one.

    Args:
        objects: The identifiables of the package.
        concept: The description that holds the value list.
        language: The language of the names.

    Returns:
        The plan. Nothing changes.
    """
    index = ReferenceIndex(objects)
    new: list[tuple[model.ValueReferencePair, ConceptDescription]] = []
    existing: list[tuple[model.ValueReferencePair, model.Identifiable]] = []
    skipped: list[tuple[model.ValueReferencePair, str]] = []
    made: set[str] = set()
    for pair in value_pairs_of(concept):
        if pair.value_id is None:
            skipped.append((pair, "it has no value id"))
            continue
        id_ = concept_id_of(pair.value_id)
        taken = index.with_id(id_)
        if taken:
            existing.append((pair, taken[0]))
        elif id_ in made:
            skipped.append((pair, f"another pair has the id {id_}"))
        else:
            made.add(id_)
            new.append((pair, concept_for_pair(pair, language)))
    return PairsPlan(tuple(new), tuple(existing), tuple(skipped))


def from_pairs_commands(
    observer: ModelChangeObserver, store: object, plan: PairsPlan
) -> list[Command]:
    """Builds the commands that add the descriptions of a `PairsPlan`."""
    return [
        AddMember(
            observer,
            store,
            created,
            description=f"Create concept description {created.id_short or created.id}",
        )
        for _, created in plan.new
    ]


@dataclass(frozen=True, eq=False)
class InvalidConcept:
    """A description that says nothing, and what refers to it.

    Attributes:
        concept: The description.
        usages: How many references point at it. Deleting it leaves them
            pointing at nothing unless the user takes them away.
    """

    concept: ConceptDescription
    usages: int


def plan_invalid(
    objects: Iterable[model.Identifiable],
) -> tuple[InvalidConcept, ...]:
    """Lists the invalid concept descriptions of a package.

    A description is invalid when it has no embedded data specification, no
    `is_case_of`, and no extension (see `is_empty_concept`). The original
    editor warns about a description without a record, and the metamodel
    says a description is defined by a data specification.

    Args:
        objects: The identifiables of the package.

    Returns:
        The descriptions in a stable order, each with its usages.
    """
    all_objects = list(objects)
    index = ReferenceIndex(all_objects)
    return tuple(
        InvalidConcept(concept, usage_count(index, concept))
        for concept in empty_concepts(all_objects)
    )
