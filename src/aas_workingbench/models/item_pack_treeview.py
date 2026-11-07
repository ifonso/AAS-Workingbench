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
from types import GeneratorType

from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from PyQt6.QtCore import QVariant

from aas_workingbench.domain.readable_values import count_text
from aas_workingbench.domain.tree_names import node_description
from aas_workingbench.domain.tree_names import node_name
from aas_workingbench.domain.tree_names import type_name
from aas_workingbench.models import StandardItem
from aas_workingbench.settings.app_settings import (
    PACKAGE_ROLE,
    ATTRIBUTE_COLUMN,
    TYPE_COLUMN,
    VALUE_COLUMN,
)
from aas_workingbench.utils.util import getLimitStr
from aas_workingbench.utils.util_classes import ClassesInfo
from aas_workingbench.utils.util_type import isIterable
from aas_workingbench.package import Package, StoredFile


class PackTreeViewItem(StandardItem):
    # The rows are the elements of the object, in the order of the object.
    supportsIncrementalRows = True

    @property
    def repopulatesOnChange(self) -> bool:
        # The rows of the file store are stand-ins for names in the container.
        # A command that adds, removes, renames, or replaces a file reports the
        # container, and the rows are read from it again.
        return isinstance(self.obj, DictSupplementaryFileContainer)

    def __init__(self, obj, parent, **kwargs):
        super().__init__(obj, parent=parent, **kwargs)
        if obj is None and parent is None:
            self.child = []
        elif isinstance(obj, Package):
            self.typehint = Package
            self.package = obj
        else:
            self.package = parent.data(PACKAGE_ROLE)
        self.populate()

    def populate(self):
        kwargs = {
            "parent": self,
            "new": self.new,
        }
        if ClassesInfo.hasPackViewAttrs(type(self.obj)):
            for attr in ClassesInfo.packViewAttrs(type(self.obj)):
                # set package objStore as obj, so that delete works
                itemObj = getattr(self.obj, attr)
                packItem = PackTreeViewItem(itemObj, name=attr, **kwargs)
                if isinstance(itemObj, GeneratorType):
                    packItem.obj = self.obj.objStore
        elif isIterable(self.obj):
            if isinstance(self.obj, DictSupplementaryFileContainer):
                self._populateFileContainer(self.obj, **kwargs)
            else:
                self._populateIterable(self.obj, **kwargs)

    @property
    def isNode(self) -> bool:
        """Tell whether the row only groups objects of its parent.

        The shells, submodels, concept descriptions and files of a package,
        and the variables of an operation. They are found by `objName`, the
        name of the attribute in the SDK, which `displayName` does not change.
        """
        owner = self.parentObj
        return (
            owner is not None
            and bool(self.objName)
            and self.objName in ClassesInfo.packViewAttrs(type(owner))
        )

    @property
    def displayName(self) -> str:
        """What the first column reads: the AAS words for a group of objects."""
        if self.isNode:
            return node_name(type(self.parentObj), self.objName)
        return self.objectName

    @property
    def typeText(self) -> str:
        """What the type column reads: the AAS class, or nothing for a group."""
        return type_name(self.objTypeName, is_node=self.isNode)

    def _getDisplayRoleData(self, column, column_name):
        if column == ATTRIBUTE_COLUMN:
            return getLimitStr(self.displayName)
        if column == TYPE_COLUMN:
            return getLimitStr(self.typeText)
        if column == VALUE_COLUMN and self.isNode:
            # The object of the row is the store that holds every kind of
            # object of the package. The rows below tell what the group has.
            return count_text([child.obj for child in self.children()])
        return super()._getDisplayRoleData(column, column_name)

    def _getTooltipRoleData(self, column, column_name):
        if self.isNode:
            description = node_description(type(self.parentObj), self.objName)
            if column == ATTRIBUTE_COLUMN:
                return f"{self.displayName}\n\n{description}".strip()
            if column == TYPE_COLUMN:
                return QVariant()
        elif column == TYPE_COLUMN:
            return self.typeText
        elif column == ATTRIBUTE_COLUMN:
            return self._fullNameTooltip(column, column_name)
        return super()._getTooltipRoleData(column, column_name)

    @property
    def pathText(self) -> str:
        """Where the row is: the names from its package down to it."""
        names = []
        node = self
        while isinstance(node, PackTreeViewItem) and node.obj is not None:
            names.append(node.displayName)
            node = node.parent()
        return " / ".join(reversed(names))

    def _fullNameTooltip(self, column, column_name):
        """The whole name of a row, which the column may cut, and where it is.

        The name is not cut here, and below it comes the path from the package,
        which the indent of a deep row does not show.
        """
        name = self.displayName
        tooltip = name
        path = self.pathText
        if path and path != name:
            tooltip = f"{name}\n{path}"
        extra = super()._getTooltipRoleData(column, column_name)
        if isinstance(extra, str) and extra and extra != name:
            tooltip = f"{tooltip}\n\n{extra}"
        return tooltip

    def acceptsChild(self, obj) -> bool:
        # The shells, submodels and concept descriptions of a package share
        # its object store, so the type of the object tells where it belongs.
        parent = self.parent()
        if parent is not None and isinstance(parent.obj, Package):
            addType = ClassesInfo.addType(Package, self.objName)
            return addType is None or isinstance(obj, addType)
        return True

    def createChildFor(self, obj):
        return PackTreeViewItem(obj, parent=self, new=True)

    @staticmethod
    def _populateIterable(obj, **kwargs):
        for sub_item_obj in obj:
            PackTreeViewItem(sub_item_obj, **kwargs)

    @staticmethod
    def _populateFileContainer(fileContainer, **kwargs):
        # populate file container
        for name in fileContainer:
            itemObj = StoredFile(name, fileContainer)
            PackTreeViewItem(itemObj, **kwargs)

    def _getEditRoleData(self, column, column_name):
        if column == ATTRIBUTE_COLUMN:
            return self.obj
        return super(PackTreeViewItem, self)._getEditRoleData(
            column, column_name
        )
