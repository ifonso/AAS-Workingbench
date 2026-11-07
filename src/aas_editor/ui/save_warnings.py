"""Dialogs that tell the user what a save refuses, drops, or leaves broken.

The decisions are made in `aas_editor.application.save`. This module only shows
them, and returns the answer of the user.
"""

from collections.abc import Callable
from collections.abc import Sequence
import errno
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.save import DANGLING_FILES
from aas_editor.application.save import FILES_NOT_WRITTEN
from aas_editor.application.save import LOAD_REPORT
from aas_editor.application.save import SaveCheck
from aas_editor.application.save import SaveIssue
from aas_editor.domain.parts import MissingFile
from aas_editor.ui.dialog_layout import finish_dialog
from aas_editor.ui.dialog_layout import make_button_box

# How many paths the dialog about missing files lists.
MAX_LISTED_PATHS = 10


class IssuesDialog(QDialog):
    """Lists issues with their details, and asks to go on or to cancel.

    Attributes:
        summary_label: The sentence above the list.
        issues_list: One row per issue and one indented row per detail.
        buttons: The buttons. With an accept text there are two, "accept" and
            "cancel". Without, there is only an OK button.
    """

    def __init__(
        self,
        title: str,
        summary: str,
        issues: Sequence[SaveIssue],
        accept_text: str | None = None,
        cancel_text: str = "Cancel",
        parent: QWidget | None = None,
        extra_text: str | None = None,
        on_extra: Callable[[], None] | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            title: The window title.
            summary: The sentence above the list.
            issues: What to list.
            accept_text: The text of the button that goes on. None for a
                dialog that only informs, with a single OK button.
            cancel_text: The text of the button that cancels. The default
                button, so that Enter never goes on.
            parent: The parent widget.
            extra_text: The text of a third button that helps to fix the
                issues, such as "Repair file references...". None for none.
            on_extra: Called when that button is pressed. The dialog then
                closes as cancelled, so that nothing is saved before the user
                looked at the result of the repair.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        # Messages name the rule, the place, and the problem, and ran past
        # 480 pixels.
        self.setMinimumWidth(720)

        self.summary_label = QLabel(summary)
        self.summary_label.setWordWrap(True)

        self.issues_list = QListWidget()
        self.issues_list.setWordWrap(True)
        self.issues_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for issue in issues:
            self.issues_list.addItem(issue.message)
            for detail in issue.details:
                self.issues_list.addItem(f"    {detail}")

        if accept_text is None:
            self.buttons = QDialogButtonBox()
            ok = self.buttons.addButton(QDialogButtonBox.StandardButton.Ok)
            if ok is not None:
                ok.setDefault(True)
            self.buttons.accepted.connect(self.accept)
        else:
            self.buttons = make_button_box(
                self, accept_text, cancel_text, safe_default=True
            )

        self.extra_button = None
        if extra_text is not None and on_extra is not None:
            self.extra_button = self.buttons.addButton(
                extra_text, QDialogButtonBox.ButtonRole.ActionRole
            )
            if self.extra_button is not None:
                self.extra_button.setAutoDefault(False)
                self.extra_button.clicked.connect(
                    lambda: self._run_extra(on_extra)
                )

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.issues_list)
        layout.addWidget(self.buttons)
        finish_dialog(self)

    def _run_extra(self, action: Callable[[], None]) -> None:
        self.reject()
        action()


def _has_code(issues: Sequence[SaveIssue], code: str) -> bool:
    return any(issue.code == code for issue in issues)


def confirm_save(
    check: SaveCheck,
    parent: QWidget | None = None,
    show_files: Callable[[], None] | None = None,
) -> bool:
    """Asks whether to save although the save drops content.

    Args:
        check: The result of the check, with warnings.
        parent: The parent widget.
        show_files: Shows the files of the package. When the warnings are
            about files that the target format cannot hold, the dialog offers
            a button that cancels the save and calls it, so the user can
            look at the files first.

    Returns:
        True if the user chose to save anyway.
    """
    offer_files = show_files is not None and _has_code(
        check.warnings, FILES_NOT_WRITTEN
    )
    dialog = IssuesDialog(
        "Save package",
        "Saving this package drops content, or the package breaks rules of "
        "the metamodel. Do you want to save anyway?",
        check.warnings,
        accept_text="Save anyway",
        parent=parent,
        extra_text="Show package files..." if offer_files else None,
        on_extra=show_files if offer_files else None,
    )
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted.value


