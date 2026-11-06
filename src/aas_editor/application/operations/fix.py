"""Repairing references and copying idShorts to concept descriptions.

`plan_fix_references` finds the model references that can be repaired, and
those that cannot. It repairs two kinds of defect:

- A reference whose first key holds the idShort of the identifiable instead of
  its id, which the original editor also fixes.
- A reference whose keys have other types than the objects they name, such as
  a `Submodel` key for a concept description, and a `ModelReference` that was
  built for another type of target.

`sync_id_short_commands` copies the idShort of an element to the concept
description that its semantic id names, where that has no idShort or short
name yet.
"""

from collections.abc import Collection
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import SetAttribute
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.domain.references import DanglingReference
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import ReferenceSlot
from aas_editor.domain.references import is_model_reference
from aas_editor.domain.references import with_keys

# The longest short name of an IEC 61360 data specification (ShortNameType).
MAX_SHORT_NAME_LENGTH = 18

# Key types that name a kind of object, not one class. A key of such a type is
# correct for every object of the kind.
_GENERAL_KEY_TYPES = frozenset(
    {
        model.KeyTypes.SUBMODEL_ELEMENT,
        model.KeyTypes.DATA_ELEMENT,
        model.KeyTypes.EVENT_ELEMENT,
    }
)

_KEY_CLASSES: dict[model.KeyTypes, type[model.Identifiable]] = {
    model.KeyTypes.SUBMODEL: model.Submodel,
    model.KeyTypes.ASSET_ADMINISTRATION_SHELL: model.AssetAdministrationShell,
    model.KeyTypes.CONCEPT_DESCRIPTION: ConceptDescription,
}


@dataclass(frozen=True, eq=False)
class FixReferencesPlan:
    """The references that Fix References would repair.

    Attributes:
        changes: The repairs, one for each stored reference.
        unfixable: The references that point at nothing, and that no repair
            can reach, such as a reference to a submodel that was deleted.
    """

    changes: tuple[ReferenceChange, ...]
    unfixable: tuple[DanglingReference, ...]


def plan_fix_references(
    objects: Iterable[model.Identifiable],
    roots: Collection[model.Identifiable] | None = None,
) -> FixReferencesPlan:
    """Finds the model references that can be repaired.

    Args:
        objects: The identifiables of the package.
        roots: Only the references stored in these objects and below them.
            None checks the whole package.

    Returns:
        The plan. Nothing changes.
    """
    index = ReferenceIndex(objects)
    only = None if roots is None else {id(root) for root in roots}
    changes: list[ReferenceChange] = []
    unfixable: list[DanglingReference] = []
    for slot in index.slots:
        if only is not None and id(slot.root) not in only:
            continue
        after = _repaired(index, slot, slot.reference, unfixable)
        if after is not slot.reference:
            changes.append(ReferenceChange(slot, after))
    return FixReferencesPlan(tuple(changes), tuple(unfixable))


def sync_id_short_commands(
    observer: ModelChangeObserver,
    objects: Iterable[model.Identifiable],
    target: model.Referable,
    language: str = "en",
) -> list[Command]:
    """Builds the commands that copy an idShort to a concept description.

    For an element, the concept description is the one that its semantic id
    names. Its empty idShort gets the idShort of the element, and an IEC 61360
    data specification without a short name gets one in the language. For a
    concept description, the data specification without a short name gets one
    from the idShort of the description. A name that is set is never replaced.

    The SDK does not allow an empty preferred name, so unlike the original
    this never has to fill that.

    Args:
        observer: Where the commands report.
        objects: The identifiables of the package.
        target: An element or a concept description.
        language: The language of the new short name.

    Returns:
        The commands. Empty when there is nothing to fill in.
    """
    if isinstance(target, ConceptDescription):
        return _fill_concept(observer, target, target.id_short, language, False)
    concept = concept_of(ReferenceIndex(objects), target)
    if concept is None or not target.id_short:
        return []
    return _fill_concept(observer, concept, target.id_short, language, True)


