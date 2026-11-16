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

from typing import Any

from PyQt6.QtCore import QModelIndex, QPersistentModelIndex
from PyQt6.QtGui import QFont

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.models import DetailedInfoItem, StandardTable
from aas_workingbench.settings.app_settings import (
    PACKAGE_ROLE,
    NAME_ROLE,
    OBJECT_ROLE,
    COLUMNS_IN_ATTRIBUTE_TABS,
    PACK_ITEM_ROLE,
    DEFAULT_FONT,
    LINKED_CONCEPT_ROLE,
    VALUE_COLUMN,
)


class DetailedInfoTable(StandardTable):
    itemTyp = DetailedInfoItem
    currFont = QFont(DEFAULT_FONT)

    def __init__(self, packItem: QModelIndex):
        self.packItem = QPersistentModelIndex(packItem)
        self.mainObj = packItem.data(OBJECT_ROLE)
        self.package = packItem.data(PACKAGE_ROLE)
        root = DetailedInfoItem(
            self.mainObj,
            name=packItem.data(NAME_ROLE),
            package=self.package,
            new=False,
        )
        super(DetailedInfoTable, self).__init__(COLUMNS_IN_ATTRIBUTE_TABS, root)
        # Other tabs may edit the objects that this one shows.
        self.watchPackage(self.package)
        # Read mode hides the null attributes, so the rows change with the mode.
        edit_mode().subscribe(self._onEditModeChanged)

    def _onEditModeChanged(self, editing: bool):
        try:
            self._repopulate(QModelIndex())
        except RuntimeError:
            # The model was deleted with its tab.
            pass

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role == PACK_ITEM_ROLE:
            return QModelIndex(self.packItem)
        else:
            return super(DetailedInfoTable, self).data(index, role)

    def getLinkedItem(self, index: QModelIndex) -> QModelIndex:
        """Finds the row of the tree that a link of the detail opens.

        A semanticId that names a concept description of the package links
        to it (proposal 3.5), and so does the unit of a value that the concept
        gives (proposal 3.7). Other links resolve their reference.
        """
        concept = index.siblingAtColumn(VALUE_COLUMN).data(LINKED_CONCEPT_ROLE)
        if concept is None:
            return super().getLinkedItem(index)
        from aas_workingbench.ui.reference_jump import find_row

        tree = QModelIndex(self.packItem).model()
        if tree is None:
            return QModelIndex()
        found = find_row(tree, concept)
        return found if found is not None else QModelIndex()
