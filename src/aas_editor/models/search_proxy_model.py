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

from collections.abc import Mapping, Set
from typing import List, Any, Optional

from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from basyx.aas.model import AbstractObjectStore
from basyx.aas.model import NamespaceSet
from basyx.aas.model.concept import ConceptDescription

from PyQt6.QtCore import (
    QSortFilterProxyModel,
    QModelIndex,
    Qt,
    QPersistentModelIndex,
    QObject,
    QAbstractItemModel,
    QRegularExpression,
)

from aas_editor.domain.concept_order import ConceptOrder, sort_key
from aas_editor.settings.app_settings import OBJECT_ROLE


def hasSavedOrder(obj: Any) -> bool:
    """Tell whether the rows below an object follow an order that is saved.

    The elements of a submodel, the items of a list, the variables of an
    operation and the attributes of an object do. So do the qualifiers and
    extensions of an element, which the SDK keeps in a `NamespaceSet` that
    remembers the order of insertion. The members of another set, an object
    store or a file container have none, so the tree orders them by name.

    A tab names an entry of such a set by its key, such as the type of a
    qualifier, so sorting it by name would show another order than the file.
    """
    if isinstance(obj, NamespaceSet):
        return True
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
        # How concept descriptions are listed, which the user can change. It
        # changes the view only (decision D16).
        self._conceptOrder = ConceptOrder.NAME
        self._conceptRanks: Mapping[str, int] = {}
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

    def setConceptOrder(
        self, order: ConceptOrder, ranks: Optional[Mapping[str, int]] = None
    ) -> None:
        """Choose how the concept descriptions are listed.

        :param order: the order of the view, which never changes the package
        :param ranks: for the first use order, the rank of each description
        """
        self._conceptOrder = order
        self._conceptRanks = dict(ranks or {})
        self.invalidate()

    def conceptOrder(self) -> ConceptOrder:
        """Tell how the concept descriptions are listed."""
        return self._conceptOrder

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        if self._natural:
            first, second = left.data(OBJECT_ROLE), right.data(OBJECT_ROLE)
            if isinstance(first, ConceptDescription) and isinstance(
                second, ConceptDescription
            ):
                # The set of the package has no order, so the view decides.
                return sort_key(
                    self._conceptOrder, first, self._conceptRanks
                ) < sort_key(self._conceptOrder, second, self._conceptRanks)
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

            # Save the rows that match in this column. With recursive
            # filtering the proxy also shows the parents of a match, so each
            # row is asked itself, and a parent kept for its children is not
            # counted as a match.
            for index in self.iterItems():
                srcIndex = self.mapToSource(index.siblingAtColumn(column))
                if self._matchesItself(srcIndex):
                    foundItems.append(QPersistentModelIndex(srcIndex))

        if not filter:
            self.show_all_items()

        foundItems = [
            QPersistentModelIndex(self.mapFromSource(QModelIndex(i)))
            for i in foundItems
        ]
        return foundItems

    def _matchesItself(self, srcIndex: QModelIndex) -> bool:
        """Tell whether a row matches the filter, not only a row below it."""
        return QSortFilterProxyModel.filterAcceptsRow(
            self, srcIndex.row(), srcIndex.parent()
        )

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
