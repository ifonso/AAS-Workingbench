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
import logging
from typing import List

from PyQt6 import sip
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEngineProfile
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import (
    pyqtSignal,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    QSize,
    QMimeData,
    QUrl,
    QStandardPaths,
    Qt,
    QObject,
    QAbstractProxyModel,
    qDebug,
    qCritical,
    QAbstractItemModel,
    QTimer,
)
from PyQt6.QtGui import (
    QPixmap,
    QRegion,
    QDrag,
    QCursor,
    QMouseEvent,
    QDragEnterEvent,
    QDragLeaveEvent,
    QDropEvent,
    QCloseEvent,
    QAction,
)
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QHBoxLayout,
    QApplication,
    QFrame,
    QMainWindow,
    QTabBar,
    QMenu,
    QSplitter,
    QPushButton,
    QMessageBox,
    QToolButton,
    QFileDialog,
    QCompleter,
    QStyledItemDelegate,
    QSizePolicy,
)

from basyx.aas.model import Identifiable, Referable

from aas_editor.application.changes import Change, ChangeKind, observer_for
from aas_editor.settings.app_settings import *
from aas_editor.settings.icons import (
    FORWARD_ICON,
    BACK_ICON,
    COPY_ICON,
    SPLIT_VERT_ICON,
    SPLIT_HORIZ_ICON,
    ZOOM_IN_ICON,
    ZOOM_OUT_ICON,
)
from aas_editor.domain.design_tokens import CONTROL_HEIGHT
from aas_editor.ui.breadcrumb import Breadcrumb
from aas_editor.ui.theme.icons import tabler_icon
from aas_editor.settings.shortcuts import SC_BACK, SC_FORWARD
from aas_editor.utils.util_type import getTypeName
from aas_editor.widgets import SearchBar, ToolBar
from aas_editor.utils.util import getTreeItemPath
from aas_editor.models import StandardTable
from aas_editor.widgets import LineEdit
from aas_editor.ui.embedded_concept import EmbeddedConceptPanel
from aas_editor.ui.embedded_concept import open_in_tab
from aas_editor.ui.hints_bar import HintsBar

COMPLETION_ROLE = Qt.ItemDataRole.DisplayRole

# The share of a tab that the preview of a stored file gets, until the user
# drags the handle. The attributes get the rest, at least this many pixels.
PREVIEW_DEFAULT_SHARE = 1 / 3
# The attributes keep at least this width, and so does a tab that has a
# preview open: a narrower tab opens with the preview dragged shut.
PREVIEW_MIN_ATTRIBUTES_WIDTH = 360
PREVIEW_MIN_TAB_WIDTH = 720
# A tab is as wide as its title, between these widths in pixels (plan, section 3).
TAB_MIN_WIDTH = 120
TAB_MAX_WIDTH = 240
CASE_SENSITIVITY = Qt.CaseSensitivity.CaseInsensitive


class Signal(QObject):
    modelChanged = pyqtSignal(["QAbstractItemModel"])


class AddressLine(LineEdit):
    """Class for address line used in tabs"""

    signal = Signal()
    _model: StandardTable = None

    def __init__(self, parent: "Tab") -> None:
        super().__init__(parent)
        self.tab = parent

        self.setCompleter(AddressLineCompleter(self))
        self.completer().setCompletionRole(COMPLETION_ROLE)
        self.completer().setCaseSensitivity(CASE_SENSITIVITY)
        if AddressLine._model:
            self.completer().setModel(AddressLine._model)
            self.completer().activated[QModelIndex].connect(
                self.onReturnPressed
            )
            self.returnPressed.connect(self.onReturnPressed)
            self.clicked.connect(self.completer().complete)
        AddressLine.signal.modelChanged.connect(self.onModelChanged)
        self.setPlaceholderText("Address Line")

    @classmethod
    def setModel(cls, model: StandardTable):
        cls._model = model
        cls.signal.modelChanged.emit(model)
        logging.debug("New model for address completer was set")

    def onModelChanged(self):
        self.completer().setModel(AddressLine._model)
        self.returnPressed.connect(self.onReturnPressed)

    def open(self, index: QModelIndex):
        model: QAbstractProxyModel = index.model()
        if model and index.isValid():
            qDebug(f"Open address: {self.text()}")
            index = model.mapToSource(index)
            self.tab.openItem(index)
        else:
            qCritical(f"Index was not found for address {self.text()}")
            QMessageBox.critical(
                self, "Error", f"Item not found: {self.text()}"
            )

    def onReturnPressed(self):
        self.completer().setCompletionPrefix(self.text().rstrip("/"))
        if self.completer().currentCompletion() == self.text():
            index = self.completer().currentIndex()
            self.open(index)
        else:
            QMessageBox.critical(
                self, "Error", f"Item not found: {self.text()}"
            )


