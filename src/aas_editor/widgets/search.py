#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

from typing import List, Optional

from PyQt6.QtCore import (
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PyQt6.QtGui import QBrush, QAction, QShortcut
from PyQt6.QtWidgets import (
    QLabel,
    QWidget,
    QHBoxLayout,
    QToolButton,
    QTreeView,
)

from aas_editor.models.search_proxy_model import SearchProxyModel
from aas_editor.settings.colors import HIGHLIGHT_YELLOW
from aas_editor.settings.shortcuts import SC_SEARCH
from aas_editor.settings.icons import (
    NEXT_ICON,
    PREV_ICON,
    FILTER_ICON,
    REGEX_ICON,
    CASE_ICON,
    CLOSE_ICON,
)
from aas_editor.utils.util import absRow
from aas_editor.widgets.toolbar import ToolBar
from aas_editor.widgets.editWidgets import LineEdit


class SearchBar(ToolBar):
    def __init__(
        self,
        view: QTreeView,
        filterColumns: List[int],
        parent: QWidget,
        closable=False,
    ):
        super(SearchBar, self).__init__(parent)
        self.view = view
        self._selectionModel: Optional[QItemSelectionModel] = None
        self.foundItems: List[QPersistentModelIndex] = []
        self.setModel(view.model())
        self.filterColumns = filterColumns

        self.searchLine = LineEdit(self)
        self.searchLine.setClearButtonEnabled(True)
        self.searchLine.setPlaceholderText("Search")
        # How many rows match, and which one is current: "2 of 5".
        self.resultLabel = QLabel(self)
        self.resultLabel.setObjectName("searchResultLabel")
        self.resultLabel.setAccessibleName("Search results")
        self.filterBtn = QToolButton(
            self,
            icon=FILTER_ICON,
            toolTip="Filter",
            statusTip="Leave only matching items",
            checkable=True,
        )
        self.filterBtn.setAutoRaise(True)
        self.regexBtn = QToolButton(
            self,
            icon=REGEX_ICON,
            toolTip="Regex",
            statusTip="Use regular expression",
            checkable=True,
        )
        self.regexBtn.setAutoRaise(True)
        self.caseBtn = QToolButton(
            self,
            icon=CASE_ICON,
            toolTip="Match case",
            statusTip="Match upper/under case",
            checkable=True,
        )
        self.caseBtn.setAutoRaise(True)
        self.nextBtn = QToolButton(
            self,
            icon=NEXT_ICON,
            toolTip="Next",
            statusTip="Navigate to the next occurrence",
        )
        self.nextBtn.setAutoRaise(True)
        self.prevBtn = QToolButton(
            self,
            icon=PREV_ICON,
            toolTip="Previous",
            statusTip="Navigate to the previous occurrence",
        )
        self.prevBtn.setAutoRaise(True)
        self.closeBtn = QToolButton(
            self, icon=CLOSE_ICON, toolTip="Close", statusTip="Close search bar"
        )
        if not closable:
            self.closeBtn.hide()
        self.closeBtn.setAutoRaise(True)

        self.foundItems: List[QPersistentModelIndex] = []
        self.buildHandlers()
        self.initLayout()

    def buildHandlers(self):
        self.view.modelChanged.connect(self.setModel)
        self.closeBtn.clicked.connect(lambda: self.toggleView(False))
        self.nextBtn.clicked.connect(self.next)
        self.prevBtn.clicked.connect(self.previous)

        self.caseBtn.toggled.connect(self.search)
        self.filterBtn.toggled.connect(self.search)
        self.regexBtn.toggled.connect(self.search)
        self.searchLine.textChanged.connect(self.search)

    def closeBar(self):
        self.searchLine.setText("")
        self.hide()

    def setModel(self, model):
        if isinstance(model, SearchProxyModel):
            self.model = model
        else:
            self.model = SearchProxyModel()
        self.model.setRecursiveFilteringEnabled(True)
        self._followSelection()

    def _followSelection(self) -> None:
        """Keep the count current while the user moves in the view."""
        if self._selectionModel is not None:
            self._selectionModel.currentChanged.disconnect(
                self._updateResultLabel
            )
        self._selectionModel = self.view.selectionModel()
        if self._selectionModel is not None:
            self._selectionModel.currentChanged.connect(self._updateResultLabel)

    def matchedRows(self) -> List[QModelIndex]:
        """The rows that match, once each and in the order of the tree.

        A search in several columns finds a row once per column.
        """
        rows: List[QModelIndex] = []
        seen = set()
        for item in self.foundItems:
            index = QModelIndex(item).siblingAtColumn(0)
            key = QPersistentModelIndex(index)
            if index.isValid() and key not in seen:
                seen.add(key)
                rows.append(index)
        rows.sort(key=absRow)
        return rows

    def _updateResultLabel(self, *_) -> None:
        """Tell how many rows match and which one is current."""
        if not self.searchLine.text():
            self.resultLabel.setText("")
            return
        rows = self.matchedRows()
        if not rows:
            self.resultLabel.setText("No results")
            return
        current = self.view.currentIndex().siblingAtColumn(0)
        if current in rows:
            self.resultLabel.setText(
                f"{rows.index(current) + 1} of {len(rows)}"
            )
        else:
            self.resultLabel.setText(
                f"{len(rows)} result" + ("" if len(rows) == 1 else "s")
            )

    def search(self):
        self.view.itemDelegate().clearBgColors()
        self.foundItems = self.model.search(
            self.searchLine.text(),
            filterColumns=self.filterColumns,
            regExp=self.regexBtn.isChecked(),
            filter=self.filterBtn.isChecked(),
            matchCase=self.caseBtn.isChecked(),
        )
        if self.foundItems:
            self.view.setCurrentIndex(QModelIndex(self.foundItems[0]))
            for item in self.foundItems:
                self.view.itemDelegate().setBgColor(
                    QModelIndex(item), QBrush(HIGHLIGHT_YELLOW)
                )
        self.model.dataChanged.emit(QModelIndex(), QModelIndex())
        self._updateResultLabel()

    def next(self):
        items = [QModelIndex(i) for i in self.foundItems]
        items.sort(key=absRow)
        for item in items:
            if absRow(item) > absRow(self.view.currentIndex()):
                self.view.setCurrentIndex(item)
                return

    def previous(self):
        items = [QModelIndex(i) for i in self.foundItems]
        items.sort(key=absRow, reverse=True)
        for item in items:
            if absRow(item) < absRow(self.view.currentIndex()):
                self.view.setCurrentIndex(item)
                return

    def toggleViewAction(self):
        return QAction(
            "SearchBar",
            self,
            statusTip="Show/hide search bar",
            toggled=self.toggleView,
            checkable=True,
            checked=self.isVisible(),
        )

    def toggleView(self, toggled: bool):
        if toggled:
            self.show()
        else:
            self.hide()

    def showFocused(self):
        self.show()
        self.searchLine.setFocus()

    def bindFind(self, owner: QWidget) -> QShortcut:
        """Open this bar with the Find key while the focus is in a widget.

        The shortcut works in `owner` and its children only. A window with
        several views, each with its own bar, would otherwise find the key
        ambiguous and run none of them.

        :param owner: the widget whose focus the key belongs to
        :return: the shortcut, which `owner` keeps alive
        """
        return QShortcut(
            SC_SEARCH,
            owner,
            context=Qt.ShortcutContext.WidgetWithChildrenShortcut,
            activated=self.showFocused,
        )

    def initLayout(self):
        pathLayout = QHBoxLayout(self)
        pathLayout.setContentsMargins(0, 0, 0, 0)
        pathLayout.setSpacing(0)
        pathLayout.addWidget(self.searchLine)
        pathLayout.addWidget(self.resultLabel)
        pathLayout.addWidget(self.prevBtn)
        pathLayout.addWidget(self.nextBtn)
        pathLayout.addWidget(self.filterBtn)
        pathLayout.addWidget(self.caseBtn)
        pathLayout.addWidget(self.regexBtn)
        pathLayout.addWidget(self.closeBtn)
        searchBtns = QWidget(self)
        searchBtns.setLayout(pathLayout)
        self.addWidget(searchBtns)
