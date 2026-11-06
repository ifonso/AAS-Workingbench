"""Context menu actions to load and save the bytes of a Blob.

The Blob editor does the same in its dialog. These two actions skip the dialog,
and work for content that is too large for the editor to show. Loading is one
step of the history of the package, and sets the media type to the one of the
file extension when the Blob has none. Saving changes nothing, so it also works
in Read mode.
"""

from pathlib import Path

from basyx.aas import model
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QMessageBox

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.domain import blob_content
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.actions import ViewKind

LOAD_ACTION_ID = "blob.load_content"
SAVE_ACTION_ID = "blob.save_content"


def _blob(context: ActionContext) -> model.Blob | None:
    obj = context.index.data(OBJECT_ROLE)
    return obj if isinstance(obj, model.Blob) else None


def _is_blob(context: ActionContext) -> bool:
    return _blob(context) is not None


def _has_content(context: ActionContext) -> bool:
    blob = _blob(context)
    return blob is not None and blob.value is not None


def _show_error(context: ActionContext, message: str) -> None:
    QMessageBox.warning(context.view, "Blob", message)


def load_content(context: ActionContext) -> None:
    """Asks for a file and takes its bytes as the content of the Blob."""
    blob = _blob(context)
    if blob is None or context.package is None or context.stack is None:
        return
    path, _ = QFileDialog.getOpenFileName(
        context.view, "Load content into Blob from file"
    )
    if not path:
        return
    try:
        content = Path(path).read_bytes()
    except OSError as error:
        _show_error(context, f"The file could not be read: {error}")
        return
    observer = observer_for(context.package)
    with context.stack.group(f"Load content into {blob.id_short or 'Blob'}"):
        context.push(SetAttribute(observer, blob, "value", content))
        guessed = blob_content.guess_content_type(path)
        if guessed and not blob.content_type:
            context.push(SetAttribute(observer, blob, "content_type", guessed))


def save_content(context: ActionContext) -> None:
    """Asks for a file name and writes the bytes of the Blob into it."""
    blob = _blob(context)
    if blob is None or blob.value is None:
        return
    suggested = (blob.id_short or "content") + blob_content.guess_extension(
        blob.content_type
    )
    path, _ = QFileDialog.getSaveFileName(
        context.view, "Save content of Blob to file", suggested
    )
    if not path:
        return
    try:
        Path(path).write_bytes(blob.value)
    except OSError as error:
        _show_error(context, f"The file could not be written: {error}")


def register_blob_actions() -> None:
    """Adds the two actions to the registry, once.

    Call it before the first view is created, from the composition root.
    """
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    if LOAD_ACTION_ID not in registered:
        register_action(
            ActionSpec(
                action_id=LOAD_ACTION_ID,
                text="Load Blob content from file...",
                run=load_content,
                is_enabled=_is_blob,
                views=ViewKind.PACKAGES,
                status_tip="Replace the content of the Blob with a file",
                order=200,
            )
        )
    if SAVE_ACTION_ID not in registered:
        register_action(
            ActionSpec(
                action_id=SAVE_ACTION_ID,
                text="Save Blob content to file...",
                run=save_content,
                is_enabled=_has_content,
                mutates=False,
                views=ViewKind.PACKAGES,
                status_tip="Write the content of the Blob into a file",
                order=201,
            )
        )