class AddressLineCompleter(QCompleter):
    mCompleterItemDelegate = QStyledItemDelegate()

    def pathFromIndex(self, index: QModelIndex) -> str:
        return getTreeItemPath(index, role=self.completionRole())

    def splitPath(self, path: str) -> List[str]:
        return path.split("/")

    def setModel(self, c: QAbstractItemModel) -> None:
        super(AddressLineCompleter, self).setModel(c)
        self.popup().setItemDelegate(self.mCompleterItemDelegate)


class TabBar(QTabBar):
    indexTabToDrag = -1

    def __init__(self, parent=None):
        super(TabBar, self).__init__(parent)
        self.menuIndexTab = None
        self.setAccessibleName("Tabs")

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setUsesScrollButtons(True)
        self.setTabsClosable(True)
        self.setMouseTracking(True)
        self.setMovable(True)
        self.setAcceptDrops(True)
        self.initActions()
        self.initMenu()
        self.customContextMenuRequested.connect(self.openMenu)

    def setTabsClosable(self, closable: bool) -> None:
        """Shows or removes the close crosses, with none left on screen.

        Qt removes the crosses that are no more wanted with `deleteLater()`.
        Such a cross stays where it was made until the event loop comes round,
        and since the tab around it can change its title and width by then, it
        can stand on the title of the tab, as in "showcase.aa×sx". It is
        hidden here, so that nothing draws it while it waits to be deleted.

        Args:
            closable: True to give every tab a close cross.
        """
        leaving = [] if closable else self._closeButtons()
        super().setTabsClosable(closable)
        for button in leaving:
            button.hide()

    def _closeButtons(self) -> list[QWidget]:
        """Gives the widgets that sit on the tabs as their close buttons."""
        buttons: list[QWidget] = []
        for index in range(self.count()):
            for side in (
                QTabBar.ButtonPosition.LeftSide,
                QTabBar.ButtonPosition.RightSide,
            ):
                button = self.tabButton(index, side)
                if button is not None:
                    buttons.append(button)
        return buttons

    def tabLayoutChange(self) -> None:
        """Names the close buttons, which Qt makes without a name."""
        super().tabLayoutChange()
        for index in range(self.count()):
            for side in (
                QTabBar.ButtonPosition.LeftSide,
                QTabBar.ButtonPosition.RightSide,
            ):
                button = self.tabButton(index, side)
                if button is not None and not button.accessibleName():
                    button.setAccessibleName("Close tab")
                    button.setToolTip("Close tab")

    def tabSizeHint(self, index: int) -> QSize:
        """A tab is as wide as its title, between 120 and 240 pixels.

        The width was fixed at 200 pixels, so a short title left the tab empty
        and a long one was cut early. A title that does not fit is elided.
        """
        size = super().tabSizeHint(index)
        size.setWidth(max(TAB_MIN_WIDTH, min(size.width(), TAB_MAX_WIDTH)))
        size.setHeight(CONTROL_HEIGHT)
        return size

    def minimumTabSizeHint(self, index: int) -> QSize:
        """A tab that the bar has to squeeze keeps the least width."""
        return QSize(TAB_MIN_WIDTH, CONTROL_HEIGHT)

    def mousePressEvent(self, a0: QMouseEvent) -> None:
        if a0.button() == Qt.MouseButton.RightButton:
            self.menuIndexTab = self.tabAt(a0.pos())
        super(TabBar, self).mousePressEvent(a0)

    def mouseMoveEvent(self, a0: QMouseEvent) -> None:
        if (a0.buttons() == Qt.MouseButton.LeftButton) and abs(
            a0.pos().y()
        ) > 30:
            globalPos = self.mapToGlobal(a0.pos())
            posInTab = self.mapFromGlobal(globalPos)

            TabBar.indexTabToDrag = self.currentIndex()

            tabRect = self.tabRect(self.indexTabToDrag)
            pixmap = QPixmap(tabRect.size())
            self.render(pixmap, QPoint(), QRegion(tabRect))

            mimeData = QMimeData()
            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setPixmap(pixmap)
            cursor = QCursor(Qt.CursorShape.OpenHandCursor)
            drag.setHotSpot(cursor.pos())
            drag.setHotSpot(a0.pos() - posInTab)
            drag.setDragCursor(cursor.pixmap(), Qt.DropAction.MoveAction)
            dropAction = drag.exec(Qt.DropAction.MoveAction)
            # If the drag completed outside the tab bar, detach the tab and move
            # the content to the current cursor position
            if dropAction == Qt.DropAction.IgnoreAction:
                a0.accept()
                self.detachTab(self.indexTabToDrag, self.cursor().pos())
        else:
            super(TabBar, self).mouseMoveEvent(a0)

    def dragEnterEvent(self, a0: QDragEnterEvent) -> None:
        a0.accept()

    def dragLeaveEvent(self, a0: QDragLeaveEvent) -> None:
        a0.accept()

    def dropEvent(self, a0: QDropEvent) -> None:
        if (
            a0.source() == self
            or self.indexTabToDrag < 0
            or not isinstance(a0.source(), TabBar)
        ):
            a0.accept()
            return

        a0.setDropAction(Qt.DropAction.MoveAction)
        a0.accept()

        insertAfter = self.tabAt(a0.position().toPoint())
        try:
            tab = a0.source().parentWidget().widget(self.indexTabToDrag)
            packItem = QModelIndex(tab.packItem)
            index = self.parentWidget().openItemInNewTab(packItem)
            a0.source().tabCloseRequested.emit(self.indexTabToDrag)
        except AttributeError as e:
            print("Error occured while drop Event:", e)
        else:
            if insertAfter and insertAfter >= 0:
                self.moveTab(index, insertAfter + 1)
        TabBar.indexTabToDrag = -1

    def detachTab(self, index, point):
        # Get the tab content
        tab = self.parentWidget().widget(index)
        packItem = QModelIndex(tab.packItem)

        # Create a new detached tab window
        detachedTab = TabWidget.openItemInNewWindow(packItem)
        detachedTab.move(point)

        self.tabCloseRequested.emit(index)

    # noinspection PyArgumentList
    def initActions(self):
        self.closeAct = QAction(
            "Close",
            self,
            statusTip="Close selected tab",
            triggered=lambda: self.tabCloseRequested.emit(self.menuIndexTab),
        )

        self.closeOthersAct = QAction(
            "Close others",
            self,
            statusTip="Close all tabs except selected",
            triggered=lambda: self.closeOthers(),
        )

        self.closeAllRightAct = QAction(
            "Close all to the right",
            self,
            statusTip="Close all tabs to the right",
            triggered=lambda: self.closeAllRight(),
        )

        self.closeAllLeftAct = QAction(
            "Close all to the left",
            self,
            statusTip="Close all tabs to the left",
            triggered=lambda: self.closeAllLeft(),
        )

        self.splitVerticallyAct = QAction(
            SPLIT_VERT_ICON,
            "Split vertically",
            self,
            statusTip="Split editor area into 2 tab groups",
            triggered=lambda: self.splitVertically(),
        )

        self.splitHorizontallyAct = QAction(
            SPLIT_HORIZ_ICON,
            "Split horizontally",
            self,
            statusTip="Split editor area into 2 tab groups",
            triggered=lambda: self.splitHorizontally(),
        )

    def closeOthers(self):
        for i in range(self.count() - 1, -1, -1):
            if i != self.menuIndexTab:
                self.tabCloseRequested.emit(i)

    def closeAllRight(self):
        for i in range(self.count() - 1, self.menuIndexTab - 1, -1):
            if i != self.menuIndexTab:
                self.tabCloseRequested.emit(i)

    def closeAllLeft(self):
        for i in range(self.menuIndexTab - 1, -1, -1):
            if i != self.menuIndexTab:
                self.tabCloseRequested.emit(i)

    def splitHorizontally(self):
        self.addTabWidget(orientation=Qt.Orientation.Vertical)

    def splitVertically(self):
        self.addTabWidget(orientation=Qt.Orientation.Horizontal)

    def addTabWidget(self, orientation=Qt.Orientation.Horizontal):
        tabWidget: TabWidget = self.parentWidget()
        if not isinstance(tabWidget, QTabWidget):
            raise TypeError(
                "Parent widget of Tabbar must be of type QTabWidget",
                type(tabWidget),
            )

        splitter: QSplitter = tabWidget.parentWidget()
        if not isinstance(splitter, QSplitter):
            raise TypeError(
                "Parent widget of TabWidget must be of type QSplitter",
                type(splitter),
            )
        splitter.setOrientation(orientation)

        tab: TabWithTreeView = tabWidget.widget(self.menuIndexTab)
        packItem = QModelIndex(tab.packItem)
        newTabWidget = type(tabWidget)()
        newTabWidget.openItem(packItem)

        if orientation == Qt.Orientation.Horizontal:
            size = int(tabWidget.width() / 2)
        else:
            size = int(tabWidget.height() / 2)

        newTabWidgetIndex = splitter.indexOf(tabWidget) + 1
        sizes = splitter.sizes()
        sizes[splitter.indexOf(tabWidget)] = size
        sizes.insert(newTabWidgetIndex, size)

        splitter.insertWidget(newTabWidgetIndex, newTabWidget)
        splitter.setSizes(sizes)

    def initMenu(self) -> None:
        self.menu = QMenu(self)
        self.menu.addAction(self.closeAct)
        self.menu.addAction(self.closeOthersAct)
        self.menu.addAction(self.closeAllRightAct)
        self.menu.addAction(self.closeAllLeftAct)
        self.menu.addSeparator()
        self.menu.addAction(self.splitVerticallyAct)
        self.menu.addAction(self.splitHorizontallyAct)

    def openMenu(self, point):
        self.menu.exec(self.mapToGlobal(point))


