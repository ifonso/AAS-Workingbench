"""Creating shells and submodels, and the edits of a shell's asset ids.

A new shell needs valid AssetInformation, which the generated form could not
ask for. A new submodel is usually linked to a shell at once. Each flow is one
undo step: the object and its link come and go together.

`new_shell` and `new_submodel` make the objects without touching the package,
and refuse what the metamodel refuses with a message for the user. `add_shell`
and `add_submodel` put them into the package through the command stack.

Example:
    Creating a shell and a submodel linked to it::

        shell = new_shell(store, global_asset_id=new_global_asset_id())
        add_shell(stack, observer, store, shell)
        submodel = new_submodel(store, id_short="Nameplate")
        add_submodel(stack, observer, store, submodel, shell)
"""

from collections.abc import Collection
from collections.abc import Iterable
from typing import Any
from typing import cast

from basyx.aas import model

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import SetAttribute
from aas_editor.application.edits import describe
from aas_editor.application.operations.rename import DuplicateIdError
from aas_editor.domain.asset_information import DEFAULT_ASSET_KIND
from aas_editor.domain.asset_information import AssetInformationError
from aas_editor.domain.asset_information import build_asset_information
from aas_editor.domain.asset_information import check_asset_ids
from aas_editor.domain.asset_information import clean_identifier
from aas_editor.domain.asset_information import new_global_asset_id
from aas_editor.domain.ids import is_valid_id_short
from aas_editor.domain.ids import new_identifier
from aas_editor.domain.references import ReferenceIndex


class CreateError(ValueError):
    """Something cannot be created or changed. The text is for the user."""


def _free_id(objects: Iterable[model.Identifiable], wanted: str | None) -> str:
    id_ = clean_identifier(wanted) or new_identifier()
    if len(id_) > 2048:
        raise CreateError(
            f"The id has {len(id_)} characters, and 2048 are allowed"
        )
    index = ReferenceIndex(objects)
    taken = index.with_id(id_)
    if taken:
        raise DuplicateIdError(id_, taken[0])
    return id_


def _id_short(text: str | None) -> str | None:
    clean = clean_identifier(text)
    if clean is not None and not is_valid_id_short(clean):
        raise CreateError(
            f"'{clean}' is not a valid idShort. It starts with a letter, "
            "holds letters, digits, underscores and hyphens, and does not end "
            "with a hyphen (AASd-002)"
        )
    return clean


def new_shell(
    objects: Iterable[model.Identifiable],
    *,
    id_: str | None = None,
    id_short: str | None = None,
    asset_kind: model.AssetKind = DEFAULT_ASSET_KIND,
    global_asset_id: str | None = None,
    specific_asset_ids: Iterable[model.SpecificAssetId] = (),
    asset_type: str | None = None,
) -> model.AssetAdministrationShell:
    """Makes a shell with valid AssetInformation, without adding it.

    Args:
        objects: The identifiables of the package, to keep ids unique.
        id_: The id of the shell. None or blank generates a `urn:uuid:`.
        id_short: The idShort, or None.
        asset_kind: Whether the asset is a type, an instance, or neither.
        global_asset_id: The global asset id. Blank means none.
        specific_asset_ids: The specific asset ids. A shell needs a global
            asset id or at least one of these (AASd-131).
        asset_type: The type of the asset, if known.

    Returns:
        The shell.

    Raises:
        DuplicateIdError: If another object has the id.
        CreateError: If an id or the idShort is not valid, or the asset ids
            break AASd-131.
    """
    store = list(objects)
    shell_id = _free_id(store, id_)
    short = _id_short(id_short)
    try:
        information = build_asset_information(
            asset_kind, global_asset_id, specific_asset_ids, asset_type
        )
    except AssetInformationError as error:
        raise CreateError(str(error)) from error
    try:
        return model.AssetAdministrationShell(
            asset_information=information, id_=shell_id, id_short=short
        )
    except (ValueError, model.AASConstraintViolation) as error:
        raise CreateError(str(error)) from error


def new_submodel(
    objects: Iterable[model.Identifiable],
    *,
    id_: str | None = None,
    id_short: str | None = None,
    kind: model.ModellingKind = model.ModellingKind.INSTANCE,
) -> model.Submodel:
    """Makes a submodel, without adding it.

    Args:
        objects: The identifiables of the package, to keep ids unique.
        id_: The id of the submodel. None or blank generates a `urn:uuid:`.
        id_short: The idShort, or None.
        kind: Template or instance.

    Returns:
        The submodel.

    Raises:
        DuplicateIdError: If another object has the id.
        CreateError: If the id or the idShort is not valid.
    """
    store = list(objects)
    submodel_id = _free_id(store, id_)
    short = _id_short(id_short)
    try:
        return model.Submodel(id_=submodel_id, id_short=short, kind=kind)
    except (ValueError, model.AASConstraintViolation) as error:
        raise CreateError(str(error)) from error


