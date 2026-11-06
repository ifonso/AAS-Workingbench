"""The dialogs of the bulk actions.

They only show what the plans of `application/operations/` found and return
the answer. A cancelled dialog returns None, and nothing changes.

- `ChangeAttributeDialog` takes a pattern and shows, for each selected object,
  the current text, the new text, and what happens, before anything is
  applied. Apply stays disabled until the pattern is valid and nothing is
  refused.
- `RemoveExtensionsDialog` lists the extensions of the selection by name or
  semantic id, with their counts.
- `confirm_attach` tells what an add to several objects would do and skip.
"""

from collections.abc import Iterable

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QRadioButton
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.operations.attach import AttachPlan
from aas_editor.application.operations.bulk_edit import BulkAttribute
from aas_editor.application.operations.bulk_edit import BulkPlan
from aas_editor.application.operations.bulk_edit import EntryStatus
from aas_editor.application.operations.bulk_edit import ExtensionGroup
from aas_editor.application.operations.bulk_edit import ExtensionKey
from aas_editor.application.operations.bulk_edit import group_extensions
from aas_editor.application.operations.bulk_edit import languages_in
from aas_editor.application.operations.bulk_edit import plan_change_attribute
from aas_editor.domain.references import describe_object
from aas_editor.domain.rename_pattern import FILTER_NAMES
from aas_editor.domain.rename_pattern import FIELD_NAMES
from aas_editor.domain.rename_pattern import examples
from aas_editor.ui.colors import problem_color
from aas_editor.ui.dialog_layout import finish_dialog
from aas_editor.ui.theme import theme_manager

_HELP = (
    "Text is copied as it is. A field in braces is replaced, and filters "
    "after a bar change it, as in {old|upper}.\n"
    f"Fields: {', '.join(FIELD_NAMES)}.\n"
    f"Filters: {', '.join(FILTER_NAMES)}.\n"
    "Write {{ and }} for a brace. The guide in docs/software/bulk-editing.md "
    "has examples."
)

_STATUS_TEXT = {
    EntryStatus.CHANGE: "Changes",
    EntryStatus.UNCHANGED: "Unchanged",
    EntryStatus.SKIPPED: "Skipped",
    EntryStatus.REFUSED: "Refused",
}


def show_problem(
    title: str, message: str, parent: QWidget | None = None
) -> None:
    """Tells the user why an action did not happen."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    box.exec()


class ChangeAttributeDialog(QDialog):
    """Changes an attribute of the selected objects with a pattern.

    The table is the preview. It is rebuilt whenever the attribute, the
    language, or the pattern changes.
    """

    def __init__(
        self,
        objects: Iterable[model.Identifiable],
        targets: Iterable[model.Referable],
        parent: QWidget | None = None,
    ) -> None:
        """Creates the dialog.

        Args:
            objects: The identifiables of the package, to find references.
            targets: The selected objects, in the order of the selection.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._objects = list(objects)
        self._targets = list(targets)
        self._plan: BulkPlan | None = None
        self.setWindowTitle("Change attribute with a pattern")
        self.resize(820, 560)

        self.attributeBox = QComboBox(self)
        for attribute in BulkAttribute:
            self.attributeBox.addItem(attribute.label, attribute)
        self.languageBox = QComboBox(self)
        self.languageBox.setEditable(True)
        self.patternBox = QComboBox(self)
        self.patternBox.setEditable(True)
        for pattern, meaning in examples():
            self.patternBox.addItem(pattern)
            self.patternBox.setItemData(
                self.patternBox.count() - 1,
                meaning,
                Qt.ItemDataRole.ToolTipRole,
            )
        self.patternBox.setCurrentText("{old}")
        self.help = QLabel(_HELP, self)
        self.help.setWordWrap(True)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(
            ["Element", "Current", "New", "Result"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            header.setStretchLastSection(True)
            # The element names what changes, so it gets the room.
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.applyButton = self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )
        if self.applyButton is not None:
            self.applyButton.setText("Apply")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow("&Attribute:", self.attributeBox)
        form.addRow("&Language:", self.languageBox)
        form.addRow("&Pattern:", self.patternBox)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.help)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary)
        layout.addWidget(self.buttons)
        finish_dialog(self)

        self.attributeBox.currentIndexChanged.connect(self._attribute_changed)
        self.languageBox.currentTextChanged.connect(self.refresh)
        self.patternBox.currentTextChanged.connect(self.refresh)
        # The refused rows have the colour of the theme, so they are made again.
        theme_manager().changed.connect(self.refresh)
        self._attribute_changed()

    @property
    def plan(self) -> BulkPlan | None:
        """The plan for the current settings."""
        return self._plan

    @property
    def attribute(self) -> BulkAttribute:
        """The chosen attribute."""
        return self.attributeBox.currentData()

    def set_attribute(self, attribute: BulkAttribute) -> None:
        """Chooses the attribute."""
        self.attributeBox.setCurrentIndex(self.attributeBox.findData(attribute))

    def set_pattern(self, pattern: str) -> None:
        """Types the pattern."""
        self.patternBox.setCurrentText(pattern)

    def set_language(self, language: str) -> None:
        """Types the language."""
        self.languageBox.setCurrentText(language)

    def _attribute_changed(self) -> None:
        attribute = self.attribute
        self.languageBox.setEnabled(attribute.uses_language)
        found = languages_in(self._targets, attribute)
        self.languageBox.blockSignals(True)
        self.languageBox.clear()
        self.languageBox.addItems(found or ["en"])
        self.languageBox.setCurrentText(
            "en" if "en" in found else (found or ["en"])[0]
        )
        self.languageBox.blockSignals(False)
        self.refresh()

    def refresh(self, *_: object) -> None:
        """Works out the plan again and shows it."""
        plan = plan_change_attribute(
            self._objects,
            self._targets,
            self.attribute,
            self.patternBox.currentText(),
            self.languageBox.currentText().strip(),
        )
        self._plan = plan
        self.table.setRowCount(len(plan.entries))
        for row, entry in enumerate(plan.entries):
            result = _STATUS_TEXT[entry.status]
            if entry.reason:
                result = f"{result}: {entry.reason}"
            cells = (
                describe_object(entry.target),
                "" if entry.old is None else entry.old,
                "" if entry.new is None else entry.new,
                result,
            )
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setToolTip(text)
                if entry.status is EntryStatus.REFUSED:
                    item.setForeground(QBrush(QColor(problem_color())))
                elif entry.status in (
                    EntryStatus.SKIPPED,
                    EntryStatus.UNCHANGED,
                ):
                    font = item.font()
                    font.setItalic(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)
        self.summary.setText(_summary(plan))
        if self.applyButton is not None:
            self.applyButton.setEnabled(plan.can_apply)


