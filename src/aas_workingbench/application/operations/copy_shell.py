"""Copying an AAS together with its Submodels, under new ids (F-EDT-02 AC4).

Pasting a copied AAS gives it a new id and leaves its Submodel references as
they were, so the copy and the original share their Submodels (D13). The
original also offers `Copy recursively`: the AAS, its `globalAssetId` and
every Submodel it refers to get new ids, and the references of the new AAS
point to the new Submodels. `plan_copy_shell` finds that without changing
anything, and `copy_shell_commands` builds the commands, which belong in one
group.

A Submodel that the AAS refers to but the package does not hold cannot be
copied. Its reference stays as it was, and the plan lists it.

A reference inside a copied Submodel that points into another copied Submodel
is made to point into the copy, so the copies refer to each other as the
originals did. References to anything else are left alone, such as semantic
ids and elements of Submodels that were not copied.

Example:
    Duplicating the first shell of a package::

        plan = plan_copy_shell(shell, package.objStore)
        with stack.group(plan.description):
            for command in copy_shell_commands(observer, store, plan):
                stack.push(command)
"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import cast

from basyx.aas import model

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.edits import AddMember
from aas_workingbench.application.edits import describe
from aas_workingbench.application.operations.references import ReferenceChange
from aas_workingbench.application.operations.references import (
    reference_commands,
)
from aas_workingbench.domain.asset_information import new_global_asset_id
from aas_workingbench.domain.clipboard_json import clone
from aas_workingbench.domain.ids import new_identifier
from aas_workingbench.domain.references import is_model_reference
from aas_workingbench.domain.references import iter_slots
from aas_workingbench.domain.references import map_keys


@dataclass(frozen=True, eq=False)
class ShellCopyPlan:
    """What copying an AAS recursively would add.

    Attributes:
        shell: The new AAS, detached until the commands add it.
        submodels: Each Submodel that is copied, with its copy.
        unresolved: The references of the AAS to a Submodel that the package
            does not hold. The new AAS keeps them as they are.
        inner_references: The references in the copies that now point into
            another copy.
        description: Text for the undo step.
    """

    shell: model.AssetAdministrationShell
    submodels: tuple[tuple[model.Submodel, model.Submodel], ...]
    unresolved: tuple["model.ModelReference[model.Submodel]", ...]
    inner_references: tuple[ReferenceChange, ...]
    description: str


def plan_copy_shell(
    shell: model.AssetAdministrationShell,
    objects: Collection[model.Identifiable],
) -> ShellCopyPlan:
    """Plans a copy of an AAS with new ids for it and its Submodels.

    Args:
        shell: The AAS to copy. It is not changed.
        objects: The identifiables of the package, to find its Submodels.

    Returns:
        The plan.
    """
    by_id = {obj.id: obj for obj in objects}
    copy = cast("model.AssetAdministrationShell", clone(shell))
    copy.id = new_identifier()
    if copy.asset_information.global_asset_id is not None:
        copy.asset_information.global_asset_id = new_global_asset_id()
    pairs: list[tuple[model.Submodel, model.Submodel]] = []
    unresolved: list[model.ModelReference[model.Submodel]] = []
    references: list[model.ModelReference[model.Submodel]] = []
    renamed: dict[str, str] = {}
    for reference in shell.submodel:
        found = by_id.get(reference.key[0].value)
        if isinstance(found, model.Submodel) and found.id not in renamed:
            sub_copy = cast("model.Submodel", clone(found))
            sub_copy.id = new_identifier()
            renamed[found.id] = sub_copy.id
            pairs.append((found, sub_copy))
            references.append(
                cast(
                    "model.ModelReference[model.Submodel]",
                    model.ModelReference.from_referable(sub_copy),  # pyright: ignore[reportUnknownMemberType]
                )
            )
        elif isinstance(found, model.Submodel):
            # The AAS refers to the same Submodel twice. One copy serves both.
            references.append(
                cast(
                    "model.ModelReference[model.Submodel]",
                    model.ModelReference.from_referable(  # pyright: ignore[reportUnknownMemberType]
                        next(c for o, c in pairs if o is found)
                    ),
                )
            )
        else:
            unresolved.append(reference)
            references.append(reference)
    copy.submodel.clear()
    for reference in references:
        copy.submodel.add(reference)
    inner = _inner_references([c for _, c in pairs], renamed)
    name = describe(shell)
    return ShellCopyPlan(
        copy,
        tuple(pairs),
        tuple(unresolved),
        inner,
        f"Copy {name} with {len(pairs)} Submodel"
        + ("s" if len(pairs) != 1 else ""),
    )


def _inner_references(
    copies: list[model.Submodel], renamed: dict[str, str]
) -> tuple[ReferenceChange, ...]:
    """Finds the references in the copies that point into a copied Submodel."""

    def swap(
        reference: model.Reference, position: int, key: model.Key
    ) -> model.Key:
        if (
            position == 0
            and is_model_reference(reference)
            and key.type is model.KeyTypes.SUBMODEL
            and key.value in renamed
        ):
            return model.Key(key.type, renamed[key.value])
        return key

    changes: list[ReferenceChange] = []
    for copy in copies:
        for slot in iter_slots(copy):
            after = map_keys(slot.reference, swap)
            if after is not slot.reference:
                changes.append(ReferenceChange(slot, after))
    return tuple(changes)


def copy_shell_commands(
    observer: ModelChangeObserver, store: object, plan: ShellCopyPlan
) -> list[Command]:
    """Builds the commands of a copy. Push them inside one group.

    Args:
        observer: Where the commands report.
        store: The object store of the package.
        plan: What `plan_copy_shell` made.

    Returns:
        The Submodels go in first, then the references between them, then the
        AAS, so that every reference resolves as soon as it exists.
    """
    commands: list[Command] = [
        AddMember(observer, store, sub_copy, description=plan.description)
        for _, sub_copy in plan.submodels
    ]
    commands.extend(reference_commands(observer, plan.inner_references))
    commands.append(
        AddMember(observer, store, plan.shell, description=plan.description)
    )
    return commands
