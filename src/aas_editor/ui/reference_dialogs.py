"""Dialogs for renames, deletes and repairs that touch references.

The plans in `aas_editor.application.operations` decide what would happen.
These dialogs only show a plan and return the answer of the user. Each
function builds a dialog, runs it, and returns the answer, so a test stubs
`QDialog.exec` or answers through `dialog.accept()`.
"""

from collections.abc import Callable
from collections.abc import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QRadioButton
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.ui.colors import PROBLEM_STYLE
from aas_editor.application.operations.delete import DeletePlan
from aas_editor.application.operations.references import ReferenceChange
from aas_editor.application.operations.rename import InvalidIdShortError
from aas_editor.application.operations.rename import RenameError
from aas_editor.application.operations.rename import RenamePlan
from aas_editor.domain.references import Usage
from aas_editor.domain.references import describe_object
from aas_editor.domain.references import describe_reference

# How many objects the delete dialog names before it says "and N more".
MAX_LISTED_OBJECTS = 5


class ReferenceTable(QTableWidget):
    """A table of references: where each is stored, and what it holds."""

    def __init__(self, headers: Sequence[str], parent: QWidget | None = None):
        """Builds an empty table.

        Args:
            headers: The titles of the columns.
            parent: The parent widget.
        """
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(list(headers))
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.verticalHeader().setVisible(False)  # pyright: ignore[reportOptionalMemberAccess]
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setMinimumHeight(140)
        self.setWordWrap(True)
        # The end of an id tells ids apart, so the middle is left out.
        self.setTextElideMode(Qt.TextElideMode.ElideMiddle)

    def set_rows(self, rows: Sequence[Sequence[str]]) -> None:
        """Replaces the content of the table."""
        self.setRowCount(len(rows))
        for row, cells in enumerate(rows):
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                self.setItem(row, column, item)
        self.resizeRowsToContents()

    def texts(self) -> list[list[str]]:
        """Returns the text of every cell, row by row."""
        return [
            [
                (self.item(row, column) or QTableWidgetItem()).text()
                for column in range(self.columnCount())
            ]
            for row in range(self.rowCount())
        ]


def change_rows(changes: Sequence[ReferenceChange]) -> list[list[str]]:
    """Describes reference changes as rows: where, before, after."""
    return [
        [
            change.slot.location,
            describe_reference(change.before),
            "(removed)"
            if change.after is None
            else describe_reference(change.after),
        ]
        for change in changes
    ]


def usage_rows(usages: Sequence[Usage]) -> list[list[str]]:
    """Describes usages as rows: where, and the reference."""
    return [
        [usage.slot.location, describe_reference(usage.reference)]
        for usage in usages
    ]


