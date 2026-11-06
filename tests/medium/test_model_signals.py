"""The item models keep the Qt model contract when their rows change.

`QAbstractItemModelTester` reports every violation of the contract, such as a
row count that disagrees with the signals. The models are also checked behind
the proxy that the views put in front of them.
"""

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QSortFilterProxyModel
from PyQt6.QtCore import Qt
import pytest

from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel


def _submodel_with_collection():
    collection = make_collection(
        "Collection", [make_property("a"), make_property("b")]
    )
    return make_submodel(elements=[collection, make_property("x")])


def test_pack_table_keeps_the_contract_when_it_is_filled(model_support) -> None:
    table = model_support.pack_table(
        _submodel_with_collection(), make_shell(id_short="Shell")
    )

    model_support.watch(table)

    assert model_support.violations() == []
    assert model_support.names(table, table.index(0, 0)) == [
        "shells",
        "submodels",
        "concept_descriptions",
        "fileStore",
    ]


def test_detail_table_keeps_the_contract_when_it_is_filled(
    model_support,
) -> None:
    pack_table = model_support.pack_table(_submodel_with_collection())
    details = model_support.detail_table(pack_table, "submodels", "Submodel")

    model_support.watch(details)

    assert model_support.violations() == []


def test_update_keeps_the_contract_when_the_item_has_children(
    model_support,
) -> None:
    from aas_editor.settings.app_settings import UPDATE_ROLE

    table = model_support.pack_table(_submodel_with_collection())
    model_support.watch(table)
    collection = model_support.find_path(
        table, "submodels", "Submodel", "Collection"
    )

    table.setData(collection, None, UPDATE_ROLE)

    assert model_support.violations() == []
    assert model_support.names(table, collection) == ["a", "b"]


def test_update_keeps_the_contract_when_the_item_has_no_children(
    model_support,
) -> None:
    from aas_editor.settings.app_settings import UPDATE_ROLE

    table = model_support.pack_table(_submodel_with_collection())
    model_support.watch(table)
    leaf = model_support.find_path(table, "submodels", "Submodel", "x")

    table.setData(leaf, None, UPDATE_ROLE)

    assert model_support.violations() == []


def test_update_keeps_the_contract_in_the_detail_table(model_support) -> None:
    from aas_editor.settings.app_settings import UPDATE_ROLE

    pack_table = model_support.pack_table(_submodel_with_collection())
    details = model_support.detail_table(pack_table, "submodels", "Submodel")
    model_support.watch(details)

    details.setData(QModelIndex(), None, UPDATE_ROLE)
    details.setData(model_support.find(details, "extension"), None, UPDATE_ROLE)

    assert model_support.violations() == []


@pytest.mark.parametrize("model_name", ["pack", "detail"])
def test_proxy_keeps_the_contract_when_the_source_updates(
    model_support, model_name: str
) -> None:
    from aas_editor.settings.app_settings import UPDATE_ROLE

    pack_table = model_support.pack_table(_submodel_with_collection())
    source = (
        pack_table
        if model_name == "pack"
        else model_support.detail_table(pack_table, "submodels", "Submodel")
    )
    proxy = QSortFilterProxyModel()
    proxy.setSourceModel(source)
    model_support.watch(proxy)
    target = (
        model_support.find_path(
            pack_table, "submodels", "Submodel", "Collection"
        )
        if model_name == "pack"
        else model_support.find(source, "extension")
    )

    source.setData(target, None, UPDATE_ROLE)

    assert model_support.violations() == []


