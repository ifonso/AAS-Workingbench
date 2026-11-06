"""Editing values through the item models (`editItem` and `setData`)."""

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest

from tests.factories import make_asset_information
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel


@pytest.fixture
def edit_support(qapp: object):
    """Imports the models once the QApplication exists."""
    from aas_editor.models import DetailedInfoTable
    from aas_editor.models import PackTreeViewItem
    from aas_editor.models import PacksTable
    from aas_editor.package import Package
    from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_editor.settings.app_settings import DEFAULT_COLUMNS_IN_PACKS_TABLE
    from aas_editor.settings.app_settings import NAME_ROLE

    class Support:
        name_role = NAME_ROLE

        @staticmethod
        def pack_table(*objects: model.Identifiable) -> PacksTable:
            columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
            columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
            table = PacksTable(columns, PackTreeViewItem(None, None))
            package = Package()
            for obj in objects:
                package.add(obj)
            table.addItem(package)
            return table

        @staticmethod
        def detail_table(pack_table: PacksTable, *names: str):
            """Opens the detail table of the pack item found by a name path."""
            index = pack_table.index(0, 0)
            for name in names:
                index = Support.find(pack_table, name, index)
            return DetailedInfoTable(index)

        @staticmethod
        def find(table, name: str, parent: QModelIndex | None = None):
            parent = parent if parent is not None else QModelIndex()
            for row in range(table.rowCount(parent)):
                index = table.index(row, 0, parent)
                if index.data(NAME_ROLE) == name:
                    return index
            raise LookupError(f"No item named '{name}'")

        @staticmethod
        def column(table, name: str) -> int:
            return [
                table.headerData(
                    section,
                    Qt.Orientation.Horizontal,
                    Qt.ItemDataRole.DisplayRole,
                )
                for section in range(table.columnCount())
            ].index(name)

    return Support


def test_edit_keeps_text_none_when_value_is_the_string_none(
    edit_support,
) -> None:
    shell = make_shell(id_short="Shell")
    table = edit_support.pack_table(shell)
    details = edit_support.detail_table(table, "shells", "Shell")

    edited = details.setData(
        edit_support.find(details, "category"), "None", Qt.ItemDataRole.EditRole
    )

    assert edited
    assert shell.category == "None"


def test_edit_clears_optional_value_when_value_is_none(edit_support) -> None:
    shell = make_shell(id_short="Shell")
    shell.category = "Parameter"
    table = edit_support.pack_table(shell)
    details = edit_support.detail_table(table, "shells", "Shell")

    edited = details.setData(
        edit_support.find(details, "category"), None, Qt.ItemDataRole.EditRole
    )

    assert edited
    assert shell.category is None


def test_clear_row_clears_optional_value_when_default_is_none(
    edit_support,
) -> None:
    from aas_editor.settings.app_settings import CLEAR_ROW_ROLE

    shell = make_shell(id_short="Shell")
    shell.category = "Parameter"
    table = edit_support.pack_table(shell)
    details = edit_support.detail_table(table, "shells", "Shell")

    cleared = details.setData(
        edit_support.find(details, "category"), None, CLEAR_ROW_ROLE
    )

    assert cleared
    assert shell.category is None


def test_edit_keeps_text_none_when_editing_a_column_of_the_pack_table(
    edit_support,
) -> None:
    shell = make_shell(id_short="Shell")
    table = edit_support.pack_table(shell)
    shell_index = edit_support.find(
        table, "Shell", edit_support.find(table, "shells", table.index(0, 0))
    )
    category_column = edit_support.column(table, "category")

    edited = table.setData(
        shell_index.siblingAtColumn(category_column),
        "None",
        Qt.ItemDataRole.EditRole,
    )

    assert edited
    assert shell.category == "None"


def test_edit_refuses_clearing_asset_information_of_a_shell(
    edit_support,
) -> None:
    asset_information = make_asset_information()
    shell = make_shell(id_short="Shell", asset_information=asset_information)
    table = edit_support.pack_table(shell)
    details = edit_support.detail_table(table, "shells", "Shell")

    edited = details.setData(
        edit_support.find(details, "asset_information"),
        None,
        Qt.ItemDataRole.EditRole,
    )

    assert not edited
    assert shell.asset_information is asset_information
    assert "asset_information" in details.lastErrorMsg
    assert "mandatory" in details.lastErrorMsg


def test_edit_refuses_clearing_asset_information_in_the_pack_table(
    edit_support,
) -> None:
    asset_information = make_asset_information()
    shell = make_shell(id_short="Shell", asset_information=asset_information)
    table = edit_support.pack_table(shell)
    shell_index = edit_support.find(
        table, "Shell", edit_support.find(table, "shells", table.index(0, 0))
    )
    column = edit_support.column(table, "asset_information")

    edited = table.setData(
        shell_index.siblingAtColumn(column), None, Qt.ItemDataRole.EditRole
    )

    assert not edited
    assert shell.asset_information is asset_information
    assert "mandatory" in table.lastErrorMsg


def test_edit_refuses_value_and_keeps_value_type_when_value_does_not_fit(
    edit_support,
) -> None:
    prop = make_property("Count", 5, model.datatypes.Int)
    submodel = make_submodel(elements=[prop])
    table = edit_support.pack_table(submodel)
    details = edit_support.detail_table(table, "submodels", "Submodel", "Count")

    edited = details.setData(
        edit_support.find(details, "value"), "abc", Qt.ItemDataRole.EditRole
    )

    assert not edited
    assert prop.value_type is model.datatypes.Int
    assert prop.value == 5
    assert "abc" in details.lastErrorMsg


def test_edit_sets_value_when_value_fits_the_value_type(edit_support) -> None:
    prop = make_property("Count", 5, model.datatypes.Int)
    submodel = make_submodel(elements=[prop])
    table = edit_support.pack_table(submodel)
    details = edit_support.detail_table(table, "submodels", "Submodel", "Count")

    edited = details.setData(
        edit_support.find(details, "value"), 7, Qt.ItemDataRole.EditRole
    )

    assert edited
    assert prop.value == 7
    assert prop.value_type is model.datatypes.Int
