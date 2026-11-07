#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
import json
import logging
import webbrowser
from pathlib import Path

from PyQt6 import QtCore, sip
from PyQt6.QtCore import QModelIndex, QTimer, pyqtSignal
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

import aas_workingbench.widgets as widgets
import aas_workingbench.widgets.messsageBoxes
import aas_workingbench.widgets.groupBoxes
from aas_workingbench.ui.colors import problem_style
from aas_workingbench.application.theme_choice import theme_from_saved
from aas_workingbench.ui.theme import THEME_LABELS, theme_manager
from aas_workingbench.settings import app_settings
from aas_workingbench.settings.app_settings import *
from aas_workingbench.utils.recovery import (
    find_recovery_files,
    delete_recovery_file,
    cleanup_recovery_dir,
    take_over_recovery_files,
)
from aas_workingbench.application.editing import edit_mode
from aas_workingbench.application.file_transfer import transfer_reports
from aas_workingbench.application.font_sizes import FONT_SIZE_LAYOUT_VERSION
from aas_workingbench.application.font_sizes import migrated_font_size
from aas_workingbench.application.header_state import restorable_state
from aas_workingbench.domain.design_tokens import parse_density
from aas_workingbench.domain.window_layout import DEFAULT_SIZE
from aas_workingbench.domain.window_layout import saved_orientation
from aas_workingbench.domain.window_layout import window_size
from aas_workingbench.domain.window_layout import zone_widths
from aas_workingbench.ui.command_bar import FocusedViewActions
from aas_workingbench.ui.package_files import PackageFilesDock
from aas_workingbench.ui.pane_navigation import PANEL
from aas_workingbench.ui.pane_navigation import Pane
from aas_workingbench.ui.pane_navigation import PaneNavigator
from aas_workingbench.ui.pane_navigation import TAB
from aas_workingbench.ui.pane_navigation import TREE
from aas_workingbench.ui.pane_navigation import first_focusable
from aas_workingbench.ui.save_warnings import show_missing_files
from aas_workingbench.ui.selection_panel import SelectionDock
from aas_workingbench.package import Package
from aas_workingbench.utils.exceptionhook import set_crash_callback
from aas_workingbench.settings.icons import (
    EXIT_ICON,
    SETTINGS_ICON,
    NEW_PACK_ICON,
)
from aas_workingbench.settings import APPLICATION_NAME, REPORT_ERROR_LINK
from aas_workingbench.widgets.settingWidgets import SettingsDialog
from aas_workingbench.tools.aas_test.aas_test_engines_tool import (
    AasTestEnginesToolDialog,
)
from aas_workingbench.widgets import AddressLine
from aas_workingbench.widgets.tab import TabWidget
from aas_workingbench import design
from aas_workingbench.models import DetailedInfoTable, PacksTable
from aas_workingbench.treeviews.base import HeaderView
from aas_workingbench.ui.command_palette import install_palette
from aas_workingbench.ui.validation_window import install_validation


