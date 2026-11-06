"""The questions of the concept description actions.

They only show what the plans of `application/operations/concepts.py` and
`data_specs.py` found, and return the answer of the user. A cancelled dialog
returns None or False, and the action stops. A test stubs `QDialog.exec`, as
for the dialogs of `reference_dialogs`, or answers through the widgets.
"""

from collections.abc import Sequence

from basyx.aas.model.concept import ConceptDescription
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.operations.data_specs import FixKeysPlan
from aas_editor.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_editor.domain.data_specifications import iec_content_of
from aas_editor.domain.references import describe_reference
from aas_editor.ui.reference_dialogs import ReferenceTable

TITLE = "Concept descriptions"


def make_buttons(dialog: QDialog, accept_text: str) -> QDialogButtonBox:
    buttons = QDialogButtonBox()
    go_on = buttons.addButton(
        accept_text, QDialogButtonBox.ButtonRole.AcceptRole
    )
    cancel = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
    if go_on is not None:
        go_on.setAutoDefault(False)
    if cancel is not None:
        cancel.setDefault(True)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    return buttons


def accept_button(buttons: QDialogButtonBox):
    """Returns the button of a button box that accepts the dialog."""
    for button in buttons.buttons():
        if buttons.buttonRole(button) is QDialogButtonBox.ButtonRole.AcceptRole:
            return button
    return None


def answered_yes(dialog: QDialog) -> bool:
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted.value


def preferred_name_of(concept: ConceptDescription) -> str:
    """Returns the name to show for a description: its IEC 61360 name, if any."""
    for record in concept.embedded_data_specifications:
        content = iec_content_of(record)
        if content is not None and content.preferred_name:
            names = dict(content.preferred_name)
            return names.get("en") or next(iter(names.values()))
    return ""


