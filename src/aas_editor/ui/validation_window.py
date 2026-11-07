"""Puts the validation dock and the hints into the main window.

The main window is generated code and legacy code, so this module adds what
validation needs from the outside: a dock at the bottom, the counts for the
status bar, F8 and Shift+F8 to go through the findings, and the connections
between the package tree and these. The status bar says how many hints the
current object has, and a click on that opens the Hints view of the dock. The window calls `install_validation` once,
before it builds the menus that list the dock, the hints action, and the
actions for the findings.
"""

from typing import Any
from typing import cast

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QWidget

from aas_editor.application.hints import hints_mode
from aas_editor.application.validation import finding_key
from aas_editor.application.validation import step_finding
from aas_editor.application.validation import stepping_findings
from aas_editor.domain.validation import Finding
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.app_settings import OPENED_PACKS_ROLE
from aas_editor.ui.hint_kinds_setting import load_hint_kinds
from aas_editor.ui.hints_bar import finding_links
from aas_editor.ui.tree_navigation import select_object
from aas_editor.ui.validation_dock import ValidationDock
from aas_editor.ui.validation_service import service_for
from aas_editor.ui.validation_status import ValidationStatus

# How long the status bar keeps the sentence of the finding that F8 went to.
FINDING_MESSAGE_MS = 10000


