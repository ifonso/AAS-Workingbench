"""The dialog that adds or edits an IEC 61360 record of a concept description.

The dialog is a form for an `Iec61360Draft`. It checks the draft with
`check_draft` after every keystroke and says what is wrong in words. The
accept button stays disabled while the SDK would refuse the content, so the
user never sees a traceback. Constraints that the SDK does not check are shown
as notes, and do not block.

The preferred name cannot be empty, because the SDK does not allow it. The
form starts with one row in English. Every name, short name and definition has
rows of a language and a text, and a blank row is ignored.
"""

from collections.abc import Sequence

from basyx.aas import model
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QShowEvent
from PyQt6.QtGui import QStandardItem
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QGroupBox
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QScrollArea
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.domain.references import describe_reference
from aas_workingbench.ui.colors import style_as_advisory
from aas_workingbench.ui.colors import style_as_problem
from aas_workingbench.domain.data_specifications import DATA_TYPE_GROUPS
from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_workingbench.domain.data_specifications import LEVEL_TYPE_LABELS
from aas_workingbench.domain.data_specifications import MAX_DEFINITION
from aas_workingbench.domain.data_specifications import MAX_PREFERRED_NAME
from aas_workingbench.domain.data_specifications import MAX_SHORT_NAME
from aas_workingbench.domain.data_specifications import Iec61360Draft
from aas_workingbench.domain.data_specifications import check_draft
from aas_workingbench.ui.concept_dialogs import answered_yes
from aas_workingbench.ui.dialog_layout import accept_button
from aas_workingbench.ui.dialog_layout import finish_dialog
from aas_workingbench.ui.dialog_layout import focus_first_field
from aas_workingbench.ui.dialog_layout import make_button_box
from aas_workingbench.ui.user_defaults import default_languages


class LanguageRows(QWidget):
    """Rows of a language and a text, with a button to add one.

    Attributes:
        changed: Emitted when a language or a text changes, or a row is added
            or removed.
        add_button: Adds a blank row.
    """

    changed = pyqtSignal()

    def __init__(
        self, longest: int, what: str = "Text", parent: QWidget | None = None
    ) -> None:
        """Builds the widget.

        Args:
            longest: The longest text, which the rows show as a tooltip.
            what: What the rows hold, which names their fields for a screen
                reader, such as "Preferred name".
            parent: The parent widget.
        """
        super().__init__(parent)
        self._longest = longest
        self._what = what
        self._rows: list[tuple[QLineEdit, QLineEdit, QWidget]] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("Add language")
        self.add_button.clicked.connect(
            lambda: self.add_row(self._next_language())
        )
        self._layout.addWidget(self.add_button)

    def _next_language(self) -> str:
        """Returns the first default language that no row has, or nothing."""
        used = {language.text().lower() for language, _, _ in self._rows}
        return next(
            (tag for tag in default_languages() if tag.lower() not in used),
            "",
        )

    def add_row(self, language: str = "", text: str = "") -> None:
        """Adds a row. The signal fires once for the row."""
        holder = QWidget()
        line = QHBoxLayout(holder)
        line.setContentsMargins(0, 0, 0, 0)
        language_edit = QLineEdit(language)
        language_edit.setPlaceholderText("en")
        language_edit.setMaximumWidth(80)
        language_edit.setAccessibleName(f"{self._what}, language")
        language_edit.setToolTip("Language tag, such as en or de-DE")
        text_edit = QLineEdit(text)
        text_edit.setAccessibleName(f"{self._what}, text")
        text_edit.setPlaceholderText(f"Text (at most {self._longest})")
        remove = QPushButton("Remove")
        line.addWidget(language_edit)
        line.addWidget(text_edit, 1)
        line.addWidget(remove)
        self._layout.insertWidget(len(self._rows), holder)
        row = (language_edit, text_edit, holder)
        self._rows.append(row)
        language_edit.textChanged.connect(self._on_text)
        text_edit.textChanged.connect(self._on_text)
        remove.clicked.connect(lambda: self._remove(row))
        self.changed.emit()

    def _on_text(self, _text: str) -> None:
        self.changed.emit()

    def _remove(self, row: tuple[QLineEdit, QLineEdit, QWidget]) -> None:
        self._rows.remove(row)
        row[2].setParent(None)
        row[2].deleteLater()
        self.changed.emit()

    def set_rows(self, rows: Sequence[tuple[str, str]]) -> None:
        """Replaces all rows."""
        for row in list(self._rows):
            self._remove(row)
        for language, text in rows:
            self.add_row(language, text)

    def rows(self) -> list[tuple[str, str]]:
        """Returns the language and text of each row."""
        return [(lang.text(), text.text()) for lang, text, _ in self._rows]

    def row_edits(self, number: int) -> tuple[QLineEdit, QLineEdit]:
        """Returns the language edit and the text edit of a row."""
        language, text, _ = self._rows[number]
        return language, text