def isAttachedTo(obj, package) -> bool:
    """Tell whether an object that a tab shows is still part of the package.

    An element is part of it when the chain of its parents ends at an
    Identifiable that the package holds. Things that are not AAS objects of a
    package, like the stores, count as part of it.
    """
    top = obj
    while getattr(top, "parent", None) is not None:
        top = top.parent
    if isinstance(top, Identifiable):
        try:
            return package.objStore.get_item(top.id) is top
        except KeyError:
            return False
    return not isinstance(top, Referable)


class TabWithTreeView(QWidget):
    currItemChanged = pyqtSignal(["QModelIndex"])

    def __init__(
        self,
        packItem=QModelIndex(),
        parent: "TabWidget" = None,
        treeViewCls=None,
        treeViewClsKwargs=None,
    ):
        super(TabWithTreeView, self).__init__(parent)
        self.tabWidget = parent
        self.icon = QIcon()
        # The package of the shown object, and the follow-up of its changes
        self.package = None
        self._changeSubscription = None
        self._staleCheckPending = False
        self._previewShare = PREVIEW_DEFAULT_SHARE
        self._previewPlaced = False
        # A preview that is dragged shut has a button to open it, because a
        # user who sees no preview has no sign that there is one.
        self._previewCollapsed = False
        self.showPreviewBtn = QPushButton("Show preview of the file", self)
        self.showPreviewBtn.setToolTip(
            "Open the preview of the file beside the attributes"
        )
        self.showPreviewBtn.clicked.connect(self.openPreview)
        self.showPreviewBtn.hide()
        # Advice about the shown object, while hints mode is on (F-EDT-06)
        self.hintsBar = HintsBar(self)
        # The concept description of the semantic id, below the attributes
        self.embeddedConcept = EmbeddedConceptPanel(
            self, lambda concept: open_in_tab(self, concept)
        )
        self.initActions()

        # Back and forward are on the command bar of the window. A tab in a
        # window of its own has no bar, so it keeps its own pair of buttons.
        self.pathToolBar = ToolBar(self)
        self.pathToolBar.setFixedHeight(CONTROL_HEIGHT)
        self.pathToolBar.addAction(self.backAct)
        self.pathToolBar.addAction(self.forwardAct)

        # The path is read as segments. The line is what a click on the blank
        # area edits, with the completer of the addresses.
        self.pathLine: AddressLine = AddressLine(self)
        self.breadcrumb = Breadcrumb(self.pathLine, self)
        self.breadcrumb.segment_activated.connect(self.openSegment)
        self.breadcrumb.editing_stopped.connect(self.showRealPath)
        self.copyPathBtn = QToolButton(self)
        self.copyPathBtn.setIcon(COPY_ICON)
        self.copyPathBtn.setAutoRaise(True)
        self.copyPathBtn.setToolTip("Copy the path")
        self.copyPathBtn.setAccessibleName("Copy the path")
        self.copyPathBtn.clicked.connect(self.copyPath)

        globalSettings = QWebEngineProfile.defaultProfile().settings()
        globalSettings.setAttribute(
            QWebEngineSettings.WebAttribute.PluginsEnabled, True
        )
        self.mediaWidget = QWebEngineView()
        self.saveMediaAsBtn = QPushButton(
            f"Save media as..",
            self,
            toolTip="Save media file as..",
            clicked=lambda: self.saveMediaAsWithDialog(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DocumentsLocation
                )
            ),
        )
        self.saveMediaBtn = QPushButton(
            f"Save media on desktop",
            self,
            toolTip="Save media file on desktop",
            clicked=lambda: self.saveMediaAsWithDialog(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.DesktopLocation
                )
            ),
        )
        self.mediaViewWidget = QWidget()
        mediaViewWidgetLayout = QVBoxLayout(self.mediaViewWidget)
        mediaViewWidgetLayout.setContentsMargins(0, 0, 0, 0)
        mediaViewWidgetLayout.addWidget(self.mediaWidget)
        mediaViewWidgetLayout.addWidget(self.saveMediaBtn)
        mediaViewWidgetLayout.addWidget(self.saveMediaAsBtn)
        self.mediaViewWidget.hide()

        if treeViewCls is None:
            from aas_editor.treeviews.treeview_detailed import AttrsTreeView

            treeViewCls = AttrsTreeView
        self.attrsTreeView = (
            treeViewCls(self)
            if not treeViewClsKwargs
            else treeViewCls(self, **treeViewClsKwargs)
        )
        self.attrsTreeView.setFrameShape(QFrame.Shape.NoFrame)

        self.searchBar = SearchBar(
            self.attrsTreeView,
            parent=self,
            filterColumns=[ATTRIBUTE_COLUMN, VALUE_COLUMN],
            closable=True,
        )
        self.searchBar.hide()
        # Limited to this tab, so that the tree's bar and the bar of another
        # visible tab do not make the key ambiguous.
        self.openSearchBarSC = self.searchBar.bindFind(self)

        # The splitter that the preview of a stored file opens in must exist
        # before the first item is opened.
        self._initLayout()

        self.packItem = QPersistentModelIndex(QModelIndex())
        self.prevItems = []
        self.nextItems = []
        if packItem.isValid():
            self.openItem(packItem)
        else:
            self.openEmptyItem()

    def pathSegments(self) -> list[tuple[str, QPersistentModelIndex]]:
        """The names from the package down to the object, with their rows."""
        segments = []
        index = QModelIndex(self.packItem)
        while index.isValid():
            text = index.data(Qt.ItemDataRole.DisplayRole)
            segments.append((str(text), QPersistentModelIndex(index)))
            index = index.parent()
        segments.reverse()
        return segments

    def showRealPath(self) -> None:
        """Put the path of the object back in the field, after typing in it.

        A path that was refused, or typing that Escape left, would otherwise
        be what the next Ctrl+L shows, and the breadcrumb would say another
        path than the field.
        """
        self.pathLine.setText(getTreeItemPath(self.packItem))

    def openSegment(self, position: int) -> None:
        """Open the object of a segment of the path that the user clicked."""
        segments = self.pathSegments()
        if 0 <= position < len(segments) - 1:
            self.openItem(QModelIndex(segments[position][1]))

    def copyPath(self) -> None:
        """Put the path of the object on the clipboard."""
        QApplication.clipboard().setText(getTreeItemPath(self.packItem))

    # noinspection PyArgumentList
    def initActions(self):
        self.backAct = QAction(
            BACK_ICON,
            "Back",
            self,
            statusTip=f"Go back one item",
            toolTip=f"Go back one item",
            shortcut=SC_BACK,
            triggered=lambda: self.openPrevItem(),
            enabled=False,
        )

        self.forwardAct = QAction(
            FORWARD_ICON,
            "Forward",
            self,
            statusTip=f"Go forward one item",
            toolTip=f"Go forward one item",
            shortcut=SC_FORWARD,
            triggered=lambda: self.openNextItem(),
            enabled=False,
        )

    def windowTitle(self) -> str:
        # What the tree reads, so a group of objects is titled as it is named.
        return self.packItem.data(Qt.ItemDataRole.DisplayRole)

    def _typeText(self) -> str:
        """Return the type of the item as the tree reads it, if it has one."""
        text = (
            QModelIndex(self.packItem)
            .siblingAtColumn(TYPE_COLUMN)
            .data(Qt.ItemDataRole.DisplayRole)
        )
        if isinstance(text, str):
            return text
        return getTypeName(type(self.packItemObj))

    def windowIcon(self) -> QIcon:
        return self.packItem.data(Qt.ItemDataRole.DecorationRole)

    def openItem(self, packItem: QModelIndex):
        if not packItem == QModelIndex(self.packItem):
            self.nextItems.clear()
            if self.packItem.isValid():
                self.prevItems.append(self.packItem)
            self._openItem(packItem)

    def openPrevItem(self):
        if self.prevItems:
            prevItem = self.prevItems.pop()
            self.nextItems.append(self.packItem)
            self._openItem(QModelIndex(prevItem))

    def openNextItem(self):
        if self.nextItems:
            nextItem = self.nextItems.pop()
            self.prevItems.append(self.packItem)
            self._openItem(QModelIndex(nextItem))

    def openEmptyItem(self):
        self._openItem(QModelIndex())

    def _openItem(self, packItem: QModelIndex):
        try:
            currTab: TabWithTreeView = self.tabWidget.currentWidget()
            state = currTab.attrsTreeView.header().saveState()
        except AttributeError:
            # if there is no curr widget, there is no current header state, it
            state = None

        self.packItem = QPersistentModelIndex(packItem.siblingAtColumn(0))

        self.packItemObj = self.packItem.data(OBJECT_ROLE)
        self._followPackage(self.packItem.data(PACKAGE_ROLE))
        self.hintsBar.set_target(self.package, self.packItemObj)
        self.embeddedConcept.set_target(self.package, self.packItemObj)
        self.updateMediaWidget()
        self.pathLine.setText(getTreeItemPath(self.packItem))
        self.breadcrumb.set_path(
            [name for name, _ in self.pathSegments()], self._typeText()
        )
        self.fixTabOrder()

        icon = self.packItem.data(Qt.ItemDataRole.DecorationRole)
        if icon:
            self.setWindowIcon(icon)
        self.setWindowTitle(self.packItem.data(Qt.ItemDataRole.DisplayRole))
        self.attrsTreeView.newPackItem(self.packItem)
        self.currItemChanged.emit(QModelIndex(self.packItem))

        self.forwardAct.setEnabled(
            True
        ) if self.nextItems else self.forwardAct.setDisabled(True)
        self.backAct.setEnabled(
            True
        ) if self.prevItems else self.backAct.setDisabled(True)
        if state:
            self.attrsTreeView.header().restoreState(state)

    def fixTabOrder(self) -> None:
        """Makes Tab go the way the eye does: tabs, path, copy, search, rows.

        The segments of the path are made for each object, so Qt would put them
        after the panels at the bottom of the window.
        """
        chain: list[QWidget] = [
            *self.breadcrumb.focus_widgets(),
            self.copyPathBtn,
            self.searchBtn,
            self.attrsTreeView,
        ]
        bar = self.tabWidget.tabBar() if self.tabWidget is not None else None
        if bar is not None:
            chain.insert(0, bar)
        if len({widget.window() for widget in chain}) != 1:
            # Not yet in a window, such as a tab that is being made.
            return
        for first, second in zip(chain, chain[1:]):
            QWidget.setTabOrder(first, second)

    def _followPackage(self, package):
        """Learn about the removal of the object that the tab shows"""
        if package is self.package:
            return
        if self._changeSubscription is not None:
            self._changeSubscription.cancel()
            self._changeSubscription = None
        self.package = package
        if package is not None:
            self._changeSubscription = observer_for(package).subscribe(
                self.onModelChange
            )

    def onModelChange(self, change: Change):
        if change.kind in (ChangeKind.REMOVED, ChangeKind.CHANGED):
            try:
                self._scheduleStaleCheck()
            except RuntimeError:
                # The tab was deleted, and the subscription outlived it.
                pass

    def _scheduleStaleCheck(self):
        # The change is still being made, and other models still have to
        # follow it. The tab closes afterwards.
        if not self._staleCheckPending:
            self._staleCheckPending = True
            QTimer.singleShot(0, self.closeIfStale)

    def isStale(self) -> bool:
        """Whether the object of the tab was deleted from its package"""
        if self.package is None or self.packItemObj is None:
            return False
        return not isAttachedTo(self.packItemObj, self.package)

    def closeIfStale(self):
        self._staleCheckPending = False
        if self.isStale() and self.tabWidget is not None:
            self.tabWidget.closeStaleTab(self)

    def updateMediaWidget(self):
        if self.packItem.data(IS_MEDIA_ROLE):
            self.mediaWidget.setContent(b"loading...")
            self._showPreviewPane()

            try:
                mediaContent: "MediaContent" = self.packItem.data(
                    MEDIA_CONTENT_ROLE
                )
                if self.packItem.data(IS_URL_MEDIA_ROLE):
                    self.mediaWidget.load(QUrl(mediaContent.value))
                else:
                    self.mediaWidget.setContent(
                        mediaContent.value, mediaContent.content_type
                    )
            except Exception as e:
                logging.exception(e)
                self.mediaWidget.setContent(
                    b"Error occurred while loading media"
                )
            self.mediaWidget.setZoomFactor(1.0)
        else:
            self.mediaViewWidget.hide()
            self._previewCollapsed = False
            self._updatePreviewButton()

    def _showPreviewPane(self):
        """Open the preview of a stored file beside the attributes.

        The attributes are what a user edits, and the table is squeezed when
        the preview takes half of the tab. The preview gets a third, or what
        the user last dragged the handle to. A tab that is too narrow for both
        starts with the preview dragged shut. It is a splitter either way.
        """
        if self.mediaViewWidget.isHidden():
            self.mediaViewWidget.show()
            self._previewPlaced = False
            self._placePreview()

    def _placePreview(self):
        # The width of a tab that was never shown says nothing.
        if not self.isVisible():
            return
        self._previewPlaced = True
        width = self.splitter.width()
        # Only the proportion matters, the splitter scales it to its width.
        total = 3000
        share = self._previewShare if width >= PREVIEW_MIN_TAB_WIDTH else 0
        preview = round(total * share)
        self.splitter.setSizes([total - preview, preview])
        self._previewCollapsed = preview == 0
        self._updatePreviewButton()

    def openPreview(self):
        """Open a preview that was dragged shut, or never fitted in the tab.

        The attributes keep their minimum width, so in a narrow tab the
        preview gets what is left, which may be little.
        """
        total = 3000
        preview = round(total * self._previewShare)
        self.splitter.setSizes([total - preview, preview])
        self._previewCollapsed = self.splitter.sizes()[1] == 0
        self._updatePreviewButton()

    def _updatePreviewButton(self):
        self.showPreviewBtn.setVisible(
            self._previewCollapsed and not self.mediaViewWidget.isHidden()
        )

    def showEvent(self, a0):
        super().showEvent(a0)
        # The command bar of the main window has Back and Forward, which follow
        # the tab with the focus. A tab in a window of its own has no bar.
        self.pathToolBar.setVisible(not isinstance(self.window(), QMainWindow))
        if self.mediaViewWidget.isVisibleTo(self) and not self._previewPlaced:
            # The layout has its width after this event.
            QTimer.singleShot(0, self._placePreview)

    def _onPreviewResized(self, *_):
        sizes = self.splitter.sizes()
        # A preview that was dragged shut opens again at the share before.
        if self.mediaViewWidget.isVisible() and sizes[1] > 0:
            self._previewShare = sizes[1] / sum(sizes)
        self._previewCollapsed = sizes[1] == 0
        self._updatePreviewButton()

    def saveMediaAsWithDialog(self, directory="") -> bool:
        mediaContent = self.packItem.data(MEDIA_CONTENT_ROLE)
        file = self.packItem.data(NAME_ROLE)
        saved = False
        while not saved:
            try:
                file, _ = QFileDialog.getSaveFileName(
                    self, "Save media File", directory + "/" + file.strip("/")
                )
            except AttributeError as e:
                QMessageBox.critical(self, "Error", f"{e}")
            else:
                if file:
                    saved = self.saveMedia(mediaContent, file)
                else:
                    # cancel pressed
                    return

    def saveMedia(self, media=None, file: str = None) -> bool:
        try:
            with open(file, "wb") as f:
                f.write(media.value)
            return True
        except (TypeError, ValueError) as e:
            QMessageBox.critical(
                self, "Error", f"Media couldn't be saved: {file}: {e}"
            )
        except AttributeError as e:
            QMessageBox.critical(self, "Error", f"No chosen media to save: {e}")
        return False

    def _initLayout(self):
        toolBarWidget = QWidget()
        toolBarLayout = QHBoxLayout(toolBarWidget)
        toolBarLayout.setContentsMargins(0, 0, 0, 0)
        toolBarLayout.setSpacing(0)
        # The path takes what is left, and does not claim its own width.
        toolBarLayout.addWidget(self.pathToolBar)
        toolBarLayout.addWidget(self.breadcrumb, 1)
        toolBarLayout.addWidget(self.copyPathBtn)
        # The search of this tab, which Ctrl+F opens as well.
        self.searchBtn = QToolButton(self)
        self.searchBtn.setIcon(tabler_icon("search"))
        self.searchBtn.setAutoRaise(True)
        self.searchBtn.setToolTip("Search in this tab (Ctrl+F)")
        self.searchBtn.setAccessibleName("Search in this tab")
        self.searchBtn.clicked.connect(self.searchBar.showFocused)
        toolBarLayout.addWidget(self.searchBtn)
        toolBarWidget.setFixedHeight(CONTROL_HEIGHT)
        self.pathBarWidget = toolBarWidget

        treeViewWidget = QWidget()
        treeViewLayout = QVBoxLayout(treeViewWidget)
        treeViewLayout.setContentsMargins(0, 0, 0, 0)
        treeViewLayout.addWidget(self.hintsBar)
        treeViewLayout.addWidget(self.attrsTreeView)
        treeViewLayout.addWidget(self.embeddedConcept)

        # The attributes keep a width that they can be read in, and the
        # preview can be dragged shut.
        treeViewWidget.setMinimumWidth(PREVIEW_MIN_ATTRIBUTES_WIDTH)
        self.splitter = QSplitter()
        self.splitter.setOrientation(Qt.Orientation.Horizontal)
        self.splitter.setContentsMargins(0, 0, 0, 0)
        self.splitter.addWidget(treeViewWidget)
        self.splitter.addWidget(self.mediaViewWidget)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, True)
        self.splitter.handle(1).setToolTip(
            "Drag to show or hide the preview of the file"
        )
        self.splitter.splitterMoved.connect(self._onPreviewResized)

        layout = QVBoxLayout(self)
        layout.setObjectName("tabLayout")
        layout.addWidget(toolBarWidget)
        layout.addWidget(self.searchBar)
        layout.addWidget(self.showPreviewBtn, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.splitter)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 2, 0, 2)


