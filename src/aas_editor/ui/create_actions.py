"""The actions that create shells and submodels, and edit the asset ids of a shell.

Call `register_create_actions` once, before the first tree view exists. The
composition root does that. Each action is one undo step:

- Create AAS asks for what AssetInformation needs, so a new shell is valid. The
  generated form could not, and the SDK refused it with AASd-131.
- Create Submodel makes a submodel and, if the user chooses a shell, the
  reference to it in the same step.
- Link existing Submodels adds references from a shell to submodels that no
  reference from this shell names yet.
- Generate global asset id and Add specific asset id are the helpers for the
  asset ids of a shell.

The tree view's own Add on the node of the shells uses `create_shell`, so it
does not fail.
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.edits import link_submodels
from aas_editor.application.operations.create import CreateError
from aas_editor.application.operations.create import add_shell
from aas_editor.application.operations.create import (
    add_specific_asset_id_command,
)
from aas_editor.application.operations.create import add_submodel
from aas_editor.application.operations.create import (
    generate_global_asset_id_command,
)
from aas_editor.application.operations.create import shell_of
from aas_editor.application.operations.create import unlinked_submodels
from aas_editor.application.operations.rename import RenameError
from aas_editor.domain.asset_information import AssetInformationError
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.app_settings import PACK_ITEM_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.create_dialogs import CreateShellDialog
from aas_editor.ui.create_dialogs import CreateSubmodelDialog
from aas_editor.ui.create_dialogs import LinkSubmodelsDialog
from aas_editor.ui.create_dialogs import SpecificAssetIdDialog
from aas_editor.ui.reference_jump import find_row

TITLE = "Create"
CREATE_SHELL_ID = "create.shell"
CREATE_SUBMODEL_ID = "create.submodel"
LINK_SUBMODELS_ID = "create.link_submodels"
GENERATE_ASSET_ID = "asset.generate_global_id"
ADD_SPECIFIC_ID = "asset.add_specific_id"


def show_problem(message: str, parent: QWidget | None = None) -> None:
    """Tells the user why a create or edit did not happen."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(TITLE)
    box.setText(message)
    box.exec()


def select_object(view: Any, obj: object) -> bool:
    """Makes the row of an object the current row of a tree view, if shown."""
    found = find_row(view.model(), obj)
    if found is None:
        return False
    parent = found.parent()
    while parent.isValid():
        view.expand(parent)
        parent = parent.parent()
    view.setCurrentIndex(found)
    return True


def _ask(dialog: Any, build: Any, view: Any) -> Any:
    """Runs a dialog until its input builds, or the user cancels.

    The dialog validates while the user types, so the loop only repeats when
    something changed between the last check and the click.
    """
    while dialog.exec() == QDialog.DialogCode.Accepted:
        try:
            return build()
        except (CreateError, RenameError, AssetInformationError) as error:
            show_problem(str(error), view)
    return None


def create_shell(
    view: Any, package: Any
) -> model.AssetAdministrationShell | None:
    """Asks for a new shell and adds it as one undo step.

    Args:
        view: The tree view, which is the parent of the dialog.
        package: The package to add the shell to.

    Returns:
        The shell, or None if the user cancelled or Read mode is on.
    """
    objects = list(package.objStore)
    dialog = CreateShellDialog(objects, view)
    shell = _ask(dialog, dialog.build, view)
    dialog.deleteLater()
    if shell is None:
        return None
    try:
        add_shell(
            package.commandStack, observer_for(package), package.objStore, shell
        )
    except ReadOnlyError as error:
        show_problem(str(error), view)
        return None
    select_object(view, shell)
    return shell


def create_submodel(
    view: Any,
    package: Any,
    shell: model.AssetAdministrationShell | None = None,
) -> model.Submodel | None:
    """Asks for a new submodel, adds it, and links it to a shell.

    Args:
        view: The tree view, which is the parent of the dialog.
        package: The package to add the submodel to.
        shell: The shell to preselect in the dialog.

    Returns:
        The submodel, or None if the user cancelled or Read mode is on.
    """
    objects = list(package.objStore)
    shells = sorted(
        (
            obj
            for obj in objects
            if isinstance(obj, model.AssetAdministrationShell)
        ),
        key=lambda item: (item.id_short or item.id).lower(),
    )
    dialog = CreateSubmodelDialog(objects, shells, shell, view)
    submodel = _ask(dialog, dialog.build, view)
    chosen = dialog.selected_shell()
    dialog.deleteLater()
    if submodel is None:
        return None
    try:
        add_submodel(
            package.commandStack,
            observer_for(package),
            package.objStore,
            submodel,
            chosen,
        )
    except ReadOnlyError as error:
        show_problem(str(error), view)
        return None
    select_object(view, submodel)
    return submodel


