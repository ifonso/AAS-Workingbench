"""The action that copies an AAS together with its Submodels (F-EDT-02 AC3, AC4).

Call `register_shell_copy_actions` once, before the first tree view exists. The
composition root does that.

"Copy AAS with new Submodel ids" is on an AAS and on the node of the shells,
and not on the package: the original offers its copy actions on the
AdministrationShells node and not on the environment. On an AAS it copies that
one. On the node it first asks which AAS to copy. The copy gets a new id, a
new global asset id, and a copy of each Submodel under a new id, and the new
AAS refers to the copies. It is one undo step.

Copy and Paste of an AAS stays as it was: the copy has a new id and refers to
the same Submodels as the original (D13).
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.commands import ReadOnlyError
from aas_workingbench.application.operations.copy_shell import ShellCopyPlan
from aas_workingbench.application.operations.copy_shell import (
    copy_shell_commands,
)
from aas_workingbench.application.operations.copy_shell import plan_copy_shell
from aas_workingbench.domain.references import describe_object
from aas_workingbench.settings.app_settings import NAME_ROLE
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui.actions import ActionContext
from aas_workingbench.ui.actions import ActionSpec
from aas_workingbench.ui.actions import ViewKind
from aas_workingbench.ui.actions import default_registry
from aas_workingbench.ui.actions import register_action
from aas_workingbench.ui.create_actions import select_object
from aas_workingbench.ui.create_actions import show_problem

COPY_SHELL_ID = "create.copy_shell"
TITLE = "Copy AAS"


def ask_shell(
    shells: list[model.AssetAdministrationShell], parent: QWidget | None = None
) -> model.AssetAdministrationShell | None:
    """Asks which AAS to copy.

    Args:
        shells: The AAS of the package.
        parent: The parent widget.

    Returns:
        The chosen AAS, or None if the user cancelled.
    """
    labels = [describe_object(shell) for shell in shells]
    chosen, accepted = QInputDialog.getItem(
        parent, TITLE, "AAS to copy with its Submodels:", labels, 0, False
    )
    if not accepted or chosen not in labels:
        return None
    return shells[labels.index(chosen)]


def _row_shell(context: ActionContext) -> model.AssetAdministrationShell | None:
    obj = context.index.data(OBJECT_ROLE)
    return obj if isinstance(obj, model.AssetAdministrationShell) else None


def _is_shells_node(context: ActionContext) -> bool:
    return context.index.data(NAME_ROLE) == "shells"


def _shells_of(context: ActionContext) -> list[model.AssetAdministrationShell]:
    package: Any = context.package
    return sorted(
        (
            o
            for o in package.objStore
            if isinstance(o, model.AssetAdministrationShell)
        ),
        key=lambda shell: (shell.id_short or "", shell.id),
    )


def _can_copy(context: ActionContext) -> bool:
    if context.package is None:
        return False
    if _row_shell(context) is not None:
        return True
    return _is_shells_node(context) and bool(_shells_of(context))


def copy_shell(
    context: ActionContext, shell: model.AssetAdministrationShell
) -> ShellCopyPlan | None:
    """Copies an AAS with its Submodels as one undo step.

    Args:
        context: The view and package.
        shell: The AAS to copy.

    Returns:
        What was copied, or None when Read mode refused it.
    """
    package: Any = context.package
    plan = plan_copy_shell(shell, list(package.objStore))
    try:
        with package.commandStack.group(plan.description):
            for command in copy_shell_commands(
                observer_for(package), package.objStore, plan
            ):
                package.commandStack.push(command)
    except ReadOnlyError as error:
        show_problem(str(error), context.view)
        return None
    select_object(context.view, plan.shell)
    return plan


def _run(context: ActionContext) -> None:
    shell = _row_shell(context)
    if shell is None:
        shell = ask_shell(_shells_of(context), context.view)
    if shell is None:
        return
    plan = copy_shell(context, shell)
    if plan is not None and plan.unresolved:
        show_problem(
            f"{len(plan.unresolved)} Submodel reference"
            f"{'s' if len(plan.unresolved) != 1 else ''} of the AAS point "
            "to a Submodel that is not in this package. The copy refers to "
            "the same ones.",
            context.view,
        )


def register_shell_copy_actions() -> None:
    """Adds Copy AAS with new Submodel ids to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    if COPY_SHELL_ID in registered:
        return
    register_action(
        ActionSpec(
            action_id=COPY_SHELL_ID,
            text="Copy AAS with new Submodel ids...",
            run=_run,
            is_enabled=_can_copy,
            views=ViewKind.PACKAGES,
            status_tip=(
                "Copy the AAS and its Submodels under new ids, and let the "
                "copy refer to the copied Submodels"
            ),
            order=205,
        )
    )
