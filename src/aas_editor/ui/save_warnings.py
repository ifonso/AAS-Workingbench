"""Dialogs that tell the user what a save refuses, drops, or leaves broken.

The decisions are made in `aas_editor.application.save`. This module only shows
them, and returns the answer of the user.
"""

from collections.abc import Sequence

from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.save import SaveCheck
from aas_editor.application.save import SaveIssue
from aas_editor.domain.parts import MissingFile

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
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)

        self.summary_label = QLabel(summary)
        self.summary_label.setWordWrap(True)

        self.issues_list = QListWidget()
        for issue in issues:
            self.issues_list.addItem(issue.message)
            for detail in issue.details:
                self.issues_list.addItem(f"    {detail}")

        self.buttons = QDialogButtonBox()
        if accept_text is None:
            ok = self.buttons.addButton(QDialogButtonBox.StandardButton.Ok)
            if ok is not None:
                ok.setDefault(True)
            self.buttons.accepted.connect(self.accept)
        else:
            go_on = self.buttons.addButton(
                accept_text, QDialogButtonBox.ButtonRole.AcceptRole
            )
            cancel = self.buttons.addButton(
                cancel_text, QDialogButtonBox.ButtonRole.RejectRole
            )
            if go_on is not None:
                go_on.setAutoDefault(False)
            if cancel is not None:
                cancel.setDefault(True)
            self.buttons.accepted.connect(self.accept)
            self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.issues_list)
        layout.addWidget(self.buttons)


def confirm_save(check: SaveCheck, parent: QWidget | None = None) -> bool:
    """Asks whether to save although the save drops content.

    Args:
        check: The result of the check, with warnings.
        parent: The parent widget.

    Returns:
        True if the user chose to save anyway.
    """
    dialog = IssuesDialog(
        "Save package",
        "Saving this package drops content, or the package breaks rules of "
        "the metamodel. Do you want to save anyway?",
        check.warnings,
        accept_text="Save anyway",
        parent=parent,
    )
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted.value


def show_save_refused(check: SaveCheck, parent: QWidget | None = None) -> None:
    """Tells the user why a package cannot be saved.

    Args:
        check: The result of the check, with blockers.
        parent: The parent widget.
    """
    IssuesDialog(
        "Package cannot be saved",
        "The package was not saved, and nothing was changed.",
        check.blockers,
        parent=parent,
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