def _summary(plan: BulkPlan) -> str:
    if plan.pattern_error is not None:
        return f"The pattern cannot be used: {plan.pattern_error}"
    parts = [f"{len(plan.to_change)} change"]
    if plan.skipped:
        parts.append(f"{len(plan.skipped)} skipped")
    unchanged = len(plan.with_status(EntryStatus.UNCHANGED))
    if unchanged:
        parts.append(f"{unchanged} unchanged")
    if plan.refused:
        parts.append(
            f"{len(plan.refused)} refused, so nothing can be applied until "
            "the pattern or the selection is changed"
        )
    if plan.reference_count:
        parts.append(f"{plan.reference_count} references are updated")
    return ", ".join(parts) + "."


def ask_change(
    objects: Iterable[model.Identifiable],
    targets: Iterable[model.Referable],
    parent: QWidget | None = None,
) -> BulkPlan | None:
    """Opens the dialog and returns the plan to apply, or None to cancel."""
    dialog = ChangeAttributeDialog(objects, targets, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    plan = dialog.plan
    return plan if plan is not None and plan.can_apply else None


class RemoveExtensionsDialog(QDialog):
    """Lists the extensions of the selection and picks a group to remove."""

    def __init__(
        self, owners: Iterable[object], parent: QWidget | None = None
    ) -> None:
        """Creates the dialog.

        Args:
            owners: The selected objects.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._owners = list(owners)
        self._groups: list[ExtensionGroup] = []
        self.setWindowTitle("Remove extensions")
        self.byName = QRadioButton("By &name", self)
        self.bySemanticId = QRadioButton("By &semantic id", self)
        self.byName.setChecked(True)
        self.list = QListWidget(self)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.removeButton = self.buttons.button(
            QDialogButtonBox.StandardButton.Ok
        )
        if self.removeButton is not None:
            self.removeButton.setText("Remove")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Remove the extensions with the same:", self))
        layout.addWidget(self.byName)
        layout.addWidget(self.bySemanticId)
        layout.addWidget(self.list)
        layout.addWidget(self.buttons)
        finish_dialog(self, destructive=True)
        self.byName.toggled.connect(self.refresh)
        self.list.currentRowChanged.connect(self._row_changed)
        self.refresh()

    @property
    def key(self) -> ExtensionKey:
        """What the list is grouped by."""
        return (
            ExtensionKey.NAME
            if self.byName.isChecked()
            else ExtensionKey.SEMANTIC_ID
        )

    @property
    def groups(self) -> list[ExtensionGroup]:
        """The groups in the list."""
        return list(self._groups)

    @property
    def chosen(self) -> ExtensionGroup | None:
        """The group that is selected, or None."""
        row = self.list.currentRow()
        return self._groups[row] if 0 <= row < len(self._groups) else None

    def choose(self, label: str) -> None:
        """Selects the group with a label, such as `Alpha (2)`."""
        for row, group in enumerate(self._groups):
            if group.label == label:
                self.list.setCurrentRow(row)
                return
        raise LookupError(label)

    def refresh(self, *_: object) -> None:
        """Builds the list again for the chosen grouping."""
        self._groups = group_extensions(self._owners, self.key)
        self.list.clear()
        for group in self._groups:
            QListWidgetItem(group.label, self.list)
        if not self._groups:
            QListWidgetItem("No extension to remove", self.list).setFlags(
                Qt.ItemFlag.NoItemFlags
            )
        self._row_changed()

    def _row_changed(self, *_: object) -> None:
        if self.removeButton is not None:
            self.removeButton.setEnabled(self.chosen is not None)


def ask_extension_group(
    owners: Iterable[object], parent: QWidget | None = None
) -> ExtensionGroup | None:
    """Opens the dialog and returns the group to remove, or None to cancel."""
    dialog = RemoveExtensionsDialog(owners, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.chosen


def confirm_attach(plan: AttachPlan, parent: QWidget | None = None) -> bool:
    """Tells what an add would do and skip, and asks to go on.

    Args:
        plan: What `plan_attach` made.
        parent: The parent widget.

    Returns:
        True to add, False to cancel.
    """
    skipped = plan.skipped
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(f"Add {plan.kind.label}")
    owners = {id(entry.owner) for entry in plan.to_add}
    box.setText(
        f"Add the {plan.kind.label} to {len(owners)} "
        f"object{'s' if len(owners) != 1 else ''}? "
        f"{len(skipped)} will be skipped."
    )
    box.setDetailedText(
        "\n".join(
            f"{describe_object(entry.owner)}: {entry.reason}"
            for entry in skipped
        )
    )
    box.setStandardButtons(
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
    )
    box.setDefaultButton(QMessageBox.StandardButton.Ok)
    return box.exec() == QMessageBox.StandardButton.Ok