def link_existing(
    view: Any, package: Any, shell: model.AssetAdministrationShell
) -> int:
    """Asks which submodels a shell should refer to, and links them.

    Returns:
        The number of references that were added.
    """
    missing = unlinked_submodels(list(package.objStore), shell)
    if not missing:
        show_problem("The AAS refers to every Submodel of this package.", view)
        return 0
    dialog = LinkSubmodelsDialog(shell, missing, view)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    chosen = dialog.chosen() if accepted else []
    dialog.deleteLater()
    if not chosen:
        return 0
    try:
        return link_submodels(
            package.commandStack, observer_for(package), shell, chosen
        )
    except ReadOnlyError as error:
        show_problem(str(error), view)
        return 0


def generate_global_asset_id(
    view: Any, package: Any, shell: model.AssetAdministrationShell
) -> bool:
    """Gives a shell a new global asset id, as one undo step."""
    try:
        package.commandStack.push(
            generate_global_asset_id_command(observer_for(package), shell)
        )
    except (CreateError, ReadOnlyError) as error:
        show_problem(str(error), view)
        return False
    return True


def add_specific_asset_id(
    view: Any, package: Any, shell: model.AssetAdministrationShell
) -> bool:
    """Asks for a specific asset id and adds it, as one undo step."""
    dialog = SpecificAssetIdDialog(view)
    specific = _ask(dialog, dialog.build, view)
    dialog.deleteLater()
    if specific is None:
        return False
    try:
        package.commandStack.push(
            add_specific_asset_id_command(
                observer_for(package), shell, specific
            )
        )
    except (CreateError, ReadOnlyError) as error:
        show_problem(str(error), view)
        return False
    return True


# The actions


def shell_for(context: ActionContext) -> model.AssetAdministrationShell | None:
    """Finds the shell that the current row is, or belongs to.

    That is the shell itself, its AssetInformation, or one of its specific
    asset ids, in the package tree or in the tab of a shell.
    """
    package: Any = context.package
    if package is None:
        return None
    objects = list(package.objStore)
    candidates: list[object] = [context.index.data(OBJECT_ROLE)]
    pack_item: QModelIndex | None = context.index.data(PACK_ITEM_ROLE)
    if pack_item is not None:
        candidates.append(pack_item.data(OBJECT_ROLE))
    for candidate in candidates:
        shell = shell_of(candidate, objects)
        if shell is not None:
            return shell
    return None


def _has_package(context: ActionContext) -> bool:
    return context.package is not None


def _can_link(context: ActionContext) -> bool:
    shell = shell_for(context)
    package: Any = context.package
    return shell is not None and bool(
        unlinked_submodels(list(package.objStore), shell)
    )


def _run_create_shell(context: ActionContext) -> None:
    create_shell(context.view, context.package)


def _run_create_submodel(context: ActionContext) -> None:
    create_submodel(context.view, context.package, shell_for(context))


def _run_link(context: ActionContext) -> None:
    shell = shell_for(context)
    if shell is not None:
        link_existing(context.view, context.package, shell)


def _run_generate(context: ActionContext) -> None:
    shell = shell_for(context)
    if shell is not None:
        generate_global_asset_id(context.view, context.package, shell)


def _run_add_specific(context: ActionContext) -> None:
    shell = shell_for(context)
    if shell is not None:
        add_specific_asset_id(context.view, context.package, shell)


def register_create_actions() -> None:
    """Adds the create actions to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    specs = (
        ActionSpec(
            action_id=CREATE_SHELL_ID,
            text="Create AAS...",
            run=_run_create_shell,
            is_enabled=_has_package,
            views=ViewKind.PACKAGES,
            status_tip="Create an AAS with valid AssetInformation",
            order=200,
        ),
        ActionSpec(
            action_id=CREATE_SUBMODEL_ID,
            text="Create Submodel...",
            run=_run_create_submodel,
            is_enabled=_has_package,
            views=ViewKind.PACKAGES,
            status_tip="Create a Submodel and refer to it from an AAS",
            order=201,
        ),
        ActionSpec(
            action_id=LINK_SUBMODELS_ID,
            text="Link existing Submodels...",
            run=_run_link,
            is_enabled=_can_link,
            views=ViewKind.ANY,
            status_tip="Let the AAS refer to Submodels that it does not name yet",
            order=202,
        ),
        ActionSpec(
            action_id=GENERATE_ASSET_ID,
            text="Generate global asset id",
            run=_run_generate,
            is_enabled=lambda context: shell_for(context) is not None,
            views=ViewKind.ANY,
            status_tip="Give the AAS a new global asset id",
            order=203,
        ),
        ActionSpec(
            action_id=ADD_SPECIFIC_ID,
            text="Add specific asset id...",
            run=_run_add_specific,
            is_enabled=lambda context: shell_for(context) is not None,
            views=ViewKind.ANY,
            status_tip="Add a specific asset id, such as a serial number",
            order=204,
        ),
    )
    for spec in specs:
        if spec.action_id not in registered:
            register_action(spec)
