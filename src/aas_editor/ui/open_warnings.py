"""The message that says why a file could not be opened."""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from aas_editor.infrastructure.open_problems import OpenProblem


def show_open_problem(
    problem: OpenProblem, details: str, parent: QWidget | None = None
) -> None:
    """Tells the user why a file cannot be opened.

    The sentence and the advice come first. The technical text of the error is
    behind the Show Details button, for whoever reports it.

    Args:
        problem: What is wrong with the file, in plain words.
        details: The technical text of the error.
        parent: The parent widget.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Cannot open file")
    box.setText(problem.summary)
    box.setInformativeText(problem.advice)
    box.setDetailedText(details)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()
