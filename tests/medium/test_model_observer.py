"""The item models follow changes of the objects that other models made.

Every open tab has a model of its own over the same BaSyx objects, behind the
proxy that the views use. A change of an object in one of them, or by a
command, has to show up in all the others.
"""

from basyx.aas import model
from PyQt6.QtCore import Qt
import pytest

from aas_workingbench.application.changes import Change
from aas_workingbench.application.changes import observer_for
from aas_workingbench.domain.ordering import insert_at
from aas_workingbench.domain.ordering import move_to
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel


@pytest.fixture
def two_tabs(model_support):
    """Two tabs that show the same property, each behind a proxy."""
    from aas_workingbench.models.search_proxy_model import SearchProxyModel

    prop = make_property("Name", "pump")
    submodel = make_submodel(elements=[prop])
    pack_table = model_support.pack_table(submodel)
    tabs = []
    for _ in range(2):
        source = model_support.detail_table(
            pack_table, "submodels", "Submodel", "Name"
        )
        proxy = SearchProxyModel(source)
        model_support.watch(proxy)
        tabs.append(proxy)

    class Tabs:
        first, second = tabs
        pack = pack_table
        element = prop

        @staticmethod
        def value_text(proxy) -> str:
            from aas_workingbench.settings.app_settings import VALUE_COLUMN

            row = model_support.find(proxy, "value")
            return proxy.index(row.row(), VALUE_COLUMN).data(
                Qt.ItemDataRole.DisplayRole
            )

    return Tabs


def test_other_tab_shows_new_value_when_a_tab_edits_the_value(
    model_support, two_tabs
) -> None:
    value = model_support.find(two_tabs.first, "value")

    edited = two_tabs.first.setData(value, "valve", Qt.ItemDataRole.EditRole)

    assert edited
    assert two_tabs.value_text(two_tabs.first) == "valve"
    assert two_tabs.value_text(two_tabs.second) == "valve"
    assert model_support.violations() == []


def test_edited_tab_keeps_the_edited_row_when_it_follows_its_own_edit(
    model_support, two_tabs
) -> None:
    from PyQt6.QtCore import QPersistentModelIndex

    value = model_support.find(two_tabs.first, "value")
    kept = QPersistentModelIndex(value)

    two_tabs.first.setData(value, "valve", Qt.ItemDataRole.EditRole)

    assert kept.isValid()


def test_package_tree_shows_new_value_when_a_tab_edits_the_value(
    model_support, two_tabs
) -> None:
    value = model_support.find(two_tabs.first, "value")

    two_tabs.first.setData(value, "valve", Qt.ItemDataRole.EditRole)

    row = model_support.find_path(
        two_tabs.pack, "submodels", "Submodel", "Name"
    )
    column = model_support.column(two_tabs.pack, "value")
    shown = two_tabs.pack.index(row.row(), column, row.parent()).data(
        Qt.ItemDataRole.DisplayRole
    )
    assert shown == "valve"


def test_tab_shows_new_id_short_when_the_package_tree_renames_the_element(
    model_support, two_tabs
) -> None:

    row = model_support.find_path(
        two_tabs.pack, "submodels", "Submodel", "Name"
    )
    column = [
        two_tabs.pack.headerData(
            section,
            Qt.Orientation.Horizontal,
            Qt.ItemDataRole.DisplayRole,
        )
        for section in range(two_tabs.pack.columnCount())
    ].index("id_short")

    edited = two_tabs.pack.setData(
        row.siblingAtColumn(column), "Title", Qt.ItemDataRole.EditRole
    )

    assert edited
    assert two_tabs.element.id_short == "Title"
    for tab in (two_tabs.first, two_tabs.second):
        id_short = model_support.find(tab, "id_short")
        shown = tab.index(id_short.row(), 1).data(Qt.ItemDataRole.DisplayRole)
        assert shown == "Title"


def test_other_tab_shows_new_extension_when_a_tab_adds_one(
    model_support,
) -> None:
    from aas_workingbench.models.search_proxy_model import SearchProxyModel
    from aas_workingbench.settings.app_settings import ADD_ITEM_ROLE

    submodel = make_submodel(elements=[make_property("Name")])
    pack_table = model_support.pack_table(submodel)
    tabs = [
        SearchProxyModel(
            model_support.detail_table(pack_table, "submodels", "Submodel")
        )
        for _ in range(2)
    ]
    for tab in tabs:
        model_support.watch(tab)
    extensions = model_support.find(tabs[0], "extension")

    added = tabs[0].setData(
        extensions, model.Extension(name="Note"), ADD_ITEM_ROLE
    )

    assert added
    other_extensions = model_support.find(tabs[1], "extension")
    assert tabs[1].rowCount(other_extensions) == 1
    assert model_support.violations() == []