class EditorApp(QMainWindow, design.Ui_MainWindow):
    closed = pyqtSignal()

    def __init__(self, fileToOpen=None, parent=None):
        super().__init__(parent=parent)
        self.setupUi(self)
        self.loadThemes()

        widgets.groupBoxes.ModelReferenceGroupBox.CHOOSE_FRM_VIEW = (
            self.mainTreeView
        )
        AddressLine.setModel(self.mainTreeView.model())
        welcomeTabKwargs = (
            self.mainTabWidget.tabClsKwargs
            if self.mainTabWidget.tabClsKwargs
            else {}
        )
        welcomeTab = self.mainTabWidget.addTab(
            self.mainTabWidget.tabCls(
                parent=self.mainTabWidget, **welcomeTabKwargs
            ),
            "Welcome",
        )

        self.initPackageFiles()
        # The validation dock and hints mode, before the menus that list them
        self.validationController = install_validation(self)
        self.initDocks()
        # F6 and Ctrl+1, Ctrl+2, which the Navigate menu lists
        self.paneNavigator = self.initPaneNavigation()
        # Ctrl+K, which lists the actions of the menus that follow
        self.commandPalette = install_palette(self)
        self.initActions()
        self.initMenu()
        self.initToolbars()
        self.buildHandlers()
        self.restoreSettingsFromLastSession()
        set_crash_callback(self._save_recovery_files)

        # sys.excepthook misses native crashes (segfaults, OOM kills), which run no
        # Python and never reach _save_recovery_files. Persist periodically instead.
        self._recoveryTimer = QTimer(self)
        self._recoveryTimer.setInterval(RECOVERY_INTERVAL_MS)
        self._recoveryTimer.timeout.connect(self._save_recovery_files)
        self._recoveryTimer.start()
        # Shown once on failure and cleared once writing recovers.
        self._recoveryWriteFailed = False
        # Synced to settings only when it changes (open/close), not on every tick.
        self._lastPersistedOpenFiles = None
        # Permanent widget, not showMessage(): transient status tips (menu hover)
        # do not overwrite it, so the warning stays until writing recovers.
        self._recoveryStatusLabel = QLabel()
        self._recoveryStatusLabel.setStyleSheet(problem_style())
        self._recoveryStatusLabel.hide()
        self.statusBar().addPermanentWidget(self._recoveryStatusLabel)
        # The mode and the unsaved packages are always on show, so the window
        # tells the state of the work without a menu.
        self._modeStatusLabel = QLabel()
        self._modeStatusLabel.setObjectName("modeStatusLabel")
        self.statusBar().addPermanentWidget(self._modeStatusLabel)
        # The counts of errors, warnings and hints of the current package
        self.statusBar().addPermanentWidget(self.validationController.status)
        self._unsavedStatusLabel = QLabel()
        self._unsavedStatusLabel.setObjectName("unsavedStatusLabel")
        self.statusBar().addPermanentWidget(self._unsavedStatusLabel)
        self.onEditModeChanged(edit_mode().is_editing)
        self.mainTreeView.unsavedPackagesChanged.connect(self.onUnsavedChanged)
        self.mainTreeView.updateWindowModified()
        if fileToOpen:
            self.openAASFile(fileToOpen)
        else:
            self.openLastSessionFiles()
        self.applyLastSessionTabHeader()

    def loadThemes(self):
        # Each id of a theme maps to the text of its entry in the menu.
        self.themeLabels = dict(THEME_LABELS)
        self.currTheme = DEFAULT_THEME

    # noinspection PyArgumentList
    def initActions(self):
        self.exitAct = QAction(
            EXIT_ICON,
            "E&xit",
            self,
            statusTip="Exit the application",
            triggered=lambda: self.close(),
        )

        self.aboutDialogAct = QAction(
            "About",
            self,
            statusTip=f"Show information about {APPLICATION_NAME}",
            triggered=lambda: widgets.messsageBoxes.AboutMessageBox(
                self
            ).exec(),
        )

        self.testEnginesToolDialogAct = QAction(
            "AAS Test tool (V3.0)",
            self,
            statusTip="Open AAS Test Engines tool, which checks Metamodel V3.0",
            triggered=lambda: AasTestEnginesToolDialog(self).exec(),
        )

        self.handoverDocumentationToolDialogAct = QAction(
            "Handover Documentation tool",
            self,
            statusTip="Open Handover Documentation tool",
            triggered=self.openHandoverDocumentationTool,
        )

        self.importToolAct = QAction(
            "Excel AAS Generator tool",
            self,
            statusTip="Open Excel AAS Generator tool",
            triggered=lambda: self.showImportApp(),
        )

        self.settingsDialogAct = QAction(
            SETTINGS_ICON,
            "Settings",
            self,
            statusTip=f"Edit application settings",
            triggered=lambda: self.openSettings(),
        )

        self.reportBugAct = QAction(
            "Report Bug",
            self,
            statusTip="Report an error found",
            triggered=lambda: webbrowser.open(REPORT_ERROR_LINK),
        )

        # Theme actions
        self.themeActs = []
        self.themeGroup = QActionGroup(self)
        for theme, label in self.themeLabels.items():
            themeAct = QAction(
                label,
                self,
                checkable=True,
                checked=theme == self.currTheme,
                statusTip=f"Choose the theme: {label}",
                triggered=lambda: self.toggleThemeSlot(),
            )
            themeAct.setData(theme)
            self.themeGroup.addAction(themeAct)
            self.themeActs.append(themeAct)

        # Edit and Read mode (D18): one switch for all open packages
        self.editModeAct = QAction(
            "Edit mode",
            self,
            checkable=True,
            checked=edit_mode().is_editing,
            statusTip="Packages can be changed",
            triggered=lambda: edit_mode().set_editing(True),
        )
        self.readModeAct = QAction(
            "Read mode",
            self,
            checkable=True,
            checked=not edit_mode().is_editing,
            statusTip="Packages can only be looked at, not changed",
            triggered=lambda: edit_mode().set_editing(False),
        )
        self.modeActs = QActionGroup(self)
        self.modeActs.setExclusive(True)
        self.modeActs.addAction(self.editModeAct)
        self.modeActs.addAction(self.readModeAct)
        edit_mode().subscribe(self.onEditModeChanged)

        # The tab bar of the tab widget can be hidden, which the gear button of
        # each tab used to offer.
        self.tabBarAct = QAction(
            "Tab bar",
            self,
            checkable=True,
            checked=True,
            statusTip="Show or hide the tab bar",
            toggled=self.mainTabWidget.tabBar().setVisible,
        )
        # The actions of the command bar and of the Edit menu, which act on the
        # tree or the tab that has the focus.
        self.focusedActs = FocusedViewActions(
            self, self.mainTreeView, self.mainTabWidget
        )

        self.setHOrientationAct = QAction(
            "Horizontal",
            self,
            statusTip=f"Set horizontal orientation",
            triggered=lambda: self.setOrientation(
                QtCore.Qt.Orientation.Horizontal
            ),
        )
        self.setVOrientationAct = QAction(
            "Vertical",
            self,
            statusTip=f"Set vertical orientation",
            triggered=lambda: self.setOrientation(
                QtCore.Qt.Orientation.Vertical
            ),
        )

    def showImportApp(self):
        self.writeSettings()
        from aas_workingbench.tools.import_feature.import_app import ImportApp

        self.hide()
        importApp = ImportApp()
        importApp.closed.connect(self.show)
        importApp.show()

    def initMenu(self):
        self.menubar = QMenuBar(self)
        self.menubar.setObjectName("menubar")
        self.setMenuBar(self.menubar)

        self.menuFile = QMenu("&File", self.menubar)
        self.menuNewAasFile = QMenu("New AAS file...", self.menuFile)
        self.menuNewAasFile.setIcon(NEW_PACK_ICON)
        for newPackAct in self.mainTreeView.newPackActs:
            self.menuNewAasFile.addAction(newPackAct)
        self.menuFile.addMenu(self.menuNewAasFile)
        self.menuFile.addAction(self.mainTreeView.openPackAct)
        # self.menuFile.addAction(self.mainTreeView.openPackFromServerAct)

        self.menuFile.addSeparator()
        self.menuOpenRecent = QMenu("Open Recent", self.menuFile)
        for recentFileAct in self.mainTreeView.recentFileActs:
            self.menuOpenRecent.addAction(recentFileAct)
        self.menuFile.addAction(self.menuOpenRecent.menuAction())
        self.mainTreeView.recentFilesSeparator = self.menuFile.addSeparator()
        self.mainTreeView.updateRecentFileActs()

        self.menuFile.addAction(self.mainTreeView.saveAct)
        self.menuFile.addAction(self.mainTreeView.saveAsAct)
        self.menuFile.addMenu(self.mainTreeView.saveInMenu)
        self.menuFile.addAction(self.mainTreeView.saveAllAct)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.settingsDialogAct)
        self.menuFile.addSeparator()
        self.menuFile.addAction(self.mainTreeView.closeAct)
        self.menuFile.addAction(self.mainTreeView.closeAllAct)
        self.menuFile.addAction(self.exitAct)

        self.menuEdit = QMenu("&Edit", self.menubar)
        for key in ("undo", "redo"):
            self.menuEdit.addAction(self.focusedActs.actions[key])
        self.menuEdit.addSeparator()
        for key in (
            "cut",
            "copy",
            "paste",
            "paste_above",
            "paste_below",
            "paste_into",
        ):
            self.menuEdit.addAction(self.focusedActs.actions[key])
        self.menuEdit.addSeparator()
        for key in ("add", "edit", "delete"):
            self.menuEdit.addAction(self.focusedActs.actions[key])

        self.menuView = QMenu("&View", self.menubar)
        self.menuView.addSection("Mode")
        self.menuView.addAction(self.editModeAct)
        self.menuView.addAction(self.readModeAct)
        self.menuView.addSection("Appearance")
        self.menuChooseTheme = QMenu("Choose Theme", self.menuView)
        for themeAct in self.themeActs:
            self.menuChooseTheme.addAction(themeAct)
        self.menuView.addAction(self.menuChooseTheme.menuAction())
        self.menuView.addAction(self.toolBar.toggleViewAction())
        self.menuView.addAction(self.searchBarPack.toggleViewAction())
        self.menuView.addAction(self.tabBarAct)
        self.menuOrientation = QMenu("Orientation", self.menuView)
        self.menuOrientation.addAction(self.setHOrientationAct)
        self.menuOrientation.addAction(self.setVOrientationAct)
        self.menuView.addAction(self.menuOrientation.menuAction())
        self.menuView.addSection("Panels")
        self.menuView.addAction(self.filesDock.toggleViewAction())
        self.menuView.addAction(self.selectionDock.toggleViewAction())
        self.menuView.addAction(
            self.validationController.dock.toggleViewAction()
        )
        self.menuView.addSection("AAS file view")
        self.menuView.addAction(self.mainTreeView.zoomInAct)
        self.menuView.addAction(self.mainTreeView.zoomOutAct)
        # The columns of the tree. The menu is made when it opens, because the
        # header makes its actions again when a state is restored.
        self.menuColumns = QMenu("Columns", self.menuView)
        self.menuColumns.aboutToShow.connect(self.fillColumnsMenu)
        self.menuView.addAction(self.menuColumns.menuAction())
        self.menuView.addSection("Detailed view")
        self.menuView.addAction(self.mainTabWidget.zoomInAct)
        self.menuView.addAction(self.mainTabWidget.zoomOutAct)
        for key in ("collapse_all", "expand_all"):
            self.menuView.addAction(self.focusedActs.actions[key])

        self.menuValidate = QMenu("Va&lidate", self.menubar)
        self.menuValidate.addAction(
            self.validationController.dock.toggleViewAction()
        )
        self.menuValidate.addAction(self.validationController.hints_action)
        self.menuValidate.addSeparator()
        self.menuValidate.addAction(self.testEnginesToolDialogAct)

        self.menuNavigate = QMenu("&Navigate", self.menubar)
        self.menuNavigate.addAction(self.commandPalette.action)
        self.menuNavigate.addSeparator()
        for paneAct in (*self.paneNavigator.actions, self.editPathAct):
            self.menuNavigate.addAction(paneAct)
        self.menuNavigate.addSeparator()
        self.menuNavigate.addAction(self.mainTreeView.autoScrollToSrcAct)
        self.menuNavigate.addAction(self.mainTreeView.autoScrollFromSrcAct)
        self.menuNavigate.addSeparator()
        self.menuNavigate.addAction(
            self.validationController.next_finding_action
        )
        self.menuNavigate.addAction(
            self.validationController.previous_finding_action
        )
        self.menuNavigate.addSeparator()
        for actionId in ("navigate.push_location", "navigate.pop_location"):
            locationAct = self.mainTreeView.registeredActions.find(actionId)
            if locationAct is not None:
                self.menuNavigate.addAction(locationAct)

        self.menuTools = QMenu("&Tools", self.menubar)
        self.menuTools.addAction(self.testEnginesToolDialogAct)
        self.menuTools.addAction(self.handoverDocumentationToolDialogAct)
        self.menuTools.addAction(self.importToolAct)

        self.menuHelp = QMenu("&Help", self.menubar)
        self.menuHelp.addAction(self.aboutDialogAct)
        self.menuHelp.addAction(self.reportBugAct)

        self.menubar.addAction(self.menuFile.menuAction())
        self.menubar.addAction(self.menuEdit.menuAction())
        self.menubar.addAction(self.menuView.menuAction())
        self.menubar.addAction(self.menuNavigate.menuAction())
        self.menubar.addAction(self.menuValidate.menuAction())
        self.menubar.addAction(self.menuTools.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())

    def fillColumnsMenu(self):
        """Lists the columns that the header of the tree has now."""
        self.menuColumns.clear()
        for action in self.mainTreeView.header().actions():
            self.menuColumns.addAction(action)

    def initToolbars(self):
        """Fills the command bar, which acts on the view with the focus.

        The gear button is gone: its zoom and autoscroll actions are in the
        View and Navigate menus. Save All is in the File menu, and Save is
        here. Undo, redo, add, edit, and delete are of the view that has the
        focus (ui/command_bar.py), as are back and forward of its tab.
        """
        acts = self.focusedActs.actions
        self.toolBar.addAction(self.mainTreeView.openPackAct)
        self.toolBar.addAction(self.mainTreeView.saveAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(acts["undo"])
        self.toolBar.addAction(acts["redo"])
        self.toolBar.addSeparator()
        self.toolBar.addAction(acts["add"])
        self.toolBar.addAction(acts["edit"])
        self.toolBar.addAction(acts["delete"])
        self.toolBar.addSeparator()
        self.toolBar.addAction(acts["back"])
        self.toolBar.addAction(acts["forward"])
        # What features registered for the bar (ui/actions.py). Nothing does
        # now: a button with only a text, such as Paste above, is in the Edit
        # menu, and a feature that wants a button gives it an icon.
        for action in self.mainTreeView.registeredActions.toolbar_actions:
            self.toolBar.addAction(action)

    @staticmethod
    def iterItems(root):
        def recurse(parent):
            for row in range(parent.rowCount()):
                for column in range(parent.columnCount()):
                    child = parent.child(row, column)
                    yield child
                    if child.hasChildren():
                        yield from recurse(child)

        if root is not None:
            yield from recurse(root)

    def currentPackage(self):
        """The package of the current row, or the only open package"""
        package = self.mainTreeView.currentIndex().data(PACKAGE_ROLE)
        if package is None:
            packages = self.packTreeModel.openedPacks()
            package = next(iter(packages)) if len(packages) == 1 else None
        return package

    def initPackageFiles(self):
        """The panel of the supplementary files, and what feeds it"""
        self.filesDock = PackageFilesDock(self.currentPackage, self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.filesDock
        )
        self.mainTreeView.packageFilesRequested.connect(
            self.filesDock.show_package
        )
        transfer_reports.subscribe(self.onFilesCopied)
        # What is selected in the tree, and what can be done with all of it
        self.selectionDock = SelectionDock(self.mainTreeView, self)
        self.addDockWidget(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, self.selectionDock
        )
        self.selectionDock.hide()

    def initDocks(self):
        """Puts the three panels of the bottom into one strip of tabs.

        They used to sit side by side, and three open panels cut each other's
        buttons and headers. Now they share the place, with a tab each, and
        any of them can still be dragged out to float. The user's arrangement
        is saved and restored (see `applyLastSessionDocks`).
        """
        self.setTabPosition(
            QtCore.Qt.DockWidgetArea.BottomDockWidgetArea,
            QTabWidget.TabPosition.North,
        )
        validationDock = self.validationController.dock
        self.tabifyDockWidget(validationDock, self.filesDock)
        self.tabifyDockWidget(self.filesDock, self.selectionDock)
        # Hidden until asked for, and tabifying shows the dock of the first tab.
        for dock in (validationDock, self.filesDock, self.selectionDock):
            dock.hide()
            # Qt names the buttons of the title and gives them no tooltip.
            for button_name, tip in (
                ("qt_dockwidget_floatbutton", "Float this panel"),
                ("qt_dockwidget_closebutton", "Close this panel"),
            ):
                button = dock.findChild(QAbstractButton, button_name)
                if button is not None:
                    button.setToolTip(tip)
        # A panel opens at a height that leaves the trees most of the window.
        self.resizeDocks(
            [validationDock], [DOCK_HEIGHT], QtCore.Qt.Orientation.Vertical
        )
        self.nameDockTabBars()

    def nameDockTabBars(self) -> None:
        """Names the strip of tabs that Qt makes for the panels of the bottom."""
        for bar in self.findChildren(
            QTabBar, options=QtCore.Qt.FindChildOption.FindDirectChildrenOnly
        ):
            if not bar.accessibleName():
                bar.setAccessibleName("Panels")

    def initPaneNavigation(self) -> PaneNavigator:
        """Makes the keys that move the focus between the panes.

        The panes are the tree of packages, which is the start panel while no
        package is open, the tab, and the bottom panel that is on show.
        """
        docks = (
            self.validationController.dock,
            self.filesDock,
            self.selectionDock,
        )

        def treeTarget() -> QWidget | None:
            if self.emptyState.isVisible():
                return first_focusable(self.emptyState)
            return self.mainTreeView if self.mainTreeView.isVisible() else None

        def tabTarget() -> QWidget | None:
            tab = self.mainTabWidget.currentWidget()
            view = getattr(tab, "attrsTreeView", None)
            return view if view is not None and view.isVisible() else None

        def panelTarget() -> QWidget | None:
            for dock in docks:
                if dock.isVisible():
                    return first_focusable(dock)
            return None

        navigator = PaneNavigator(
            self,
            [
                Pane(TREE, lambda: [self.mainLayoutWidget], treeTarget),
                Pane(TAB, lambda: [self.subLayoutWidget], tabTarget),
                Pane(PANEL, lambda: list(docks), panelTarget),
            ],
        )
        # The path of the tab is read as segments. This key edits it as text,
        # for a person who does not use the mouse.
        self.editPathAct = QAction(
            "Edit the path",
            self,
            statusTip="Edit the path of the tab as text",
            shortcut=QKeySequence("Ctrl+L"),
            triggered=self.editCurrentPath,
        )
        self.addAction(self.editPathAct)
        return navigator

    def editCurrentPath(self) -> None:
        """Shows the path of the current tab as text, to edit."""
        breadcrumb = getattr(
            self.mainTabWidget.currentWidget(), "breadcrumb", None
        )
        if breadcrumb is not None and breadcrumb.isVisible():
            breadcrumb.start_editing()

    def updateEmptyState(self, *_):
        """Shows the start instead of the tree and the tabs while no package is open."""
        empty = self.packTreeModel.rowCount() == 0
        self.emptyState.setVisible(empty)
        self.mainTreeView.setVisible(not empty)
        self.emptyDetail.setVisible(empty)
        self.splitterTabWidgets.setVisible(not empty)

    def onFilesCopied(self, plan):
        """Tell the user what a paste did with the files of the objects"""
        message = plan.summary()
        if message:
            self.statusBar().showMessage(message, 15000)

    def buildHandlers(self):
        self.mainTabWidget.currItemChanged.connect(self.onCurrTabItemChanged)
        self.mainTreeView.selectionModel().currentChanged.connect(
            lambda *_: self.filesDock.panel.follow_current_package()
        )
        self.mainTreeView.selectionModel().currentChanged.connect(
            self.onSelectedPackItemChanged
        )
        self.mainTreeView.doubleClicked.connect(self.onDoubleClicked)
        # The Find key searches the tree while the focus is on its side of the
        # window. Each tab has its own bar for the same key.
        self.searchBarPack.bindFind(self.mainLayoutWidget)

        self.mainTreeView.wheelClicked.connect(
            self.mainTabWidget.openItemInBgTab
        )
        self.mainTreeView.openInBgTabClicked.connect(
            self.mainTabWidget.openItemInBgTab
        )
        self.mainTreeView.openInNewTabClicked.connect(
            self.mainTabWidget.openItemInNewTab
        )
        self.mainTreeView.openInCurrTabClicked.connect(
            self.mainTabWidget.openItem
        )
        self.mainTreeView.openInNewWindowClicked.connect(
            self.mainTabWidget.openItemInNewWindow
        )

        self.packTreeModel.rowsRemoved.connect(self.onPackRowsRemoved)
        for signal in (
            self.packTreeModel.rowsInserted,
            self.packTreeModel.rowsRemoved,
            self.packTreeModel.modelReset,
        ):
            signal.connect(self.updateEmptyState)
        self.updateEmptyState()

    def onEditModeChanged(self, editing: bool):
        """Show the mode in the menu and in the status bar"""
        self.editModeAct.setChecked(editing)
        self.readModeAct.setChecked(not editing)
        self._modeStatusLabel.setText("Edit mode" if editing else "Read mode")
        self._modeStatusLabel.setToolTip(
            "Packages can be changed"
            if editing
            else "Packages can only be looked at. Switch to Edit mode in the "
            "View menu to change them"
        )

    def onUnsavedChanged(self, unsaved: int):
        """Show how many open packages have changes that are not saved"""
        if not self.packTreeModel.openedPacks():
            text = ""
        elif unsaved == 0:
            text = "All changes saved"
        elif unsaved == 1:
            text = "1 package with unsaved changes"
        else:
            text = f"{unsaved} packages with unsaved changes"
        self._unsavedStatusLabel.setText(text)

    def onCurrTabItemChanged(self, item: QModelIndex):
        if self.mainTreeView.autoScrollFromSrcAct.isChecked():
            if not item.siblingAtColumn(
                0
            ) == self.mainTreeView.currentIndex().siblingAtColumn(0):
                self.mainTreeView.setCurrentIndex(item)

    def onSelectedPackItemChanged(self, item: QModelIndex):
        if self.mainTreeView.autoScrollToSrcAct.isChecked():
            self.mainTabWidget.openItem(item)

    def onDoubleClicked(self, item: QModelIndex):
        if not self.mainTreeView.autoScrollToSrcAct.isChecked():
            self.mainTabWidget.openItemInNewTab(item)

    def onPackRowsRemoved(self, parent: QModelIndex, first: int, last: int):
        """Close the tabs of a package that was closed.

        Only the rows at the top of the tree are packages. Objects that were
        deleted inside a package close their own tabs (see TabWithTreeView).
        """
        if parent.isValid():
            return
        openedPackages = self.packTreeModel.openedPacks()
        for tabWidget in list(TabWidget.openedTabWidgets):
            # The tab widget of a window that is gone is no more.
            if not sip.isdeleted(tabWidget):
                tabWidget.removeTabsOfClosedPackages(openedPackages)

    def toggleThemeSlot(self):
        action = self.sender()
        if action:
            self.toggleTheme(action.data())

    def toggleTheme(self, theme: str) -> None:
        """Puts a theme on.

        A name that an old release saved gives the theme that replaced it, and
        a name that is unknown gives the default.
        """
        theme = theme_from_saved(theme)
        theme_manager().apply(theme)
        self.currTheme = theme
        for themeAct in self.themeActs:
            themeAct.setChecked(themeAct.data() == theme)
        # The recovery warning stays open across a switch of theme. It does not
        # exist yet when the theme of the last session is put on.
        recoveryLabel = getattr(self, "_recoveryStatusLabel", None)
        if recoveryLabel is not None:
            recoveryLabel.setStyleSheet(problem_style())

    def closeEvent(self, a0: QCloseEvent) -> None:
        # Edits made in a detached tab window set the flag on that window, not on this one,
        # so rebuild it from the packages before deciding whether to ask for saving
        self.mainTreeView.updateWindowModified()
        if not self.packTreeModel.openedFiles():
            a0.accept()
        elif self.isWindowModified():
            reply = QMessageBox.question(
                self,
                "Window Close",
                "Do you want to save files before closing the window?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.No,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.mainTreeView.saveAll()
                a0.accept()
            elif reply == QMessageBox.StandardButton.No:
                # Discarding: stop recovery writes and drop the recovery files so the
                # next launch does not offer to restore discarded changes.
                self._recoveryTimer.stop()
                for pkg in self.packTreeModel.openedPacks():
                    if pkg.changed:
                        pkg.delete_recovery(app_settings.recovery_dir())
                a0.accept()
            else:
                return a0.ignore()
        self.writeSettings()
        self.closed.emit()

    def restoreSettingsFromLastSession(self):
        self.applyLastSessionTheme()
        self.applyLastSessionMainWindowSize()
        self.applyLastSessionOrientation()
        self.applyLastSessionLayouts()
        self.applyLastSessionDocks()
        self.applyLastSessionTreeFontSizes()
        self.applyLastSessionTreeStates()

    def openLastSessionFiles(self):
        recovery_folder = app_settings.recovery_dir()
        # An unsaved session of an earlier release is in the old folder, inside
        # the source tree, and survives the update when it is moved here first.
        take_over_recovery_files(app_settings.OLD_RECOVERY_DIR, recovery_folder)
        recovery_map = find_recovery_files(recovery_folder)
        openedAasFiles = AppSettings.AAS_FILES_TO_OPEN_ON_START.value()
        # Recovery files restored this launch: kept through the sweep below until their
        # first save, so a native crash before that save still has the restored data.
        keptRecoveries = []
        for file in openedAasFiles:
            # resolve() to match find_recovery_files()'s resolved keys, so a
            # symlinked or '..'-containing path still lines up with its recovery.
            file_path = Path(file).resolve()
            if file_path in recovery_map:
                reply = QMessageBox.question(
                    self,
                    "Restore unsaved changes",
                    f"A recovery file was found for:\n{file_path.name}\n\n"
                    "The app may have crashed with unsaved changes.\n"
                    "Do you want to restore the last auto-saved version?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    rec = recovery_map[file_path]
                    # Kept whether or not the restore succeeds: a failed restore still
                    # keeps the recovery data as it may be salvageable by hand.
                    keptRecoveries.append(rec)
                    try:
                        pack = Package.restore_from_recovery(rec, file_path)
                    except Exception:
                        logging.exception(
                            "Failed to restore recovery file %s", rec
                        )
                        QMessageBox.warning(
                            self,
                            "Restore failed",
                            f"The recovery file for {file_path.name} could not be opened.\n\n"
                            f"It was kept at:\n{rec}\n\n"
                            "Opening the last saved version instead.",
                        )
                        self.openAASFile(file)
                    else:
                        self.mainTreeView.add_pack_to_tree(pack)
                        # Restored content is unsaved until the user writes it back
                        pack.changed = True
                        self.setWindowModified(True)
                        if pack.missingFiles:
                            # The original is gone, and a JSON recovery has no
                            # files, so say so before a save is refused.
                            show_missing_files(
                                pack.name, pack.missingFiles, self
                            )
                else:
                    delete_recovery_file(recovery_map[file_path])
                    self.openAASFile(file)
            else:
                self.openAASFile(file)

        # Drop everything left in the recovery dir except the entries just restored:
        # declined files, orphans (recovery for files no longer opened on start),
        # stale .meta.json and leftover .tmp writes. Keeps the dir from growing forever.
        cleanup_recovery_dir(recovery_folder, keptRecoveries)

    def _save_recovery_files(self):
        # Persist open-file list before crash exits — closeEvent won't run. Restore
        # matches recovery files against this list, so it must stay current for a native
        # crash to offer them. Sync only when it changed to keep it off the disk on
        # every tick.
        openFiles = self.packTreeModel.openedFiles()
        if openFiles != self._lastPersistedOpenFiles:
            AppSettings.AAS_FILES_TO_OPEN_ON_START.setValue(openFiles)
            SETTINGS.sync()
            self._lastPersistedOpenFiles = openFiles
        writeFailed = False
        for pkg in self.packTreeModel.openedPacks():
            # Per-package flag: the window modified flag is shared and gets reset
            # whenever any package is saved or closed
            if pkg.changed or pkg.recoveryWritten:
                try:
                    pkg.update_recovery(app_settings.recovery_dir())
                except Exception:
                    # Never let a failed recovery write abort the crash handler or the
                    # timer, but log it: a silent failure means the user believes they
                    # are protected while no recovery is being written (disk full, etc.).
                    writeFailed = True
                    logging.exception(
                        "Failed to write recovery file for %s", pkg.file
                    )
        self._reportRecoveryWriteStatus(writeFailed)

    def _reportRecoveryWriteStatus(self, writeFailed: bool):
        """Show a non-blocking status-bar warning while recovery writes are failing.

        Informant only: no dialog, no interruption. Shown once on the transition to
        failure and cleared once writes recover, so a persistently failing write does
        not spam a message on every tick.
        """
        if writeFailed and not self._recoveryWriteFailed:
            self._recoveryStatusLabel.setText(
                "⚠ Auto-recovery could not be saved — unsaved changes are not backed up. "
                "See log for details."
            )
            self._recoveryStatusLabel.show()
        elif not writeFailed and self._recoveryWriteFailed:
            self._recoveryStatusLabel.hide()
        self._recoveryWriteFailed = writeFailed

    def openAASFile(self, filePath: str):
        """Return the opened Package, or None if it could not be opened."""
        pack = None
        try:
            pack = self.mainTreeView.openPack(filePath)
        except OSError:
            pass
        return pack  # None if the file could not be opened

    def applyLastSessionTreeStates(self):
        packTreeViewHeader: HeaderView = self.mainTreeView.header()
        # A state that an earlier release saved would bring its widths back.
        packTreeViewHeaderState = restorable_state(
            AppSettings.PACKTREEVIEW_HEADER_STATE.value(),
            AppSettings.PACKTREEVIEW_HEADER_LAYOUT.value(),
            PACK_TREE_HEADER_LAYOUT_VERSION,
        )
        if packTreeViewHeaderState:
            packTreeViewHeader.restoreState(packTreeViewHeaderState)
        else:
            packTreeViewHeader.showSectionWithNames(
                DEFAULT_COLUMNS_IN_PACKS_TABLE_TO_SHOW, only=True
            )
            # The indentation of nested elements comes out of this column, so
            # a narrow one hides their names.
            packTreeViewHeader.resizeSection(0, PACK_TREE_OBJECT_COLUMN_WIDTH)
        with open(
            AppSettings.PACKTREEVIEW_HEADER_CUSTOM_COLUMN_LISTS_FILE
        ) as json_file:
            customLists = json.load(json_file)
            packTreeViewHeader.setCustomLists(customLists)
        packTreeViewHeader.initMenu()

    def applyLastSessionTabHeader(self):
        """Puts the columns of the last session on the first tab.

        This runs after the package of the first tab is open, because opening
        an item in a tab sets its header up again, and what was restored
        before would be gone.
        """
        # A state that an earlier release saved would bring its columns back.
        tabTreeViewHeaderState = restorable_state(
            AppSettings.TABTREEVIEW_HEADER_STATE.value(),
            AppSettings.TABTREEVIEW_HEADER_LAYOUT.value(),
            TAB_HEADER_LAYOUT_VERSION,
        )
        if tabTreeViewHeaderState:
            attrsTreeView = self.mainTabWidget.currentWidget().attrsTreeView
            attrsTreeView.header().restoreState(tabTreeViewHeaderState)
            # The view fits its columns to the room when it is shown, unless
            # the user sized them, and a restored state does not tell it so.
            attrsTreeView.userSizedColumns = bool(
                AppSettings.TABTREEVIEW_COLUMNS_SIZED.value()
            )

    def applyLastSessionTreeFontSizes(self):
        # The old default of 12 pt was saved at every exit, so it takes the new
        # default once, and any other size is the choice of the user.
        savedVersion = AppSettings.FONTSIZE_LAYOUT.value()
        fontSizeFilesView = migrated_font_size(
            AppSettings.FONTSIZE_FILES_VIEW.value(),
            savedVersion,
            DEFAULT_FONT.pointSize(),
        )
        fontSizeDetailedView = migrated_font_size(
            AppSettings.FONTSIZE_DETAILED_VIEW.value(),
            savedVersion,
            DEFAULT_FONT.pointSize(),
        )
        PacksTable.currFont.setPointSize(fontSizeFilesView)
        DetailedInfoTable.currFont.setPointSize(fontSizeDetailedView)

    def applyLastSessionLayouts(self):
        saved = restorable_state(
            (
                AppSettings.LEFT_ZONE_SIZE.value(),
                AppSettings.RIGHT_ZONE_SIZE.value(),
            ),
            AppSettings.ZONES_LAYOUT.value(),
            ZONES_LAYOUT_VERSION,
        )
        stacked = self.splitter.orientation() == QtCore.Qt.Orientation.Vertical
        if saved:
            left, right = saved
            # The sizes of a splitter run along it: heights, if the zones are
            # one above the other.
            sizes = (
                [left.height(), right.height()]
                if stacked
                else [left.width(), right.width()]
            )
        elif stacked:
            # No saved heights: the splitter keeps the halves it starts with.
            return
        else:
            # A first run, or sizes of an earlier release: the new default.
            # The command bar is over the whole window, so it asks for no room.
            sizes = list(zone_widths(self.width()))
        self.splitter.setSizes(sizes)

    def applyLastSessionDocks(self):
        """Puts the panels where the last session left them.

        A state of another version, or none, leaves the panels tabbed and
        hidden, as `initDocks` made them. The command bar is part of the state,
        so a bar that was hidden stays hidden.
        """
        state = AppSettings.DOCK_STATE.value()
        if state:
            self.restoreState(state, DOCKS_LAYOUT_VERSION)
            # Restoring may have made the strip again.
            self.nameDockTabBars()

    def applyLastSessionOrientation(self):
        """Puts the two zones side by side or one above the other, as saved.

        A first run, and a value that is no orientation, leave the layout that
        the window starts with.
        """
        if not AppSettings.ORIENTATION.isSaved():
            return
        saved = saved_orientation(AppSettings.ORIENTATION.value())
        if saved == "horizontal":
            self.setOrientation(QtCore.Qt.Orientation.Horizontal)
        elif saved == "vertical":
            self.setOrientation(QtCore.Qt.Orientation.Vertical)

    def applyLastSessionMainWindowSize(self):
        saved = AppSettings.SIZE.value() if AppSettings.SIZE.isSaved() else None
        screen = QGuiApplication.primaryScreen()
        room = (
            screen.availableGeometry() if screen else QRect(0, 0, *DEFAULT_SIZE)
        )
        width, height = window_size(
            (saved.width(), saved.height()) if saved else None,
            room.width(),
            room.height(),
        )
        self.resize(width, height)

    def applyLastSessionTheme(self):
        self.applyDensity()
        theme = AppSettings.THEME.value()
        self.toggleTheme(theme)

    def applyDensity(self) -> None:
        """Puts the density of the settings on the trees."""
        theme_manager().set_density(parse_density(AppSettings.DENSITY.value()))

    def openSettings(self) -> None:
        """Shows the settings, and applies the ones that act at once."""
        if SettingsDialog(self).exec():
            self.applyDensity()

    def writeSettings(self):
        AppSettings.THEME.setValue(self.currTheme)
        AppSettings.SIZE.setValue(self.size())
        AppSettings.LEFT_ZONE_SIZE.setValue(self.mainLayoutWidget.size())
        AppSettings.RIGHT_ZONE_SIZE.setValue(self.subLayoutWidget.size())
        AppSettings.AAS_FILES_TO_OPEN_ON_START.setValue(
            self.packTreeModel.openedFiles()
        )
        AppSettings.FONTSIZE_FILES_VIEW.setValue(
            PacksTable.currFont.pointSize()
        )
        AppSettings.FONTSIZE_DETAILED_VIEW.setValue(
            DetailedInfoTable.currFont.pointSize()
        )
        AppSettings.PACKTREEVIEW_HEADER_STATE.setValue(
            self.mainTreeView.header().saveState()
        )
        AppSettings.TABTREEVIEW_HEADER_STATE.setValue(
            self.mainTabWidget.currentWidget()
            .attrsTreeView.header()
            .saveState()
        )
        AppSettings.TABTREEVIEW_HEADER_LAYOUT.setValue(
            TAB_HEADER_LAYOUT_VERSION
        )
        AppSettings.TABTREEVIEW_COLUMNS_SIZED.setValue(
            self.mainTabWidget.currentWidget().attrsTreeView.userSizedColumns
        )
        AppSettings.PACKTREEVIEW_HEADER_LAYOUT.setValue(
            PACK_TREE_HEADER_LAYOUT_VERSION
        )
        AppSettings.ZONES_LAYOUT.setValue(ZONES_LAYOUT_VERSION)
        # The version goes in the state, and a state of another one is refused.
        AppSettings.DOCK_STATE.setValue(self.saveState(DOCKS_LAYOUT_VERSION))
        AppSettings.FONTSIZE_LAYOUT.setValue(FONT_SIZE_LAYOUT_VERSION)
        # AppSettings.DEFAULT_NEW_FILETYPE_FILTER.setValue(self.packTreeView.defaultNewFileType)

    def openHandoverDocumentationTool(self):
        from aas_workingbench.tools.handover_doc_llm.handover_documentation_tool import (
            HandoverDocumentationToolDialog,
        )

        dialog = HandoverDocumentationToolDialog(self)
        dialog.handoverExtracted.connect(self.mainTreeView.add_handover_to_file)
        dialog.exec()
