"""Dialogs for converting an element and for changing what a list fixes.

The plans in `aas_workingbench.domain` decide what would be lost. These dialogs show
a plan and return the answer of the user. Each function builds a dialog, runs
it, and returns the answer, so a test stubs the function or `QDialog.exec`.
"""

from collections.abc import Sequence
from typing import Any
from typing import cast

from basyx.aas import model
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.operations.replace import ReferenceUpdates
from aas_workingbench.domain.element_copy import item_name
from aas_workingbench.domain.list_settings import LIST_ITEM_TYPES
from aas_workingbench.domain.list_settings import ListSettings
from aas_workingbench.domain.list_settings import detect_settings
from aas_workingbench.domain.list_settings import settings_of
from aas_workingbench.domain.references import describe_reference
from aas_workingbench.domain.replacement import ReplacementPlan
from aas_workingbench.ui.dialog_layout import finish_dialog
from aas_workingbench.ui.dialog_layout import make_button_box
from aas_workingbench.ui.reference_dialogs import ReferenceTable
from aas_workingbench.ui.reference_dialogs import usage_rows
from aas_workingbench.ui.value_editor import ValueTypeBox

ElementType = type[model.SubmodelElement]


def _answered_yes(dialog: QDialog) -> bool:
    dialog.exec()
    return dialog.result() == QDialog.DialogCode.Accepted.value


