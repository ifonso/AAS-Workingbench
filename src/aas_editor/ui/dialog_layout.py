"""The pattern that the dialogs of the editor follow.

A dialog has 12 pixels of padding and 8 between its parts, and its buttons sit
in a `QDialogButtonBox`, so that the platform decides their order and side.
The button that Enter presses is marked, and Cancel keeps that mark where the
dialog asks for a safe default. The style sheet draws the accent from these
marks (`ui/theme/app.qss.template`):

* The accept button is filled with the accent when it is the default one. That
  is the action that the dialog is for. A dialog that has no accept button
  fills its default button, such as Close.
* A default button that is not the accept button, such as Cancel as a safe
  default, has an accent outline and no fill, so that a person sees what Enter
  does without a second button that looks like the main action.
* A button of a destructive action is never filled.

Use `make_button_box` for the buttons and `finish_dialog` as the last step of
the constructor. A dialog that builds its fields after its buttons calls
`focus_first_field` from `showEvent`.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLayout
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QScrollArea
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.design_tokens import DIALOG_GAP
from aas_editor.domain.design_tokens import DIALOG_PADDING

PRIMARY: str = "primary"
"""The property that the style sheet fills with the accent."""


def pad_dialog(layout: QLayout) -> None:
    """Gives the outer layout of a dialog the padding and gap of the pattern.

    Args:
        layout: The layout that holds the content and the buttons.
    """
    layout.setContentsMargins(
        DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING
    )
    layout.setSpacing(DIALOG_GAP)


def accept_button(buttons: QDialogButtonBox) -> QPushButton | None:
    """Finds the button of a button box that accepts the dialog.

    Args:
        buttons: The button box.

    Returns:
        The first button with the accept role, or None.
    """
    for button in buttons.buttons():
        if buttons.buttonRole(
            button
        ) is QDialogButtonBox.ButtonRole.AcceptRole and isinstance(
            button, QPushButton
        ):
            return button
    return None


def make_button_box(
    dialog: QDialog,
    accept_text: str,
    reject_text: str = "Cancel",
    *,
    safe_default: bool = False,
) -> QDialogButtonBox:
    """Builds the accept and reject buttons of a dialog.

    Args:
        dialog: The dialog that `accepted` and `rejected` are connected to.
        accept_text: The text of the accept button.
        reject_text: The text of the reject button.
        safe_default: Whether Enter presses the reject button, for a dialog
            that changes much, so that a stray Enter does nothing.

    Returns:
        The box. Call `finish_dialog` when the dialog is complete.
    """
    buttons = QDialogButtonBox()
    go_on = buttons.addButton(
        accept_text, QDialogButtonBox.ButtonRole.AcceptRole
    )
    cancel = buttons.addButton(
        reject_text, QDialogButtonBox.ButtonRole.RejectRole
    )
    if safe_default:
        if go_on is not None:
            go_on.setAutoDefault(False)
        if cancel is not None:
            cancel.setDefault(True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


def _main_button(buttons: QDialogButtonBox) -> QPushButton | None:
    """Finds the button that the dialog is for: accept, or else apply."""
    for role in (
        QDialogButtonBox.ButtonRole.AcceptRole,
        QDialogButtonBox.ButtonRole.ApplyRole,
    ):
        for button in buttons.buttons():
            if buttons.buttonRole(button) is role and isinstance(
                button, QPushButton
            ):
                return button
    return None


def mark_primary(button: QPushButton, primary: bool = True) -> None:
    """Fills a button with the accent, or takes the fill away.

    Args:
        button: The button.
        primary: Whether it is the main action of its dialog.
    """
    button.setProperty(PRIMARY, primary)
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)


def finish_dialog(
    dialog: QDialog, *, destructive: bool = False, pad: bool = True
) -> None:
    """Applies the pattern to a dialog whose content is complete.

    It pads the layout, and settles which button Enter presses. A default
    that was set while its box was not yet inside the dialog is set again,
    because the dialog only notes it then. Without that, the first helper
    button of the dialog, such as "Generate", took the default at the first
    show.

    Args:
        dialog: The dialog, with its layout and its button boxes.
        destructive: Whether the accept button deletes or removes. It then
            has no fill.
        pad: Whether to pad the layout. A dialog that pads its own parts, as
            `EditDialog` does for its scroll area, passes False.
    """
    layout = QDialog.layout(dialog)
    if pad and layout is not None:
        pad_dialog(layout)
    for box in dialog.findChildren(QDialogButtonBox):
        accept = _main_button(box)
        default = next(
            (
                button
                for button in box.buttons()
                if isinstance(button, QPushButton) and button.isDefault()
            ),
            None,
        )
        if default is None:
            default = accept
        if default is not None:
            default.setDefault(False)
            default.setDefault(True)
        # A dialog with no accept or apply button, such as one that only has
        # Close, fills its default button.
        main = accept if accept is not None else default
        if main is not None:
            mark_primary(main, default is main and not destructive)


def _is_read_only(widget: QWidget) -> bool:
    """Tells whether a widget shows text that the user cannot change."""
    return (
        isinstance(widget, QLineEdit | QPlainTextEdit | QTextEdit)
        and widget.isReadOnly()
    )


def focus_first_field(dialog: QDialog) -> None:
    """Gives the first field of a dialog the focus, when a button has it.

    A dialog that builds its buttons before its fields has the buttons first
    in the order of the Tab key. Qt then puts the focus on the default button,
    so a person who opens the dialog and types gets nothing, and Enter
    accepts what was not looked at. Call this from `showEvent`.

    Args:
        dialog: The dialog. Nothing happens if a field already has the focus.
    """
    current = dialog.focusWidget()
    if current is not None and not isinstance(current, QPushButton):
        return
    boxes = dialog.findChildren(QDialogButtonBox)
    widget = dialog.nextInFocusChain()
    while widget is not None and widget is not dialog:
        in_boxes = any(box.isAncestorOf(widget) for box in boxes)
        takes_keys = bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
        if (
            takes_keys
            and not in_boxes
            and not isinstance(widget, QPushButton | QScrollArea)
            and widget.isEnabled()
            and widget.isVisibleTo(dialog)
            and not _is_read_only(widget)
        ):
            widget.setFocus()
            return
        widget = widget.nextInFocusChain()
