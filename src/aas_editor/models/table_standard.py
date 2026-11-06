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
from typing import Any, Callable, Iterable, Union, AbstractSet, List

from collections.abc import MutableMapping

from basyx.aas.model import (
    AASConstraintViolation,
    Identifiable,
    LangStringSet,
    NamespaceSet,
    Referable,
)
from PyQt6.QtCore import (
    QAbstractItemModel,
    QVariant,
    QModelIndex,
    Qt,
    QItemSelection,
    QSize,
    QPersistentModelIndex,
    pyqtSignal,
)
from PyQt6.QtGui import QFont

from aas_editor.application.changes import Change, ChangeKind, observer_for
from aas_editor.application.commands import Command, ReadOnlyError
from aas_editor.application.editing import edit_mode
from aas_editor.application.edits import (
    AddMember,
    RemoveMember,
    ReplaceMember,
    SetAttribute,
    SetValueType,
)
from aas_editor.application.listeners import Subscription
from aas_editor.domain.containers import is_list_like
from aas_editor.domain.language_tags import check_language_tag
from aas_editor.domain.list_settings import fixed_attribute_hint
from aas_editor.domain.typed_values import (
    is_value_attr,
    is_value_type_attr,
    prepare_edit,
)
from aas_editor.domain.value_types import InvalidValueError
from aas_editor.application.operations.rename import RenameCommand
from aas_editor.application.operations.rename import RenameError
from aas_editor.application.operations.rename import ReplaceIdentifiable
from aas_editor.models import StandardItem
from aas_editor.package import Package
from aas_editor.ui.reference_actions import EditCancelled
from aas_editor.ui.reference_actions import rename_command
from aas_editor.ui.reference_actions import replace_command
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
    UPDATE_ROLE,
    TYPE_HINT_COLUMN,
    COLUMN_NAME_ROLE,
    LINKED_ITEM_ROLE,
    COPY_ROLE,
    EDIT_TARGET_ROLE,
)
from aas_editor.settings import NOT_GIVEN
from aas_editor.settings.colors import LINK_BLUE, CHANGED_BLUE, NEW_GREEN
from aas_editor.utils.util import actualizeAASParents

from aas_editor.utils.util_classes import ClassesInfo
from aas_editor.additional.classes import DictItem
from aas_editor.utils.util_type import getArgs, isIterable


def isMemberContainer(obj) -> bool:
    """Tell whether an object holds members that are edited as a whole.

    That is a list, which includes the ConstrainedList of the supplemental
    semantic ids, a set, or a mapping like a LangStringSet.
    """
    return is_list_like(obj) or isinstance(obj, (AbstractSet, MutableMapping))


# Why a change is refused, in words the user can read. A view shows the message
# of such an error as it is, without the traceback of an unexpected failure.
REFUSALS = (
    ReadOnlyError,
    InvalidValueError,
    AASConstraintViolation,
    RenameError,
)

# What `renameCommand` returns for an edit that is no rename.
_NOT_RENAMED = object()