class ReplacementDialog(QDialog):
    """Shows what a replacement loses, and asks to go on.

    Attributes:
        intro_label: The sentence above the tables.
        losses_table: One row for each loss: what, and its value.
        notes_label: What the new element got that the user did not set.
        updates_label: How many references follow the new element.
        orphaned_table: The references that will point at nothing.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        title: str,
        intro: str,
        plan: ReplacementPlan,
        updates: ReferenceUpdates,
        accept_text: str,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            title: The window title.
            intro: The sentence above the tables.
            plan: The conversion or rebuild.
            updates: What happens to the references.
            accept_text: The text of the button that goes on.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(640)
        self.intro_label = QLabel(intro)
        self.intro_label.setWordWrap(True)
        self.losses_table = ReferenceTable(["Lost", "Value"])
        self.losses_table.set_rows(
            [[loss.what, loss.detail] for loss in plan.losses]
        )
        self.losses_table.setVisible(bool(plan.losses))
        self.notes_label = QLabel("\n".join(plan.notes))
        self.notes_label.setWordWrap(True)
        self.notes_label.setVisible(bool(plan.notes))
        count = len(updates.changes)
        self.updates_label = QLabel(
            f"{count} {'reference follows' if count == 1 else 'references follow'}"
            " the new element and keep pointing at it."
        )
        self.updates_label.setVisible(count > 0)
        self.orphaned_label = QLabel(
            "These references point at items that will be gone. They are"
            " left as they are, and point at nothing:"
        )
        self.orphaned_label.setWordWrap(True)
        self.orphaned_table = ReferenceTable(["Where", "Reference"])
        self.orphaned_table.set_rows(usage_rows(updates.orphaned))
        self.orphaned_label.setVisible(bool(updates.orphaned))
        self.orphaned_table.setVisible(bool(updates.orphaned))
        self.buttons = make_button_box(self, accept_text, safe_default=True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.intro_label)
        layout.addWidget(self.losses_table)
        layout.addWidget(self.notes_label)
        layout.addWidget(self.updates_label)
        layout.addWidget(self.orphaned_label)
        layout.addWidget(self.orphaned_table)
        layout.addWidget(self.buttons)
        finish_dialog(self)


def confirm_replacement(
    title: str,
    intro: str,
    plan: ReplacementPlan,
    updates: ReferenceUpdates,
    accept_text: str,
    parent: QWidget | None = None,
) -> bool:
    """Shows what a replacement loses, and asks whether to go on.

    Args:
        title: The window title.
        intro: The sentence above the tables.
        plan: The conversion or rebuild.
        updates: What happens to the references.
        accept_text: The text of the button that goes on.
        parent: The parent widget.

    Returns:
        True if the user accepted.
    """
    return _answered_yes(
        ReplacementDialog(title, intro, plan, updates, accept_text, parent)
    )


def choose_target(
    element: model.SubmodelElement,
    targets: Sequence[ElementType],
    parent: QWidget | None = None,
) -> ElementType | None:
    """Asks which type to convert an element to.

    Args:
        element: The element to convert.
        targets: The types on offer.
        parent: The parent widget.

    Returns:
        The chosen type, or None if the user cancelled.
    """
    names = [target.__name__ for target in targets]
    chosen, accepted = QInputDialog.getItem(
        parent,
        "Convert to another element type",
        f"Convert {type(element).__name__} '{item_name(element)}' to:",
        names,
        0,
        False,
    )
    if not accepted or chosen not in names:
        return None
    return targets[names.index(chosen)]


def ask_use_file_content(
    path: str, size: int, parent: QWidget | None = None
) -> bool | None:
    """Asks whether a Blob made from a File should hold the file's content.

    Args:
        path: The path of the file in the package.
        size: The size of the stored file.
        parent: The parent widget.

    Returns:
        True to copy the content, False to keep the path as text, None if the
        user cancelled.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle("Convert file to Blob")
    box.setText(
        f"The file '{path}' is stored in the package ({size} bytes). "
        "Copy its content into the Blob?"
    )
    box.setInformativeText(
        "The package grows by the size of the file. The file stays in the "
        "package. If you decline, the Blob holds the path as text."
    )
    copy = box.addButton("Copy content", QMessageBox.ButtonRole.AcceptRole)
    path_only = box.addButton("Keep the path", QMessageBox.ButtonRole.NoRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(cancel)
    box.exec()
    clicked = box.clickedButton()
    if clicked is copy and copy is not None:
        return True
    if clicked is path_only and path_only is not None:
        return False
    return None


class ListSettingsDialog(QDialog):
    """Chooses what a list fixes: type, value type, semantic id, and order.

    Attributes:
        type_box: The type of the items.
        value_type_box: The value type of Property and Range items.
        semantic_box: What the semantic id of the items is.
        semantic_edit: The global id, when the semantic box asks for one.
        order_box: Whether the order of the items matters.
        detect_button: Fills the settings from the items.
        buttons: The accept and the cancel button.
    """

    def __init__(
        self,
        item_list: "model.SubmodelElementList[Any]",
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog with the settings the list has now.

        Args:
            item_list: The list to change. It is not changed here.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Change list settings")
        self.setMinimumWidth(480)
        self._list = item_list
        current = settings_of(item_list)
        self.type_box = QComboBox()
        for item_type in LIST_ITEM_TYPES:
            self.type_box.addItem(item_type.__name__, item_type)
        self.value_type_box = ValueTypeBox(current.value_type)
        self.semantic_box = QComboBox()
        self.semantic_edit = QLineEdit()
        self.semantic_edit.setAccessibleName("Global semantic id of the items")
        self.semantic_edit.setPlaceholderText(
            "Global id such as an IRDI or URL"
        )
        self.order_box = QCheckBox("The order of the items is relevant")
        self.detect_button = QPushButton("Detect from the items")
        self.detect_button.setToolTip(
            "Take the type, value type, and semantic id that the items share"
        )
        self.detect_button.setEnabled(detect_settings(item_list) is not None)
        self.hint_label = QLabel(
            "Items that do not fit the new settings are not kept. You see them"
            " before anything changes."
        )
        self.hint_label.setWordWrap(True)
        self.buttons = make_button_box(self, "Rebuild list", safe_default=True)

        form = QFormLayout()
        form.addRow("Type of the items", self.type_box)
        form.addRow("Value type of the items", self.value_type_box)
        form.addRow("Semantic id of the items", self.semantic_box)
        form.addRow("", self.semantic_edit)
        form.addRow("", self.order_box)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.detect_button)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.buttons)
        finish_dialog(self)

        self.show_settings(current)
        self.type_box.currentIndexChanged.connect(self._update_enabled)
        self.semantic_box.currentIndexChanged.connect(self._update_enabled)
        self.detect_button.clicked.connect(self._detect)
        self._update_enabled()

    def show_settings(self, settings: ListSettings) -> None:
        """Shows settings in the widgets."""
        self.type_box.setCurrentIndex(
            self.type_box.findData(settings.element_type)
        )
        self.value_type_box.set_value_type(settings.value_type)
        self.order_box.setChecked(settings.order_relevant)
        self._fill_semantic_box(settings.semantic_id)
        self._update_enabled()

    def settings(self) -> ListSettings:
        """Returns the settings the widgets show."""
        element_type = cast(ElementType, self.type_box.currentData())
        return ListSettings(
            element_type,
            self.value_type_box.value_type(),
            self._semantic_id(),
            self.order_box.isChecked(),
        ).normalized()

    def _fill_semantic_box(self, semantic_id: model.Reference | None) -> None:
        self.semantic_box.clear()
        self.semantic_box.addItem("None", None)
        if semantic_id is not None:
            self.semantic_box.addItem(
                f"Keep {describe_reference(semantic_id)}", semantic_id
            )
        self.semantic_box.addItem("Global id...", "global")
        index = 1 if semantic_id is not None else 0
        self.semantic_box.setCurrentIndex(index)
        self.semantic_edit.clear()

    def _semantic_id(self) -> model.Reference | None:
        data = self.semantic_box.currentData()
        if data == "global":
            text = self.semantic_edit.text().strip()
            if not text:
                return None
            return model.ExternalReference(
                (model.Key(model.KeyTypes.GLOBAL_REFERENCE, text),)
            )
        return cast("model.Reference | None", data)

    def _update_enabled(self, _: int = 0) -> None:
        element_type = self.type_box.currentData()
        self.value_type_box.setEnabled(
            element_type in (model.Property, model.Range)
        )
        self.semantic_edit.setEnabled(
            self.semantic_box.currentData() == "global"
        )

    def _detect(self) -> None:
        detected = detect_settings(self._list)
        if detected is not None:
            self.show_settings(detected)


def ask_list_settings(
    item_list: "model.SubmodelElementList[Any]",
    parent: QWidget | None = None,
) -> ListSettings | None:
    """Asks for new settings of a list.

    Args:
        item_list: The list to change.
        parent: The parent widget.

    Returns:
        The settings, or None if the user cancelled.
    """
    dialog = ListSettingsDialog(item_list, parent)
    if _answered_yes(dialog):
        return dialog.settings()
    return None


__all__ = [
    "ListSettingsDialog",
    "ReplacementDialog",
    "ask_list_settings",
    "ask_use_file_content",
    "choose_target",
    "confirm_replacement",
]
