#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
from basyx.aas.model.aas import *
from basyx.aas.model.base import *
from basyx.aas.model.concept import *
from basyx.aas.model.submodel import *

from enum import Enum
from typing import Dict

from PyQt6.QtGui import QPainter, QBrush, QIntValidator
from PyQt6.QtWidgets import (
    QWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QCompleter,
    QCheckBox,
)
from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QModelIndex

from aas_editor.domain.typed_values import is_value_attr, value_type_of
from aas_editor.settings import DEFAULT_COMPLETIONS
from aas_editor.settings.app_settings import EDIT_TARGET_ROLE
from aas_editor.ui.value_editor import ValueLineEdit
from aas_editor.additional.classes import DictItem
from aas_editor.utils.util_type import issubtype, isoftype
from aas_editor.widgets.editWidgets import (
    ComboBox,
    CompleterComboBox,
    DictItemEdit,
    LineEdit,
)


class ColorDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.indexColors: Dict[QModelIndex, QBrush] = {}
        self.hoverIndex = QModelIndex()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ):
        opt = QStyleOptionViewItem(option)
        # paint row of the tree with MouseOver style if one cell of the row is chosen
        if (
            not opt.state & QStyle.StateFlag.State_HasFocus
            and not opt.state & QStyle.StateFlag.State_Selected
        ):
            view = opt.styleObject
            hoverIndex: QModelIndex = view.currentIndex()
            if (
                not opt.state & QStyle.StateFlag.State_MouseOver
                and index.siblingAtColumn(0) == hoverIndex.siblingAtColumn(0)
            ):
                opt.state |= QStyle.StateFlag.State_MouseOver
                model = view.model()
                model.dataChanged.emit(index, index)

        if index.isValid() and index in self.indexColors:
            self.initStyleOption(opt, index)
            opt.backgroundBrush = self.indexColors[index]
            widget = opt.widget
            style = widget.style()
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget
            )
        else:
            super(ColorDelegate, self).paint(painter, opt, index)

    def setBgColor(self, index: QModelIndex, val: QBrush):
        self.indexColors[index] = val

    def bgColor(self, index: QModelIndex):
        return self.indexColors[index]

    def removeBgColor(self, index: QModelIndex):
        self.indexColors.pop(index)

    def clearBgColors(self):
        self.indexColors.clear()


class EditDelegate(ColorDelegate):
    editableTypesInTable = (bool, int, str, Enum)

    @staticmethod
    def typedValueTarget(index: QtCore.QModelIndex):
        """Return the object and attribute of a cell that follows a value type

        :return: a tuple of the Property, Range, Qualifier or Extension and the
            name of the attribute that holds the value, or None for other cells
        """
        target = index.data(EDIT_TARGET_ROLE)
        if target and is_value_attr(*target):
            return target
        return None

    def isTypedValueCell(self, index: QtCore.QModelIndex) -> bool:
        return self.typedValueTarget(index) is not None

    def createEditor(
        self,
        parent: QWidget,
        option: "QStyleOptionViewItem",
        index: QtCore.QModelIndex,
    ) -> QWidget:
        target = self.typedValueTarget(index)
        if target:
            # The text is parsed by the model, for the value type of the owner.
            owner, _ = target
            return ValueLineEdit(value_type_of(owner), parent)
        objType = type(index.data(Qt.ItemDataRole.EditRole))
        attr = index.data(Qt.ItemDataRole.DisplayRole)
        if issubtype(objType, bool):
            widget = QCheckBox(parent)
        elif issubtype(objType, str):
            widget = LineEdit(parent)
            completions = DEFAULT_COMPLETIONS.get(objType, {}).get(attr, [])
            if completions:
                completer = QCompleter(parent, completions=completions)
                completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                widget.setCompleter(completer)
        elif issubtype(objType, int):
            widget = LineEdit(parent)
            widget.setValidator(QIntValidator())
        elif issubtype(objType, Enum):
            # add enum types to types
            enums = [member for member in objType]
            if len(enums) <= 6:
                widget = ComboBox(parent)
            else:
                widget = CompleterComboBox(parent)
            widget.setAutoFillBackground(True)
        elif issubtype(objType, DictItem):
            widget = DictItemEdit(parent)
        else:
            return super().createEditor(parent, option, index)
        return widget

    def setEditorData(self, editor: QWidget, index: QtCore.QModelIndex) -> None:
        if isinstance(editor, ValueLineEdit):
            editor.set_value(index.data(Qt.ItemDataRole.EditRole))
            editor.initial_text = editor.text()
        elif isinstance(index.data(Qt.ItemDataRole.EditRole), Enum):
            currItem = index.data(Qt.ItemDataRole.EditRole)
            items = [member for member in type(currItem)]
            for item in items:
                editor.addItem(item.name, item)
            editor.model().sort(0, Qt.SortOrder.AscendingOrder)
            editor.setCurrentText(currItem.name)
        elif isinstance(index.data(Qt.ItemDataRole.EditRole), DictItem):
            currItem = index.data(Qt.ItemDataRole.EditRole)
            editor.setCurrentData(currItem)
        else:
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget,
        model: QtCore.QAbstractItemModel,
        index: QtCore.QModelIndex,
    ) -> None:
        if isinstance(editor, ValueLineEdit):
            # Leaving the text as it was is no edit, so an empty string value
            # does not replace a missing one.
            if editor.text() != editor.initial_text:
                model.setData(index, editor.text(), Qt.ItemDataRole.EditRole)
        elif isoftype(index.data(Qt.ItemDataRole.EditRole), (Enum, DictItem)):
            obj = editor.currentData()
            model.setData(index, obj, Qt.ItemDataRole.EditRole)
        elif isoftype(index.data(Qt.ItemDataRole.EditRole), int):
            obj = int(editor.text())
            model.setData(index, obj, Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

    def updateEditorGeometry(
        self,
        editor: QWidget,
        option: "QStyleOptionViewItem",
        index: QtCore.QModelIndex,
    ) -> None:
        editor.setGeometry(option.rect)
