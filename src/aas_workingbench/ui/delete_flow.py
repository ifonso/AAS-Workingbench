"""The questions that come before deleting objects (decision D11).

A tree view calls `prepare_delete` before it deletes the selected rows. The
function finds the references to the objects, asks the user what the plan
needs asked, and returns the commands for the references. The view pushes them
in the same group as the deletes, so one undo brings everything back.
"""

from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass

from basyx.aas import model
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.edits import describe
from aas_workingbench.application.operations.delete import DeletePrompt
from aas_workingbench.application.operations.delete import cleanup_commands
from aas_workingbench.application.operations.delete import plan_delete
from aas_workingbench.application.operations.delete import prompt_for
from aas_workingbench.ui import reference_dialogs


class DeleteCancelled(Exception):  # noqa: N818
    """The user answered a question before a delete with Cancel."""


@dataclass(frozen=True)
class PreparedDelete:
    """What to do for the references, once the user has answered.

    Attributes:
        commands: The commands for the references: new positions for list
            items, and the references to take away if the user chose so.
            Empty when the delete needs none.
        description: The text for the undo step, if the view groups them.
    """

    commands: list[Command]
    description: str


def prepare_delete(
    objects: Iterable[model.Identifiable],
    targets: Sequence[model.Referable],
    observer: ModelChangeObserver,
    confirm: bool = True,
    skip_confirmation: bool = False,
    parent: QWidget | None = None,
) -> PreparedDelete:
    """Plans a delete, asks what the plan needs, and builds the commands.

    Args:
        objects: The identifiables of the package.
        targets: The shells, submodels, concept descriptions and elements the
            view is about to delete.
        observer: Where the commands report.
        confirm: False for a cut, which asks nothing and leaves the
            references, as the object comes back with the paste (D12).
        skip_confirmation: True if the user asked to delete without a question
            (Shift). The usages are still shown.
        parent: The parent widget of the dialogs.

    Returns:
        The commands for the references.

    Raises:
        DeleteCancelled: If the user cancelled.
    """
    plan = plan_delete(objects, targets)
    remove_references = False
    if confirm:
        prompt = prompt_for(plan, skip_confirmation)
        if prompt is DeletePrompt.USAGES:
            answer = reference_dialogs.ask_delete(plan, parent)
            if answer is None:
                raise DeleteCancelled
            remove_references = answer
        elif prompt is DeletePrompt.CONFIRM:
            if not reference_dialogs.confirm_delete(plan, parent):
                raise DeleteCancelled
    commands = cleanup_commands(observer, plan, remove_references)
    description = (
        f"Delete {describe(plan.targets[0])}"
        if len(plan.targets) == 1
        else f"Delete {len(plan.targets)} items"
    )
    return PreparedDelete(commands, description)