class Iec61360Dialog(QDialog):
    """A form for the content of an IEC 61360 record.

    Attributes:
        preferred_name, short_name, definition: Rows of a language and a text.
        unit, unit_id, source_of_definition, symbol, value_format, value:
            Line edits.
        data_type: The list of data types, grouped. The first entry is
            "(none)".
        level_checks: A check box for each level type.
        value_list_label: How many pairs the value list has.
        pairs_list: The pairs of the value list, one row each.
        remove_pair_button: Takes the selected pair out.
        remove_list_button: Takes the whole value list away.
        problems_label: The reasons why the record cannot be made yet.
        advisories_label: The constraints the SDK does not check.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        draft: Iec61360Draft,
        title: str = "IEC 61360 record",
        accept_text: str = "Add record",
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            draft: What the form starts with.
            title: The window title.
            accept_text: The text of the accept button.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 560)
        # The pairs of the record, in the order of the list. Pairs are added
        # by the import, and removed here.
        self._pairs: list[model.ValueReferencePair] = sorted(
            draft.value_list or (), key=lambda pair: (pair.value, id(pair))
        )

        self.preferred_name = LanguageRows(MAX_PREFERRED_NAME, "Preferred name")
        self.short_name = LanguageRows(MAX_SHORT_NAME, "Short name")
        self.definition = LanguageRows(MAX_DEFINITION, "Definition")
        self.unit = QLineEdit(draft.unit)
        self.unit.setPlaceholderText("such as m/s")
        self.unit_id = QLineEdit(draft.unit_id)
        self.unit_id.setPlaceholderText(
            "value of a global reference, such as an IRDI"
        )
        self.source_of_definition = QLineEdit(draft.source_of_definition)
        self.symbol = QLineEdit(draft.symbol)
        self.value_format = QLineEdit(draft.value_format)
        self.value = QLineEdit(draft.value)
        self.data_type = self._data_type_box()
        self.level_checks: dict[model.IEC61360LevelType, QCheckBox] = {}
        levels = QHBoxLayout()
        for level, label in LEVEL_TYPE_LABELS:
            check = QCheckBox(label)
            check.setChecked(level in draft.level_types)
            self.level_checks[level] = check
            levels.addWidget(check)
        levels.addStretch(1)
        self.value_list_label = QLabel()
        self.pairs_list = QListWidget()
        self.pairs_list.setAccessibleName("Pairs of the value list")
        self.pairs_list.setMaximumHeight(96)
        self.pairs_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.remove_pair_button = QPushButton("Remove pair")
        self.remove_pair_button.setToolTip(
            "Take the selected pair out of the value list"
        )
        self.remove_list_button = QPushButton("Remove value list")
        self.remove_list_button.setToolTip(
            "Take the whole value list away. The record has none then"
        )
        self.pairs_list.currentRowChanged.connect(self._update_pair_buttons)
        self.remove_pair_button.clicked.connect(
            lambda: self.remove_pair(self.pairs_list.currentRow())
        )
        self.remove_list_button.clicked.connect(self.remove_value_list)
        pair_buttons = QHBoxLayout()
        pair_buttons.addWidget(self.remove_pair_button)
        pair_buttons.addWidget(self.remove_list_button)
        pair_buttons.addStretch(1)
        value_list_box = QWidget()
        value_list_layout = QVBoxLayout(value_list_box)
        value_list_layout.setContentsMargins(0, 0, 0, 0)
        value_list_layout.addWidget(self.value_list_label)
        value_list_layout.addWidget(self.pairs_list)
        value_list_layout.addLayout(pair_buttons)

        template = QLineEdit(IEC_61360_TEMPLATE_KEY)
        template.setReadOnly(True)
        template.setToolTip(
            "The record names this template (constraint AASc-3a-050)"
        )

        names = QGroupBox("Names and definition")
        names_form = QFormLayout(names)
        names_form.addRow("Preferred name *", self.preferred_name)
        names_form.addRow("Short name", self.short_name)
        names_form.addRow("Definition", self.definition)
        values = QGroupBox("Type, unit and value")
        values_form = QFormLayout(values)
        values_form.addRow("Data type", self.data_type)
        values_form.addRow("Unit", self.unit)
        values_form.addRow("Unit id", self.unit_id)
        values_form.addRow("Symbol", self.symbol)
        values_form.addRow("Value format", self.value_format)
        values_form.addRow("Value", self.value)
        values_form.addRow("Value list", value_list_box)
        values_form.addRow("Level types", levels)
        values_form.addRow("Source of definition", self.source_of_definition)

        self.problems_label = QLabel()
        self.problems_label.setWordWrap(True)
        style_as_problem(self.problems_label)
        self.advisories_label = QLabel()
        self.advisories_label.setWordWrap(True)
        style_as_advisory(self.advisories_label)
        self.buttons = make_button_box(self, accept_text, safe_default=True)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        template_label = QLabel("Template")
        template_label.setBuddy(template)
        content_layout.addWidget(template_label)
        content_layout.addWidget(template)
        content_layout.addWidget(names)
        content_layout.addWidget(values)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.problems_label)
        layout.addWidget(self.advisories_label)
        layout.addWidget(self.buttons)
        finish_dialog(self)

        self.preferred_name.set_rows(draft.preferred_name)
        self.short_name.set_rows(draft.short_name)
        self.definition.set_rows(draft.definition)
        self.set_data_type(draft.data_type)
        self._refresh_pairs()
        for rows in (self.preferred_name, self.short_name, self.definition):
            rows.changed.connect(self._update)
        for edit in (
            self.unit,
            self.unit_id,
            self.source_of_definition,
            self.symbol,
            self.value_format,
            self.value,
        ):
            edit.textChanged.connect(self._update)
        self.data_type.currentIndexChanged.connect(self._update)
        for check in self.level_checks.values():
            check.stateChanged.connect(self._update)
        self._update()

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        """Starts in the first field, not on the scroll area."""
        super().showEvent(event)
        focus_first_field(self)

    @staticmethod
    def _data_type_box() -> QComboBox:
        box = QComboBox()
        item_model = QStandardItemModel(box)
        none = QStandardItem("(none)")
        none.setData(None, 256)
        item_model.appendRow(none)
        for group, types in DATA_TYPE_GROUPS:
            header = QStandardItem(f"-- {group} --")
            header.setEnabled(False)
            item_model.appendRow(header)
            for data_type in types:
                item = QStandardItem(data_type.name)
                item.setData(data_type, 256)
                item_model.appendRow(item)
        box.setModel(item_model)
        return box

    def set_data_type(self, data_type: model.DataTypeIEC61360 | None) -> None:
        """Chooses a data type in the list, or none."""
        self.data_type.setCurrentIndex(
            0 if data_type is None else self.data_type.findData(data_type)
        )

    def data_types(self) -> list[model.DataTypeIEC61360]:
        """Returns the data types the list offers, in order."""
        return [
            self.data_type.itemData(n)
            for n in range(self.data_type.count())
            if isinstance(self.data_type.itemData(n), model.DataTypeIEC61360)
        ]

    @property
    def draft(self) -> Iec61360Draft:
        """The draft that the form holds now."""
        chosen = self.data_type.currentData()
        return Iec61360Draft(
            preferred_name=self.preferred_name.rows(),
            short_name=self.short_name.rows(),
            definition=self.definition.rows(),
            unit=self.unit.text(),
            unit_id=self.unit_id.text(),
            source_of_definition=self.source_of_definition.text(),
            symbol=self.symbol.text(),
            data_type=chosen
            if isinstance(chosen, model.DataTypeIEC61360)
            else None,
            value_format=self.value_format.text(),
            value=self.value.text(),
            level_types=frozenset(
                level
                for level, check in self.level_checks.items()
                if check.isChecked()
            ),
            value_list=tuple(self._pairs) or None,
        )

    def remove_pair(self, row: int) -> None:
        """Takes one pair out of the value list.

        When it was the last pair, the record has no value list at all, since
        a value list has at least one pair.

        Args:
            row: The number of the pair in the list of pairs. A number that
                names no pair does nothing.
        """
        if 0 <= row < len(self._pairs):
            del self._pairs[row]
            self._refresh_pairs()
            self._update()

    def remove_value_list(self) -> None:
        """Takes the whole value list away."""
        self._pairs.clear()
        self._refresh_pairs()
        self._update()

    def _refresh_pairs(self) -> None:
        count = len(self._pairs)
        self.pairs_list.clear()
        for pair in self._pairs:
            target = (
                f"  =  {describe_reference(pair.value_id)}"
                if pair.value_id is not None
                else ""
            )
            self.pairs_list.addItem(f"{pair.value}{target}")
        self.value_list_label.setText(
            f"{count} pair{'' if count == 1 else 's'}. "
            "Use Import value list to add more."
            if count
            else "No pairs. Use Import value list to add them."
        )
        self.pairs_list.setVisible(bool(count))
        self._update_pair_buttons()

    def _update_pair_buttons(self, _row: int = -1) -> None:
        self.remove_pair_button.setVisible(bool(self._pairs))
        self.remove_pair_button.setEnabled(self.pairs_list.currentRow() >= 0)
        self.remove_list_button.setVisible(bool(self._pairs))

    def _update(self) -> None:
        report = check_draft(self.draft)
        self.problems_label.setText("\n".join(report.errors))
        self.advisories_label.setText("\n".join(report.advisories))
        button = accept_button(self.buttons)
        if button is not None:
            button.setEnabled(report.is_valid)


def ask_iec61360(
    draft: Iec61360Draft,
    title: str = "IEC 61360 record",
    accept_text: str = "Add record",
    parent: QWidget | None = None,
) -> Iec61360Draft | None:
    """Asks the user to fill in an IEC 61360 record.

    Args:
        draft: What the form starts with.
        title: The window title.
        accept_text: The text of the accept button.
        parent: The parent widget.

    Returns:
        A draft that `check_draft` accepts, or None if the user cancelled.
    """
    dialog = Iec61360Dialog(draft, title, accept_text, parent)
    if not answered_yes(dialog):
        return None
    return dialog.draft
