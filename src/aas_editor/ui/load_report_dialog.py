"""The dialog that tells the user what the SDK left out when a package opened.

A package that only opens in failsafe mode lacks what the SDK refused to read.
The decision is in `aas_editor.domain.load_report`, and this module shows it:
a short summary on top, the full list below, and a button that copies the list.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.load_report import LoadReport


class LoadReportDialog(QDialog):
    """Shows what was left out of a package, and lets the user copy it.

    Attributes:
        summary_label: The explanation and the counts above the list.
        issues_list: One row for each thing the SDK reported, the biggest
            first.
        copy_button: Puts the whole report, with the records of the SDK, on
            the clipboard.
    """

    def __init__(
        self,
        package_name: str,
        report: LoadReport,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            package_name: The name of the package file.
            report: What the SDK reported when it read the package.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._report = report
        self.setWindowTitle("Content left out of the package")
        self.setMinimumWidth(760)

        self.summary_label = QLabel(_explanation(package_name, report))
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.issues_list = QListWidget()
        self.issues_list.setWordWrap(True)
        self.issues_list.setMinimumHeight(220)
        self.issues_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        for issue in report.by_weight():
            self.issues_list.addItem(issue.describe())

        self.copy_button = QPushButton("Copy list")
        self.copy_button.setToolTip(
            "Copy the list and the messages of the SDK to the clipboard"
        )
        self.copy_button.clicked.connect(self.copy_report)
        buttons = QDialogButtonBox()
        buttons.addButton(
            self.copy_button, QDialogButtonBox.ButtonRole.ActionRole
        )
        close = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        if close is not None:
            close.setDefault(True)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.issues_list)
        layout.addWidget(buttons)

    def copy_report(self) -> None:
        """Puts the report as text on the clipboard."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._report.text())


def _explanation(package_name: str, report: LoadReport) -> str:
    return (
        f"{package_name} could not be read completely. The editor opened "
        "what the SDK accepted.\n\n"
        f"{report.summary()}\n\n"
        "This content is not in the open package, and it is not in a copy "
        "that you save with Save As, because the SDK does not hand it to the "
        "editor. The file on disk is unchanged, and the package cannot "
        "overwrite it. The list has every message of the SDK, the largest "
        "losses first."
    )


def show_load_report(
    package_name: str, report: LoadReport, parent: QWidget | None = None
) -> None:
    """Shows what was left out when a package opened.

    Args:
        package_name: The name of the package file.
        report: What the SDK reported. An empty report shows nothing.
        parent: The parent widget.
    """
    if report:
        LoadReportDialog(package_name, report, parent).exec()