class TestRowsAtPositions:
    @pytest.fixture
    def collection_tree(self, model_support):
        from aas_editor.models.search_proxy_model import SearchProxyModel

        collection = make_collection(
            "Collection", [make_property("a"), make_property("b")]
        )
        table = model_support.pack_table(make_submodel(elements=[collection]))
        proxy = SearchProxyModel(table)
        model_support.watch(table)
        model_support.watch(proxy)

        class Tree:
            owner = collection
            source = table
            index = model_support.find_path(
                table, "submodels", "Submodel", "Collection"
            )

            @staticmethod
            def rows() -> list[str]:
                return model_support.names(table, Tree.index)

            @staticmethod
            def elements() -> list[str | None]:
                return [e.id_short for e in collection.value]

            @staticmethod
            def shown_by_proxy() -> list[str]:
                return model_support.names(
                    proxy, proxy.mapFromSource(Tree.index)
                )

        return Tree

    def test_add_item_puts_row_and_element_at_the_position(
        self, model_support, collection_tree
    ) -> None:
        collection_tree.source.addItem(
            make_property("n"), collection_tree.index, row=1
        )

        assert collection_tree.rows() == ["a", "n", "b"]
        assert collection_tree.elements() == ["a", "n", "b"]
        assert collection_tree.shown_by_proxy() == ["a", "n", "b"]
        assert model_support.violations() == []

    def test_add_item_puts_row_and_element_first_when_row_is_zero(
        self, model_support, collection_tree
    ) -> None:
        collection_tree.source.addItem(
            make_property("n"), collection_tree.index, row=0
        )

        assert collection_tree.rows() == ["n", "a", "b"]
        assert collection_tree.elements() == ["n", "a", "b"]
        assert model_support.violations() == []

    def test_add_item_appends_when_no_row_is_given(
        self, model_support, collection_tree
    ) -> None:
        collection_tree.source.addItem(
            make_property("n"), collection_tree.index
        )

        assert collection_tree.rows() == ["a", "b", "n"]
        assert collection_tree.elements() == ["a", "b", "n"]
        assert model_support.violations() == []

    def test_add_item_keeps_the_other_rows_valid(
        self, model_support, collection_tree
    ) -> None:
        from PyQt6.QtCore import QPersistentModelIndex

        b = QPersistentModelIndex(
            model_support.find(
                collection_tree.source, "b", collection_tree.index
            )
        )

        collection_tree.source.addItem(
            make_property("n"), collection_tree.index, row=0
        )

        assert b.row() == 2
        assert b.data(Qt.ItemDataRole.DisplayRole) == "b"

    def test_undo_removes_the_element_that_was_added_at_a_position(
        self, model_support, collection_tree
    ) -> None:
        from aas_editor.settings.app_settings import UNDO_ROLE
        from aas_editor.settings.app_settings import NOT_GIVEN

        collection_tree.source.addItem(
            make_property("n"), collection_tree.index, row=1
        )

        collection_tree.source.setData(QModelIndex(), NOT_GIVEN, UNDO_ROLE)

        assert collection_tree.rows() == ["a", "b"]
        assert collection_tree.elements() == ["a", "b"]
        assert model_support.violations() == []

    def test_move_item_moves_the_row_down(
        self, model_support, collection_tree
    ) -> None:
        first = model_support.find(
            collection_tree.source, "a", collection_tree.index
        )

        moved = collection_tree.source.moveItem(first, 1)

        assert moved
        assert collection_tree.rows() == ["b", "a"]
        assert collection_tree.shown_by_proxy() == ["b", "a"]
        assert model_support.violations() == []

    def test_move_item_moves_the_row_up(
        self, model_support, collection_tree
    ) -> None:
        last = model_support.find(
            collection_tree.source, "b", collection_tree.index
        )

        moved = collection_tree.source.moveItem(last, 0)

        assert moved
        assert collection_tree.rows() == ["b", "a"]
        assert model_support.violations() == []

    def test_move_item_keeps_the_moved_row_valid(
        self, model_support, collection_tree
    ) -> None:
        from PyQt6.QtCore import QPersistentModelIndex

        first = model_support.find(
            collection_tree.source, "a", collection_tree.index
        )
        kept = QPersistentModelIndex(first)

        collection_tree.source.moveItem(first, 1)

        assert kept.row() == 1
        assert kept.data(Qt.ItemDataRole.DisplayRole) == "a"

    def test_move_item_does_nothing_when_the_row_stays(
        self, model_support, collection_tree
    ) -> None:
        first = model_support.find(
            collection_tree.source, "a", collection_tree.index
        )

        moved = collection_tree.source.moveItem(first, 0)

        assert not moved
        assert collection_tree.rows() == ["a", "b"]
