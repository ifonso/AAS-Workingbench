#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import copy
import logging
import traceback
from collections import namedtuple, deque
from typing import Any, Callable, Iterable, Union, AbstractSet, List

from basyx.aas.model import NamespaceSet, Referable
from PyQt6.QtCore import (
    QAbstractItemModel,
    QVariant,
    QModelIndex,
    Qt,
    QItemSelection,
    QSize,
    QPersistentModelIndex,
)
from PyQt6.QtGui import QFont

from aas_editor.application.changes import Change, ChangeKind, observer_for
from aas_editor.application.listeners import Subscription
from aas_editor.domain import ordering
from aas_editor.models import StandardItem
from aas_editor.package import Package
from aas_editor.settings.app_settings import (
    NAME_ROLE,
    OBJECT_ROLE,
    ATTRIBUTE_COLUMN,
    VALUE_COLUMN,
    PACKAGE_ROLE,
    PACK_ITEM_ROLE,
    DEFAULT_FONT,
    ADD_ITEM_ROLE,
    CLEAR_ROW_ROLE,
    DATA_CHANGE_FAILED_ROLE,
    IS_LINK_ROLE,
    TYPE_COLUMN,
    TYPE_CHECK_ROLE,
    TYPE_ROLE,
    UNDO_ROLE,
    REDO_ROLE,
    MAX_UNDOS,
    UPDATE_ROLE,
    TYPE_HINT_COLUMN,
    COLUMN_NAME_ROLE,
    LINKED_ITEM_ROLE,
    COPY_ROLE,
)
from aas_editor.settings import NOT_GIVEN
from aas_editor.settings.colors import LINK_BLUE, CHANGED_BLUE, NEW_GREEN
from aas_editor.utils.util import actualizeAASParents

from aas_editor.utils.util_classes import ClassesInfo
from aas_editor.additional.classes import DictItem
from aas_editor.utils.util_type import getArgs, isIterable

SetDataItem = namedtuple("SetDataItem", ("index", "value", "role"))


