"""Puts the validation dock and the hints into the main window.

The main window is generated code and legacy code, so this module adds what
validation needs from the outside: a dock at the bottom, an entry in the View
menu, and the connections between the package tree and the dock. The window
calls `install_validation` once, after its menus and handlers exist.
"""

from typing import Any
from typing import cast

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QMenu

from aas_editor.application.hints import hints_mode
from aas_editor.domain.validation import Finding
from aas_editor.settings.app_settings import OPENED_PACKS_ROLE
from aas_editor.ui.tree_navigation import select_object
from aas_editor.ui.validation_dock import ValidationDock


class ValidationController:
    """Connects the package tree, the dock, and hints mode.

    Attributes:
        dock: The validation dock.
        hints_action: The checkable View menu entry for hints mode.
    """

    def __init__(self, window: QMainWindow) -> None:
        """Adds the dock and the menu entries to the window.

        Args:
            window: The main window. It needs `mainTreeView`, `packTreeModel`
                and `menuView`, as `EditorApp` has them.
        """
        self._window = window
        self._tree = cast("Any", window).mainTreeView
        self._pack_model = cast("Any", window).packTreeModel
        self.dock = ValidationDock(window)
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)
        # Hidden at first, and then it does not run the rules.
        self.dock.hide()
        self.dock.set_active(False)
        self.dock.visibilityChanged.connect(self.dock.set_active)
        self.dock.finding_activated.connect(self.go_to)

        self.hints_action = QAction("Hints", window)
        self.hints_action.setCheckable(True)
        self.hints_action.setChecked(hints_mode().is_on)
        self.hints_action.setStatusTip(
            "Show advice about the object next to its attributes"
        )
        self.hints_action.toggled.connect(hints_mode().set_on)
        hints_mode().subscribe(self._on_hints_mode)

        menu = cast("QMenu", cast("Any", window).menuView)
        menu.addSection("Validation")
        menu.addAction(self.dock.toggleViewAction())
        menu.addAction(self.hints_action)

        selection = self._tree.selectionModel()
        selection.currentChanged.connect(self._follow_package)
        self._pack_model.rowsInserted.connect(self._follow_package)
        self._pack_model.rowsRemoved.connect(self._follow_package)
        self._follow_package()

    def go_to(self, finding: Finding) -> None:
        """Selects the element of a finding in the package tree.

        A finding about the package as a whole selects the package.

        Args:
            finding: The finding the user opened.
        """
        package = self.dock.package
        if package is not None:
            select_object(self._tree, finding.anchor, package)

    def _follow_package(self, *_: object) -> None:
        """Shows the findings of the package of the current row."""
        opened = self._pack_model.data(QModelIndex(), OPENED_PACKS_ROLE)
        current = self._tree.activePackage()
        if current is not None and current not in opened:
            current = None
        self.dock.set_package(current)

    def _on_hints_mode(self, on: bool) -> None:
        self.hints_action.setChecked(on)


def install_validation(window: QMainWindow) -> ValidationController:
    """Adds the validation dock and hints mode to the main window.

    Args:
        window: The main window.

    Returns:
        The controller, which the window should keep.
    """
    return ValidationController(window)
