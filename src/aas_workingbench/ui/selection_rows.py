"""The rows that Delete, Cut and Copy act on.

A selection can hold the cells of a row, rows below other selected rows, and
rows of several parents. Delete, Cut and Copy act on all of it, or on none:
they take each selected row once, in the order of the tree, and refuse a
selection that the action cannot serve in one step. Rows of two packages are
such a selection, because each package has its own history and its own set of
concept descriptions and files.
"""

from collections.abc import Iterable

from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget

from aas_workingbench.settings.app_settings import PACKAGE_ROLE

DIFFERENT_PACKAGES_TEXT = (
    "The selected rows are in different packages, and {action} works on one "
    "package at a time. Select rows of one package."
)


def _path(index: QModelIndex) -> tuple[int, ...]:
    """Return the rows that lead from the top of the tree to a row."""
    rows: list[int] = []
    while index.isValid():
        rows.append(index.row())
        index = index.parent()
    return tuple(reversed(rows))


def top_level_rows(indexes: Iterable[QModelIndex]) -> list[QModelIndex]:
    """Return each selected row once, in the order of the tree.

    A view that selects rows lists every cell of a row, but a row is one item.
    A row below a selected row goes with it, so it is left out. The rows may
    have different parents.

    Args:
        indexes: The selected indexes, in any order.

    Returns:
        The first index of each remaining row, from the top of the tree down.
    """
    first: dict[tuple[QModelIndex, int], QModelIndex] = {}
    for index in indexes:
        if index.isValid():
            first.setdefault((index.parent(), index.row()), index)

    def has_selected_ancestor(index: QModelIndex) -> bool:
        ancestor = index.parent()
        while ancestor.isValid():
            if (ancestor.parent(), ancestor.row()) in first:
                return True
            ancestor = ancestor.parent()
        return False

    rows = [i for i in first.values() if not has_selected_ancestor(i)]
    return sorted(rows, key=_path)


def in_one_package(rows: Iterable[QModelIndex]) -> bool:
    """Tell whether the rows belong to at most one package."""
    packages = {id(row.data(PACKAGE_ROLE)) for row in rows}
    return len(packages) <= 1


def show_refusal(
    title: str, message: str, parent: QWidget | None = None
) -> None:
    """Tell the user why an action on the selection was not done."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(message)
    box.exec()