class ValidationController(QObject):
    """Connects the package tree, the dock, the status counts, and hints mode.

    Attributes:
        dock: The validation dock.
        status: The counts of errors and warnings, and the hints of the
            current object, for the status bar. The window puts it into its
            status bar.
        hints_action: The checkable View menu entry for hints mode.
        next_finding_action: Goes to the next finding, F8.
        previous_finding_action: Goes to the previous finding, Shift+F8.
    """

    def __init__(self, window: QMainWindow) -> None:
        """Adds the dock and the menu entries to the window.

        Args:
            window: The main window. It needs `mainTreeView` and
                `packTreeModel`, as `EditorApp` has them. The window puts
                `dock.toggleViewAction()` and `hints_action` into its menu.
        """
        super().__init__(window)
        self._window = window
        self._tree = cast("Any", window).mainTreeView
        self._pack_model = cast("Any", window).packTreeModel
        # The kinds of hints that the user turned off in an earlier session.
        load_hint_kinds()
        self.dock = ValidationDock(window)
        window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.dock)
        # Hidden at first. The dock does not run the rules while it is hidden,
        # and the counts in the status bar keep the report up to date (ADR 0029).
        self.dock.hide()
        self.dock.set_active(False)
        self.dock.visibilityChanged.connect(self.dock.set_active)
        self.dock.finding_activated.connect(self.go_to)
        self.status = ValidationStatus(window)
        self.status.opened.connect(self.show_dock)
        self.status.hints_opened.connect(self.show_hints)
        finding_links().opened.connect(self._open_from_bar)
        self._last_key: tuple[str, str, str] | None = None

        self.hints_action = QAction("Hints", window)
        self.hints_action.setCheckable(True)
        self.hints_action.setChecked(hints_mode().is_on)
        self.hints_action.setStatusTip(
            "Show advice about the object next to its attributes"
        )
        self.hints_action.toggled.connect(hints_mode().set_on)
        self._hints_subscription = hints_mode().subscribe(self._on_hints_mode)

        self.next_finding_action = QAction("Next finding", window)
        self.next_finding_action.setShortcut(QKeySequence("F8"))
        self.next_finding_action.setStatusTip(
            "Go to the next error or warning of the package"
        )
        self.next_finding_action.triggered.connect(
            lambda: self.step(forward=True)
        )
        self.previous_finding_action = QAction("Previous finding", window)
        self.previous_finding_action.setShortcut(QKeySequence("Shift+F8"))
        self.previous_finding_action.setStatusTip(
            "Go to the previous error or warning of the package"
        )
        self.previous_finding_action.triggered.connect(
            lambda: self.step(forward=False)
        )
        # The keys work whether or not a menu lists the actions.
        window.addAction(self.next_finding_action)
        window.addAction(self.previous_finding_action)

        selection = self._tree.selectionModel()
        selection.currentChanged.connect(self._follow_package)
        self._pack_model.rowsInserted.connect(self._follow_package)
        self._pack_model.rowsRemoved.connect(self._follow_package)
        self._follow_package()
        # The object of the status bar is the one that the tree or the focused
        # tab shows, as the bar above a tab shows the hints of its object.
        self._focus_in_tab = False
        selection.currentChanged.connect(self._follow_object)
        tabs = getattr(window, "mainTabWidget", None)
        if tabs is not None:
            tabs.currItemChanged.connect(self._follow_object)
            tabs.currentChanged.connect(self._follow_object)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._on_focus)
        self._follow_object()

    def go_to(self, finding: Finding) -> None:
        """Selects the element of a finding in the package tree.

        A finding about the package as a whole selects the package.

        Args:
            finding: The finding the user opened.
        """
        package = self.dock.package
        if package is not None:
            select_object(self._tree, finding.anchor, package)

    def show_dock(self) -> None:
        """Shows the Validation panel on its list of errors and warnings, as a
        click on their counts asks."""
        self.dock.show_findings()

    def show_hints(self) -> None:
        """Shows the Hints view of the panel, as a click on the hints asks."""
        self.dock.show_hints()

    def current_object(self) -> object | None:
        """Returns the object that the status bar says the hints of.

        It is the object of the tab when the focus is in a tab of the window,
        and the object of the current row of the package tree otherwise.
        """
        tabs = getattr(self._window, "mainTabWidget", None)
        if self._focus_in_tab and tabs is not None:
            return getattr(tabs.currentWidget(), "packItemObj", None)
        return self._tree.currentIndex().data(OBJECT_ROLE)

    def step(self, forward: bool) -> Finding | None:
        """Goes to the next or the previous error or warning of the package.

        The element of the finding becomes the current row of the tree, the
        status bar says what the finding is, and the panel selects it when it
        is open. The order is the one of the report, errors first, and the
        walk wraps around.

        Args:
            forward: True for F8, False for Shift+F8.

        Returns:
            The finding, or None when the package has none.
        """
        package = self.dock.package
        if package is None:
            return None
        service = service_for(package)
        if service.is_stale:
            service.refresh()
        findings = stepping_findings(service.report)
        number = step_finding(findings, self._last_key, forward)
        status_bar = self._window.statusBar()
        if number is None:
            self._last_key = None
            if status_bar is not None:
                status_bar.showMessage("No errors or warnings", 5000)
            return None
        finding = findings[number]
        self._last_key = finding_key(finding)
        self.go_to(finding)
        if self.dock.isVisible():
            self.dock.reveal(finding)
        if status_bar is not None:
            kind = finding.severity.value.capitalize()
            status_bar.showMessage(
                f"{kind} {number + 1} of {len(findings)}: "
                f"{finding.rule_id}, {finding.location}: {finding.message}",
                FINDING_MESSAGE_MS,
            )
        return finding

    def _open_from_bar(self, package: object, finding: Finding) -> None:
        """Opens a finding in the panel, when the bar of a tab asks for it."""
        if package is not self.dock.package:
            # The package of the tab is not the current one. Its element
            # becomes the current row, which makes its package current.
            select_object(self._tree, finding.anchor, package)
        self._last_key = finding_key(finding)
        self.dock.reveal(finding)

    def _follow_package(self, *_: object) -> None:
        """Shows the findings of the package of the current row."""
        opened = self._pack_model.data(QModelIndex(), OPENED_PACKS_ROLE)
        current = self._tree.activePackage()
        if current is not None and current not in opened:
            current = None
        self.dock.set_package(current)
        self.status.set_package(current)

    def _follow_object(self, *_: object) -> None:
        """Shows the hints of the current object in the status bar."""
        self.status.set_target(self.current_object())

    def _on_focus(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Follows the tree or the tab, whichever took the focus last."""
        tabs = getattr(self._window, "mainTabWidget", None)
        widget = new
        while widget is not None:
            if widget is self._tree:
                self._focus_in_tab = False
                break
            if widget is tabs:
                self._focus_in_tab = True
                break
            widget = widget.parentWidget()
        else:
            return
        self._follow_object()

    def _on_hints_mode(self, on: bool) -> None:
        try:
            self.hints_action.setChecked(on)
        except RuntimeError:
            # The window was deleted, and the subscription outlived it. Stop
            # listening, as a failure would be logged at every change.
            self._hints_subscription.cancel()


def install_validation(window: QMainWindow) -> ValidationController:
    """Adds the validation dock and hints mode to the main window.

    Args:
        window: The main window.

    Returns:
        The controller, which the window should keep.
    """
    return ValidationController(window)