def reference_to_submodel(
    submodel: model.Submodel,
) -> "model.ModelReference[model.Submodel]":
    """Returns the reference a shell holds for a submodel."""
    return cast(
        "model.ModelReference[model.Submodel]",
        model.ModelReference.from_referable(submodel),  # pyright: ignore[reportUnknownMemberType]
    )


def add_shell(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: object,
    shell: model.AssetAdministrationShell,
) -> None:
    """Adds a shell to the package as one undo step.

    Args:
        stack: The history of the package.
        observer: Where to report the change.
        store: The object store of the package.
        shell: The shell from `new_shell`.
    """
    stack.push(
        AddMember(
            observer, store, shell, description=f"Create AAS {describe(shell)}"
        )
    )


def add_submodel(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: object,
    submodel: model.Submodel,
    shell: model.AssetAdministrationShell | None = None,
) -> None:
    """Adds a submodel, and links it to a shell, as one undo step.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        store: The object store of the package.
        submodel: The submodel from `new_submodel`.
        shell: The shell to refer to the submodel. None adds a free submodel.
    """
    with stack.group(f"Create Submodel {describe(submodel)}"):
        stack.push(AddMember(observer, store, submodel))
        if shell is not None:
            stack.push(
                AddMember(
                    observer,
                    shell.submodel,
                    reference_to_submodel(submodel),
                    description=f"Link {describe(submodel)}",
                )
            )


def unlinked_submodels(
    objects: Iterable[model.Identifiable],
    shell: model.AssetAdministrationShell,
) -> list[model.Submodel]:
    """Lists the submodels of the package that a shell does not refer to."""
    return [
        obj
        for obj in objects
        if isinstance(obj, model.Submodel)
        and reference_to_submodel(obj) not in shell.submodel
    ]


# The asset ids of a shell


def global_asset_id_command(
    observer: ModelChangeObserver,
    shell: model.AssetAdministrationShell,
    value: str | None,
) -> Command:
    """Builds the command that sets or clears the global asset id.

    Args:
        observer: Where to report the change.
        shell: The shell to change.
        value: The new id. Blank clears it.

    Returns:
        The command.

    Raises:
        CreateError: If clearing it would leave the shell without any asset
            id (AASd-131), or the id is too long.
    """
    new = clean_identifier(value)
    problem = check_asset_ids(new, shell.asset_information.specific_asset_id)
    if problem is not None:
        raise CreateError(problem)
    return SetAttribute(
        observer,
        shell.asset_information,
        "global_asset_id",
        new,
        description=f"Edit global asset id of {describe(shell)}",
    )


def generate_global_asset_id_command(
    observer: ModelChangeObserver, shell: model.AssetAdministrationShell
) -> Command:
    """Builds the command that gives the shell a new global asset id."""
    return global_asset_id_command(observer, shell, new_global_asset_id())


def add_specific_asset_id_command(
    observer: ModelChangeObserver,
    shell: model.AssetAdministrationShell,
    specific: model.SpecificAssetId,
) -> Command:
    """Builds the command that adds a specific asset id to a shell."""
    return AddMember(
        observer,
        shell.asset_information.specific_asset_id,
        specific,
        description=f"Add specific asset id {specific.name}",
    )


def remove_specific_asset_id_command(
    observer: ModelChangeObserver,
    shell: model.AssetAdministrationShell,
    specific: model.SpecificAssetId,
) -> Command:
    """Builds the command that removes a specific asset id from a shell.

    Raises:
        CreateError: If it is the only asset id (AASd-131).
    """
    remaining = [
        item
        for item in shell.asset_information.specific_asset_id
        if item is not specific
    ]
    problem = check_asset_ids(
        shell.asset_information.global_asset_id, remaining
    )
    if problem is not None:
        raise CreateError(problem)
    return RemoveMember(
        observer,
        shell.asset_information.specific_asset_id,
        specific,
        description=f"Delete specific asset id {specific.name}",
    )


def shell_of(obj: Any, objects: Collection[model.Identifiable]) -> Any:
    """Returns the shell that owns an AssetInformation or a specific asset id.

    Args:
        obj: An `AssetAdministrationShell`, its `AssetInformation`, or one of
            its `SpecificAssetId`.
        objects: The identifiables of the package.

    Returns:
        The shell, or None if the object belongs to none.
    """
    for candidate in objects:
        if not isinstance(candidate, model.AssetAdministrationShell):
            continue
        information = candidate.asset_information
        if (
            obj is candidate
            or obj is information
            or any(obj is item for item in information.specific_asset_id)
        ):
            return candidate
    return None