class TabWidget(QTabWidget):
    # signal for changing current item in packet treeview
    currItemChanged = pyqtSignal(["QModelIndex"])
    openedTabWidgets = []

    def __init__(
        self,
        parent: QWidget = None,
        unclosable=False,
        tabBarCls=TabBar,
        tabBarClsKwargs=None,
        tabCls=TabWithTreeView,
        tabClsKwargs=None,
    ):
        super(TabWidget, self).__init__(parent)
        self.unclosable = unclosable

        self.initActions()
        self.buildHandlers()

        self.setTabBar(
            tabBarCls(self)
            if not tabBarClsKwargs
            else tabBarCls(self, **tabBarClsKwargs)
        )
        self.setAcceptDrops(True)
        self.setCurrentIndex(-1)
        self.resize(QSize(800, 500))
        # The tab widget of a main window that was deleted gets no close event,
        # so it would stay here, and a package closed later would ask it.
        TabWidget.openedTabWidgets[:] = [
            tabWidget
            for tabWidget in TabWidget.openedTabWidgets
            if not sip.isdeleted(tabWidget)
        ]
        TabWidget.openedTabWidgets.append(self)
        self.tabCls = tabCls
        self.tabClsKwargs = tabClsKwargs

    def closeEvent(self, a0: QCloseEvent) -> None:
        TabWidget.openedTabWidgets.remove(self)
        super(TabWidget, self).closeEvent(a0)

    # noinspection PyArgumentList
    def initActions(self):
        self.zoomInAct = QAction(
            ZOOM_IN_ICON,
            "Zoom in",
            self,
            statusTip="Zoom in detailed info",
            triggered=lambda: self.zoomIn(),
        )

        self.zoomOutAct = QAction(
            ZOOM_OUT_ICON,
            "Zoom out",
            self,
            statusTip="Zoom out detailed info",
            triggered=lambda: self.zoomOut(),
        )

    def zoomIn(self):
        if isinstance(self.currentWidget(), TabWithTreeView):
            self.currentWidget().attrsTreeView.zoomIn()

    def zoomOut(self):
        if isinstance(self.currentWidget(), TabWithTreeView):
            self.currentWidget().attrsTreeView.zoomOut()

    def buildHandlers(self):
        self.tabCloseRequested.connect(self.removeTab)
        self.currentChanged.connect(self.onCurrTabChanged)

    def tabRemoved(self, index):
        super(TabWidget, self).tabRemoved(index)
        self._syncCloseButtons()

    def _syncCloseButtons(self):
        """The last tab of a window that needs one cannot be closed, so it has no button."""
        self.tabBar().setTabsClosable(
            not (self.unclosable and self.count() <= 1)
        )

    def tabInserted(self, index):
        super(TabWidget, self).tabInserted(index)
        self._syncCloseButtons()
        tab: TabWithTreeView = self.widget(index)
        tab.windowTitleChanged.connect(
            lambda text: self.setTabText(self.indexOf(tab), text)
        )
        tab.windowIconChanged.connect(
            lambda icon: self.setTabIcon(self.indexOf(tab), icon)
        )
        tab.currItemChanged.connect(
            lambda packItem: self.onCurrTabItemChanged(tab, packItem)
        )
        tab.attrsTreeView.openInCurrTabClicked.connect(self.openItem)
        tab.attrsTreeView.openInNewTabClicked.connect(self.openItemInNewTab)
        tab.attrsTreeView.openInBgTabClicked.connect(self.openItemInBgTab)
        tab.attrsTreeView.openInNewWindowClicked.connect(
            TabWidget.openItemInNewWindow
        )

    def onCurrTabItemChanged(
        self, tab: "TabWithTreeView", packItem: QModelIndex
    ):
        if tab == self.currentWidget():
            self.currItemChanged.emit(packItem)

    def onCurrTabChanged(self, index: int):
        if index >= 0:
            # The tab bar leads to the tab that is shown.
            self.widget(index).fixTabOrder()
            packItem = QModelIndex(self.widget(index).packItem)
            self.currItemChanged.emit(packItem)
        else:
            self.currItemChanged.emit(QModelIndex())

    def openItem(self, packItem: QModelIndex = QModelIndex()) -> int:
        if not self.count():
            return self.openItemInNewTab(packItem)
        else:
            self.currentWidget().openItem(packItem)
            return self.currentIndex()

    @classmethod
    def openItemInNewWindow(cls, packItem: QModelIndex) -> int:
        tabWindow = cls()
        tabWindow.openItemInNewTab(packItem)
        tabWindow.setWindowModality(Qt.WindowModality.NonModal)
        tabWindow.setWindowTitle("Tabs")
        tabWindow.show()
        return tabWindow

    def openItemInNewTab(
        self, packItem: QModelIndex, afterCurrent: bool = True
    ) -> int:
        kwargs = self.tabClsKwargs if self.tabClsKwargs else {}
        tab = self.tabCls(packItem, parent=self, **kwargs)
        tabIndex = self.newTab(tab, afterCurrent)
        self.setCurrentWidget(tab)
        self.currItemChanged.emit(packItem)
        return tabIndex

    def openItemInBgTab(self, packItem: QModelIndex) -> int:
        kwargs = self.tabClsKwargs if self.tabClsKwargs else {}
        tab = self.tabCls(packItem, parent=self, **kwargs)
        tabIndex = self.newTab(tab, afterCurrent=True)
        return tabIndex

    def newTab(self, widget: QWidget, afterCurrent: bool = False) -> int:
        icon = widget.windowIcon() if widget.windowIcon() else QIcon()
        label = widget.windowTitle() if widget.windowTitle() else ""
        if afterCurrent:
            tabIndex = self.insertTab(
                self.currentIndex() + 1, widget, icon, label
            )
        else:
            tabIndex = self.addTab(widget, icon, label)
        return tabIndex

    def setCurrentTab(self, tabName: str):
        for index in range(self.count()):
            if self.tabText(index) == tabName:
                tab = self.widget(index)
                self.setCurrentWidget(tab)
                return True
        return False

    def removeTab(self, index: int):
        if self.unclosable and self.count() == 1:
            return
        widget = self.widget(index)
        if widget is not None:
            widget.deleteLater()
        super(TabWidget, self).removeTab(index)
        if not self.unclosable and not self.count():
            self.deleteLater()

    def closeStaleTab(self, tab: "TabWithTreeView"):
        """Close a tab whose object is gone, or empty the last tab"""
        index = self.indexOf(tab)
        if index < 0:
            return
        if self.unclosable and self.count() == 1:
            tab.openEmptyItem()
        else:
            self.removeTab(index)

    def removeTabsOfClosedPackages(self, openedPackages):
        """Close the tabs that show objects of a package that is not open"""
        for tabIndex in range(self.count() - 1, -1, -1):
            tab = self.widget(tabIndex)
            package = getattr(tab, "package", None)
            if package is not None and package not in openedPackages:
                self.closeStaleTab(tab)
