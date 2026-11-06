"""The actions Push location and Pop location (F-EDT-01 AC10 and AC11).

Call `register_location_actions` once, before the first tree view exists. The
composition root does that. The shortcuts are the ones of Package Explorer,
Ctrl+Shift+P and Ctrl+Shift+O. They are free here: `settings/shortcuts.py`
and the other actions use neither.

Push stores the selected row with its expand state. Pop selects the last
pushed row that still exists, expands or collapses it as it was, and says in
the status bar when nothing was left to go back to. Neither changes a package,
so both work in Read mode.
"""

from basyx.aas import model
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMainWindow

from aas_editor.application.locations import LocationStack
from aas_editor.application.locations import default_stack
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.tree_navigation import find_object
from aas_editor.ui.tree_navigation import select_object

PUSH_ID = "navigate.push_location"
POP_ID = "navigate.pop_location"
PUSH_KEY = "Ctrl+Shift+P"
POP_KEY = "Ctrl+Shift+O"

_MESSAGE_MS = 5000


def _target(context: ActionContext) -> object | None:
    """The object of the current row, if a location can name it."""
    if not context.index.isValid() or context.package is None:
        return None
    obj = context.index.data(OBJECT_ROLE)
    if obj is context.package or isinstance(obj, model.Referable):
        return obj
    return None


def _say(context: ActionContext, text: str) -> None:
    window = context.view.window()
    if isinstance(window, QMainWindow):
        status = window.statusBar()
        if status is not None:
            status.showMessage(text, _MESSAGE_MS)


def push_location(
    context: ActionContext, stack: LocationStack | None = None
) -> bool:
    """Stores the current row on the stack.

    Args:
        context: The view and its current row.
        stack: The stack to use, by default the one of the editor.

    Returns:
        False when the current row cannot be a location, so nothing is stored.
    """
    target = _target(context)
    if target is None:
        return False
    column0 = context.index.siblingAtColumn(0)
    (stack or default_stack()).push(
        target, context.package, context.view.isExpanded(column0)
    )
    _say(context, "Editing location pushed.")
    return True


def pop_location(
    context: ActionContext, stack: LocationStack | None = None
) -> bool:
    """Selects the last pushed row that is still in the tree.

    Locations whose object is gone, or that the tree does not show, are
    dropped. With none left nothing changes except a message.

    Args:
        context: The package tree view.
        stack: The stack to use, by default the one of the editor.

    Returns:
        Whether a row was selected.
    """
    stack = stack or default_stack()
    model_ = context.view.model()
    if len(stack) == 0:
        _say(context, "No editing location is pushed.")
        return False
    while model_ is not None:
        place = stack.pop()
        if place is None:
            break
        index = find_object(model_, place.target, place.package)
        if not index.isValid():
            continue
        select_object(context.view, place.target, place.package)
        current = context.view.currentIndex().siblingAtColumn(0)
        if context.view.isExpanded(current) != place.expanded:
            context.view.setExpanded(current, place.expanded)
        _say(context, "Editing location restored.")
        return True
    _say(context, "The pushed locations are no longer in the tree.")
    return False


def _push(context: ActionContext) -> None:
    push_location(context)


def _pop(context: ActionContext) -> None:
    pop_location(context)


def register_location_actions() -> None:
    """Adds Push location and Pop location to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    specs = (
        ActionSpec(
            action_id=PUSH_ID,
            text="Push location",
            run=_push,
            is_enabled=lambda context: _target(context) is not None,
            mutates=False,
            views=ViewKind.PACKAGES,
            shortcut=QKeySequence(PUSH_KEY),
            status_tip="Remember the selected row, to come back to it with Pop",
            order=900,
        ),
        ActionSpec(
            action_id=POP_ID,
            text="Pop location",
            run=_pop,
            is_enabled=lambda context: context.package is not None,
            mutates=False,
            views=ViewKind.PACKAGES,
            shortcut=QKeySequence(POP_KEY),
            status_tip="Go back to the row that Push location remembered",
            order=901,
        ),
    )
    for spec in specs:
        if spec.action_id not in registered:
            register_action(spec)
