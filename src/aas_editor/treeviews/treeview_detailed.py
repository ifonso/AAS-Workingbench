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
from PyQt6.QtCore import Qt, QModelIndex
from PyQt6.QtGui import QFont, QFontMetrics
from PyQt6.QtWidgets import QAbstractScrollArea, QHeaderView

import aas_editor.widgets as widgets
import aas_editor.widgets.messsageBoxes
from aas_editor.models import DetailedInfoTable
from aas_editor.delegates import EditDelegate
from aas_editor.settings.app_settings import (
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
    IS_LINK_ROLE,
    PARENT_OBJ_ROLE,
)
from aas_editor.ui.value_editor import (
    ValueEditDialog,
    entryTextArgs,
    value_dialog_args,
)
from aas_editor.utils.util import getAttrTypeHint
from aas_editor import dialogs
from aas_editor.treeviews.base import TreeView


class AttrsTreeView(TreeView):
    def __init__(self, parent=None, treeModel=DetailedInfoTable, **kwargs):
        super(AttrsTreeView, self).__init__(parent, **kwargs)
        self.treeModel = treeModel
        # Until the user sizes a column, or a saved state does, the columns
        # keep fitting the room that the view has.
        self.userSizedColumns = False
        self._fittingColumns = False
        self.header().sectionResized.connect(self._onSectionResized)

    def _onSectionResized(self, section: int, *_):
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
        self.setModelWithProxy(self.treeModel(packItem))
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
            WIDEST_ATTRIBUTE_NAME, True, ATTR_COLUMN_PADDING, ATTR_COLUMN_WIDTH
        )

    def fittingTypeWidth(self) -> int:
        """Return the width that keeps the common type names whole."""
        return self._measured(
            WIDEST_TYPE_NAME, False, TYPE_COLUMN_PADDING, TYPE_COLUMN_WIDTH
        )

    def buildHandlers(self):
        super(AttrsTreeView, self).buildHandlers()
        self.setItemDelegate(EditDelegate(self))
        self.clicked.connect(self.openRef)
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
            self.setCurrentIndex(valColIndex)
            self.editCreateInDialogAct.setEnabled(True)
        if self.isEditableInsideCell(valColIndex):
            self.setCurrentIndex(valColIndex)
            self.editAct.setEnabled(True)

    def onAddAct(self, parent: QModelIndex = None):
        try:
            parent = parent if parent else self.currentIndex()
            attribute = parent.data(NAME_ROLE)
            attrTypeHint = getAttrTypeHint(
                type(parent.data(PARENT_OBJ_ROLE)), attribute
            )  # FIXME
            self.addItemWithDialog(
                parent=parent,
                objTypeHint=attrTypeHint,
                title=f"Add {attribute} element",
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
                    title=f"Edit {attribute}",
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
                title=f"Edit/Create {attribute}",
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
    ):
        """Open referenced item if clicked on Reference and item is saved locally"""
        if detailInfoItem.column() == VALUE_COLUMN and detailInfoItem.data(
            IS_LINK_ROLE
        ):
            linkedPackItem = detailInfoItem.data(LINKED_ITEM_ROLE)
            if newWindow:
                self.openInNewWindowClicked.emit(linkedPackItem)
            elif newTab and setCurrent:
                self.openInNewTabClicked.emit(linkedPackItem)
            elif newTab and not setCurrent:
                self.openInBgTabClicked.emit(linkedPackItem)
            else:
                self.openInCurrTabClicked.emit(linkedPackItem)