def show_save_refused(
    check: SaveCheck,
    parent: QWidget | None = None,
    repair_files: Callable[[], None] | None = None,
    show_load_report: Callable[[], None] | None = None,
) -> None:
    """Tells the user why a package cannot be saved.

    Args:
        check: The result of the check, with blockers.
        parent: The parent widget.
        repair_files: Opens the repair of the file references. When a File
            points to a file that is not in the package, the dialog offers a
            button for it.
        show_load_report: Shows the full list of what the SDK left out when
            the package was opened. When that is why the package cannot be
            saved, the dialog offers a button for it, because it lists only
            the first items.
    """
    offer_repair = repair_files is not None and _has_code(
        check.blockers, DANGLING_FILES
    )
    offer_report = show_load_report is not None and _has_code(
        check.blockers, LOAD_REPORT
    )
    extra_text = None
    on_extra = None
    if offer_repair:
        extra_text, on_extra = "Repair file references...", repair_files
    elif offer_report:
        extra_text, on_extra = "Show the full list...", show_load_report
    IssuesDialog(
        "Package cannot be saved",
        "The package was not saved, and nothing was changed.",
        check.blockers,
        parent=parent,
        extra_text=extra_text,
        on_extra=on_extra,
    ).exec()


def show_missing_files(
    package_name: str,
    missing: Sequence[MissingFile],
    parent: QWidget | None = None,
) -> None:
    """Tells the user that a package opened with files missing.

    Args:
        package_name: The name of the package file.
        missing: The File elements that point to a file that is not stored.
        parent: The parent widget.
    """
    paths = sorted({file.path for file in missing})
    listed = paths[:MAX_LISTED_PATHS]
    if len(paths) > MAX_LISTED_PATHS:
        listed.append(f"... and {len(paths) - MAX_LISTED_PATHS} more")
    IssuesDialog(
        "Files missing in package",
        f"{package_name} points to files that are not in the package. It "
        "was opened so that you can repair it. It cannot be saved as AASX "
        "until the paths are removed or the files are added.",
        [SaveIssue(f"{len(paths)} missing", tuple(listed))],
        parent=parent,
    ).exec()


def explain_save_error(target: Path, error: BaseException) -> str | None:
    """Says in plain words why a file could not be written, when it is known.

    Args:
        target: The file that the save wrote to.
        error: What the write raised.

    Returns:
        A sentence for the user, or None when the cause is not one of the
        causes that a person can act on.
    """
    unchanged = (
        "Your changes are still in the editor, and the file on disk is as it "
        "was."
    )
    if isinstance(error, PermissionError):
        return (
            f"{target.name} could not be written. It is read-only, or "
            "another program has it open. Close it there, or choose Save As "
            f"and give the copy another name. {unchanged}"
        )
    if isinstance(error, FileNotFoundError):
        return (
            f"The folder {target.parent} does not exist. Choose Save As and "
            f"pick a folder that does. {unchanged}"
        )
    if isinstance(error, OSError) and error.errno == errno.ENOSPC:
        return (
            f"There is no space left on the disk of {target.name}. Free some "
            f"space, or choose Save As and pick another disk. {unchanged}"
        )
    return None


def show_save_failed(
    explanation: str, details: str, parent: QWidget | None = None
) -> None:
    """Tells the user that a save failed, with the cause in plain words.

    Args:
        explanation: The sentence of `explain_save_error`.
        details: The technical text of the error, behind Show Details.
        parent: The parent widget.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Package was not saved")
    box.setText(explanation)
    box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
