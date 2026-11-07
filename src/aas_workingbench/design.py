# -*- coding: utf-8 -*-

#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

# The layout of the main window, written by hand.
#
# This file was generated from `mainwindow_base.ui` once, a long time ago. Since
# then it was edited by hand and the `.ui` file was not (it still has a
# `QLineEdit` and a `QTabWidget`, and none of the views of the editor), so
# running pyuic again would not give this file back. The `.ui` file is kept
# only as the record of where this started (ADR 0028).
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QFrame

from aas_workingbench.models import PacksTable, StandardTable, PackTreeViewItem
from aas_workingbench.settings import EXTENDED_COLUMNS_IN_PACK_TABLE, APP_LOGO
from aas_workingbench.settings.app_settings import ATTRIBUTE_COLUMN, AppSettings, \
    DEFAULT_COLUMNS_IN_PACKS_TABLE, WINDOW_TITLE
from aas_workingbench.ui.empty_state import EmptyState
from aas_workingbench.widgets import ToolBar, TabWidget, SearchBar
from aas_workingbench.treeviews.treeview_pack import PackTreeView


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setWindowIcon(APP_LOGO)
        MainWindow.setAutoFillBackground(True)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.gridLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.gridLayout.setContentsMargins(0, 0, 0, 0)

        self.splitter = QtWidgets.QSplitter(self.centralwidget)
        self.mainLayoutWidget = QtWidgets.QWidget(self.splitter)
        self.mainVerticalLayout = self.setupMainLayout(parent=self.mainLayoutWidget)

        self.packTreeModel = self.setupMainTreeModel()
        self.mainTreeView = self.setupMainTreeView(parent=self.mainLayoutWidget, model=self.packTreeModel)

        # One bar over the whole window. Its buttons act on the view with the
        # focus (ui/command_bar.py), and the window fills it (editorApp.py).
        self.toolBar = ToolBar(MainWindow)
        self.toolBar.setObjectName("commandBar")
        self.toolBar.setWindowTitle("Command bar")
        self.toolBar.setMovable(False)
        self.toolBar.setFloatable(False)
        MainWindow.addToolBar(QtCore.Qt.ToolBarArea.TopToolBarArea, self.toolBar)

        self.searchBarPack = SearchBar(self.mainTreeView, filterColumns=[ATTRIBUTE_COLUMN],
                                       parent=self.mainLayoutWidget, closable=True)
        self.searchBarPack.closeBar()

        self.mainVerticalLayout.addWidget(self.searchBarPack)
        self.mainVerticalLayout.addWidget(self.mainTreeView)
        # Instead of the tree, until a package is open.
        self.emptyState = EmptyState(
            self.mainTreeView.openPackAct,
            self.mainTreeView.newPackActs,
            self.mainTreeView.recentFileActs,
            self.mainTreeView.openPack,
            parent=self.mainLayoutWidget,
        )
        self.mainVerticalLayout.addWidget(self.emptyState)

        # Sub part
        self.subLayoutWidget = QtWidgets.QWidget(self.splitter)
        self.subVerticalLayout = self.setupSubLayout(parent=self.subLayoutWidget)

        self.splitterTabWidgets = QtWidgets.QSplitter(self.subLayoutWidget)
        self.splitterTabWidgets.setOrientation(QtCore.Qt.Orientation.Horizontal)
        self.splitterTabWidgets.setFrameShape(QFrame.Shape.NoFrame)
        self.subVerticalLayout.addWidget(self.splitterTabWidgets)

        self.mainTabWidget = TabWidget(self.splitterTabWidgets, unclosable=True)
        # Instead of the tabs, until a package is open: no fields, nothing to read.
        self.emptyDetail = QtWidgets.QWidget(self.subLayoutWidget)
        self.emptyDetail.setObjectName("emptyDetail")
        self.emptyDetail.setBackgroundRole(QtGui.QPalette.ColorRole.Base)
        self.emptyDetail.setAutoFillBackground(True)
        self.subVerticalLayout.addWidget(self.emptyDetail)

        self.gridLayout.addWidget(self.splitter, 1, 0, 1, 1)
        MainWindow.setCentralWidget(self.centralwidget)

        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(f"{WINDOW_TITLE}[*]")

    def setOrientation(self, o: QtCore.Qt.Orientation):
        if o == QtCore.Qt.Orientation.Horizontal:
            self.splitter.setOrientation(QtCore.Qt.Orientation.Horizontal)
            AppSettings.ORIENTATION.setValue(QtCore.Qt.Orientation.Horizontal)
        elif o == QtCore.Qt.Orientation.Vertical:
            self.splitter.setOrientation(QtCore.Qt.Orientation.Vertical)
            AppSettings.ORIENTATION.setValue(QtCore.Qt.Orientation.Vertical)

    def setupMainTreeView(self, parent, model: StandardTable) -> PackTreeView:
        mainTreeView = PackTreeView(parent)
        mainTreeView.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        mainTreeView.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        mainTreeView.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        mainTreeView.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        mainTreeView.setModelWithProxy(model)
        for column in range(model.columnCount(), 2, -1):
            mainTreeView.hideColumn(column)
        return mainTreeView

    def setupMainLayout(self, parent) -> QtWidgets.QVBoxLayout:
        mainVerticalLayout = QtWidgets.QVBoxLayout(parent)
        mainVerticalLayout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetDefaultConstraint)
        mainVerticalLayout.setContentsMargins(0, 0, 0, 0)
        mainVerticalLayout.setSpacing(0)
        return mainVerticalLayout

    def setupSubLayout(self, parent) -> QtWidgets.QVBoxLayout:
        subVerticalLayout = QtWidgets.QVBoxLayout(parent)
        subVerticalLayout.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetDefaultConstraint)
        subVerticalLayout.setContentsMargins(0, 0, 0, 0)
        return subVerticalLayout

    def setupMainTreeModel(self) -> StandardTable:
        columns_in_packs_table = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
        columns_in_packs_table.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
        return PacksTable(columns_in_packs_table, PackTreeViewItem(None, None))
