"""Dialogs of the package files: pickers, questions, a text editor.

The decisions are made in `aas_editor.application.supplementary_files`. These
functions only ask the user and return the answer. Each one builds a widget,
runs it, and returns, so a test replaces the function or stubs `QDialog.exec`.
"""

from collections.abc import Sequence
import enum
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.supplementary_files import StoredFileInfo
from aas_editor.domain.file_references import FileReference

TITLE = "Package files"
# How many references the question about a removal lists.
MAX_LISTED = 8


class ReferenceAnswer(enum.Enum):
    """The answer to the question about references to a file that goes."""

    CLEAR = "clear"
    LEAVE = "leave"
    CANCEL = "cancel"


def show_warning(parent: QWidget | None, text: str) -> None:
    """Tells the user why something did not work."""
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        TITLE,
        text,
        QMessageBox.StandardButton.Ok,
        parent,
    )
    box.exec()


def show_information(parent: QWidget | None, text: str) -> None:
    """Tells the user what happened."""
    box = QMessageBox(
        QMessageBox.Icon.Information,
        TITLE,
        text,
        QMessageBox.StandardButton.Ok,
        parent,
    )
    box.exec()


def ask_remove_references(
    references: Sequence[FileReference], parent: QWidget | None = None
) -> ReferenceAnswer:
    """Asks what to do with the references to a file that is removed.

    Args:
        references: The File elements and thumbnails that refer to the file.
        parent: The parent widget.

    Returns:
        Clear the paths, leave them, or cancel the removal.
    """
    listed = [ref.location for ref in references[:MAX_LISTED]]
    if len(references) > MAX_LISTED:
        listed.append(f"... and {len(references) - MAX_LISTED} more")
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(TITLE)
    box.setText(
        f"{len(references)} reference(s) point to this file:\n\n"
        + "\n".join(listed)
    )
    box.setInformativeText(
        "Remove the paths, or leave them? Paths that are left point to a "
        "file that is no longer in the package, and the package cannot be "
        "saved as AASX until they are repaired."
    )
    clear = box.addButton(
        "Remove the paths", QMessageBox.ButtonRole.DestructiveRole
    )
    leave = box.addButton("Leave the paths", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    clicked = box.clickedButton()
    if clicked is clear:
        return ReferenceAnswer.CLEAR
    if clicked is leave:
        return ReferenceAnswer.LEAVE
    return ReferenceAnswer.CANCEL


def confirm(parent: QWidget | None, text: str) -> bool:
    """Asks a yes or no question. Cancel is the default."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(TITLE)
    box.setText(text)
    go_on = box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is go_on


def ask_text(
    parent: QWidget | None, title: str, label: str, text: str = ""
) -> str | None:
    """Asks for one line of text.

    Returns:
        The text, or None if the user cancelled or left it empty.
    """
    answer, accepted = QInputDialog.getText(
        parent, title, label, QLineEdit.EchoMode.Normal, text
    )
    answer = answer.strip()
    return answer if accepted and answer else None


def pick_file_to_add(parent: QWidget | None) -> Path | None:
    """Asks for a file on disk to add to the package."""
    path, _ = QFileDialog.getOpenFileName(parent, "Add file to package")
    return Path(path) if path else None


def pick_path_to_save(parent: QWidget | None, suggested: str) -> Path | None:
    """Asks where to write a file that is taken out of the package."""
    path, _ = QFileDialog.getSaveFileName(
        parent, "Save package file as", suggested
    )
    return Path(path) if path else None


class FileChoiceDialog(QDialog):
    """Lists the stored files, to choose one.

    Attributes:
        files_list: One row for each file, with its media type.
        filter_edit: Narrows the list to names that contain the text.
    """

    def __init__(
        self,
        infos: Sequence[StoredFileInfo],
        current: str | None = None,
        title: str = "Choose package file",
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            infos: The stored files to choose from.
            current: The name to select first.
            title: The window title.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(480, 360)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by name")
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        for info in infos:
            item = QListWidgetItem(f"{info.name}   ({info.content_type})")
            item.setData(Qt.ItemDataRole.UserRole, info.name)
            self.files_list.addItem(item)
            if info.name == current:
                self.files_list.setCurrentItem(item)
        self.files_list.itemDoubleClicked.connect(self._accept_item)
        self.empty_label = QLabel("The package has no files.")
        self.empty_label.setVisible(not infos)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.files_list)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.buttons)

    def _accept_item(self, item: QListWidgetItem) -> None:
        del item
        self.accept()

    def _apply_filter(self, text: str) -> None:
        needle = text.lower()
        for row in range(self.files_list.count()):
            item = self.files_list.item(row)
            if item is not None:
                item.setHidden(needle not in item.text().lower())

    @property
    def chosen(self) -> str | None:
        """The name of the selected file, or None."""
        item = self.files_list.currentItem()
        if item is None or item.isHidden():
            return None
        name = item.data(Qt.ItemDataRole.UserRole)
        return name if isinstance(name, str) else None


def choose_stored_file(
    infos: Sequence[StoredFileInfo],
    current: str | None = None,
    title: str = "Choose package file",
    parent: QWidget | None = None,
) -> str | None:
    """Asks the user to choose one of the stored files.

    Returns:
        The name of the file, or None if the user cancelled.
    """
    dialog = FileChoiceDialog(infos, current, title, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted.value:
        return None
    return dialog.chosen


class TextFileDialog(QDialog):
    """Edits the text of a stored file.

    Attributes:
        editor: The text editor.
    """

    def __init__(
        self, name: str, text: str, parent: QWidget | None = None
    ) -> None:
        """Builds the dialog.

        Args:
            name: The name of the file, for the title.
            text: The content to edit.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Edit text file '{name}'")
        self.resize(640, 480)
        self.editor = QPlainTextEdit()
        self.editor.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.editor.setPlainText(text)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.editor)
        layout.addWidget(self.buttons)

    @property
    def text(self) -> str:
        """The edited text."""
        return self.editor.toPlainText()


