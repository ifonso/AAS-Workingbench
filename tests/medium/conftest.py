"""Fixtures for tests of the Qt item models."""

from collections.abc import Callable
from collections.abc import Iterator
import io
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QAbstractItemModel
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QAbstractItemModelTester
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_submodel
from tests.medium.forms import answering
from tests.medium.forms import Form
from tests.serialization import snapshot


class ModelSupport:
    """Builds the legacy item models over BaSyx objects.

    The Qt modules of `aas_editor` need a `QApplication`, so they are imported
    when a test asks for this support, not at the top of the test module.
    """

    def __init__(self, qtbot: QtBot, qtlog: object) -> None:
        self._qtbot = qtbot
        self._qtlog = qtlog
        self._testers: list[QAbstractItemModelTester] = []

    def pack_table(
        self,
        *objects: model.Identifiable,
        files: dict[str, tuple[bytes, str]] | None = None,
    ):
        """Creates the package tree model with one package of the objects.

        Args:
            objects: What the package holds.
            files: Supplementary files as a mapping from the part name to the
                content and the content type.
        """

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
        for name, (content, content_type) in (files or {}).items():
            package.fileStore.add_file(name, io.BytesIO(content), content_type)
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


@pytest.fixture
def views(qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    """Builds the package tree view and the views of tabs over packages."""
    from aas_editor.models import PackTreeViewItem
    from aas_editor.models import PacksTable
    from aas_editor.package import Package
    from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_editor.settings.app_settings import DEFAULT_COLUMNS_IN_PACKS_TABLE
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.treeviews.treeview_pack import PackTreeView
    from aas_editor.widgets.messsageBoxes import ErrorMessageBox

    errors: list[str] = []

    def fake_exec(box: ErrorMessageBox) -> int:
        errors.append(box.text())
        return 0

    monkeypatch.setattr(ErrorMessageBox, "exec", fake_exec)
    holders: list[QWidget] = []

    class Views:
        shown_errors = errors

        def __init__(self) -> None:
            self.window = QWidget()
            qtbot.addWidget(self.window)
            columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
            columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
            self.table = PacksTable(columns, PackTreeViewItem(None, None))
            self.view = PackTreeView(self.window)
            self.view.setModelWithProxy(self.table)
            self.view.expandAll()
            holders.append(self.window)

        def open_package(
            self,
            *objects: model.Identifiable,
            files: dict[str, tuple[bytes, str]] | None = None,
        ) -> object:
            package = Package()
            for obj in objects:
                package.add(obj)
            for name, (content, content_type) in (files or {}).items():
                package.fileStore.add_file(
                    name, io.BytesIO(content), content_type
                )
            self.table.addItem(package)
            self.view.expandAll()
            return package

        def index(self, *names: str, package: int = 0) -> QModelIndex:
            """Finds an index of the package tree view by a path of names."""
            proxy = self.view.model()
            index = proxy.index(package, 0)
            for name in names:
                for row in range(proxy.rowCount(index)):
                    child = proxy.index(row, 0, index)
                    if child.data(NAME_ROLE) == name:
                        index = child
                        break
                else:
                    raise LookupError(name)
            return index

        def select(self, *indexes: QModelIndex) -> None:
            selection = self.view.selectionModel()
            selection.clear()
            for index in indexes:
                selection.select(
                    index, QItemSelectionModel.SelectionFlag.Select
                )
            selection.setCurrentIndex(
                indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
            )

        def attrs_view(self, *names: str, package: int = 0):
            """Opens the attributes of an item in a view, as a tab does."""
            from aas_editor.treeviews.treeview_detailed import AttrsTreeView

            holder = QWidget()
            qtbot.addWidget(holder)
            holders.append(holder)
            attrs = AttrsTreeView(holder)
            attrs.newPackItem(self.index(*names, package=package))
            return attrs

    return Views


ELEMENT_ID = "Element"
SUBMODEL_PATH = ("submodels", "Submodel")
ELEMENT_PATH = (*SUBMODEL_PATH, ELEMENT_ID)


@pytest.fixture
def lab_class(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """The class of labs: a package with a submodel, and ways to edit it."""
    from aas_editor.dialogs import EditObjDialog
    from aas_editor.package import Package
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.ui.value_editor import ValueEditDialog

    class Lab:
        refusal = ""
        value_dialog = ValueEditDialog

        def __init__(self, *elements: model.SubmodelElement) -> None:
            self.monkeypatch = monkeypatch
            self.shown = views()
            self.submodel = make_submodel(elements=elements)
            self.package = self.shown.open_package(self.submodel)
            self.stack = self.package.commandStack

        def add(
            self,
            fill: Callable[[Form], None],
            *path: str,
            refused: bool = False,
        ) -> None:
            """Adds an element through the add dialog of the item at the path.

            Args:
                fill: Fills the dialog.
                path: The names that lead to the item to add to.
                refused: Whether the editor is expected to refuse the answer.
                    The dialog is then cancelled when it is asked again, and
                    the message is in `shown.shown_errors`.
            """
            parent = self.shown.index(*(path or SUBMODEL_PATH))
            self.shown.select(parent)
            with answering(
                monkeypatch,
                EditObjDialog,
                lambda dialog: fill(Form(dialog)),
                self.shown.shown_errors,
                cancel_when_asked_again=refused,
            ):
                self.shown.view.onAddAct(parent)

        def element(self) -> Any:
            return self.submodel.get_referable(ELEMENT_ID)

        def attrs(self, *names: str):
            """Opens the attributes of an element of the submodel, as a tab does.

            Args:
                names: The names below the submodel. The element that the
                    dialogs make if empty.
            """
            return self.shown.attrs_view(
                *SUBMODEL_PATH, *(names or (ELEMENT_ID,))
            )

        def row(self, attrs, name: str, *children: str) -> QModelIndex:
            """Finds the value cell of an attribute, or of a row below it."""
            proxy = attrs.model()
            index = QModelIndex()
            for wanted in (name, *children):
                for number in range(proxy.rowCount(index)):
                    candidate = proxy.index(number, 0, index)
                    if candidate.data(NAME_ROLE) == wanted:
                        index = candidate
                        break
                else:
                    raise LookupError(wanted)
            return index.siblingAtColumn(1)

        def set(self, attrs, name: str, value: object, *children: str) -> bool:
            from aas_editor.settings.app_settings import DATA_CHANGE_FAILED_ROLE

            index = self.row(attrs, name, *children)
            edited = attrs.model().setData(
                index, value, Qt.ItemDataRole.EditRole
            )
            if not edited:
                self.refusal = attrs.model().data(
                    index, DATA_CHANGE_FAILED_ROLE
                )
            return edited

        def edit_in_dialog(
            self,
            attrs,
            name: str,
            fill: Callable[[Any], None],
            dialog_class: type = EditObjDialog,
            refused: bool = False,
        ) -> None:
            """Edits an attribute in the dialog that its row opens."""
            index = self.row(attrs, name)
            attrs.setCurrentIndex(index)
            with answering(
                monkeypatch,
                dialog_class,
                fill,
                self.shown.shown_errors,
                cancel_when_asked_again=refused,
            ):
                attrs.onEditCreate(None, index)

        def save_and_reload(self) -> str:
            path = tmp_path / "saved.aasx"
            self.package.write(path)
            return snapshot(Package(path).objStore)

    return Lab


@pytest.fixture
def lab(lab_class):
    """A package with an empty submodel, and ways to add and edit elements."""
    return lab_class()
