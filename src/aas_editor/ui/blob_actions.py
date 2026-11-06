"""Context menu actions to load, save, and convert the bytes of a Blob.

The Blob editor does the same in its dialog. The load and save actions skip the
dialog, and work for content that is too large for the editor to show. Loading
is one step of the history of the package, and sets the media type to the one
of the file extension when the Blob has none. Saving changes nothing, so it
also works in Read mode.

"Base64 text to bytes" and "Bytes to Base64 text" (F-EDT-04 AC9, F-EDT-10 AC14
and AC15) change the bytes themselves: the content of a Blob that holds Base64
text becomes the bytes it spells, and the other way round. They are not about
how a file stores a Blob, which is always Base64 in JSON and XML. Each is one
undo step, which is why there is no question before it (the original asks
because it cannot undo).
"""

from collections.abc import Callable
from pathlib import Path

from basyx.aas import model
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QMessageBox

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.domain import blob_content
from aas_editor.domain.value_types import InvalidValueError
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.actions import ViewKind

LOAD_ACTION_ID = "blob.load_content"
SAVE_ACTION_ID = "blob.save_content"
FROM_BASE64_ACTION_ID = "blob.from_base64"
TO_BASE64_ACTION_ID = "blob.to_base64"


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


def _convert(
    context: ActionContext,
    convert: Callable[[bytes], bytes],
    description: str,
) -> None:
    """Replaces the bytes of the Blob by the converted ones, or says why not."""
    blob = _blob(context)
    if blob is None or blob.value is None or context.package is None:
        return
    try:
        converted = convert(blob.value)
    except InvalidValueError as error:
        _show_error(context, f"The content was not changed. {error}.")
        return
    context.push(
        SetAttribute(
            observer_for(context.package),
            blob,
            "value",
            converted,
            description=f"{description} of {blob.id_short or 'Blob'}",
        )
    )


def base64_text_to_bytes(context: ActionContext) -> None:
    """Takes the content as Base64 text and keeps the bytes that it spells."""
    _convert(context, blob_content.decode_base64, "Base64 text to bytes")


def bytes_to_base64_text(context: ActionContext) -> None:
    """Replaces the bytes by their Base64 text."""
    _convert(context, blob_content.encode_base64, "Bytes to Base64 text")


def register_blob_actions() -> None:
    """Adds the actions to the registry, once.

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
    if FROM_BASE64_ACTION_ID not in registered:
        register_action(
            ActionSpec(
                action_id=FROM_BASE64_ACTION_ID,
                text="Blob: Base64 text to bytes",
                run=base64_text_to_bytes,
                is_enabled=_has_content,
                views=ViewKind.PACKAGES,
                status_tip="The content is Base64 text. Replace it by the "
                "bytes that it spells",
                order=202,
            )
        )
    if TO_BASE64_ACTION_ID not in registered:
        register_action(
            ActionSpec(
                action_id=TO_BASE64_ACTION_ID,
                text="Blob: Bytes to Base64 text",
                run=bytes_to_base64_text,
                is_enabled=_has_content,
                views=ViewKind.PACKAGES,
                status_tip="Replace the bytes of the content by their Base64 "
                "text",
                order=203,
            )
        )
