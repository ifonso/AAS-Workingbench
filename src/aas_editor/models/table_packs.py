#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

from typing import Any, Union, Iterable

from PyQt6.QtCore import QModelIndex, Qt
from PyQt6.QtGui import QFont

from aas_editor.application.commands import Command
from aas_editor.application.edits import (
    AddMember,
    AddSupplementaryFile,
    SetAttribute,
)
from aas_editor.models import StandardTable, PackTreeViewItem
from aas_editor.models.table_standard import _NOT_RENAMED
from aas_editor.package import Package, StoredFile
from aas_editor.settings.app_settings import (
    PACKAGE_ROLE,
    DEFAULT_FONT,
    OPENED_PACKS_ROLE,
    OPENED_FILES_ROLE,
    DEFAULT_COLUMNS_IN_PACKS_TABLE,
    OBJECT_ROLE,
    COLUMN_NAME_ROLE,
    NAME_ROLE,
)
from aas_editor.utils.util import getAttrTypeHint
from aas_editor.utils.util_classes import ClassesInfo


class PacksTable(StandardTable):
    itemTyp = PackTreeViewItem
    currFont = QFont(DEFAULT_FONT)

    def openedPacks(self):
        packs = set()
        for i in range(self.rowCount()):
            item = self.index(row=i)
            pack: Package = item.data(PACKAGE_ROLE)
            if pack:
                try:
                    packs.add(pack)
                except AttributeError:
                    continue
        return packs

    def openedFiles(self):
        files = set([pack.file for pack in self.openedPacks()])
        return files

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._getFgColor(index)
        elif role == OPENED_PACKS_ROLE:
            return self.openedPacks()
        elif role == OPENED_FILES_ROLE:
            return self.openedFiles()
        else:
            return super(PacksTable, self).data(index, role)

    def addItem(
        self,
        obj: Union[Package, "SubmodelElement", Iterable],
        parent: QModelIndex = QModelIndex(),
        row: int = None,
    ):
        itemIndex = super().addItem(obj, parent, row)
        if isinstance(obj, Package):
            self.watchPackage(obj)
        return itemIndex

    def editCommand(self, index: QModelIndex, value) -> Command | None:
        if index.data(COLUMN_NAME_ROLE) not in DEFAULT_COLUMNS_IN_PACKS_TABLE:
            owner = index.data(OBJECT_ROLE)
            attribute = index.data(COLUMN_NAME_ROLE)
            try:
                typehint = getAttrTypeHint(
                    type(owner), attribute, delOptional=False
                )
            except KeyError:
                typehint = None
            self._checkClearable(attribute, typehint, value)
            renamed = self.renameCommand(index, owner, attribute, value)
            if renamed is not _NOT_RENAMED:
                return renamed
            command = SetAttribute(
                self._observerFor(index), owner, attribute, value, origin=self
            )
            return None if command.is_noop else command
        return super().editCommand(index, value)

    def _changedObject(self, index: QModelIndex):
        if index.data(COLUMN_NAME_ROLE) not in DEFAULT_COLUMNS_IN_PACKS_TABLE:
            return index.data(OBJECT_ROLE)
        return super()._changedObject(index)

    def _addCommand(
        self,
        obj: Union[Package, "SubmodelElement", Iterable],
        parent: QModelIndex,
        row: int = None,
    ) -> Command | None:
        parentObj = parent.data(OBJECT_ROLE)
        parentObjCls = type(parentObj)
        parentName = parent.data(NAME_ROLE)
        if isinstance(obj, Package):
            return None
        elif parentName in ClassesInfo.packViewAttrs(Package):
            return self._addToPackageCommand(parent, obj)
        elif ClassesInfo.changedParentObject(parentObjCls):  # FIXME: Refactor
            container = getattr(
                parentObj, ClassesInfo.changedParentObject(parentObjCls)
            )
            return AddMember(self._observerFor(parent), container, obj, row)
        else:
            return super()._addCommand(obj, parent, row)

    def _addToPackageCommand(self, parent: QModelIndex, obj) -> Command:
        """Return the command that adds an object or a file to the package"""
        package: Package = parent.data(PACKAGE_ROLE)
        observer = self._observerFor(parent)
        if not isinstance(obj, StoredFile):
            return AddMember(observer, package.objStore, obj)
        store = package.fileStore
        state = obj.storeState()

        def follow(name: str | None):
            # The object that the tree shows is the one the user passed in.
            if name is None:
                obj.setFileStore(*state)
            else:
                obj.setFileStore(name, store)

        return AddSupplementaryFile(
            observer,
            store,
            obj.name,
            obj.value,
            obj.mime_type,
            obj,
            follow,
        )

    def _getKwargsForItemInit(
        self, obj: Union[Package, "SubmodelElement", Iterable], parent
    ):
        kwargs = super()._getKwargsForItemInit(obj, parent)
        if isinstance(obj, Package):
            kwargs["parent"] = self._rootItem
            kwargs["new"] = False
        return kwargs

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        flags = super().flags(index)

        if Qt.ItemFlag.ItemIsEditable & flags and not self._isEditable(index):
            flags ^= Qt.ItemFlag.ItemIsEditable
        return flags

    def _isEditable(self, index: QModelIndex):
        objtype = type(index.data(OBJECT_ROLE))
        return not ClassesInfo.isForbiddenToEditInGui(objtype)