class StandardTable(QAbstractItemModel):
    currFont = QFont(DEFAULT_FONT)

    # The undo history or the saved state of a package that the model shows
    # changed, so views refresh their actions and the modified flag.
    historyChanged = pyqtSignal()

    def __init__(self, columns=("Item",), rootItem: StandardItem = None):
        super(StandardTable, self).__init__()
        self._rootItem = rootItem
        self._columns = columns
        self.lastErrorMsg = ""
        self.changedItems: List[QModelIndex] = []
        self._changeSubscriptions: dict[int, tuple[Subscription, ...]] = {}

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

        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # Read mode (D18): nothing is edited, not even inline. The position of
        # an item in a list is no attribute, so it is never edited.
        if edit_mode().is_editing and not getattr(
            self.objByIndex(index), "readOnly", False
        ):
            flags |= Qt.ItemFlag.ItemIsEditable
        return flags

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

        An AAS object is added by a command, so that the add can be undone and
        every model that shows the parent follows it. Opening a package is no
        edit and has no command.

        :param row: position among the siblings, None appends
        :return: the index of the new row, invalid if it is not shown
        """
        parent = parent.siblingAtColumn(0)
        command = self._addCommand(obj, parent, row)
        if command is None:
            itemInitKwargs = self._getKwargsForItemInit(obj, parent)
            return self._addItem(parent, itemInitKwargs, row)
        self._run(parent, command)
        return self._indexShowing(parent, obj)

    def _getKwargsForItemInit(
        self, obj: Union[Package, "SubmodelElement", Iterable], parent
    ):
        parentItem = self.objByIndex(parent)
        kwargs = {
            "obj": obj,
            "parent": parentItem,
        }
        return kwargs

    def _addCommand(
        self,
        obj: Union[Package, "SubmodelElement", Iterable],
        parent: QModelIndex,
        row: int = None,
    ) -> Command | None:
        """Return the command that adds obj to the object of the parent item.

        :param row: position in the parent object, None appends
        :return: the command, or None if obj is no AAS object to add, like a
            package that is opened
        :raise AttributeError: if the object of the parent cannot take obj
        """
        parentObj = parent.data(OBJECT_ROLE)
        if isinstance(parentObj, MutableMapping):
            return self._addEntryCommand(parent, parentObj, obj)
        if isinstance(parentObj, AbstractSet) or is_list_like(parentObj):
            return AddMember(self._observerFor(parent), parentObj, obj, row)
        raise AttributeError(
            f"Object couldn't be added: parent obj type is not appendable: {type(parentObj)}"
        )

    def _addEntryCommand(
        self, parent: QModelIndex, mapping: MutableMapping, entry: DictItem
    ) -> Command:
        observer = self._observerFor(parent)
        if entry.key in mapping:
            # The entry replaces the one with the same key, as it always did.
            old = DictItem(entry.key, mapping[entry.key])
            return ReplaceMember(observer, mapping, old, entry)
        return AddMember(observer, mapping, entry)

    def _addItem(self, parent: QModelIndex, itemInitKwargs, row: int = None):
        """Show a new row without changing any AAS object."""
        (item,) = self.insertItems(
            parent, row, lambda: self.itemTyp(**itemInitKwargs)
        )
        return self.index(item.row(), 0, parent)

    def _indexShowing(self, parent: QModelIndex, obj) -> QModelIndex:
        """Return the index of the row of the parent that shows obj"""
        child = self._childShowing(self.objByIndex(parent), obj)
        if child is None:
            return QModelIndex()
        return self.index(child.row(), 0, parent)

    def _observerFor(self, index: QModelIndex):
        """Return the observer of the package behind an item"""
        package = self._packageOf(index)
        if package is None:
            raise AttributeError("The item belongs to no package")
        return observer_for(package)

    def _run(self, index: QModelIndex, command: Command):
        """Apply a command by pushing it on the stack of the package.

        :raise ReadOnlyError: in read mode
        """
        package = self._packageOf(index)
        if package is None:
            raise AttributeError("The item belongs to no package")
        package.commandStack.push(command)

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
        if role == COLUMN_NAME_ROLE:
            column = index.column()
            return self._columns[column]
        if role == LINKED_ITEM_ROLE:
            return self.getLinkedItem(index)
        if role == EDIT_TARGET_ROLE:
            return self.editTarget(index)
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
            except REFUSALS as e:
                self._reportFailure(index, str(e))
            except Exception as e:
                tb = traceback.format_exc()
                self._reportFailure(
                    index,
                    f"Error occurred while adding item to {index.data(NAME_ROLE)}: {e}\n\n{tb}",
                    log=True,
                )
        elif role == CLEAR_ROW_ROLE:
            try:
                parent = index.parent()
                self.clearRow(index.row(), parent, value)
                return True
            except REFUSALS as e:
                self._reportFailure(index, str(e))
            except Exception as e:
                tb = traceback.format_exc()
                self._reportFailure(
                    index,
                    f"{index.data(NAME_ROLE)} could not be deleted or set to default: {e}\n\n{tb}",
                )
        elif role == Qt.ItemDataRole.EditRole:
            try:
                command = self.editCommand(index, value)
                if command is not None:
                    self._run(index, command)
                    # The command named this model as the origin of its first
                    # report, so the model shows the edit by itself.
                    self._syncAfterEdit(index, command)
                    self.setChanged(index)
                    self.update(index)
                return True
            except EditCancelled:
                # The user said no to a question, so this is no failure.
                return False
            except REFUSALS as e:
                self._reportFailure(index, str(e))
            except Exception as e:
                tb = traceback.format_exc()
                self._reportFailure(
                    index,
                    f"Error occurred while setting {getattr(self.objByIndex(index), 'objectName', 'UNKNOWN_OBJECT')}: {e}\n\n{tb}",
                )
        elif role == UPDATE_ROLE:
            self.update(index)
        else:
            raise ValueError(f"Unknown role: {role}")
        return False

    def _reportFailure(self, index: QModelIndex, message: str, log=False):
        """Remember why a change failed, and tell the views"""
        self.lastErrorMsg = message
        if log:
            logging.error(message)
        self.dataChanged.emit(index, index, [DATA_CHANGE_FAILED_ROLE])

    def editCommand(self, index: QModelIndex, value) -> Command | None:
        """Return the command that sets the value of the item.

        :return: the command, or None if the item already has the value
        :raise ValueError: if a mandatory attribute would be cleared
        """
        item = self.objByIndex(index)
        # Only a real None clears a value. The text "None" is ordinary text.
        self._checkClearable(item.objName, item.typehint, value)

        container = self._changedObject(index)
        if isMemberContainer(container):
            # The edited item is a member of the container, not an attribute.
            if isinstance(item.obj, Identifiable) and isinstance(
                value, Identifiable
            ):
                # An object with another id leaves references behind.
                return replace_command(
                    self._packageOf(index), container, item.obj, value, self
                )
            return ReplaceMember(
                self._observerFor(index),
                container,
                item.obj,
                self._checkedMember(container, item.obj, value),
                origin=self,
            )
        return self.attributeCommand(index, container, item.objName, value)

    def editTarget(self, index: QModelIndex):
        """Return the object and the attribute that an edit of the cell sets.

        :return: a tuple of the object and the name of its attribute, or None
            if the cell shows an element of a container or no attribute
        """
        if not index.isValid() or index.column() != VALUE_COLUMN:
            return None
        owner = self._changedObject(index)
        if isMemberContainer(owner):
            return None
        return owner, self.objByIndex(index).objName

    def attributeCommand(
        self, index: QModelIndex, owner, name: str, value
    ) -> Command | None:
        """Return the command that sets an attribute of an object.

        The values of a Property, a Range, a Qualifier, and an Extension follow
        their value type, so text is parsed for it, and a change of the type
        converts the values with it.

        :return: the command, or None if the attribute has the value already
        :raise InvalidValueError: if the value does not fit the value type, or
            the attribute is fixed once the object is made
        """
        if name == "index" and getattr(
            self.objByIndex(index), "readOnly", False
        ):
            raise InvalidValueError(
                "The position of an item in a list cannot be edited."
            )
        renamed = self.renameCommand(index, owner, name, value)
        if renamed is not _NOT_RENAMED:
            return renamed
        fixed = getattr(type(owner), name, None)
        if isinstance(fixed, property) and fixed.fset is None:
            # The SDK sets these only in the constructor, like the type of the
            # children of a SubmodelElementList.
            raise InvalidValueError(
                f"'{name}' cannot be changed after the "
                f"{type(owner).__name__} is made. {fixed_attribute_hint(owner)}"
            )
        observer = self._observerFor(index)
        if is_value_type_attr(owner, name):
            typeCommand = SetValueType(observer, owner, value, origin=self)
            return None if typeCommand.is_noop else typeCommand
        if is_value_attr(owner, name):
            value = prepare_edit(owner, name, value)
        command = SetAttribute(observer, owner, name, value, origin=self)
        return None if command.is_noop else command

    @staticmethod
    def _checkedMember(container, old, value):
        """Return the member to put into a container instead of old, or refuse.

        :raise InvalidValueError: if the language of a text is no language tag,
            is used by another text, or the text is empty
        """
        if isinstance(container, LangStringSet) and isinstance(value, DictItem):
            problem = check_language_tag(value.key)
            if problem:
                raise InvalidValueError(problem)
            taken = value.key in container and (
                not isinstance(old, DictItem) or old.key != value.key
            )
            if taken:
                raise InvalidValueError(
                    f"The language '{value.key}' is used by another text"
                )
            if not value.value:
                raise InvalidValueError(
                    f"The text for the language '{value.key}' cannot be empty"
                )
        return value

    def renameCommand(self, index: QModelIndex, owner, attribute, value):
        """Return the command for an id or idShort edit, with its references.

        An id that another object has is refused. A rename that changes
        references shows a preview first.

        :return: the command, None if nothing changes, or _NOT_RENAMED if the
            edit is no rename
        :raise EditCancelled: if the user cancelled a question
        :raise RenameError: if the value cannot be used
        """
        if (
            attribute not in ("id", "id_short")
            or not isinstance(owner, Referable)
            or not isinstance(value, str)
        ):
            return _NOT_RENAMED
        package = self._packageOf(index)
        if package is None:
            return _NOT_RENAMED
        return rename_command(package, owner, attribute, value, self)

    def _syncAfterEdit(self, index: QModelIndex, command: Command):
        """Make the item show the object that the edit made of it"""
        item = self.objByIndex(index)
        if isinstance(command, (ReplaceMember, ReplaceIdentifiable)):
            item.obj = command.new
        elif isinstance(command, RenameCommand):
            if item.objName == command.name:
                item.obj = getattr(command.owner, command.name)
        elif isinstance(command, SetAttribute) and item.objName == command.name:
            item.obj = getattr(command.owner, command.name)
        elif isinstance(command, SetValueType) and item.objName == "value_type":
            item.obj = command.value_type
            self._syncValueRows(item, command)

    def _syncValueRows(self, item: StandardItem, command: SetValueType):
        """Show the values that a change of the value type converted"""
        for sibling in item.parent().children():
            if sibling.objName in command.value_names:
                sibling.obj = getattr(command.owner, sibling.objName)
                self._emitRowChanged(self._indexOf(sibling))

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
        """Delete rows if they are children of Iterable else set to Default

        Each deleted object is removed by a command, which remembers its
        position. The views follow the change that the command reports.
        """
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
            if isMemberContainer(parentObj):
                # A mapping member is a pair, and the item shows it as such.
                self._run(
                    parent,
                    RemoveMember(
                        self._observerFor(parent), parentObj, child.obj
                    ),
                )
            else:
                if not defaultVal == NOT_GIVEN:
                    index = self.index(currRow, 0, parent)
                    self.setData(index, defaultVal, Qt.ItemDataRole.EditRole)
                elif isinstance(child.obj, Package):
                    # Closing a package is not an edit and cannot be undone
                    # (D9). Its history ends with it.
                    oldValue = child.obj
                    self.removeRow(currRow, parent)
                    self.unwatchPackage(oldValue)
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
        change in the package. It also reports changes of the undo history and
        the saved state with `historyChanged`.
        """
        if package is None or id(package) in self._changeSubscriptions:
            return
        self._changeSubscriptions[id(package)] = (
            observer_for(package).subscribe(self.onModelChange),
            package.commandStack.subscribe(self._onHistoryChanged),
        )

    def unwatchPackage(self, package: Package):
        """Stop following the changes of a package, for example once closed."""
        for subscription in self._changeSubscriptions.pop(id(package), ()):
            subscription.cancel()

    def _onHistoryChanged(self):
        self.historyChanged.emit()

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
