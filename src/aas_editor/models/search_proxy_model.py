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

from collections.abc import Set
from typing import List, Any, Optional

from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from basyx.aas.model import AbstractObjectStore

from PyQt6.QtCore import (
    QSortFilterProxyModel,
    QModelIndex,
    Qt,
    QPersistentModelIndex,
    QObject,
    QAbstractItemModel,
    QRegularExpression,
)

from aas_editor.settings.app_settings import OBJECT_ROLE


def hasSavedOrder(obj: Any) -> bool:
    """Tell whether the rows below an object follow an order that is saved.

    The elements of a submodel, the items of a list, the variables of an
    operation and the attributes of an object do. The members of a set, an
    object store or a file container have none, so the tree orders them by
    name.
    """
    return not isinstance(
        obj, (Set, AbstractObjectStore, AbstractSupplementaryFileContainer)
    )


class SearchProxyModel(QSortFilterProxyModel):
    def __init__(
        self,
        sourceModel: QAbstractItemModel = None,
        parent: Optional[QObject] = None,
    ):
        super(SearchProxyModel, self).__init__(parent)
        # Natural order: levels with a saved order show it, the others are
        # sorted by name. A click on a column header sorts every level.
        self._natural = True
        super().sort(0, Qt.SortOrder.AscendingOrder)
        if sourceModel:
            self.setSourceModel(sourceModel)

    def sort(
        self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder
    ) -> None:
        # A column below zero is the natural order, which the header selects
        # when no column is sorted (decision D16).
        self._natural = column < 0
        if self._natural:
            super().sort(0, Qt.SortOrder.AscendingOrder)
        else:
            super().sort(column, order)
        # Qt skips a sort by the column and order it has already, which is the
        # case when the natural order is the sort of column 0.
        self.invalidate()

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if self._natural and hasSavedOrder(
            left.parent().data(OBJECT_ROLE) if left.parent().isValid() else None
        ):
            # The rows keep the order of the source. Comparing their rows,
            # not calling them equal, also places a row that is added or put
            # back in the middle where it belongs.
            return left.row() < right.row()
        return super().lessThan(left, right)

    def isNaturalOrder(self) -> bool:
        """Tell whether no column is sorted by the user."""
        return self._natural

    def match(
        self,
        start: QModelIndex,
        role: int,
        value: Any,
        hits: int = ...,
        flags: Qt.MatchFlag = ...,
    ) -> List[QModelIndex]:
        # The source knows nothing about the indexes of the proxy.
        start = self.mapToSource(start)
        items = self.sourceModel().match(start, role, value, hits, flags)
        return [self.mapFromSource(item) for item in items]

    def search(
        self,
        pattern: str,
        filterColumns: List[int],
        regExp: bool = True,
        filter: bool = False,
        matchCase: bool = False,
    ) -> List[QPersistentModelIndex]:
        foundItems = []
        if not pattern:
            self.show_all_items()
            return foundItems

        if matchCase:
            self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        else:
            self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        if regExp:
            self.setFilterRegularExpression(QRegularExpression(pattern))
        else:
            self.setFilterFixedString(pattern)

        for column in filterColumns:
            self.setFilterKeyColumn(column)

            # save found items in column
            for index in self.iterItems():
                srcIndex = self.mapToSource(index.siblingAtColumn(column))
                foundItems.append(QPersistentModelIndex(srcIndex))

        if not filter:
            self.show_all_items()

        foundItems = [
            QPersistentModelIndex(self.mapFromSource(QModelIndex(i)))
            for i in foundItems
        ]
        return foundItems

    def show_all_items(self):
        self.setFilterRegularExpression(QRegularExpression(""))

    def iterItems(self, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        def recurse(parent: QModelIndex):
            for row in range(self.rowCount(parent)):
                childIndex = self.index(row, 0, parent)
                yield childIndex
                if self.rowCount(childIndex):
                    yield from recurse(childIndex)

        yield from recurse(parent)
