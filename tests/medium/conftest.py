"""Fixtures for tests of the Qt item models."""

from collections.abc import Iterator

from basyx.aas import model
from PyQt6.QtCore import QAbstractItemModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QAbstractItemModelTester
import pytest
from pytestqt.qtbot import QtBot


class ModelSupport:
    """Builds the legacy item models over BaSyx objects.

    The Qt modules of `aas_editor` need a `QApplication`, so they are imported
    when a test asks for this support, not at the top of the test module.
    """

    def __init__(self, qtbot: QtBot, qtlog: object) -> None:
        self._qtbot = qtbot
        self._qtlog = qtlog
        self._testers: list[QAbstractItemModelTester] = []

    def pack_table(self, *objects: model.Identifiable):
        """Creates the package tree model with one package of the objects."""
        from aas_editor.models import PackTreeViewItem
        from aas_editor.models import PacksTable
        from aas_editor.package import Package
        from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
        from aas_editor.settings.app_settings import (
            DEFAULT_COLUMNS_IN_PACKS_TABLE,
        )

        columns: list[str] = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
        columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
        table = PacksTable(columns, PackTreeViewItem(None, None))
        package = Package()
        for obj in objects:
            package.add(obj)
        table.addItem(package)
        return table

    def package_of(self, table: QAbstractItemModel):
        """Returns the one package that a package tree model shows."""
        from aas_editor.settings.app_settings import PACKAGE_ROLE

        return table.index(0, 0).data(PACKAGE_ROLE)

    def detail_table(self, pack_table: QAbstractItemModel, *names: str):
        """Creates the model of a tab that shows the item found by its names."""
        from aas_editor.models import DetailedInfoTable

        index = self.find_path(pack_table, "", *names)
        return DetailedInfoTable(index)

    def find_path(
        self, table: QAbstractItemModel, first: str, *names: str
    ) -> QModelIndex:
        """Walks from the package item down through the named children."""
        index = table.index(0, 0)
        for name in [first, *names] if first else names:
            index = self.find(table, name, index)
        return index

    def find(
        self,
        table: QAbstractItemModel,
        name: str,
        parent: QModelIndex | None = None,
    ) -> QModelIndex:
        """Finds the child of a parent by the name in the first column."""
        from aas_editor.settings.app_settings import NAME_ROLE

        parent = parent if parent is not None else QModelIndex()
        for row in range(table.rowCount(parent)):
            index = table.index(row, 0, parent)
            if index.data(NAME_ROLE) == name:
                return index
        raise LookupError(f"No item named '{name}'")

    def names(
        self, table: QAbstractItemModel, parent: QModelIndex | None = None
    ) -> list[str]:
        """Lists the names of the children of a parent, in row order."""
        from aas_editor.settings.app_settings import NAME_ROLE

        parent = parent if parent is not None else QModelIndex()
        return [
            table.index(row, 0, parent).data(NAME_ROLE)
            for row in range(table.rowCount(parent))
        ]

    def column(self, table: QAbstractItemModel, name: str) -> int:
        """Returns the number of the column with the given header text."""
        return [
            table.headerData(
                section,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            for section in range(table.columnCount())
        ].index(name)

    def watch(self, table: QAbstractItemModel) -> None:
        """Checks the model against the Qt model contract from now on.

        Qt reports violations as warnings of the Qt log, and `violations`
        returns them.
        """
        self._testers.append(
            QAbstractItemModelTester(
                table, QAbstractItemModelTester.FailureReportingMode.Warning
            )
        )

    def violations(self) -> list[str]:
        """Returns the contract violations that the testers found so far."""
        self._qtbot.wait(1)  # lets queued checks of the testers run
        return [
            record.message
            for record in self._qtlog.records  # type: ignore[attr-defined]
            if record.message.startswith("FAIL!")
        ]


@pytest.fixture
def model_support(
    qapp: object, qtbot: QtBot, qtlog: object
) -> Iterator[ModelSupport]:
    """Provides builders and contract checks for the item models."""
    yield ModelSupport(qtbot, qtlog)