class StandardTable(QAbstractItemModel):
    currFont = QFont(DEFAULT_FONT)

    def __init__(self, columns=("Item",), rootItem: StandardItem = None):
        super(StandardTable, self).__init__()
        self._rootItem = rootItem
        self._columns = columns
        self.lastErrorMsg = ""
        self.undo: deque[SetDataItem] = deque(maxlen=MAX_UNDOS)
        self.redo: List[SetDataItem] = []
        self.changedItems: List[QModelIndex] = []
        self._changeSubscriptions: dict[int, Subscription] = {}

    def index(
        self, row: int, column: int = 0, parent: QModelIndex = QModelIndex()
    ) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()
        parentObj = self.objByIndex(parent)
        return self.createIndex(row, column, parentObj.children()[row])

    def parent(self, child: QModelIndex) -> QModelIndex:
        if not child.isValid():
            return QModelIndex()

        try:
            childObj = self.objByIndex(child)
            parentObj = childObj.parent()
        except (RuntimeError, AttributeError) as e:
            logging.exception(e)
            return QModelIndex()

        if parentObj == self._rootItem or not parentObj:
            return QModelIndex()

        grandParentObj = parentObj.parent()
        row = grandParentObj.children().index(parentObj)
        return self.createIndex(row, 0, parentObj)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        # Only the first column of an item has children (Qt model contract).
        if parent.isValid() and parent.column() > 0:
            return 0
        return len(self.objByIndex(parent).children())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._columns)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = ...
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._columns[section]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if (
            not index.isValid()
            or index.data(Qt.ItemDataRole.DisplayRole) is None
        ):
            return Qt.ItemFlag.NoItemFlags

        if index.column() in (TYPE_COLUMN, TYPE_HINT_COLUMN):
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

        return (
            Qt.ItemFlag.ItemIsEditable
            | Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
        )

    def hasChildren(self, parent: QModelIndex = ...) -> bool:
        return True if self.rowCount(parent) else False

    def objByIndex(self, index: QModelIndex):
        if not index.isValid():
            return self._rootItem
        return index.internalPointer()

    def iterItems(self, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        def recurse(parent: QModelIndex):
            for row in range(self.rowCount(parent)):
                childIndex = self.index(row, 0, parent)
                yield childIndex
                child = self.objByIndex(childIndex)
                if child.children():
                    yield from recurse(childIndex)

        yield from recurse(parent)

    def match(
        self,
        start: QModelIndex,
        role: int,
        value: Any,
        hits: int = ...,
        flags: Qt.MatchFlag = ...,
    ) -> List[QModelIndex]:
        kwargs = {}
        if hits is not ...:
            kwargs["hits"] = hits
        if flags is not ...:
            kwargs["flags"] = flags

        if role == OBJECT_ROLE and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if (item.data(OBJECT_ROLE) is value) or (
                        item.data(OBJECT_ROLE) == value
                    ):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        elif role == TYPE_ROLE and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if issubclass(value, item.data(TYPE_ROLE)):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        elif role == Qt.ItemDataRole.DisplayRole and hits != 0:
            res = []
            for item in self.iterItems(start):
                logging.info("match for: %s", item.data(NAME_ROLE))
                try:
                    if value == item.data(Qt.ItemDataRole.DisplayRole):
                        res.append(item)
                except AttributeError:
                    continue
                if hits == len(res):
                    break
            return res
        else:
            return super(StandardTable, self).match(
                start, role, value, **kwargs
            )

    def addItem(
        self,
        obj: Union[Package, "SubmodelElement", Iterable],
        parent: QModelIndex = QModelIndex(),
        row: int = None,
    ):
        """Add obj to the parent object and show it as a row of the parent.

        :param row: position among the siblings, None appends
        """
        parent = parent.siblingAtColumn(0)
        container = self._addItemObjToParentObj(obj, parent, row)
        itemInitKwargs = self._getKwargsForItemInit(obj, parent)
        itemIndex = self._addItem(parent, itemInitKwargs, row)
        self._publishAdded(parent, container, obj)
        return itemIndex

    def _getKwargsForItemInit(
        self, obj: Union[Package, "SubmodelElement", Iterable], parent
    ):
        parentItem = self.objByIndex(parent)
        kwargs = {
            "obj": obj,
            "parent": parentItem,
        }
        return kwargs

    def _addItemObjToParentObj(
        self,
        obj: Union[Package, "SubmodelElement", Iterable],
        parent: QModelIndex,
        row: int = None,
    ):
        """Add obj to the object of the parent item.

        :param row: position in the parent object, None appends
        :return: the container that obj was added to
        """
        parentObj = parent.data(OBJECT_ROLE)
        if isinstance(parentObj, NamespaceSet) and row is not None:
            ordering.insert_at(parentObj, obj, row)
        elif isinstance(parentObj, AbstractSet):
            parentObj.add(obj)
        elif isinstance(parentObj, list):
            if row is None:
                parentObj.append(obj)
            else:
                parentObj.insert(row, obj)
        elif isinstance(parentObj, dict):
            parentObj[obj.key] = obj.value
        else:
            raise AttributeError(
                f"Object couldn't be added: parent obj type is not appendable: {type(parentObj)}"
            )
        return parentObj

    def _addItem(self, parent: QModelIndex, itemInitKwargs, row: int = None):
        (item,) = self.insertItems(
            parent, row, lambda: self.itemTyp(**itemInitKwargs)
        )
        itemIndex = self.index(item.row(), 0, parent)
        self.undo.append(
            SetDataItem(
                index=QPersistentModelIndex(itemIndex),
                value=NOT_GIVEN,
                role=CLEAR_ROW_ROLE,
            )
        )
        self.redo.clear()
        return itemIndex

    def insertItems(
        self,
        parent: QModelIndex,
        row: int,
        create: Callable[[], Any],
    ) -> List[StandardItem]:
        """Show the items that `create` makes as new rows of the parent.

        Rows are the QObject children of the parent item, so `create` builds
        the items with the parent item as their parent, which appends them.
        They are then put at `row` and announced to the views.

        :param parent: index of the parent item, invalid for the root
        :param row: position among the siblings, None appends
        :param create: builds the new items under the parent item
        :return: the new items in the order they were created
        """
        parentItem = self.objByIndex(parent)
        existing = parentItem.children()
        create()
        created = parentItem.children()[len(existing) :]
        if not created:
            return []
        row = len(existing) if row is None else max(0, min(row, len(existing)))
        trailing = existing[row:]
        # The views must hear about rows before they exist, so the new items
        # wait outside of the parent until then.
        for child in created:
            child.setParent(None)
        self.beginInsertRows(parent, row, row + len(created) - 1)
        # Qt appends a child, so the siblings behind the new rows move to the
        # end again after them.
        for child in trailing:
            child.setParent(None)
        for child in created + trailing:
            child.setParent(parentItem)
        self.endInsertRows()
        return created

    def moveRows(
        self,
        sourceParent: QModelIndex,
        sourceRow: int,
        count: int,
        destinationParent: QModelIndex,
        destinationChild: int,
    ) -> bool:
        """Move rows among the children of the same parent.

        Only the order of the rows changes. It follows the order of the AAS
        objects, which the code that moves them changes.

        :param destinationChild: the row to move before, as in Qt
        :return: False if the parent differs or the move would change nothing
        """
        if sourceParent != destinationParent:
            return False
        if not self.beginMoveRows(
            sourceParent,
            sourceRow,
            sourceRow + count - 1,
            destinationParent,
            destinationChild,
        ):
            return False
        parentItem = self.objByIndex(sourceParent)
        children = parentItem.children()
        moved = children[sourceRow : sourceRow + count]
        rest = children[:sourceRow] + children[sourceRow + count :]
        target = (
            destinationChild - count
            if destinationChild > sourceRow
            else destinationChild
        )
        newOrder = rest[:target] + moved + rest[target:]
        first = min(sourceRow, target)
        for child in newOrder[first:]:
            child.setParent(None)
        for child in newOrder[first:]:
            child.setParent(parentItem)
        self.endMoveRows()
        return True

    def moveItem(self, index: QModelIndex, newRow: int) -> bool:
        """Move the row of an item, so that it ends up at `newRow`."""
        parent = index.parent()
        row = index.row()
        newRow = max(0, min(newRow, self.rowCount(parent) - 1))
        if newRow == row:
            return False
        destination = newRow + 1 if newRow > row else newRow
        return self.moveRows(parent, row, 1, parent, destination)

    def update(self, index: QModelIndex):
        """Update item: remove all children rows, then add updated rows"""
        if not index.isValid():
            return False
        index = index.siblingAtColumn(0)
        self._repopulate(index)
        self.dataChanged.emit(
            index, index.siblingAtColumn(self.columnCount() - 1)
        )
        return True

    def _repopulate(self, index: QModelIndex):
        """Replace the rows below an item by new ones read from its object

        :param index: index of the item, invalid for the root item
        """
        item = self.objByIndex(index)
        count = self.rowCount(index)
        if count:
            self.removeRows(0, count, index)
        self.insertItems(index, None, item.populate)

    def data(self, index: QModelIndex, role: int = ...) -> Any:
        if role == Qt.ItemDataRole.ForegroundRole:
            return self._getFgColor(index)
        if role == Qt.ItemDataRole.FontRole:
            return self._getFont(index)
        if role == Qt.ItemDataRole.SizeHintRole:
            fontSize = self.currFont.pointSize()
            return QSize(-1, int((fontSize + 2) * 1.9))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if role == DATA_CHANGE_FAILED_ROLE:
            return self.lastErrorMsg
        if role == UNDO_ROLE:
            return self.undo
        if role == REDO_ROLE:
            return self.redo
        if role == COLUMN_NAME_ROLE:
            column = index.column()
            return self._columns[column]
        if role == LINKED_ITEM_ROLE:
            return self.getLinkedItem(index)
        if role == COPY_ROLE:
            try:
                if index.column() in (ATTRIBUTE_COLUMN, VALUE_COLUMN):
                    objToCopy = index.data(OBJECT_ROLE)
                    objToCopy = copy.deepcopy(objToCopy)  # FIXME
                    actualizeAASParents(
                        objToCopy
                    )  # TODO check if there is a better solution to del aas parents
                    return objToCopy
                elif index.column() in (TYPE_COLUMN, TYPE_HINT_COLUMN):
                    return index.data(Qt.ItemDataRole.DisplayRole)
                else:
                    objToCopy = index.data(Qt.ItemDataRole.EditRole)
                    objToCopy = copy.deepcopy(objToCopy)
                    actualizeAASParents(
                        objToCopy
                    )  # TODO check if there is a better solution to del aas parents
                    return objToCopy
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred copying {index.data(NAME_ROLE)}: {e}\n\n{tb}"
                logging.exception(self.lastErrorMsg)
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        else:
            item = self.objByIndex(index)
            column = index.column()
            return item.data(role, column, column_name=self._columns[column])

    def _getFgColor(self, index: QModelIndex):
        column = index.column()
        # color fg in red if obj type and typehint don't fit
        if index.data(IS_LINK_ROLE):
            return LINK_BLUE
        elif column == ATTRIBUTE_COLUMN:
            if self.objByIndex(index).new:
                return NEW_GREEN
            elif self.objByIndex(index).changed:
                return CHANGED_BLUE
        return QVariant()

    def _getFont(self, index: QModelIndex):
        font = QFont(self.currFont)
        if index.data(IS_LINK_ROLE):
            font.setUnderline(True)
        elif index.column() == ATTRIBUTE_COLUMN:
            font.setBold(True)
            font.setUnderline(True)
        elif index.column() not in (TYPE_COLUMN, TYPE_HINT_COLUMN):
            font.setItalic(True)
        return font

    def getLinkedItem(self, index: QModelIndex) -> QModelIndex:
        if not index.data(IS_LINK_ROLE):
            return QModelIndex()
        try:
            reference = self.data(index, OBJECT_ROLE)
            objStore = self.data(index, PACKAGE_ROLE).objStore
            obj = reference.resolve(objStore)
            (linkedPackItem,) = (
                self.data(index, PACK_ITEM_ROLE)
                .model()
                .match(QModelIndex(), OBJECT_ROLE, obj, hits=1)
            )
            return linkedPackItem
        except AttributeError:
            return QModelIndex()

    def setData(self, index: QModelIndex, value: Any, role: int = ...) -> bool:
        if isinstance(index, QPersistentModelIndex):
            index = QModelIndex(index)
        if not index.isValid() and role not in (
            Qt.ItemDataRole.FontRole,
            ADD_ITEM_ROLE,
            UNDO_ROLE,
            REDO_ROLE,
        ):
            return QVariant()
        elif role == Qt.ItemDataRole.FontRole:
            if isinstance(value, QFont):
                font = QFont(value)
                self.currFont.setPointSize(font.pointSize())
                self.dataChanged.emit(
                    self.index(0), self.index(self.rowCount())
                )
                return True
        elif role == ADD_ITEM_ROLE:
            try:
                self.addItem(value, index)
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred while adding item to {index.data(NAME_ROLE)}: {e}\n\n{tb}"
                logging.exception(self.lastErrorMsg)
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == CLEAR_ROW_ROLE:
            try:
                parent = index.parent()
                self.clearRow(index.row(), parent, value)
                self.dataChanged.emit(parent, parent)
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"{index.data(NAME_ROLE)} could not be deleted or set to default: {e}\n\n{tb}"
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == Qt.ItemDataRole.EditRole:
            try:
                changedObj = self._changedObject(index)
                newValue, oldValue = self.editItem(index, value)
                self.setChanged(index)
                self.update(index)
                self._publish(index, Change.changed(changedObj, origin=self))
                self.undo.append(
                    SetDataItem(
                        index=QPersistentModelIndex(index),
                        value=oldValue,
                        role=role,
                    )
                )
                self.redo.clear()
                return True
            except Exception as e:
                tb = traceback.format_exc()
                self.lastErrorMsg = f"Error occurred while setting {getattr(self.objByIndex(index), 'objectName', 'UNKNOWN_OBJECT')}: {e}\n\n{tb}"
                self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])
        elif role == UNDO_ROLE:
            if value == NOT_GIVEN and self.undo:
                lastUndo: SetDataItem = self.undo.pop()
                tempRedoList = self.redo
                self.redo = []
                if self.setData(*lastUndo):
                    self.redo = tempRedoList
                    self.redo.append(self.undo.pop())
                    return True
            elif isIterable(value):
                self.undo = deque(value)
                return True
        elif role == REDO_ROLE:
            if value == NOT_GIVEN and self.redo:
                lastRedo: SetDataItem = self.redo.pop()
                tempRedoList = self.redo
                self.redo = []
                if self.setData(*lastRedo):
                    self.redo = tempRedoList
                    return True
            elif isIterable(value):
                self.redo = list(value)
                return True
        elif role == UPDATE_ROLE:
            self.update(index)
        else:
            raise ValueError(f"Unknown role: {role}")
        return False

    def editItem(self, index: QModelIndex, value):
        # Only a real None clears a value. The text "None" is ordinary text.
        newValue = value
        item = self.objByIndex(index)
        self._checkClearable(item.objName, item.typehint, newValue)

        parentObj = self._changedObject(index)

        if isinstance(parentObj, list):
            oldValue = item.obj
            objIndex = parentObj.index(item.obj)
            parentObj[objIndex] = newValue
            item.obj = newValue
        elif isinstance(parentObj, NamespaceSet):
            oldValue = item.obj
            # The replacement takes the place of the old element (D19).
            ordering.replace_item(parentObj, item.obj, newValue)
            item.obj = newValue
        elif isinstance(parentObj, AbstractSet):
            oldValue = item.obj
            parentObj.remove(item.obj)
            parentObj.add(newValue)
            item.obj = newValue
        elif isinstance(item.obj, DictItem):
            oldValue: DictItem = item.obj
            item.obj = newValue
            if newValue.key != oldValue.key:
                parentObj.pop(oldValue.key)
            parentObj.update([item.obj])
        else:
            oldValue = getattr(parentObj, item.objName)
            # A value the SDK rejects, such as text for an integer Property,
            # raises here and the edit is refused. The value_type stays as it is.
            self._setAttribute(parentObj, item.objName, newValue)
            item.obj = getattr(parentObj, item.objName)
        return newValue, oldValue

    @staticmethod
    def _setAttribute(obj, name: str, value):
        """Set an attribute, keeping the position when an idShort is renamed.

        The SDK moves a renamed element to the end of its namespace.
        """
        if name == "id_short" and isinstance(obj, Referable):
            ordering.set_id_short(obj, value)
        else:
            setattr(obj, name, value)

    def _changedObject(self, index: QModelIndex):
        """Return the object that an edit of the item changes.

        That is the object that holds the attribute, or the container that
        holds the item if it is an element of a list or a set.
        """
        parentObj = self.objByIndex(index).parentObj
        if (
            ClassesInfo.changedParentObject(type(parentObj))
            and index.parent().isValid()
        ):
            parentObj = getattr(
                parentObj, ClassesInfo.changedParentObject(type(parentObj))
            )
        return parentObj

    @staticmethod
    def _checkClearable(name: str, typehint, newValue):
        """Refuse to set a mandatory attribute to None.

        :raise ValueError if the type hint does not allow None
        """
        if newValue is not None:
            return
        if (
            typehint is None
            or typehint is Any
            or type(None) in getArgs(typehint)
        ):
            return
        raise ValueError(f"'{name}' is mandatory and cannot be cleared")

    def setChanged(self, topLeft: QModelIndex, bottomRight: QModelIndex = None):
        """Set the item and all parents as changed"""
        self._setChanged(True, topLeft, bottomRight)

    def setUnchanged(
        self, topLeft: QModelIndex, bottomRight: QModelIndex = None
    ):
        self._setChanged(False, topLeft, bottomRight)

    def _setChanged(
        self, changed: bool, topLeft: QModelIndex, bottomRight: QModelIndex
    ):
        bottomRight = topLeft if bottomRight is None else bottomRight
        if topLeft.isValid() and bottomRight.isValid():
            selection = QItemSelection(topLeft, bottomRight)
            for index in selection.indexes():
                self.objByIndex(index).changed = changed
                if changed:
                    self.changedItems.append(index)
                else:
                    self.changedItems.append(index)

                if index.parent().isValid():
                    self.setChanged(index.parent())
                else:
                    packItem: QModelIndex = index.data(PACK_ITEM_ROLE)
                    if packItem and packItem.isValid():
                        packItem.model().dataChanged.emit(packItem, packItem)

    def removeRows(
        self, row: int, count: int, parent: QModelIndex = ...
    ) -> bool:
        parentItem = self.objByIndex(parent)

        self.beginRemoveRows(parent, row, row + count - 1)
        for n in range(count):
            child = parentItem.children()[row]
            child.setParent(None)
            # child.deleteLater()
        self.endRemoveRows()
        return True

    def clearRows(
        self,
        row: int,
        count: int,
        parent: QModelIndex = ...,
        defaultVal=NOT_GIVEN,
    ) -> bool:
        """Delete rows if they are children of Iterable else set to Default"""
        parentItem = self.objByIndex(parent)
        parentObj = parentItem.data(OBJECT_ROLE)

        # if parentObj is Submodel and the parentObj is not rootItem
        # set submodel_element as parentObj
        if parent.isValid():
            try:
                parentAttr = ClassesInfo.changedParentObject(type(parentObj))
                parentObj = getattr(parentObj, parentAttr)
            except AttributeError:
                pass

        for currRow in range(row + count - 1, row - 1, -1):
            child = parentItem.children()[currRow]
            if isinstance(parentObj, (list, dict, AbstractSet)):
                if isinstance(parentObj, list):
                    oldValue = parentObj.pop(currRow)
                elif isinstance(parentObj, dict):
                    oldValue: DictItem = child.data(OBJECT_ROLE)
                    parentObj.pop(oldValue.key)
                elif isinstance(parentObj, AbstractSet):
                    parentObj.discard(child.obj)
                    oldValue = child.obj
                else:
                    raise TypeError(
                        f"Unknown parent object type: "
                        f"object could not be deleted or set to default: "
                        f"{type(parentObj)}"
                    )
                self.removeRow(currRow, parent)
                self._publishRemoved(parent, parentObj, oldValue, currRow)
                self.undo.append(
                    SetDataItem(
                        index=QPersistentModelIndex(parent),
                        value=oldValue,
                        role=ADD_ITEM_ROLE,
                    )
                )
                self.redo.clear()
            else:
                if not defaultVal == NOT_GIVEN:
                    index = self.index(currRow, 0, parent)
                    self.setData(index, defaultVal, Qt.ItemDataRole.EditRole)
                elif isinstance(child.obj, Package):
                    # close package
                    oldValue = child.obj
                    self.removeRow(currRow, parent)
                    self.unwatchPackage(oldValue)
                    self.undo.append(
                        SetDataItem(
                            index=QPersistentModelIndex(parent),
                            value=oldValue,
                            role=ADD_ITEM_ROLE,
                        )
                    )
                    self.redo.clear()
                else:
                    raise TypeError(
                        f"Unknown parent object type: "
                        f"object could not be deleted or set to default: "
                        f"{type(parentObj)}"
                    )
        return True

    def clearRow(
        self, row: int, parent: QModelIndex = ..., defaultVal=NOT_GIVEN
    ) -> bool:
        """Delete row if it is child of Iterable else set to Default"""
        return self.clearRows(row, 1, parent, defaultVal)

    # Following the changes that other models and commands report

    def watchPackage(self, package: Package):
        """Follow the changes that are reported for the objects of a package.

        The model then shows what other models, such as the ones of other tabs,
        change in the package.
        """
        if package is None or id(package) in self._changeSubscriptions:
            return
        self._changeSubscriptions[id(package)] = observer_for(
            package
        ).subscribe(self.onModelChange)

    def unwatchPackage(self, package: Package):
        """Stop following the changes of a package, for example once closed."""
        subscription = self._changeSubscriptions.pop(id(package), None)
        if subscription:
            subscription.cancel()

    def onModelChange(self, change: Change):
        """Show a change that the model has not made itself.

        Changes are named by their AAS objects. This looks for the items that
        show these objects, and updates them without touching the others.
        """
        if change.origin is self:
            return
        if change.kind is ChangeKind.CHANGED:
            self._onObjectChanged(change.target)
        else:
            self._onContainerChanged(change)

    def _onObjectChanged(self, target):
        items = list(self._allItems())
        for item in items:
            # The index costs more than the test, so it is made only for hits.
            if item.obj is not target and item.containerObj is not target:
                continue
            index = self._indexOf(item)
            if index is None:
                continue
            if item.obj is target:
                if item.repopulatesOnChange:
                    self._repopulate(index)
                if index.isValid():
                    self._emitRowChanged(index)
                self._refreshAncestors(item)
            elif item.containerObj is target:
                # The elements of the container changed, like after a replace.
                self._repopulate(index)

    def _onContainerChanged(self, change: Change):
        for item in list(self._allItems()):
            if (
                item.obj is not change.parent
                and item.containerObj is not change.parent
            ):
                continue
            index = self._indexOf(item)
            if index is None:
                continue
            if not item.supportsIncrementalRows:
                self._repopulate(index)
                continue
            if change.kind is ChangeKind.ADDED:
                self._showAdded(item, index, change)
            else:
                child = self._childShowing(item, change.target)
                if child is None:
                    continue
                if change.kind is ChangeKind.REMOVED:
                    self.removeRows(child.row(), 1, index)
                elif change.index is not None:
                    self.moveItem(self._indexOf(child), change.index)

    def _showAdded(
        self, item: StandardItem, index: QModelIndex, change: Change
    ):
        target = change.target
        if not item.acceptsChild(target) or self._childShowing(item, target):
            return
        self.insertItems(
            index, change.index, lambda: item.createChildFor(target)
        )

    @staticmethod
    def _childShowing(item: StandardItem, obj):
        for child in item.children():
            if child.obj is obj:
                return child
        return None

    def _allItems(self):
        """Iterate over all items of the model, the root item first."""
        stack = [self._rootItem]
        while stack:
            item = stack.pop()
            yield item
            stack.extend(reversed(item.children()))

    def _indexOf(self, item: StandardItem):
        """Return the index of the item, None if it is not in the model"""
        if item is self._rootItem:
            return QModelIndex()
        top = item
        while top.parent() is not None:
            top = top.parent()
        if top is not self._rootItem:
            return None
        return self.createIndex(item.row(), 0, item)

    def _emitRowChanged(self, index: QModelIndex):
        self.dataChanged.emit(
            index.siblingAtColumn(0),
            index.siblingAtColumn(self.columnCount() - 1),
        )

    def _refreshAncestors(self, item: StandardItem):
        """Tell the views that the rows above an item show other values now"""
        ancestor = item.parent()
        while ancestor is not None and ancestor is not self._rootItem:
            self._emitRowChanged(self._indexOf(ancestor))
            ancestor = ancestor.parent()

    def _packageOf(self, index: QModelIndex):
        try:
            return index.data(PACKAGE_ROLE)
        except AttributeError:
            return None

    def _publish(self, index: QModelIndex, change: Change):
        """Report a change to the other models of the package of an item"""
        package = self._packageOf(index)
        if package is not None:
            observer_for(package).notify(change)

    def _publishAdded(self, parent: QModelIndex, container, obj):
        if container is None:
            return
        if isinstance(container, dict):
            change = Change.changed(container, origin=self)
        else:
            change = Change.added(
                container, obj, self._positionIn(container, obj), self
            )
        self._publish(parent, change)

    def _publishRemoved(self, parent: QModelIndex, container, obj, row: int):
        if isinstance(container, dict) or isinstance(obj, DictItem):
            change = Change.changed(container, origin=self)
        else:
            change = Change.removed(container, obj, row, self)
        self._publish(parent, change)

    @staticmethod
    def _positionIn(container, obj):
        """Return the position of obj in an ordered container, else None"""
        if isinstance(container, AbstractSet) and not isinstance(
            container, NamespaceSet
        ):
            return None
        for position, member in enumerate(container):
            if member is obj:
                return position
        return None
