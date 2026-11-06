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

from aas_editor.domain.containers import position_of
from aas_editor.models import StandardItem
from aas_editor import settings
from aas_editor.settings import DICT_TYPES
from aas_editor.utils.util import getAttrs4detailInfo, isSimpleIterable
from aas_editor.utils.util_type import getTypeName
from aas_editor.additional.classes import DictItem
from aas_editor.package import Package


class DetailedInfoItem(StandardItem):
    # The rows show attributes and their values, and the names of the rows of
    # a list contain their position, so everything below is read again.
    repopulatesOnChange = True

    def __init__(
        self, obj, name="", parent=None, package: Package = None, **kwargs
    ):
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
            DetailedInfoItem(
                DictItem(key, obj[key]),
                name=f"{getTypeName(DictItem)} {i}",
                **kwargs,
            )

    @staticmethod
    def _populateIterable(obj, **kwargs):
        for i, sub_item_obj in enumerate(obj):
            DetailedInfoItem(
                sub_item_obj,
                name=f"{getTypeName(sub_item_obj.__class__)} {i}",
                **kwargs,
            )

    @staticmethod
    def _populateUnknown(obj, **kwargs):
        for attr in getAttrs4detailInfo(obj):
            if attr == "id_short" and isListItem(obj):
                # The item of a list has no idShort: its position names it.
                ListIndexItem(obj, name=LIST_INDEX_NAME, **kwargs)
                continue
            DetailedInfoItem(getattr(obj, attr), name=attr, **kwargs)


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
        super().__init__(self.position(), name=name, typehint=int, **kwargs)

    def position(self) -> int:
        """Return the position of the element in its list."""
        position = position_of(self.element.parent.value, self.element)
        return -1 if position is None else position

    def data(self, role, column=settings.ATTRIBUTE_COLUMN, column_name=""):
        self._obj = self.position()
        return super().data(role, column, column_name)