def _buttons(
    dialog: QDialog, accept_text: str, cancel_text: str = "Cancel"
) -> QDialogButtonBox:
    """Builds an accept and a cancel button, with cancel as the default."""
    buttons = QDialogButtonBox()
    go_on = buttons.addButton(
        accept_text, QDialogButtonBox.ButtonRole.AcceptRole
    )
    cancel = buttons.addButton(
        cancel_text, QDialogButtonBox.ButtonRole.RejectRole
    )
    if go_on is not None:
        go_on.setAutoDefault(False)
    if cancel is not None:
        cancel.setDefault(True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


def _answered_yes(dialog: QDialog) -> bool:
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted.value


class ReferenceChangesDialog(QDialog):
    """Shows the references that an action would change, and asks to go on.

    Attributes:
        intro_label: The sentence above the table.
        table: One row for each change: where, before, after.
        notes_label: Text below the table, or hidden when there is none.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        title: str,
        intro: str,
        changes: Sequence[ReferenceChange],
        notes: Sequence[str] = (),
        accept_text: str = "Update references",
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            title: The window title.
            intro: The sentence above the table.
            changes: The changes to list.
            notes: Lines below the table, such as references that stay.
            accept_text: The text of the button that goes on.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(640)
        self.intro_label = QLabel(intro)
        self.intro_label.setWordWrap(True)
        self.table = ReferenceTable(["Where", "Before", "After"])
        self.table.set_rows(change_rows(changes))
        self.notes_label = QLabel("\n".join(notes))
        self.notes_label.setWordWrap(True)
        self.notes_label.setVisible(bool(notes))
        self.buttons = _buttons(self, accept_text)
        layout = QVBoxLayout(self)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.table)
        layout.addWidget(self.notes_label)
        layout.addWidget(self.buttons)


class RenameDialog(QDialog):
    """Asks for a new id or idShort, with a preview of the references.

    The preview follows the text. A text that cannot be used shows why and
    disables the accept button. The plan comes from a function, so the dialog
    knows nothing about ids and idShorts.

    Attributes:
        edit: The line edit with the new value.
        error_label: Why the text cannot be used, or empty.
        table: The references that would change.
        fix_button: Replaces the text by the suggestion. None if the dialog
            has no way to suggest.
        generate_button: Replaces the text by a new id. None if the dialog
            has no way to generate.
        buttons: The accept and the cancel button.
        plan: The plan for the text now, or None if the text cannot be used.
    """

    def __init__(
        self,
        title: str,
        label: str,
        text: str,
        plan_for: Callable[[str], RenamePlan],
        suggest: Callable[[str], str] | None = None,
        generate: Callable[[], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            title: The window title.
            label: What the text is, such as "New id".
            text: The current value, which the line edit starts with.
            plan_for: Makes the plan for a text. It raises `RenameError` when
                the text cannot be used.
            suggest: Returns a valid text close to the one given. Adds a Fix
                button.
            generate: Returns a new value. Adds a Generate button.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(640)
        self._plan_for = plan_for
        self._suggest = suggest
        self.plan: RenamePlan | None = None

        self.edit = QLineEdit(text)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet(PROBLEM_STYLE)
        self.preview_label = QLabel()
        self.table = ReferenceTable(["Where", "Before", "After"])
        self.fix_button: QPushButton | None = None
        self.generate_button: QPushButton | None = None
        self.buttons = _buttons(self, "Rename")

        row = QVBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(self.edit)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        if suggest is not None:
            self.fix_button = QPushButton("Fix")
            self.fix_button.setToolTip(
                "Replace the text by a valid value that is close to it"
            )
            self.fix_button.clicked.connect(self._on_fix)
            layout.addWidget(self.fix_button)
        if generate is not None:
            self.generate_button = QPushButton("Generate")
            self.generate_button.setToolTip("Use a new unique id")
            self.generate_button.clicked.connect(
                lambda: self.edit.setText(generate())
            )
            layout.addWidget(self.generate_button)
        layout.addWidget(self.error_label)
        layout.addWidget(self.preview_label)
        layout.addWidget(self.table)
        layout.addWidget(self.buttons)

        self.edit.textChanged.connect(self._update)
        self._update(text)

    @property
    def value(self) -> str:
        """The text in the line edit."""
        return self.edit.text()

    @property
    def accept_button(self) -> QPushButton | None:
        """The button that accepts the dialog."""
        for button in self.buttons.buttons():
            role = self.buttons.buttonRole(button)
            if role is QDialogButtonBox.ButtonRole.AcceptRole:
                return button  # pyright: ignore[reportReturnType]
        return None

    def _on_fix(self) -> None:
        if self._suggest is not None:
            self.edit.setText(self._suggest(self.edit.text()))

    def _update(self, text: str) -> None:
        try:
            self.plan = self._plan_for(text)
        except RenameError as error:
            self.plan = None
            self.error_label.setText(str(error))
            self.preview_label.setText("")
            self.table.set_rows([])
        else:
            self.error_label.setText("")
            self.preview_label.setText(_preview_sentence(self.plan))
            self.table.set_rows(change_rows(self.plan.changes))
        if self.fix_button is not None:
            self.fix_button.setEnabled(self.plan is None)
        accept = self.accept_button
        if accept is not None:
            accept.setEnabled(self.plan is not None and not self.plan.is_noop)


def _preview_sentence(plan: RenamePlan) -> str:
    count = len(plan.changes)
    if plan.is_noop:
        return "This is the current value."
    if count == 0:
        return "No reference has to change."
    noun = "reference" if count == 1 else "references"
    return f"{count} {noun} will be updated, in the same undo step."


class DeleteDialog(QDialog):
    """Shows what refers to the objects about to be deleted.

    Attributes:
        summary_label: What is deleted.
        table: The references to it from objects that stay.
        kept_label: The references that cannot be taken away, or hidden.
        remove_button: Choose to take the references away.
        keep_button: Choose to leave the references.
        buttons: The delete and the cancel button.
    """

    def __init__(self, plan: DeletePlan, parent: QWidget | None = None) -> None:
        """Builds the dialog.

        Args:
            plan: What `plan_delete` made.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Delete")
        self.setMinimumWidth(640)
        self.summary_label = QLabel(_delete_sentence(plan))
        self.summary_label.setWordWrap(True)
        self.table = ReferenceTable(["Where", "Reference"])
        self.table.set_rows(usage_rows(plan.usages))
        kept = "\n".join(
            [
                "These cannot be taken away, because the attribute is"
                " required. They will point at nothing:",
                *(f"  {usage.slot.location}" for usage in plan.kept),
            ]
        )
        self.kept_label = QLabel(kept)
        self.kept_label.setWordWrap(True)
        self.kept_label.setVisible(bool(plan.kept))
        removable = len(plan.removals)
        self.remove_button = QRadioButton(
            f"Delete and remove {removable} "
            f"{'reference' if removable == 1 else 'references'}"
        )
        self.keep_button = QRadioButton(
            "Delete and leave the references. They point at nothing."
        )
        # The group makes the two exclusive, whatever their parent is.
        self._choices = QButtonGroup(self)
        self._choices.addButton(self.remove_button)
        self._choices.addButton(self.keep_button)
        self.remove_button.setChecked(True)
        self.remove_button.setEnabled(bool(plan.removals))
        if not plan.removals:
            self.keep_button.setChecked(True)
        self.buttons = _buttons(self, "Delete")
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        layout.addWidget(self.kept_label)
        layout.addWidget(self.remove_button)
        layout.addWidget(self.keep_button)
        layout.addWidget(self.buttons)

    @property
    def remove_references(self) -> bool:
        """Whether the user chose to take the references away."""
        return self.remove_button.isChecked()


def _delete_sentence(plan: DeletePlan) -> str:
    names = [describe_object(target) for target in plan.targets]
    listed = names[:MAX_LISTED_OBJECTS]
    if len(names) > MAX_LISTED_OBJECTS:
        listed.append(f"and {len(names) - MAX_LISTED_OBJECTS} more")
    count = len(plan.usages)
    noun = "reference refers" if count == 1 else "references refer"
    return (
        f"Delete {', '.join(listed)}?\n\n"
        f"{count} {noun} to what you delete. Undo brings everything back."
    )


def ask_rename(
    title: str,
    label: str,
    text: str,
    plan_for: Callable[[str], RenamePlan],
    suggest: Callable[[str], str] | None = None,
    generate: Callable[[], str] | None = None,
    parent: QWidget | None = None,
) -> RenamePlan | None:
    """Asks for a new id or idShort.

    Args:
        title: The window title.
        label: What the text is.
        text: The current value.
        plan_for: Makes the plan for a text, or raises `RenameError`.
        suggest: Returns a valid text close to the one given.
        generate: Returns a new value.
        parent: The parent widget.

    Returns:
        The plan for the accepted text, or None if the user cancelled or kept
        the current value.
    """
    dialog = RenameDialog(
        title, label, text, plan_for, suggest, generate, parent
    )
    if _answered_yes(dialog) and dialog.plan is not None:
        return None if dialog.plan.is_noop else dialog.plan
    return None


def confirm_reference_changes(
    title: str,
    intro: str,
    changes: Sequence[ReferenceChange],
    notes: Sequence[str] = (),
    accept_text: str = "Update references",
    parent: QWidget | None = None,
) -> bool:
    """Shows the references an action would change, and asks to go on.

    Args:
        title: The window title.
        intro: The sentence above the table.
        changes: The changes to list.
        notes: Lines below the table.
        accept_text: The text of the button that goes on.
        parent: The parent widget.

    Returns:
        True if the user accepted.
    """
    return _answered_yes(
        ReferenceChangesDialog(
            title, intro, changes, notes, accept_text, parent
        )
    )


def confirm_rename(plan: RenamePlan, parent: QWidget | None = None) -> bool:
    """Shows the preview of a rename that was typed in a cell.

    Args:
        plan: The rename. A plan without changes needs no preview.
        parent: The parent widget.

    Returns:
        True if the rename may go on.
    """
    if not plan.changes:
        return True
    attribute = "id" if plan.attribute == "id" else "idShort"
    return confirm_reference_changes(
        f"Rename {attribute}",
        f"Renaming {describe_object(plan.target)} from '{plan.old}' to "
        f"'{plan.new}' updates these references:",
        plan.changes,
        parent=parent,
    )


def ask_delete(plan: DeletePlan, parent: QWidget | None = None) -> bool | None:
    """Shows the usages of what is deleted, and asks what to do with them.

    Args:
        plan: What `plan_delete` made.
        parent: The parent widget.

    Returns:
        True to delete and remove the references, False to delete and leave
        them, None if the user cancelled.
    """
    dialog = DeleteDialog(plan, parent)
    if not _answered_yes(dialog):
        return None
    return dialog.remove_references


def confirm_delete(plan: DeletePlan, parent: QWidget | None = None) -> bool:
    """Asks whether to delete something that has no usages.

    Args:
        plan: What `plan_delete` made.
        parent: The parent widget.

    Returns:
        True if the user wants to delete.
    """
    names = [describe_object(target) for target in plan.targets]
    listed = names[:MAX_LISTED_OBJECTS]
    if len(names) > MAX_LISTED_OBJECTS:
        listed.append(f"and {len(names) - MAX_LISTED_OBJECTS} more")
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Delete")
    box.setText(f"Delete {', '.join(listed)}?")
    box.setInformativeText("Undo brings it back.")
    delete = box.addButton("Delete", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    # A stubbed exec leaves no clicked button, which counts as a cancel.
    return box.clickedButton() is delete and delete is not None


def confirm_suggested_id_short(
    error: InvalidIdShortError, parent: QWidget | None = None
) -> bool:
    """Asks whether to use the suggestion for an idShort that cannot be used.

    Args:
        error: Why the idShort was refused, with a suggestion.
        parent: The parent widget.

    Returns:
        True if the user accepts the suggestion.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("idShort")
    box.setText(str(error))
    box.setInformativeText(f"Use '{error.suggestion}' instead?")
    use = box.addButton("Use suggestion", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is use and use is not None


def show_message(title: str, text: str, parent: QWidget | None = None) -> None:
    """Tells the user something, with an OK button."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.exec()