def test_other_tab_drops_the_extension_when_a_tab_deletes_it(
    model_support,
) -> None:
    from aas_workingbench.models.search_proxy_model import SearchProxyModel
    from aas_workingbench.settings.app_settings import CLEAR_ROW_ROLE

    submodel = make_submodel(elements=[make_property("Name")])
    submodel.extension.add(model.Extension(name="Note"))
    pack_table = model_support.pack_table(submodel)
    tabs = [
        SearchProxyModel(
            model_support.detail_table(pack_table, "submodels", "Submodel")
        )
        for _ in range(2)
    ]
    for tab in tabs:
        model_support.watch(tab)
    note = tabs[0].index(0, 0, model_support.find(tabs[0], "extension"))

    deleted = tabs[0].setData(note, None, CLEAR_ROW_ROLE)

    assert deleted
    assert tabs[1].rowCount(model_support.find(tabs[1], "extension")) == 0
    assert model_support.violations() == []


class TestFollowsCommands:
    """What a command does is reported only to the observer."""

    @pytest.fixture
    def tree(self, model_support):
        collection = make_collection(
            "Collection", [make_property("a"), make_property("b")]
        )
        submodel = make_submodel(elements=[collection])
        table = model_support.pack_table(submodel)
        model_support.watch(table)
        index = model_support.find_path(
            table, "submodels", "Submodel", "Collection"
        )

        class Tree:
            pack = table
            owner = collection
            observer = observer_for(model_support.package_of(table))
            collection_index = index

            @staticmethod
            def rows() -> list[str]:
                return model_support.names(table, index)

        return Tree

    def test_row_appears_at_the_position_when_an_element_is_added(
        self, model_support, tree
    ) -> None:
        new = make_property("n")
        insert_at(tree.owner.value, new, 1)

        tree.observer.notify(Change.added(tree.owner.value, new, 1))

        assert tree.rows() == ["a", "n", "b"]
        assert model_support.violations() == []

    def test_row_appears_when_the_owner_is_named_as_the_parent(
        self, model_support, tree
    ) -> None:
        new = make_property("n")
        insert_at(tree.owner.value, new, 0)

        tree.observer.notify(Change.added(tree.owner, new, 0))

        assert tree.rows() == ["n", "a", "b"]
        assert model_support.violations() == []

    def test_row_disappears_when_an_element_is_removed(
        self, model_support, tree
    ) -> None:
        first = list(tree.owner.value)[0]
        tree.owner.value.remove(first)

        tree.observer.notify(Change.removed(tree.owner.value, first, 0))

        assert tree.rows() == ["b"]
        assert model_support.violations() == []

    def test_row_moves_when_an_element_is_moved(
        self, model_support, tree
    ) -> None:
        first = list(tree.owner.value)[0]
        move_to(tree.owner.value, first, 1)

        tree.observer.notify(Change.moved(tree.owner.value, first, 0, 1))

        assert tree.rows() == ["b", "a"]
        assert model_support.violations() == []

    def test_row_is_not_added_twice_when_the_change_is_reported_twice(
        self, model_support, tree
    ) -> None:
        new = make_property("n")
        insert_at(tree.owner.value, new, 2)

        tree.observer.notify(Change.added(tree.owner.value, new, 2))
        tree.observer.notify(Change.added(tree.owner.value, new, 2))

        assert tree.rows() == ["a", "b", "n"]

    def test_name_changes_when_an_element_was_renamed(
        self, model_support, tree
    ) -> None:
        first = list(tree.owner.value)[0]
        from aas_workingbench.domain.ordering import set_id_short

        set_id_short(first, "z")

        tree.observer.notify(Change.changed(first))

        assert tree.rows() == ["z", "b"]
        assert model_support.violations() == []

    def test_rows_are_read_again_when_the_container_changed(
        self, model_support, tree
    ) -> None:
        new = make_property("n")
        tree.owner.value.add(new)

        tree.observer.notify(Change.changed(tree.owner.value))

        assert tree.rows() == ["a", "b", "n"]
        assert model_support.violations() == []

    def test_unrelated_rows_stay_when_another_object_changes(
        self, model_support, tree
    ) -> None:
        stranger = make_property("stranger")

        tree.observer.notify(Change.changed(stranger))

        assert tree.rows() == ["a", "b"]
