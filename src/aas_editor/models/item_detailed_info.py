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

from basyx.aas.model import SubmodelElementList
from PyQt6.QtCore import Qt

from aas_editor.application.editing import edit_mode
from aas_editor.domain.attribute_display import entry_label
from aas_editor.domain.attribute_display import type_column_text
from aas_editor.domain.attribute_display import value_text
from aas_editor.domain.attribute_vocabulary import LIST_INDEX
from aas_editor.domain.attribute_vocabulary import AttributeInfo
from aas_editor.domain.attribute_vocabulary import attribute_info
from aas_editor.domain.containers import position_of
from aas_editor.domain.samm import attribute_order
from aas_editor.models import StandardItem
from aas_editor import settings
from aas_editor.settings import DICT_TYPES
from aas_editor.utils.util import getAttrs4detailInfo, getLimitStr
from aas_editor.utils.util import isSimpleIterable
from aas_editor.utils.util_type import getTypeName
from aas_editor.additional.classes import DictItem
from aas_editor.package import Package


class DetailedInfoItem(StandardItem):
    # The rows show attributes and their values, and the names of the rows of
    # a list contain their position, so everything below is read again.
    repopulatesOnChange = True

    def __init__(
        self,
        obj,
        name="",
        parent=None,
        package: Package = None,
        label: str = None,
        **kwargs,
    ):
        # `label` is what the first column shows for an entry of a list. The
        # name stays what the editor finds the row by, so a row is found again
        # after the view was rebuilt, and is not the text a person reads.
        self._label = label
        super().__init__(obj, name, parent, **kwargs)
        if parent and not package:
            self.package = parent.data(settings.PACKAGE_ROLE)
        else:
            self.package = package
        self.populate()

    def populate(self):
        if (
            isinstance(self.obj, settings.TYPES_WITH_INSTANCES_NOT_TO_POPULATE)
            or type(self.obj) in settings.TYPES_NOT_TO_POPULATE
        ):
            return

        kwargs = {
            "parent": self,
            "package": self.package,
            "new": self.new,
        }

        if isinstance(self.obj, DICT_TYPES):
            self._populateDict(self.obj, **kwargs)
        elif isSimpleIterable(self.obj):
            self._populateIterable(self.obj, **kwargs)
        else:
            self._populateUnknown(self.obj, **kwargs)

    @staticmethod
    def _populateDict(obj, **kwargs):
        for i, key in enumerate(obj):
            entry = DictItem(key, obj[key])
            DetailedInfoItem(
                entry,
                name=f"{getTypeName(DictItem)} {i}",
                label=entry_label(entry, i),
                **kwargs,
            )

    @staticmethod
    def _populateIterable(obj, **kwargs):
        for i, sub_item_obj in enumerate(obj):
            DetailedInfoItem(
                sub_item_obj,
                name=f"{getTypeName(sub_item_obj.__class__)} {i}",
                label=entry_label(sub_item_obj, i),
                **kwargs,
            )

    @property
    def attributeInfo(self) -> AttributeInfo | None:
        """The vocabulary entry of the attribute that the row shows, if any."""
        owner = self.parentObj
        if owner is None or not self.objName:
            return None
        return attribute_info(type(owner), self.objName)

    @property
    def displayName(self) -> str:
        """What the first column reads: the name that the metamodel gives."""
        if self._label:
            return self._label
        info = self.attributeInfo
        return info.name if info is not None else self.objectName

    @property
    def typeText(self) -> str:
        """What the type column reads, in words of the AAS."""
        return type_column_text(self.attributeInfo, self.obj)

    def data(self, role, column=settings.ATTRIBUTE_COLUMN, column_name=""):
        if role == Qt.ItemDataRole.WhatsThisRole:
            info = self.attributeInfo
            if info is not None:
                return info.description
        return super().data(role, column, column_name)

    def _getDisplayRoleData(self, column, column_name):
        if column == settings.ATTRIBUTE_COLUMN:
            return getLimitStr(self.displayName)
        if column == settings.TYPE_COLUMN:
            return getLimitStr(self.typeText)
        if column == settings.VALUE_COLUMN:
            text = value_text(self.obj)
            if text is not None:
                return text
        return super()._getDisplayRoleData(column, column_name)

    def _getTooltipRoleData(self, column, column_name):
        info = self.attributeInfo
        if column == settings.ATTRIBUTE_COLUMN:
            if info is None:
                return self.displayName
            return f"{info.name}: {info.type_name}\n\n{info.description}"
        if column in (settings.VALUE_COLUMN, settings.TYPE_COLUMN):
            shown = (
                self.typeText
                if column == settings.TYPE_COLUMN
                else self.displayValue
            )
            if self.typecheck or info is None:
                return getLimitStr(shown)
            actual = type_column_text(None, self.obj)
            return getLimitStr(
                f"{shown}\n\nThe value must be of type '{info.type_name}', "
                f"not of type '{actual}'!"
            )
        return super()._getTooltipRoleData(column, column_name)

    @staticmethod
    def _populateUnknown(obj, **kwargs):
        # Read mode shows what an object has, not what it could have (F-EDT-01
        # AC1). A null attribute is a row to create it from, which Edit mode needs.
        editing = edit_mode().is_editing
        # A concept description with a SAMM element lists its Identifiable
        # attributes first (F-EDT-05 AC18).
        for attr in attribute_order(obj, getAttrs4detailInfo(obj)):
            if attr == "id_short" and isListItem(obj):
                # The item of a list has no idShort: its position names it.
                ListIndexItem(obj, name=LIST_INDEX_NAME, **kwargs)
                continue
            value = getattr(obj, attr)
            if value is None and not editing:
                continue
            DetailedInfoItem(value, name=attr, **kwargs)


LIST_INDEX_NAME = "index"


def isListItem(obj) -> bool:
    """Tell whether an object is an item of a SubmodelElementList."""
    return isinstance(getattr(obj, "parent", None), SubmodelElementList)


class ListIndexItem(DetailedInfoItem):
    """The read-only row with the position of an item in its list.

    The position is read from the list whenever the row is shown, so the row
    follows an item that moved, and an item that was added or removed before it.
    """

    readOnly = True

    def __init__(self, element, name=LIST_INDEX_NAME, **kwargs):
        self.element = element
        super().__init__(
            self.position(),
            name=name,
            label=LIST_INDEX.name,
            typehint=int,
            **kwargs,
        )

    @property
    def attributeInfo(self) -> AttributeInfo | None:
        return LIST_INDEX

    def position(self) -> int:
        """Return the position of the element in its list, -1 if it has left it.

        A row can be asked for its data after its element was removed, for
        example when the view repaints before the row itself is removed.
        """
        parent = self.element.parent
        if parent is None:
            return -1
        position = position_of(parent.value, self.element)
        return -1 if position is None else position

    def data(self, role, column=settings.ATTRIBUTE_COLUMN, column_name=""):
        self._obj = self.position()
        return super().data(role, column, column_name)