def edit_text(
    name: str, text: str, parent: QWidget | None = None
) -> str | None:
    """Lets the user edit the text of a file.

    Returns:
        The new text, or None if the user cancelled.
    """
    dialog = TextFileDialog(name, text, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted.value:
        return None
    return dialog.text


class DanglingDialog(QDialog):
    """Lists the references to files that are not in the package.

    The buttons are connected by the caller, which repairs the selected
    references and then calls `show_references` again.

    Attributes:
        table: One row for each reference: where it is, and its path.
        choose_button: Link the selected references to a stored file.
        add_button: Add a file from disk and link the references to it.
        clear_button: Take the paths out.
        summary_label: How many references are dangling.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Builds an empty dialog."""
        super().__init__(parent)
        self.setWindowTitle("Dangling file references")
        self.setMinimumSize(560, 360)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Where", "Path"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.buttons = QDialogButtonBox()
        self.choose_button = self.buttons.addButton(
            "Choose package file...", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.add_button = self.buttons.addButton(
            "Add file...", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.clear_button = self.buttons.addButton(
            "Clear path", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.buttons.addButton(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        layout.addWidget(self.buttons)
        self._references: list[FileReference] = []

    def show_references(self, references: Sequence[FileReference]) -> None:
        """Replaces the rows with the dangling references."""
        self._references = list(references)
        self.table.setRowCount(len(self._references))
        for row, reference in enumerate(self._references):
            self.table.setItem(row, 0, QTableWidgetItem(reference.location))
            self.table.setItem(row, 1, QTableWidgetItem(reference.path))
        has_rows = bool(self._references)
        self.summary_label.setText(
            f"{len(self._references)} reference(s) point to a file that is not "
            "in the package. The package cannot be saved as AASX until they "
            "are repaired."
            if has_rows
            else "No reference points to a missing file."
        )
        for button in (self.choose_button, self.add_button, self.clear_button):
            if button is not None:
                button.setEnabled(has_rows)
        if has_rows:
            self.table.selectRow(0)

    def selected_references(self) -> list[FileReference]:
        """The references of the selected rows."""
        selection = self.table.selectionModel()
        rows = (
            sorted({index.row() for index in selection.selectedRows()})
            if selection is not None
            else []
        )
        return [self._references[row] for row in rows]
