#  Copyright (C) 2025  Igor Garmaev, garmaev@gmx.net
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
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

from PyQt6 import QtCore
from PyQt6.QtCore import QItemSelectionModel, Qt, QModelIndex, QRect
from PyQt6.QtGui import QFont, QFontMetrics, QKeyEvent, QMouseEvent, QPainter
from PyQt6.QtWidgets import (
    QAbstractScrollArea,
    QHeaderView,
    QStyleOptionViewItem,
)

import aas_workingbench.widgets as widgets
import aas_workingbench.widgets.messsageBoxes
from aas_workingbench.models import DetailedInfoTable
from aas_workingbench.delegates import EditDelegate
from aas_workingbench.settings.app_settings import (
    ATTR_COLUMN_PADDING,
    ATTR_MAX_SHARE,
    TYPE_MAX_SHARE,
    ATTR_COLUMN_WIDTH,
    NAME_ROLE,
    ATTRIBUTE_COLUMN,
    TYPE_COLUMN,
    TYPE_COLUMN_PADDING,
    TYPE_COLUMN_WIDTH,
    TYPE_HINT_COLUMN,
    VALUE_COLUMN,
    VALUE_COLUMN_WIDTH,
    WIDEST_ATTRIBUTE_NAME,
    WIDEST_TYPE_NAME,
    LINKED_ITEM_ROLE,
    LINKED_CONCEPT_ROLE,
    IS_LINK_ROLE,
    PARENT_OBJ_ROLE,
)
from aas_workingbench.ui.value_editor import (
    ValueEditDialog,
    entryTextArgs,
    value_dialog_args,
)
from aas_workingbench.domain.attribute_vocabulary import metamodel_name
from aas_workingbench.utils.util import getAttrTypeHint
from aas_workingbench import dialogs
from aas_workingbench.treeviews.base import TreeView
from aas_workingbench.ui.detail_sections import SectionBands
from aas_workingbench.ui.detail_sections import band_height
from aas_workingbench.ui.detail_sections import paint_band
from aas_workingbench.ui.theme import theme_manager


