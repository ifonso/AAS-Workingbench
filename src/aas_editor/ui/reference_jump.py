"""Jumping from a reference to the object it points at (F-EDT-11).

Clicking the link of a model reference that resolves already opens its target
in a tab. This adds the action "Jump to target" for every kind of reference:

- A model reference that resolves, and an external reference whose id belongs
  to an object of the package, open that object.
- A reference that resolves in part opens the deepest object it reaches, and
  says which key was not found. Package Explorer stays silent here.
- A reference to nothing, and an external reference to something outside of the
  package, say so in a message.

The package tree shows shells, submodels, and elements, not their
references, so the action belongs to the attribute tabs. The target opens in the
same tab, so Back returns to the object being edited, and Forward goes on again.

Call `register_jump_actions` once before the first tree view exists.
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.reference_picker import ReferenceState
from aas_editor.domain.reference_picker import ReferenceStatus
from aas_editor.domain.reference_picker import status_of
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import describe_object
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.app_settings import PACK_ITEM_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action

JUMP_ID = "reference.jump"
TITLE = "Jump to target"


def show_notice(text: str, parent: QWidget | None = None) -> None:
    """Tells the user why a jump did not go where the reference points."""
    QMessageBox.information(parent, TITLE, text)


def reference_of(index: QModelIndex) -> model.Reference | None:
    """Returns the reference a row shows, or the one a key row belongs to."""
    obj: object = index.data(OBJECT_ROLE)
    if isinstance(obj, model.Key):
        obj = index.parent().data(OBJECT_ROLE)
    return obj if isinstance(obj, model.Reference) else None


def explain_jump(status: ReferenceStatus) -> str | None:
    """Returns what to tell the user about a jump, or None if it went well."""
    if status.state is ReferenceState.RESOLVED:
        return None
    if status.state is ReferenceState.PARTIAL and status.reached is not None:
        return (
            f"Target not found. {status.text}.\n\n"
            f"{describe_object(status.reached)} is the closest object, "
            "and it was opened."
        )
    if status.state is ReferenceState.OUTSIDE:
        return f"{status.text}. There is no object in this package to jump to."
    return f"Target not found. {status.text}."


def _find_in_model(shown: Any, obj: object) -> QModelIndex | None:
    """Finds the row of an object, in the index space of the model given.

    The model may be a proxy over the model of the packages, and only the
    model of the packages knows the objects of its rows.
    """
    source = shown.sourceModel() if hasattr(shown, "sourceModel") else shown
    found: list[QModelIndex] = source.match(
        QModelIndex(), OBJECT_ROLE, obj, hits=1
    )
    if not found:
        return None
    if source is shown:
        return found[0]
    mapped: QModelIndex = shown.mapFromSource(found[0])
    return mapped if mapped.isValid() else None


def _is_tab_view(view: object) -> bool:
    from aas_editor.treeviews.treeview_detailed import AttrsTreeView

    return isinstance(view, AttrsTreeView)


def _open_in_tab(context: ActionContext, target: model.Referable) -> bool:
    pack_item: QModelIndex | None = context.index.data(PACK_ITEM_ROLE)
    shown = pack_item.model() if pack_item is not None else None
    if shown is None:
        return False
    found = _find_in_model(shown, target)
    if found is None:
        return False
    # The tab keeps the current object in its history, so Back returns to it.
    view: Any = context.view
    view.openInCurrTabClicked.emit(found)
    return True


def jump(context: ActionContext) -> None:
    """Opens the target of the reference in the current row."""
    reference = reference_of(context.index)
    package: Any = context.package
    if reference is None or package is None:
        return
    status = status_of(ReferenceIndex(package.objStore), reference)
    destination = status.target or status.reached
    opened = False
    if destination is not None:
        opened = _is_tab_view(context.view) and _open_in_tab(
            context, destination
        )
    message = explain_jump(status)
    if destination is not None and not opened:
        message = (
            f"{describe_object(destination)} is in this package, but no "
            "view could open it."
        )
    if message is not None:
        show_notice(message, context.view)


def _can_jump(context: ActionContext) -> bool:
    return context.package is not None and (
        reference_of(context.index) is not None
    )


def register_jump_actions() -> None:
    """Adds the jump actions to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    if JUMP_ID in registered:
        return
    register_action(
        ActionSpec(
            action_id=JUMP_ID,
            text="Jump to target",
            run=jump,
            is_enabled=_can_jump,
            mutates=False,
            views=ViewKind.DETAILS,
            status_tip="Open the object that the reference points at",
            order=400,
        )
    )
