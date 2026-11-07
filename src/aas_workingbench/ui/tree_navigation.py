"""Finding an AAS object in the package tree and selecting it."""

from PyQt6.QtCore import QAbstractItemModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QTreeView

from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.settings.app_settings import PACKAGE_ROLE


def find_object(
    model: QAbstractItemModel, obj: object | None, package: object
) -> QModelIndex:
    """Finds the row that shows an object of a package.

    Args:
        model: The model of the package tree, or a proxy over it.
        obj: A shell, submodel, concept description or element of the package.
            None, or the package itself, finds the row of the package.
        package: The package that holds the object.

    Returns:
        The index of the first column of the row, or an invalid index if the
        tree does not show the object, for example because a filter hides it.
    """
    for number in range(model.rowCount()):
        root = model.index(number, 0)
        if root.data(PACKAGE_ROLE) is not package:
            continue
        if obj is None or obj is package:
            return root
        return _search(model, root, obj)
    return QModelIndex()


def select_object(view: QTreeView, obj: object | None, package: object) -> bool:
    """Makes an object the current row of the tree, showing it.

    The rows above it are expanded, and the view scrolls to it.

    Args:
        view: The package tree view.
        obj: The object to go to. None selects the package.
        package: The package that holds the object.

    Returns:
        True if the tree shows the object.
    """
    model = view.model()
    if model is None:
        return False
    index = find_object(model, obj, package)
    if not index.isValid():
        return False
    parent = index.parent()
    while parent.isValid():
        view.expand(parent)
        parent = parent.parent()
    view.setCurrentIndex(index)
    view.scrollTo(index, QAbstractItemView.ScrollHint.PositionAtCenter)
    return True


def _search(
    model: QAbstractItemModel, root: QModelIndex, obj: object
) -> QModelIndex:
    pending = [root]
    while pending:
        parent = pending.pop()
        for number in range(model.rowCount(parent)):
            child = model.index(number, 0, parent)
            if child.data(OBJECT_ROLE) is obj:
                return child
            pending.append(child)
    return QModelIndex()