class AttrsTreeView(TreeView):
    # The first column names an attribute, and is drawn as a label.
    namesAreLabels = True

    def __init__(self, parent=None, treeModel=DetailedInfoTable, **kwargs):
        super(AttrsTreeView, self).__init__(parent, **kwargs)
        self.treeModel = treeModel
        # The attributes are read in sections, which the view draws as bands
        # over the rows of the model (proposals 3.2, 3.3).
        self.bands = SectionBands()
        self.setUniformRowHeights(False)
        # Until the user sizes a column, or a saved state does, the columns
        # keep fitting the room that the view has.
        self.userSizedColumns = False
        self._fittingColumns = False
        self.header().sectionResized.connect(self._onSectionResized)

    def _onSectionResized(self, section: int, *_):
        # Without a header there is nothing that a user could size a column
        # with, so a column that changes is the view hiding or fitting it.
        if self.header().isHidden():
            return
        if not self._fittingColumns and section in (
            ATTRIBUTE_COLUMN,
            TYPE_COLUMN,
        ):
            self.userSizedColumns = True

    def fitColumns(self):
        """Size the name and type columns to their names, within the room.

        The names that nearly every element shows are kept whole when the
        view has the room. A narrow view gives the name and the type a share
        of its width at most, so that the value, which is what is edited,
        keeps the rest. Once the user sizes a column, nothing is refitted.
        """
        width = self.viewport().width()
        if self.userSizedColumns:
            return
        attribute, kind = self.fittingAttributeWidth(), self.fittingTypeWidth()
        if width > 0:
            attribute = min(attribute, int(width * ATTR_MAX_SHARE))
            kind = min(kind, int(width * TYPE_MAX_SHARE))
        self._fittingColumns = True
        try:
            self.setColumnWidth(ATTRIBUTE_COLUMN, attribute)
            self.setColumnWidth(TYPE_COLUMN, kind)
        finally:
            self._fittingColumns = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fitColumns()

    def _onClicked(self, index: QModelIndex) -> None:
        """Follows a link that was clicked.

        A concept that a semanticId names opens in the same tab, so that Back
        returns to the element (proposals 3.5, 4.3). A reference opens a tab.
        """
        concept = index.siblingAtColumn(VALUE_COLUMN).data(LINKED_CONCEPT_ROLE)
        if concept is not None:
            self.openRef(index, newTab=False)
        else:
            self.openRef(index)

    # -- sections ---------------------------------------------------------

    def readSections(self, *_) -> None:
        """Reads the sections of the rows, and hides those of closed ones."""
        model = self.model()
        self.bands.read(model)
        if model is None:
            return
        root = QModelIndex()
        for row in range(model.rowCount(root)):
            self.setRowHidden(row, root, self.bands.is_hidden(row))
        self.scheduleDelayedItemsLayout()
        self.viewport().update()

    def rowHeight(self) -> int:
        """The height of a row of the density in use, without a band."""
        return theme_manager().row_height

    def bandOffset(self, index: QModelIndex) -> int:
        """How far the cells of a row are below the top of the row.

        A row with a band above it draws its cells below the band, and an
        editor of such a cell goes there too.
        """
        band = self.bands.band_at(index.siblingAtColumn(0))
        if band is None:
            return 0
        return band_height(self.rowHeight())

    def toggleSection(self, index: QModelIndex) -> bool:
        """Opens or closes the section whose band is above a row.

        Returns:
            Whether the row has a band.
        """
        band = self.bands.band_at(index.siblingAtColumn(0))
        if band is None:
            return False
        self.bands.toggle(band.section)
        self.readSections()
        return True

    def visualRect(self, index: QModelIndex) -> QRect:
        """The room of a cell, below the band of its section if it has one.

        A click, an editor, and a scroll aim at the cell, not at the band
        above it. The first row of a closed section is all band.
        """
        rect = super().visualRect(index)
        if not index.isValid() or self.bands.shows_only_band(
            index.siblingAtColumn(0)
        ):
            return rect
        offset = self.bandOffset(index)
        if offset:
            rect.setTop(rect.top() + offset)
        return rect

    def _bandHit(self, event: QMouseEvent | None) -> QModelIndex:
        """Gives the row whose band the pointer is on, or an invalid index."""
        if event is None:
            return QModelIndex()
        position = event.position().toPoint()
        index = self.indexAt(position)
        if not index.isValid() or not self.bandOffset(index):
            return QModelIndex()
        if self.bands.shows_only_band(index.siblingAtColumn(0)):
            return index
        if position.y() < self.visualRect(index).top():
            return index
        return QModelIndex()

    def mousePressEvent(self, e: QMouseEvent | None) -> None:
        """Opens a concept from its link, or a section from its band."""
        if e is not None and e.button() == Qt.MouseButton.LeftButton:
            position = e.position().toPoint()
            cell = self.indexAt(position)
            delegate = self.itemDelegate()
            if (
                cell.isValid()
                and hasattr(delegate, "linkAt")
                and delegate.linkAt(cell, position)
            ):
                self.openRef(
                    cell.siblingAtColumn(VALUE_COLUMN),
                    newTab=False,
                    viaLink=True,
                )
                e.accept()
                return
        index = self._bandHit(e)
        if (
            index.isValid()
            and e is not None
            and e.button() == Qt.MouseButton.LeftButton
        ):
            self.toggleSection(index)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e: QMouseEvent | None) -> None:
        """A double click on a band toggles it once, and edits nothing."""
        if self._bandHit(e).isValid():
            if e is not None:
                e.accept()
            return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e: QMouseEvent | None) -> None:
        """Shows that a band can be clicked."""
        if self._bandHit(e).isValid():
            self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.viewport().unsetCursor()
        super().mouseMoveEvent(e)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Space on the first row of a section opens or closes it."""
        index = super().currentIndex().siblingAtColumn(0)
        if (
            event.key() == Qt.Key.Key_Space
            and event.modifiers() == Qt.KeyboardModifier.NoModifier
            and self.bands.shows_only_band(index)
        ):
            self.toggleSection(index)
            event.accept()
            return
        super().keyPressEvent(event)

    def drawRow(
        self,
        painter: QPainter | None,
        options: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Draws the band of a section above its first row, then the row."""
        band = self.bands.band_at(index.siblingAtColumn(0))
        if band is None or painter is None:
            super().drawRow(painter, options, index)
            return
        height = band_height(self.rowHeight())
        is_open = self.bands.is_open(band.section)
        paint_band(
            painter,
            QRect(0, options.rect.top(), self.viewport().width(), height),
            band,
            is_open=is_open,
            draw_line=band.first_row != 0,
            font=QFont(DetailedInfoTable.currFont),
        )
        if not is_open:
            return
        below = QStyleOptionViewItem(options)
        below.rect = options.rect.adjusted(0, height, 0, 0)
        super().drawRow(painter, below, index)

    # noinspection PyUnresolvedReferences
    def newPackItem(self, packItem):
        self.initTreeView(packItem)

    def initTreeView(self, packItem):
        self.setExpandsOnDoubleClick(False)
        self.setBaseSize(QtCore.QSize(429, 555))
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        self.setObjectName("attrsTreeView")
        self.setAccessibleName("Attributes")
        self.setModelWithProxy(self.treeModel(packItem))
        self.setUniformRowHeights(False)
        proxy = self.model()
        for signal in (
            proxy.modelReset,
            proxy.rowsInserted,
            proxy.rowsRemoved,
            proxy.layoutChanged,
        ):
            signal.connect(self.readSections)
        self.readSections()
        # The value is what a user edits, so it takes the width that the name
        # and the type leave. A tab is not wide, and a scroll bar for the
        # columns hides the type.
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            ATTRIBUTE_COLUMN, QHeaderView.ResizeMode.Interactive
        )
        header.setSectionResizeMode(
            VALUE_COLUMN, QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            TYPE_COLUMN, QHeaderView.ResizeMode.Interactive
        )
        self.userSizedColumns = False
        self.fitColumns()
        self.setColumnWidth(VALUE_COLUMN, VALUE_COLUMN_WIDTH)
        # The type that the Python SDK declares says what the type column
        # says, in words that only a programmer reads.
        self.header().hideSection(TYPE_HINT_COLUMN)
        # The type of the metamodel shows only where it helps: in the tooltip
        # of the name of an attribute, and in the field while a value is
        # edited. A column of it read as a list of loose technical names, and
        # a header over a name and a value says nothing (proposals 1.2, 3.6).
        self.header().hide()
        self.header().hideSection(TYPE_COLUMN)
        self.userSizedColumns = False
        self.fitColumns()
        self.setItemDelegate(EditDelegate(self))

    @staticmethod
    def _measured(text: str, bold: bool, padding: int, fallback: int) -> int:
        font = QFont(DetailedInfoTable.currFont)
        font.setBold(bold)
        width = QFontMetrics(font).horizontalAdvance(text)
        return width + padding if width > 0 else fallback

    def fittingAttributeWidth(self) -> int:
        """Return the width that keeps the common attribute names whole."""
        return self._measured(
            WIDEST_ATTRIBUTE_NAME, False, ATTR_COLUMN_PADDING, ATTR_COLUMN_WIDTH
        )

    def fittingTypeWidth(self) -> int:
        """Return the width that keeps the common type names whole."""
        return self._measured(
            WIDEST_TYPE_NAME, False, TYPE_COLUMN_PADDING, TYPE_COLUMN_WIDTH
        )

    def buildHandlers(self):
        super(AttrsTreeView, self).buildHandlers()
        self.setItemDelegate(EditDelegate(self))
        self.clicked.connect(self._onClicked)
        self.wheelClicked.connect(
            lambda refItem: self.openRef(refItem, setCurrent=False)
        )

    # noinspection PyArgumentList
    def initMenu(self):
        super(AttrsTreeView, self).initMenu()
        self.openInCurrTabAct.triggered.connect(
            lambda: self.openRef(
                self.currentIndex().siblingAtColumn(VALUE_COLUMN), newTab=False
            )
        )
        self.openInNewTabAct.triggered.connect(
            lambda: self.openRef(
                self.currentIndex().siblingAtColumn(VALUE_COLUMN)
            )
        )
        self.openInBackgroundAct.triggered.connect(
            lambda: self.openRef(
                self.currentIndex().siblingAtColumn(VALUE_COLUMN),
                setCurrent=False,
            )
        )
        self.openInNewWindowAct.triggered.connect(
            lambda: self.openRef(
                self.currentIndex().siblingAtColumn(VALUE_COLUMN),
                newWindow=True,
            )
        )

    def updateActions(self, index: QModelIndex):
        super().updateActions(index)
        # update open actions
        indexIsLink = bool(index.data(IS_LINK_ROLE))
        self.openInCurrTabAct.setEnabled(indexIsLink)
        self.openInBackgroundAct.setEnabled(indexIsLink)
        self.openInNewTabAct.setEnabled(indexIsLink)
        self.openInNewWindowAct.setEnabled(indexIsLink)

        self.openInCurrTabAct.setVisible(indexIsLink)
        self.openInBackgroundAct.setVisible(indexIsLink)
        self.openInNewTabAct.setVisible(indexIsLink)
        self.openInNewWindowAct.setVisible(indexIsLink)
        # Without a link there is nothing to open, and the entry is empty.
        self.openInMenu.menuAction().setVisible(indexIsLink)

    def updateEditActs(self, index: QModelIndex):
        super().updateEditActs(index)
        # update edit action
        valColIndex = index.siblingAtColumn(VALUE_COLUMN)
        if valColIndex.flags() & Qt.ItemFlag.ItemIsEditable:
            self._moveCurrentTo(valColIndex)
            self.editCreateInDialogAct.setEnabled(True)
        if self.isEditableInsideCell(valColIndex):
            self._moveCurrentTo(valColIndex)
            self.editAct.setEnabled(True)

    def _moveCurrentTo(self, index: QModelIndex):
        """Make the cell current without changing what is selected.

        The actions are refreshed whenever the selection changes, and
        `setCurrentIndex` would select the cell alone, so a selection of
        several rows could never be kept.
        """
        self.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.NoUpdate
        )

    def onAddAct(self, parent: QModelIndex = None):
        try:
            parent = parent if parent else self.currentIndex()
            attribute = parent.data(NAME_ROLE)
            attrTypeHint = getAttrTypeHint(
                type(parent.data(PARENT_OBJ_ROLE)), attribute
            )  # FIXME
            name = metamodel_name(type(parent.data(PARENT_OBJ_ROLE)), attribute)
            self.addItemWithDialog(
                parent=parent,
                objTypeHint=attrTypeHint,
                title=f"Add {name} element",
            )
        except Exception as e:
            widgets.messsageBoxes.ErrorMessageBox.withTraceback(
                self, str(e)
            ).exec()

    def onEditCreate(self, objVal, index=QModelIndex()):
        """
        :param objVal: value to set in dialog input widgets
        :param index: QModelIndex of the item to edit
        :raise KeyError if no typehint found and no objVal was given
        """
        if not index.isValid():
            index = self.currentIndex()
        if index.isValid():
            objVal = (
                objVal
                if objVal
                else index.siblingAtColumn(VALUE_COLUMN).data(
                    Qt.ItemDataRole.EditRole
                )
            )
            attribute = index.data(NAME_ROLE)
            parentObj = index.data(PARENT_OBJ_ROLE)
            valueArgs = value_dialog_args(parentObj, attribute)
            if valueArgs is not None:
                # A value follows its value type, and bytes are not literals.
                self.replItemWithDialog(
                    index=index,
                    title=f"Edit {metamodel_name(type(parentObj), attribute)}",
                    objVal=objVal,
                    editDialogType=ValueEditDialog,
                    **valueArgs,
                )
                return
            try:
                attrTypeHint = getAttrTypeHint(type(parentObj), attribute)
            except KeyError as e:
                if objVal:
                    attrTypeHint = type(objVal)
                else:
                    raise KeyError(
                        "No typehint found for the given item", attribute
                    )
            self.replItemWithDialog(
                index=index,
                objTypeHint=attrTypeHint,
                title=f"Edit/Create {metamodel_name(type(parentObj), attribute)}",
                objVal=objVal,
                **entryTextArgs(parentObj),
            )

    def currentIndex(self) -> QtCore.QModelIndex:
        return (
            super(AttrsTreeView, self)
            .currentIndex()
            .siblingAtColumn(VALUE_COLUMN)
        )

    def isEditableInsideCell(self, index: QModelIndex):
        index = index.siblingAtColumn(VALUE_COLUMN)
        return super().isEditableInsideCell(index)

    def openRef(
        self,
        detailInfoItem: QModelIndex,
        newTab=True,
        setCurrent=True,
        newWindow=False,
        viaLink=False,
    ):
        """Open referenced item if clicked on Reference and item is saved locally

        :param viaLink: the link drawn beside a value was clicked, such as the
            concept that gives the unit of a value (proposal 3.7)
        """
        isLink = detailInfoItem.data(IS_LINK_ROLE) or (
            viaLink and detailInfoItem.data(LINKED_CONCEPT_ROLE) is not None
        )
        if detailInfoItem.column() == VALUE_COLUMN and isLink:
            linkedPackItem = detailInfoItem.data(LINKED_ITEM_ROLE)
            if newWindow:
                self.openInNewWindowClicked.emit(linkedPackItem)
            elif newTab and setCurrent:
                self.openInNewTabClicked.emit(linkedPackItem)
            elif newTab and not setCurrent:
                self.openInBgTabClicked.emit(linkedPackItem)
            else:
                self.openInCurrTabClicked.emit(linkedPackItem)
