"""Saving and clearing through the package tree view."""

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from tests.factories import make_shell
from tests.factories import make_submodel


@pytest.fixture
def view_support(qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    from aas_workingbench.models import PackTreeViewItem
    from aas_workingbench.models import PacksTable
    from aas_workingbench.package import Package
    from aas_workingbench.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_workingbench.settings.app_settings import (
        DEFAULT_COLUMNS_IN_PACKS_TABLE,
    )
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.treeviews.treeview_pack import PackTreeView
    from aas_workingbench.widgets.messsageBoxes import ErrorMessageBox

    errors: list[str] = []
    windows: list[QWidget] = []

    def fake_exec(box: ErrorMessageBox) -> int:
        errors.append(box.text())
        return 0

    monkeypatch.setattr(ErrorMessageBox, "exec", fake_exec)

    class Support:
        shown_errors = errors

        @staticmethod
        def open_view(*objects):
            columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
            columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
            table = PacksTable(columns, PackTreeViewItem(None, None))
            package = Package()
            for obj in objects:
                package.add(obj)
            table.addItem(package)
            # The view reports its modified state to its window.
            window = QWidget()
            qtbot.addWidget(window)
            windows.append(window)  # keeps the window and its view alive
            view = PackTreeView(window)
            view.setModelWithProxy(table)
            return view, package

        @staticmethod
        def find(table, name: str, parent):
            for row in range(table.rowCount(parent)):
                index = table.index(row, 0, parent)
                if index.data(NAME_ROLE) == name:
                    return index
            raise LookupError(name)

    return Support


def test_save_says_why_and_keeps_running_when_the_folder_is_gone(
    view_support, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtWidgets import QMessageBox

    said: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: said.append(box.text()) or 0
    )
    view, package = view_support.open_view(make_submodel())
    unwritable = tmp_path / "missing folder" / "package.json"

    saved = view.savePack(package, unwritable.as_posix())

    assert saved is False
    assert len(said) == 1
    assert f"The folder {unwritable.parent} does not exist." in said[0]
    assert "Your changes are still in the editor" in said[0]
    assert view_support.shown_errors == []
    assert not unwritable.exists()


def test_save_shows_error_and_keeps_running_when_the_file_type_is_wrong(
    view_support, tmp_path: Path
) -> None:
    view, package = view_support.open_view(make_submodel())
    unwritable = tmp_path / "package.txt"

    saved = view.savePack(package, unwritable.as_posix())

    assert saved is False
    assert len(view_support.shown_errors) == 1
    assert "Package couldn't be saved" in view_support.shown_errors[0]
    assert "package.txt" in view_support.shown_errors[0]
    assert not unwritable.exists()


def test_save_writes_file_when_file_can_be_written(
    view_support, tmp_path: Path
) -> None:
    view, package = view_support.open_view(make_submodel())
    target = tmp_path / "package.json"

    saved = view.savePack(package, target.as_posix())

    assert saved is True
    assert target.is_file()
    assert view_support.shown_errors == []


def test_clear_refuses_with_error_when_attribute_is_mandatory(
    view_support,
) -> None:

    shell = make_shell(id_short="Shell")
    asset_information = shell.asset_information
    view, _ = view_support.open_view(shell)
    table = view.sourceModel()
    shells = view_support.find(table, "shells", table.index(0, 0))
    shell_index = view_support.find(table, "Shell", shells)
    column = [
        table.headerData(
            section, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        )
        for section in range(table.columnCount())
    ].index("asset_information")
    cell = view.model().mapFromSource(shell_index.siblingAtColumn(column))

    view.onOneItemDelClear(cell)

    assert shell.asset_information is asset_information
    assert len(view_support.shown_errors) == 1
    assert "asset_information" in view_support.shown_errors[0]
