"""The actions that change many selected objects at once.

Call `register_bulk_edit_actions` once, before the first tree view exists. The
composition root does that.

- "Change attribute with a pattern..." changes the idShort, description,
  display name, or text value of the selected objects, after a preview of
  every result (see `ui/bulk_dialogs.py` and
  `application/operations/bulk_edit.py`).
- "Remove extensions..." removes the extensions of the selected objects that
  share a name or a semantic id.

Each is one undo step and is refused in Read mode. The moves of a selection
are in `ui/move_actions.py`, and the presets and the clipboard in
`ui/preset_actions.py`.
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QWidget

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import Command
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.operations.bulk_edit import change_commands
from aas_editor.application.operations.bulk_edit import (
    remove_extension_commands,
)
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui import bulk_dialogs
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.move_actions import selected_rows

CHANGE_ID = "bulk.change_attribute"
REMOVE_EXTENSIONS_ID = "bulk.remove_extensions"


def selected_objects(context: ActionContext) -> list[Any]:
    """Returns the objects of the selected rows, in the order of the rows."""
    objects: list[Any] = []
    for index in selected_rows(context):
        obj = index.data(OBJECT_ROLE)
        if obj is not None and not any(obj is held for held in objects):
            objects.append(obj)
    return objects


def run_group(
    context: ActionContext,
    title: str,
    description: str,
    commands: list[Command],
) -> bool:
    """Pushes commands as one undo step, and tells the user if that fails.

    Args:
        context: What the action works on.
        title: The title of a message.
        description: The text of the undo step.
        commands: The commands to push.

    Returns:
        Whether the step was made. After a failure nothing has changed.
    """
    parent: QWidget = context.view
    stack = context.stack
    if stack is None:
        return False
    try:
        with stack.group(description):
            for command in commands:
                stack.push(command)
    except ReadOnlyError as error:
        bulk_dialogs.show_problem(title, str(error), parent)
        return False
    except Exception as error:  # noqa: BLE001
        bulk_dialogs.show_problem(
            title,
            f"The change was refused, and nothing was changed: {error}",
            parent,
        )
        return False
    return True


def _referables(context: ActionContext) -> list[model.Referable]:
    return [
        obj
        for obj in selected_objects(context)
        if isinstance(obj, model.Referable)
    ]


def _can_change(context: ActionContext) -> bool:
    return context.package is not None and bool(_referables(context))


def _change(context: ActionContext) -> None:
    package: Any = context.package
    targets = _referables(context)
    if package is None or not targets:
        return
    plan = bulk_dialogs.ask_change(package.objStore, targets, context.view)
    if plan is None:
        return
    try:
        commands = change_commands(observer_for(package), plan)
    except ValueError as error:
        bulk_dialogs.show_problem("Change attribute", str(error), context.view)
        return
    run_group(context, "Change attribute", plan.description, commands)


def _can_remove_extensions(context: ActionContext) -> bool:
    # The state is asked when the current row changes, so it cannot depend on
    # whether an object has extensions now: an add would leave it stale.
    return context.package is not None and any(
        isinstance(obj, model.HasExtension) for obj in selected_objects(context)
    )


def _remove_extensions(context: ActionContext) -> None:
    package: Any = context.package
    if package is None:
        return
    group = bulk_dialogs.ask_extension_group(
        selected_objects(context), context.view
    )
    if group is None:
        return
    commands = remove_extension_commands(observer_for(package), group)
    run_group(
        context,
        "Remove extensions",
        f"Remove {group.count} extensions named {group.key}"
        if group.entries
        else "Remove extensions",
        commands,
    )


def register_bulk_edit_actions() -> None:
    """Adds the bulk change and the removal of extensions, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    specs = (
        ActionSpec(
            action_id=CHANGE_ID,
            text="Change attribute with a pattern...",
            run=_change,
            is_enabled=_can_change,
            views=ViewKind.PACKAGES,
            status_tip=(
                "Change the idShort, description, display name or value of "
                "the selected objects, with a preview"
            ),
            order=400,
        ),
        ActionSpec(
            action_id=REMOVE_EXTENSIONS_ID,
            text="Remove extensions...",
            run=_remove_extensions,
            is_enabled=_can_remove_extensions,
            views=ViewKind.PACKAGES,
            status_tip=(
                "Remove the extensions of the selected objects that share "
                "a name or semantic id"
            ),
            order=401,
        ),
    )
    for spec in specs:
        if spec.action_id not in registered:
            register_action(spec)
