"""The questions that come when elements are pasted into another package.

They only show what `application/operations/companions.py` found and return
the answer. A cancelled question returns None, and the paste stops.
"""

from collections.abc import Sequence

from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QRadioButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.operations.companions import ConceptChoice
from aas_workingbench.application.operations.companions import ConceptConflict
from aas_workingbench.application.operations.companions import ConceptPlan
from aas_workingbench.domain.references import describe_object
from aas_workingbench.ui.dialog_layout import finish_dialog

TITLE = "Copy & Paste"


def ask_copy_concepts(
    plan: ConceptPlan, parent: QWidget | None = None
) -> bool | None:
    """Asks whether the concept descriptions of a copy should come along.

    Args:
        plan: What the copy needs from the other package.
        parent: The parent widget of the question.

    Returns:
        True to copy them, False to paste without them, None to cancel.
    """
    count = len(plan.to_add) + len(plan.conflicts)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(TITLE)
    box.setText(
        f"The pasted elements refer to {count} concept description"
        f"{'s' if count != 1 else ''} that this package does not have."
    )
    box.setInformativeText(
        "Copy the concept descriptions too? Without them, the semantic ids "
        "of the pasted elements point at nothing."
    )
    yes = box.addButton("Copy them", QMessageBox.ButtonRole.YesRole)
    no = box.addButton("Paste without them", QMessageBox.ButtonRole.NoRole)
    cancel = box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(yes)
    box.exec()
    clicked = box.clickedButton()
    if clicked is yes:
        return True
    if clicked is no:
        return False
    del cancel
    return None


def ask_concept_conflict(
    conflict: ConceptConflict, parent: QWidget | None = None
) -> ConceptChoice | None:
    """Asks what to do with a description that the target has, with other content.

    Args:
        conflict: The two descriptions with the same id.
        parent: The parent widget of the question.

    Returns:
        The choice, or None to cancel.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(TITLE)
    box.setText(
        f"This package has another {describe_object(conflict.existing)} "
        f"with the id {conflict.source.id}."
    )
    box.setInformativeText(
        "Keep the one of this package, or add the copied one under a new id "
        "for the pasted elements?"
    )
    keep = box.addButton("Keep existing", QMessageBox.ButtonRole.AcceptRole)
    add = box.addButton("Add as new", QMessageBox.ButtonRole.AcceptRole)
    box.addButton(QMessageBox.StandardButton.Cancel)
    box.setDefaultButton(keep)
    box.exec()
    clicked = box.clickedButton()
    if clicked is keep:
        return ConceptChoice.KEEP_EXISTING
    if clicked is add:
        return ConceptChoice.ADD_WITH_NEW_ID
    return None


def show_problem(message: str, parent: QWidget | None = None) -> None:
    """Tells the user why a paste did not happen."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(TITLE)
    box.setText(message)
    box.exec()


class PasteTextDialog(QDialog):
    """A text box for the JSON of copied elements, and where to put them.

    It is the way to paste when the system clipboard cannot be read, for
    example when the platform denies access to it (F-EDT-08 AC8).

    Attributes:
        text_edit: Where the user pastes or types the JSON.
        places: The radio buttons by the key of the place.
    """

    def __init__(
        self,
        places: Sequence[tuple[str, str]],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            places: The places that apply to the selected row, each a key and
                a label, such as `("below", "Below the selected row")`. The
                first one is chosen.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Paste from text")
        self.setMinimumWidth(480)
        self.places: dict[str, QRadioButton] = {}
        layout = QVBoxLayout(self)
        label = QLabel(
            "Paste the JSON of the copied elements here. Use it when the "
            "clipboard cannot be read."
        )
        label.setWordWrap(True)
        layout.addWidget(label)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText('[ {"idShort": "...", ...} ]')
        layout.addWidget(self.text_edit)
        for key, text in places:
            button = QRadioButton(text)
            self.places[key] = button
            layout.addWidget(button)
        if self.places:
            next(iter(self.places.values())).setChecked(True)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        finish_dialog(self)

    def chosen_place(self) -> str | None:
        """Returns the key of the chosen place, or None if there is none."""
        for key, button in self.places.items():
            if button.isChecked():
                return key
        return None


def ask_paste_text(
    places: Sequence[tuple[str, str]], parent: QWidget | None = None
) -> tuple[str, str] | None:
    """Asks for the JSON of copied elements and where to paste them.

    Args:
        places: The places that apply, each a key and a label.
        parent: The parent widget.

    Returns:
        The text and the key of the place, or None when the user cancelled or
        typed nothing.
    """
    dialog = PasteTextDialog(places, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted.value:
        return None
    text = dialog.text_edit.toPlainText().strip()
    place = dialog.chosen_place()
    if not text or place is None:
        return None
    return text, place
