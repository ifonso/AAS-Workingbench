"""Every kind of edit through the item models is one undoable step.

Each test drives the real Qt models, as the views do, and compares the
package through its SDK serialization. An undo must give back the original
content, including the position of every member, and a second tab on the same
object must show the same state as the first.
"""

from pathlib import Path
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.serialization import snapshot

EDIT = Qt.ItemDataRole.EditRole


@pytest.fixture
def world(model_support):
    """A package with one shell, two submodels, and two tabs per request."""
    from aas_workingbench.models.search_proxy_model import SearchProxyModel
    from aas_workingbench.settings.app_settings import ADD_ITEM_ROLE
    from aas_workingbench.settings.app_settings import CLEAR_ROW_ROLE
    from aas_workingbench.settings.app_settings import VALUE_COLUMN

    prop = make_property("a", "text")
    prop.description = model.MultiLanguageTextType(
        {"en": "one", "de": "eins", "fr": "un"}
    )
    collection = make_collection(
        "Collection",
        [make_property("x"), make_property("y"), make_property("z")],
    )
    submodel = make_submodel(
        elements=[
            prop,
            collection,
            make_property("c"),
            make_property("n", 5, model.datatypes.Int),
        ]
    )
    other = make_submodel(
        "urn:uuid:00000000-0000-4000-8000-0000000000a2", "Other"
    )
    shell = make_shell(submodels=[submodel])
    table = model_support.pack_table(shell, submodel, other)
    model_support.watch(table)
    package = model_support.package_of(table)

    world = SimpleNamespace()
    world.table = table
    world.package = package
    world.stack = package.commandStack
    world.submodel = submodel
    world.other = other
    world.shell = shell
    world.collection = collection
    world.prop = prop
    world.original = snapshot(package.objStore)
    world.add_role = ADD_ITEM_ROLE
    world.clear_role = CLEAR_ROW_ROLE

    def tab(*names: str):
        proxy = SearchProxyModel(model_support.detail_table(table, *names))
        model_support.watch(proxy)
        return proxy

    def pack_index(*names: str) -> QModelIndex:
        return model_support.find_path(table, "", *names)

    def pack_column(name: str) -> int:
        return model_support.column(table, name)

    def shown_value(proxy) -> str:
        row = model_support.find(proxy, "value")
        return proxy.index(row.row(), VALUE_COLUMN).data(
            Qt.ItemDataRole.DisplayRole
        )

    def element_ids(owner) -> list[str]:
        return [element.id_short for element in owner]

    def now() -> str:
        return snapshot(package.objStore)

    world.tab = tab
    world.pack_index = pack_index
    world.pack_column = pack_column
    world.shown_value = shown_value
    world.element_ids = element_ids
    world.now = now
    return world


def test_value_edit_in_a_tab_is_undone_and_redone_and_followed_by_the_other_tab(
    model_support, world
) -> None:
    first = world.tab("submodels", "Submodel", "a")
    second = world.tab("submodels", "Submodel", "a")

    first.setData(model_support.find(first, "value"), "changed", EDIT)
    edited = world.now()
    after_edit = (world.shown_value(first), world.shown_value(second))
    dirty_after_edit = not world.stack.is_clean
    world.stack.undo()
    after_undo = (world.shown_value(first), world.shown_value(second))
    world.stack.redo()
    after_redo = (world.shown_value(first), world.shown_value(second))

    assert after_edit == ("changed", "changed")
    assert dirty_after_edit
    assert after_undo == ("text", "text")
    assert after_redo == ("changed", "changed")
    assert world.now() == edited
    assert model_support.violations() == []


def test_undo_gives_back_the_original_content_when_a_value_was_edited(
    world, model_support
) -> None:
    tab = world.tab("submodels", "Submodel", "a")

    tab.setData(model_support.find(tab, "value"), "changed", EDIT)
    world.stack.undo()

    assert world.now() == world.original
    assert world.stack.is_clean


def test_editing_the_same_value_records_no_step(world, model_support) -> None:
    tab = world.tab("submodels", "Submodel", "a")

    edited = tab.setData(model_support.find(tab, "value"), "text", EDIT)

    assert edited
    assert not world.stack.can_undo
    assert world.stack.is_clean


