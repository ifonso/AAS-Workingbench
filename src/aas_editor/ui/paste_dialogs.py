"""The questions that come when elements are pasted into another package.

They only show what `application/operations/companions.py` found and return
the answer. A cancelled question returns None, and the paste stops.
"""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from aas_editor.application.operations.companions import ConceptChoice
from aas_editor.application.operations.companions import ConceptConflict
from aas_editor.application.operations.companions import ConceptPlan
from aas_editor.domain.references import describe_object

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
