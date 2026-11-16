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

from PyQt6.QtGui import QColor, QFont, QPainter, QPalette, QBrush, QIntValidator
from PyQt6.QtWidgets import (
    QWidget,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QStyle,
    QCompleter,
    QCheckBox,
)
from PyQt6 import QtCore
from PyQt6.QtCore import Qt, QModelIndex, QPersistentModelIndex, QPoint, QRect

from aas_workingbench.domain.typed_values import is_value_attr, value_type_of
from aas_workingbench.settings import DEFAULT_COMPLETIONS
from aas_workingbench.settings.app_settings import EDIT_TARGET_ROLE
from aas_workingbench.settings.app_settings import LANGUAGE_BADGE_ROLE
from aas_workingbench.settings.app_settings import SUBTEXT_ROLE
from aas_workingbench.settings.app_settings import UNIT_ROLE
from aas_workingbench.settings.app_settings import NAME_ROLE
from aas_workingbench.settings.app_settings import PARENT_OBJ_ROLE
from aas_workingbench.ui.compact_rows import (
    child_count_text,
    paint_child_count,
    paint_row_signs,
    row_size_hint,
)
from aas_workingbench.ui.detail_sections import band_size
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.value_editor import ValueLineEdit
from aas_workingbench.ui.value_marks import (
    MARK_GAP,
    badge_width,
    paint_badge,
    paint_link,
    paint_subtext,
    subtext_height,
)
from aas_workingbench.additional.classes import DictItem
from aas_workingbench.utils.util_type import issubtype, isoftype
from aas_workingbench.widgets.editWidgets import (
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
        # Where each cell drew the link to its concept, which a click opens.
        self.linkRects: Dict[QPersistentModelIndex, QRect] = {}

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

        # The band and the bar of a selected row say where the focus is, so
        # the box of the focus around the name cell is not drawn (proposal 2.5).
        if opt.state & QStyle.StateFlag.State_Selected:
            opt.state &= ~QStyle.StateFlag.State_HasFocus
        # The name of an attribute is a label and its value is what a person
        # reads, so the name takes the secondary color (proposal 1.1). A name
        # with a mark or a link keeps the color that the model gives it.
        if (
            index.column() == 0
            and getattr(opt.widget, "namesAreLabels", False)
            and index.data(Qt.ItemDataRole.ForegroundRole) is None
        ):
            label = QColor(current_tokens().fg_secondary)
            opt.palette.setColor(QPalette.ColorRole.Text, label)
        # A row with a second line, such as the id under the name of the
        # concept of a semanticId, draws its value in the first line.
        cell = QRect(opt.rect)
        subtext = self._subtext(opt, index)
        # The name of such a row reads beside the first line, too.
        if subtext or self._subtext(opt, index.siblingAtColumn(1)):
            opt.rect = QRect(
                cell.left(),
                cell.top(),
                cell.width(),
                cell.height() - subtext_height(),
            )
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
        paint_row_signs(painter, opt, index)
        if subtext:
            paint_subtext(painter, cell, self._textLeft(opt, index), subtext)
        self._paintMarks(painter, opt, index)
        count = child_count_text(opt.widget, index)
        if count:
            paint_child_count(
                painter, opt, index, count, self._nameEnd(opt, index)
            )

    @staticmethod
    def _subtext(option: QStyleOptionViewItem, index: QModelIndex) -> str:
        if not getattr(option.widget, "namesAreLabels", False):
            return ""
        text = index.data(SUBTEXT_ROLE)
        return text if isinstance(text, str) else ""

    def _paintMarks(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        """Draws the languages, the unit and its concept beside a value."""
        if not getattr(option.widget, "namesAreLabels", False):
            return
        languages = index.data(LANGUAGE_BADGE_ROLE)
        unit = index.data(UNIT_ROLE)
        key = QPersistentModelIndex(index)
        self.linkRects.pop(key, None)
        if not languages and not unit:
            return
        x = self._nameEnd(option, index) + MARK_GAP
        line = option.rect
        if languages:
            if x + badge_width(languages, "language") <= line.right():
                x = paint_badge(painter, line, x, languages, "language")
        if unit:
            text, source = unit
            label = f"unit {text}"
            if x + badge_width(label) > line.right():
                return
            x = paint_badge(painter, line, x, label) + MARK_GAP
            self.linkRects[key] = paint_link(
                painter, line, x, f"from concept {source}"
            )

    def linkAt(self, index: QModelIndex, point: QPoint) -> bool:
        """Tells whether a point is on the link that a cell drew."""
        rect = self.linkRects.get(QPersistentModelIndex(index))
        return rect is not None and rect.contains(point)

    def _textLeft(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> int:
        """Where the text of a cell starts, in the coordinates of the view."""
        textOption = QStyleOptionViewItem(option)
        self.initStyleOption(textOption, index)
        widget = textOption.widget
        style = widget.style() if widget is not None else None
        if style is None:
            return option.rect.left()
        return style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, textOption, widget
        ).left()

    def _nameEnd(self, option: QStyleOptionViewItem, index: QModelIndex) -> int:
        """Where the text of a cell ends, in the coordinates of the view."""
        textOption = QStyleOptionViewItem(option)
        self.initStyleOption(textOption, index)
        widget = textOption.widget
        style = widget.style() if widget is not None else None
        if style is None:
            return option.rect.right()
        textRect = style.subElementRect(
            QStyle.SubElement.SE_ItemViewItemText, textOption, widget
        )
        return textRect.left() + textOption.fontMetrics.horizontalAdvance(
            textOption.text
        )

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        # Qt ignores the height of a row in a style sheet, so it comes from the
        # density of the theme and the font of the row (ADR 0025).
        font = index.data(Qt.ItemDataRole.FontRole)
        size = row_size_hint(font if isinstance(font, QFont) else option.font)
        if self._subtext(option, index):
            size.setHeight(size.height() + subtext_height())
        # The first row of a section of the detail has its band above it.
        bands = getattr(option.widget, "bands", None)
        if bands is not None:
            size = band_size(size, index, bands, size.height())
        return size

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

    @staticmethod
    def completionsFor(index: QtCore.QModelIndex) -> list:
        """Return the values to suggest for the attribute that a cell shows

        The list belongs to the attribute of the owner, by the name that the
        SDK gives it, and not to the text that the cell holds now.
        """
        attrName = index.data(NAME_ROLE)
        for cls in type(index.data(PARENT_OBJ_ROLE)).__mro__:
            if cls in DEFAULT_COMPLETIONS:
                return DEFAULT_COMPLETIONS[cls].get(attrName, [])
        return []

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
            editor = ValueLineEdit(value_type_of(owner), parent)
            # The type changes what may be typed, so the field says it while
            # the value is edited, and the detail shows no column of types
            # (proposal 3.6).
            editor.show_type_inside(True)
            return editor
        objType = type(index.data(Qt.ItemDataRole.EditRole))
        if issubtype(objType, bool):
            widget = QCheckBox(parent)
        elif issubtype(objType, str):
            widget = LineEdit(parent)
            completions = self.completionsFor(index)
            if completions:
                completer = QCompleter(completions, parent)
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
        # The view gives the cell of a row with the band of a section below
        # the band (`AttrsTreeView.visualRect`).
        editor.setGeometry(option.rect)