def test_a_refused_edit_records_no_step(world, model_support) -> None:
    tab = world.tab("submodels", "Submodel", "n")

    edited = tab.setData(model_support.find(tab, "value"), "abc", EDIT)

    assert not edited
    assert not world.stack.can_undo
    assert world.submodel.get_referable("n").value == 5


def test_rename_in_the_package_tree_keeps_the_position_through_undo_and_redo(
    model_support, world
) -> None:
    other_tab = world.tab("submodels", "Submodel", "Collection")
    row = world.pack_index("submodels", "Submodel", "Collection", "y")

    world.table.setData(
        row.siblingAtColumn(world.pack_column("id_short")), "q", EDIT
    )
    renamed = world.now()
    ids_after_rename = world.element_ids(world.collection.value)
    world.stack.undo()
    ids_after_undo = world.element_ids(world.collection.value)
    rows_after_undo = model_support.names(
        world.table, world.pack_index("submodels", "Submodel", "Collection")
    )
    world.stack.redo()

    assert ids_after_rename == ["x", "q", "z"]
    assert ids_after_undo == ["x", "y", "z"]
    assert rows_after_undo == ["x", "y", "z"]
    assert world.now() == renamed
    assert other_tab.rowCount() > 0
    assert model_support.violations() == []


def test_rename_in_a_tab_is_followed_by_the_package_tree_and_undone(
    model_support, world
) -> None:
    tab = world.tab("submodels", "Submodel", "Collection", "y")

    tab.setData(model_support.find(tab, "id_short"), "q", EDIT)
    names_after_rename = model_support.names(
        world.table, world.pack_index("submodels", "Submodel", "Collection")
    )
    world.stack.undo()

    assert names_after_rename == ["x", "q", "z"]
    assert model_support.names(
        world.table, world.pack_index("submodels", "Submodel", "Collection")
    ) == ["x", "y", "z"]
    assert world.now() == world.original


def test_replacing_an_element_keeps_its_position_through_undo(
    model_support, world
) -> None:
    row = world.pack_index("submodels", "Submodel", "Collection", "y")
    replacement = make_property("n")

    world.table.setData(row, replacement, EDIT)
    ids_after_replace = world.element_ids(world.collection.value)
    world.stack.undo()

    assert ids_after_replace == ["x", "n", "z"]
    assert world.element_ids(world.collection.value) == ["x", "y", "z"]
    assert world.now() == world.original
    assert model_support.violations() == []


def test_adding_an_element_at_a_position_is_undone_and_redone(
    model_support, world
) -> None:
    tab = world.tab("submodels", "Submodel", "Collection")
    collection = world.pack_index("submodels", "Submodel", "Collection")

    world.table.addItem(make_property("n"), collection, row=1)
    added = world.now()
    ids_after_add = world.element_ids(world.collection.value)
    rows_after_add = model_support.names(world.table, collection)
    world.stack.undo()
    rows_after_undo = model_support.names(world.table, collection)
    world.stack.redo()

    assert ids_after_add == ["x", "n", "y", "z"]
    assert rows_after_add == ["x", "n", "y", "z"]
    assert rows_after_undo == ["x", "y", "z"]
    assert world.element_ids(world.collection.value) == ["x", "n", "y", "z"]
    assert world.now() == added
    assert tab.rowCount() > 0
    assert model_support.violations() == []


def test_undo_of_an_add_gives_back_the_original_content(world) -> None:
    collection = world.pack_index("submodels", "Submodel", "Collection")

    world.table.setData(collection, make_property("n"), world.add_role)
    world.stack.undo()

    assert world.now() == world.original
    assert world.stack.is_clean


def test_a_refused_add_records_no_step(world) -> None:
    collection = world.pack_index("submodels", "Submodel", "Collection")

    added = world.table.setData(collection, make_property("x"), world.add_role)

    assert not added
    assert not world.stack.can_undo
    assert "x" in world.table.lastErrorMsg