class PreviewDialog(QDialog):
    """Lists what an action would do, and asks to go on.

    Attributes:
        intro_label: The sentence above the table.
        table: One row for each item.
        notes_label: Text below the table, hidden when there is none.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        title: str,
        intro: str,
        headers: Sequence[str],
        rows: Sequence[Sequence[str]],
        notes: Sequence[str] = (),
        accept_text: str = "OK",
        selectable: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            title: The window title.
            intro: The sentence above the table.
            headers: The titles of the columns.
            rows: The cells of each row.
            notes: Lines below the table.
            accept_text: The text of the button that goes on.
            selectable: Whether the user chooses rows. All start selected,
                and `chosen` returns the rows that stay selected.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(680)
        self.intro_label = QLabel(intro)
        self.intro_label.setWordWrap(True)
        self.table = ReferenceTable(headers)
        self.table.set_rows(rows)
        if selectable:
            self.table.setSelectionMode(
                QAbstractItemView.SelectionMode.MultiSelection
            )
            self.table.selectAll()
        else:
            self.table.setSelectionMode(
                QAbstractItemView.SelectionMode.NoSelection
            )
        self.notes_label = QLabel("\n".join(notes))
        self.notes_label.setWordWrap(True)
        self.notes_label.setVisible(bool(notes))
        self.buttons = make_buttons(self, accept_text)
        layout = QVBoxLayout(self)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.table)
        layout.addWidget(self.notes_label)
        layout.addWidget(self.buttons)
        if selectable:
            self.table.itemSelectionChanged.connect(self._update_accept)
            self._update_accept()

    def chosen(self) -> list[int]:
        """Returns the numbers of the selected rows, in order."""
        model = self.table.selectionModel()
        if model is None:
            return []
        return sorted({index.row() for index in model.selectedRows()})

    def _update_accept(self) -> None:
        button = accept_button(self.buttons)
        if button is not None:
            button.setEnabled(bool(self.chosen()))


def confirm_preview(
    title: str,
    intro: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    notes: Sequence[str] = (),
    accept_text: str = "OK",
    parent: QWidget | None = None,
) -> bool:
    """Lists what an action would do, and asks to go on.

    Returns:
        True if the user accepted.
    """
    return answered_yes(
        PreviewDialog(
            title, intro, headers, rows, notes, accept_text, False, parent
        )
    )


def choose_rows(
    title: str,
    intro: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    notes: Sequence[str] = (),
    accept_text: str = "OK",
    parent: QWidget | None = None,
) -> list[int] | None:
    """Lists items, all selected, and returns the ones the user keeps.

    Returns:
        The numbers of the chosen rows, or None if the user cancelled.
    """
    dialog = PreviewDialog(
        title, intro, headers, rows, notes, accept_text, True, parent
    )
    if not answered_yes(dialog):
        return None
    return dialog.chosen()


def ask_create_kind(summary: str, parent: QWidget | None = None) -> bool | None:
    """Asks whether new descriptions get an IEC 61360 record.

    Args:
        summary: What will be created.
        parent: The parent widget.

    Returns:
        True for descriptions with a record whose names and definition come
        from the elements, False for plain descriptions, None to cancel.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(TITLE)
    box.setText(summary)
    box.setInformativeText(
        "Add an IEC 61360 record to each new description, with the preferred "
        "name and the definition taken from the idShort, the display name and "
        "the description of the element?"
    )
    with_record = box.addButton(
        "With IEC 61360 record", QMessageBox.ButtonRole.YesRole
    )
    plain = box.addButton("Plain", QMessageBox.ButtonRole.NoRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(with_record)
    box.exec()
    clicked = box.clickedButton()
    if clicked is with_record:
        return True
    if clicked is plain:
        return False
    return None


def confirm_replace_semantic_ids(
    lines: Sequence[str], parent: QWidget | None = None
) -> bool:
    """Asks before semantic ids are replaced.

    Args:
        lines: One line for each element: its name, the old semantic id, and
            the new one.
        parent: The parent widget.

    Returns:
        True if the user wants to replace them.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(TITLE)
    box.setText(
        "These elements have a semantic id already. Replace it?"
        if len(lines) != 1
        else "This element has a semantic id already. Replace it?"
    )
    box.setInformativeText("\n".join(lines))
    replace = box.addButton("Replace", QMessageBox.ButtonRole.AcceptRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    return box.clickedButton() is replace and replace is not None


class ConceptPickerDialog(QDialog):
    """Lets the user choose a concept description of the package.

    Attributes:
        filter_edit: Narrows the table to rows that contain the text.
        table: One row for each description: idShort, preferred name, id.
        current_label: The semantic id the element has now.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        concepts: Sequence[ConceptDescription],
        current: str,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            concepts: The descriptions to choose from.
            current: A sentence about the semantic id of the element now.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Assign concept description")
        self.setMinimumWidth(720)
        self.setMinimumHeight(420)
        self._concepts = list(concepts)
        self.current_label = QLabel(current)
        self.current_label.setWordWrap(True)
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter by idShort, name or id")
        self.table = ReferenceTable(["idShort", "Preferred name", "Id"])
        self.table.set_rows(
            [
                [c.id_short or "", preferred_name_of(c), c.id]
                for c in self._concepts
            ]
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.buttons = make_buttons(self, "Assign")
        layout = QVBoxLayout(self)
        layout.addWidget(self.current_label)
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.table)
        layout.addWidget(self.buttons)
        self.filter_edit.textChanged.connect(self._filter)
        self.table.itemSelectionChanged.connect(self._update_accept)
        self.table.itemDoubleClicked.connect(self._on_double_click)
        self._update_accept()

    @property
    def selected(self) -> ConceptDescription | None:
        """The chosen description, or None."""
        model = self.table.selectionModel()
        if model is None:
            return None
        rows = [r.row() for r in model.selectedRows()]
        shown = [r for r in rows if not self.table.isRowHidden(r)]
        return self._concepts[shown[0]] if shown else None

    def _filter(self, text: str) -> None:
        wanted = text.lower()
        for row in range(self.table.rowCount()):
            cells = [
                (self.table.item(row, column) or None)
                for column in range(self.table.columnCount())
            ]
            match = any(
                item is not None and wanted in item.text().lower()
                for item in cells
            )
            self.table.setRowHidden(row, not match)
        self._update_accept()

    def _update_accept(self) -> None:
        button = accept_button(self.buttons)
        if button is not None:
            button.setEnabled(self.selected is not None)

    def _on_double_click(self, _item: QTableWidgetItem) -> None:
        if self.selected is not None:
            self.accept()


def ask_concept(
    concepts: Sequence[ConceptDescription],
    current: str,
    parent: QWidget | None = None,
) -> ConceptDescription | None:
    """Asks which concept description to assign.

    Returns:
        The description, or None if the user cancelled.
    """
    dialog = ConceptPickerDialog(concepts, current, parent)
    if not answered_yes(dialog):
        return None
    return dialog.selected


class FixKeysDialog(QDialog):
    """Shows the records whose key will change, and asks to go on.

    Attributes:
        table: One row for each record: description, key now, key after.
        other_check: Whether to fix records that use another spelling of the
            key too. Hidden when there are none.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self, plan: FixKeysPlan, parent: QWidget | None = None
    ) -> None:
        """Builds the dialog.

        Args:
            plan: What `plan_fix_keys` made.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Fix data specification keys")
        self.setMinimumWidth(720)
        intro = QLabel(
            "A record with IEC 61360 content has to name the IEC 61360 "
            f"template. These records name something else:\n"
            f"The key to set is {IEC_61360_TEMPLATE_KEY}"
        )
        intro.setWordWrap(True)
        self.table = ReferenceTable(["Concept description", "Now", "After"])
        self.table.set_rows(
            [
                [
                    concept.id_short or concept.id,
                    describe_reference(record.data_specification),
                    "template key",
                ]
                for concept, record in plan.unknown
            ]
        )
        self.other_check = QCheckBox(
            f"Also update {len(plan.other_spelling)} record"
            f"{'' if len(plan.other_spelling) == 1 else 's'} that name the "
            "template in another spelling or version (such as http or 3/0)"
        )
        self.other_check.setVisible(bool(plan.other_spelling))
        self.buttons = make_buttons(self, "Fix keys")
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.table)
        layout.addWidget(self.other_check)
        layout.addWidget(self.buttons)
        self.table.setVisible(bool(plan.unknown))
        self.other_check.stateChanged.connect(self._update_accept)
        self._plan = plan
        self._update_accept()

    @property
    def include_other(self) -> bool:
        """Whether to fix the other spellings too."""
        return self.other_check.isChecked()

    def _update_accept(self) -> None:
        button = accept_button(self.buttons)
        if button is not None:
            button.setEnabled(
                bool(self._plan.unknown)
                or (self.include_other and bool(self._plan.other_spelling))
            )


def ask_fix_keys(
    plan: FixKeysPlan, parent: QWidget | None = None
) -> bool | None:
    """Asks whether to fix the keys of data specification records.

    Returns:
        Whether to include records with another spelling of the key, or None
        if the user cancelled.
    """
    dialog = FixKeysDialog(plan, parent)
    if not answered_yes(dialog):
        return None
    return dialog.include_other