def _fill_concept(
    observer: ModelChangeObserver,
    concept: ConceptDescription,
    id_short: str | None,
    language: str,
    fill_id_short: bool,
) -> list[Command]:
    commands: list[Command] = []
    if not id_short:
        return commands
    if fill_id_short and not concept.id_short:
        commands.append(
            SetAttribute(
                observer,
                concept,
                "id_short",
                id_short,
                description=f"Sync idShort {id_short}",
            )
        )
    if len(id_short) <= MAX_SHORT_NAME_LENGTH:
        for specification in concept.embedded_data_specifications:
            content = specification.data_specification_content
            if (
                isinstance(content, model.DataSpecificationIEC61360)
                and not content.short_name
            ):
                commands.append(
                    SetAttribute(
                        observer,
                        content,
                        "short_name",
                        model.ShortNameTypeIEC61360({language: id_short}),
                        description=f"Sync short name {id_short}",
                    )
                )
    return commands


def concept_of(
    index: ReferenceIndex, target: model.Referable
) -> ConceptDescription | None:
    """Finds the concept description that the semantic id of an object names.

    Args:
        index: The index of the package.
        target: An element, submodel, or anything else with a `semantic_id`.

    Returns:
        The first description that has the id of one of the keys of the
        semantic id, or None if there is no semantic id or no such
        description.
    """
    reference = cast(
        "model.Reference | None", getattr(target, "semantic_id", None)
    )
    if reference is None:
        return None
    for key in reference.key:
        for found in index.with_id(key.value):
            if isinstance(found, ConceptDescription):
                return found
    return None


def _repaired(
    index: ReferenceIndex,
    slot: ReferenceSlot,
    reference: model.Reference,
    unfixable: list[DanglingReference],
) -> model.Reference:
    """Returns the reference, repaired where it can be, at every level."""
    inner = reference.referred_semantic_id
    new_inner = (
        None if inner is None else _repaired(index, slot, inner, unfixable)
    )
    fixed = _repaired_keys(index, slot, reference, unfixable)
    if fixed is reference and new_inner is inner:
        return reference
    return with_keys(fixed, fixed.key, new_inner)


def _repaired_keys(
    index: ReferenceIndex,
    slot: ReferenceSlot,
    reference: model.Reference,
    unfixable: list[DanglingReference],
) -> model.Reference:
    if not is_model_reference(reference):
        return reference
    typed = cast("model.ModelReference[Any]", reference)
    candidate = typed
    target = index.resolve(typed)
    if target is None:
        found = _by_id_short(index, typed)
        target = None if found is None else index.resolve(found)
        if found is None or target is None:
            unfixable.append(DanglingReference(slot, typed, index.why(typed)))
            return reference
        candidate = found
    built = cast(
        "model.ModelReference[Any]",
        model.ModelReference.from_referable(target),  # pyright: ignore[reportUnknownMemberType]
    )
    path = tuple(
        key
        for key in candidate.key
        if key.type is not model.KeyTypes.FRAGMENT_REFERENCE
    )
    fragments = candidate.key[len(path) :]
    keys = (*_right_keys(path, built.key), *fragments)
    if candidate is typed and keys == typed.key:
        return reference
    return model.ModelReference(
        keys, built.type, candidate.referred_semantic_id
    )


def _right_keys(
    written: tuple[model.Key, ...], built: tuple[model.Key, ...]
) -> tuple[model.Key, ...]:
    """Takes the written keys, but the real type where the type is wrong.

    A general type, such as `SubmodelElement` for a property, is not wrong.
    """
    if len(written) != len(built):
        return built
    return tuple(
        key
        if key.value == real.value
        and (key.type is real.type or key.type in _GENERAL_KEY_TYPES)
        else real
        for key, real in zip(written, built, strict=True)
    )


def _by_id_short(
    index: ReferenceIndex, reference: model.ModelReference[Any]
) -> model.ModelReference[Any] | None:
    """Tries the first key as the idShort of an identifiable, not its id."""
    first = reference.key[0]
    wanted = _KEY_CLASSES.get(first.type, model.Identifiable)
    matches = [
        obj
        for obj in index.objects
        if obj.id_short == first.value and isinstance(obj, wanted)
    ]
    if len(matches) != 1:
        return None
    keys = (model.Key(first.type, matches[0].id), *reference.key[1:])
    try:
        return cast(
            "model.ModelReference[Any]",
            with_keys(reference, keys, reference.referred_semantic_id),
        )
    except model.AASConstraintViolation:
        return None