def test_deleting_an_element_is_undone_to_its_position(
    model_support, world
) -> None:
    collection = world.pack_index("submodels", "Submodel", "Collection")
    middle = world.pack_index("submodels", "Submodel", "Collection", "y")
    tab = world.tab("submodels", "Submodel", "Collection")

    world.table.setData(middle, None, world.clear_role)
    deleted = world.now()
    ids_after_delete = world.element_ids(world.collection.value)
    world.stack.undo()
    rows_after_undo = model_support.names(world.table, collection)
    world.stack.redo()

    assert ids_after_delete == ["x", "z"]
    assert world.element_ids(world.collection.value) == ["x", "z"]
    assert rows_after_undo == ["x", "y", "z"]
    assert world.now() == deleted
    assert tab.rowCount() > 0
    assert model_support.violations() == []


def test_undo_of_a_delete_gives_back_the_original_content(world) -> None:
    middle = world.pack_index("submodels", "Submodel", "Collection", "y")

    world.table.setData(middle, None, world.clear_role)
    world.stack.undo()

    assert world.now() == world.original
    assert world.stack.is_clean


def test_deleting_the_first_and_the_last_element_is_undone_to_their_positions(
    world,
) -> None:
    first = world.pack_index("submodels", "Submodel", "Collection", "x")
    last = world.pack_index("submodels", "Submodel", "Collection", "z")

    world.table.setData(last, None, world.clear_role)
    world.table.setData(first, None, world.clear_role)
    world.stack.undo()
    world.stack.undo()

    assert world.now() == world.original


def test_deleting_a_submodel_of_the_package_is_undone(
    model_support, world
) -> None:
    other = world.pack_index("submodels", "Other")
    submodels = world.pack_index("submodels")

    world.table.setData(other, None, world.clear_role)
    gone = world.package.objStore.get(
        "urn:uuid:00000000-0000-4000-8000-0000000000a2"
    )
    rows_after_delete = model_support.names(world.table, submodels)
    world.stack.undo()

    assert gone is None
    assert "Other" not in rows_after_delete
    assert "Other" in model_support.names(world.table, submodels)
    assert world.now() == world.original
    assert model_support.violations() == []


def test_adding_a_submodel_to_the_package_is_undone(
    model_support, world
) -> None:
    submodels = world.pack_index("submodels")
    new = make_submodel("urn:uuid:00000000-0000-4000-8000-0000000000a3", "New")

    world.table.setData(submodels, new, world.add_role)
    rows_after_add = model_support.names(world.table, submodels)
    world.stack.undo()

    assert "New" in rows_after_add
    assert "New" not in model_support.names(world.table, submodels)
    assert world.now() == world.original


def test_an_extension_added_in_a_tab_is_undone_in_both_tabs(
    model_support, world
) -> None:
    first = world.tab("submodels", "Submodel")
    second = world.tab("submodels", "Submodel")

    first.setData(
        model_support.find(first, "extension"),
        model.Extension(name="Note"),
        world.add_role,
    )
    rows_after_add = (
        first.rowCount(model_support.find(first, "extension")),
        second.rowCount(model_support.find(second, "extension")),
    )
    world.stack.undo()

    assert rows_after_add == (1, 1)
    assert first.rowCount(model_support.find(first, "extension")) == 0
    assert second.rowCount(model_support.find(second, "extension")) == 0
    assert world.now() == world.original
    assert model_support.violations() == []


def test_extensions_deleted_in_a_tab_come_back_in_their_order(
    model_support, world
) -> None:
    for name in ("One", "Two", "Three"):
        world.submodel.extension.add(model.Extension(name=name))
    original = world.now()
    tab = world.tab("submodels", "Submodel")
    extensions = model_support.find(tab, "extension")

    tab.setData(tab.index(1, 0, extensions), None, world.clear_role)
    left = [extension.name for extension in world.submodel.extension]
    world.stack.undo()

    assert left == ["One", "Three"]
    assert [e.name for e in world.submodel.extension] == ["One", "Two", "Three"]
    assert world.now() == original
    assert model_support.violations() == []


def test_language_entries_are_added_edited_and_deleted_in_order(
    model_support, world
) -> None:
    from aas_workingbench.additional.classes import DictItem

    first = world.tab("submodels", "Submodel", "a")
    second = world.tab("submodels", "Submodel", "a")
    description = model_support.find(first, "description")

    first.setData(description, DictItem("es", "uno"), world.add_role)
    first.setData(
        first.index(1, 0, model_support.find(first, "description")),
        DictItem("de", "hallo"),
        EDIT,
    )
    first.setData(
        first.index(0, 0, model_support.find(first, "description")),
        None,
        world.clear_role,
    )
    done = world.now()
    keys_after = list(world.prop.description)
    world.stack.undo()
    world.stack.undo()
    world.stack.undo()
    keys_after_undo = list(world.prop.description)
    world.stack.redo()
    world.stack.redo()
    world.stack.redo()

    assert keys_after == ["de", "fr", "es"]
    assert dict(world.prop.description) == {
        "de": "hallo",
        "fr": "un",
        "es": "uno",
    }
    assert keys_after_undo == ["en", "de", "fr"]
    assert world.now() == done
    assert second.rowCount(model_support.find(second, "description")) == 3
    assert model_support.violations() == []


def test_a_language_entry_with_a_new_key_keeps_its_position(
    model_support, world
) -> None:
    from aas_workingbench.additional.classes import DictItem

    tab = world.tab("submodels", "Submodel", "a")
    middle = tab.index(1, 0, model_support.find(tab, "description"))

    tab.setData(middle, DictItem("es", "eins"), EDIT)
    keys_after = list(world.prop.description)
    world.stack.undo()

    assert keys_after == ["en", "es", "fr"]
    assert list(world.prop.description) == ["en", "de", "fr"]
    assert world.now() == world.original


def test_linking_all_submodels_is_one_step_that_is_undone(
    model_support, world
) -> None:
    links = world.shell.submodel

    added = world.package.all_submodels_to_aas()
    linked = len(links)
    world.stack.undo()

    assert added == 1
    assert linked == 2
    assert len(links) == 1
    assert world.now() == world.original
    assert world.stack.is_clean
    assert model_support.violations() == []


def test_linking_shows_the_references_in_the_tabs_of_the_shell_and_removes_them(
    model_support, world
) -> None:
    tab = world.tab("shells", "Shell")

    world.package.all_submodels_to_aas()
    rows_after_link = tab.rowCount(model_support.find(tab, "submodel"))
    world.stack.undo()

    assert rows_after_link == 2
    assert tab.rowCount(model_support.find(tab, "submodel")) == 1


def test_a_file_added_to_the_package_is_removed_by_undo(
    model_support, world, tmp_path: Path
) -> None:
    from aas_workingbench.package import StoredFile

    source = tmp_path / "note.txt"
    source.write_bytes(b"hello")
    stored = StoredFile(filePath=str(source))
    file_store = world.pack_index("fileStore")

    world.table.setData(file_store, stored, world.add_role)
    in_store = list(world.package.fileStore)
    rows_after_add = model_support.names(world.table, file_store)
    world.stack.undo()
    gone = list(world.package.fileStore)
    world.stack.redo()

    assert in_store == ["/note.txt"]
    assert rows_after_add == ["/note.txt"]
    assert gone == []
    assert list(world.package.fileStore) == ["/note.txt"]
    assert stored.name == "/note.txt"


class TestDirtyState:
    def test_package_is_clean_until_it_is_edited(self, world) -> None:
        assert not world.package.changed

    def test_package_is_changed_after_an_edit_and_clean_after_undo(
        self, world, model_support
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")

        tab.setData(model_support.find(tab, "value"), "changed", EDIT)
        changed = world.package.changed
        world.stack.undo()

        assert changed
        assert not world.package.changed

    def test_package_is_changed_again_when_a_saved_edit_is_undone(
        self, world, model_support
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")
        tab.setData(model_support.find(tab, "value"), "changed", EDIT)

        world.stack.mark_saved()
        clean_after_save = not world.package.changed
        world.stack.undo()

        assert clean_after_save
        assert world.package.changed

    def test_package_is_clean_again_when_the_undone_edit_is_redone(
        self, world, model_support
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")
        tab.setData(model_support.find(tab, "value"), "changed", EDIT)
        world.stack.mark_saved()
        world.stack.undo()

        world.stack.redo()

        assert not world.package.changed

    def test_package_stays_changed_when_a_new_edit_follows_an_undo_of_a_saved_edit(
        self, world, model_support
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")
        tab.setData(model_support.find(tab, "value"), "changed", EDIT)
        world.stack.mark_saved()
        world.stack.undo()

        tab.setData(model_support.find(tab, "value"), "other", EDIT)
        world.stack.undo()

        assert world.package.changed

    def test_history_signal_tells_the_model_when_the_dirty_state_changes(
        self, world, model_support, qtbot
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")

        with qtbot.waitSignal(world.table.historyChanged):
            tab.setData(model_support.find(tab, "value"), "changed", EDIT)


class TestReadMode:
    @pytest.fixture
    def reading(self, world):
        from aas_workingbench.application.editing import edit_mode

        edit_mode().set_editing(False)
        return world

    def test_edit_is_refused_with_a_clear_error(
        self, reading, model_support
    ) -> None:
        tab = reading.tab("submodels", "Submodel", "a")

        edited = tab.setData(model_support.find(tab, "value"), "changed", EDIT)

        assert not edited
        assert reading.prop.value == "text"
        assert "Read mode" in tab.sourceModel().lastErrorMsg
        assert not reading.stack.can_undo

    def test_add_and_delete_are_refused(self, reading) -> None:
        collection = reading.pack_index("submodels", "Submodel", "Collection")
        middle = reading.pack_index("submodels", "Submodel", "Collection", "y")

        added = reading.table.setData(
            collection, make_property("n"), reading.add_role
        )
        deleted = reading.table.setData(middle, None, reading.clear_role)

        assert not added
        assert not deleted
        assert reading.now() == reading.original

    def test_items_are_not_editable_inline(
        self, reading, model_support
    ) -> None:
        tab = reading.tab("submodels", "Submodel", "a")
        value = model_support.find(tab, "value").siblingAtColumn(1)

        assert not tab.flags(value) & Qt.ItemFlag.ItemIsEditable

    def test_items_are_editable_inline_in_edit_mode(
        self, world, model_support
    ) -> None:
        tab = world.tab("submodels", "Submodel", "a")
        value = model_support.find(tab, "value").siblingAtColumn(1)

        assert tab.flags(value) & Qt.ItemFlag.ItemIsEditable

    def test_undo_is_refused(self, world, model_support) -> None:
        from aas_workingbench.application.commands import ReadOnlyError
        from aas_workingbench.application.editing import edit_mode

        tab = world.tab("submodels", "Submodel", "a")
        tab.setData(model_support.find(tab, "value"), "changed", EDIT)
        edit_mode().set_editing(False)

        with pytest.raises(ReadOnlyError):
            world.stack.undo()

        assert world.prop.value == "changed"

    def test_editing_works_again_after_switching_back(
        self, reading, model_support
    ) -> None:
        from aas_workingbench.application.editing import edit_mode

        edit_mode().set_editing(True)
        tab = reading.tab("submodels", "Submodel", "a")

        edited = tab.setData(model_support.find(tab, "value"), "changed", EDIT)

        assert edited
        assert reading.prop.value == "changed"


def test_closing_a_package_leaves_no_undo_step(model_support, world) -> None:
    from aas_workingbench.settings import NOT_GIVEN

    table = world.table
    package_row = table.index(0, 0)

    table.setData(package_row, NOT_GIVEN, world.clear_role)

    assert table.rowCount() == 0
    assert not world.stack.can_undo


def test_opening_a_package_leaves_no_undo_step(model_support, world) -> None:
    from aas_workingbench.package import Package

    other_package = Package()

    world.table.setData(QModelIndex(), other_package, world.add_role)

    assert world.table.rowCount() == 2
    assert not other_package.commandStack.can_undo
    assert not world.stack.can_undo


def test_package_detail_view_does_not_show_the_undo_history(
    model_support, world
) -> None:
    details = model_support.detail_table(world.table)

    shown = model_support.names(details)

    assert "commandStack" not in shown
    assert "recoveryWritten" not in shown
