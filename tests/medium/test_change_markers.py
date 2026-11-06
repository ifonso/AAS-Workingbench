"""The changed marker in the trees follows the saved state (F-EDT-01 AC3).

A tree shows an object that changed since the last save in another colour, and
so it shows the objects above it. Every tab and the package tree share the
marks of their package, so a save clears them everywhere, and so does an undo
that returns to the saved state.
"""

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import SetAttribute
from aas_editor.settings.colors import CHANGED_BLUE
from aas_editor.settings.colors import NEW_GREEN

FOREGROUND = Qt.ItemDataRole.ForegroundRole


@pytest.fixture
def world(model_support, qtbot: QtBot):
    """A package tree, and two tabs that show one property with a qualifier."""
    qualifier = model.Qualifier("Cardinality", model.datatypes.String, "One")
    pump = make_property("Pump", "on")
    pump.qualifier.add(qualifier)
    other = make_property("Other")
    collection = make_collection("Group", [pump, other])
    submodel = make_submodel(elements=[collection])
    pack = model_support.pack_table(submodel)
    tabs = [
        model_support.detail_table(
            pack, "submodels", "Submodel", "Group", "Pump"
        )
        for _ in range(2)
    ]
    package = model_support.package_of(pack)

    class World:
        table = pack
        first, second = tabs
        stack = package.commandStack
        observer = observer_for(package)
        marked_qualifier = qualifier
        element = pump
        sibling = other
        group = collection
        owner = submodel

        @staticmethod
        def color_in_tree(*names: str):
            index = model_support.find_path(pack, "", *names)
            return index.data(FOREGROUND)

        @staticmethod
        def package_color():
            return pack.index(0, 0).data(FOREGROUND)

        @staticmethod
        def color_in_tab(tab, *names: str):
            index = QModelIndex()
            for name in names:
                index = model_support.find(tab, name, index)
            return index.data(FOREGROUND)

        @staticmethod
        def edit_qualifier(value: str) -> None:
            package.commandStack.push(
                SetAttribute(observer_for(package), qualifier, "value", value)
            )

    return World


def test_nothing_is_marked_when_nothing_changed(world) -> None:
    assert world.color_in_tree("submodels", "Submodel") is None
    assert world.color_in_tab(world.first, "qualifier", "Qualifier 0") is None


def test_the_tree_marks_the_element_and_the_objects_above_it(world) -> None:
    world.edit_qualifier("Two")

    assert world.color_in_tree("submodels", "Submodel", "Group", "Pump") == (
        CHANGED_BLUE
    )
    assert world.color_in_tree("submodels", "Submodel", "Group") == CHANGED_BLUE
    assert world.color_in_tree("submodels", "Submodel") == CHANGED_BLUE
    assert world.package_color() == CHANGED_BLUE


def test_the_tree_does_not_mark_a_sibling_of_the_changed_element(world) -> None:
    world.edit_qualifier("Two")

    assert (
        world.color_in_tree("submodels", "Submodel", "Group", "Other") is None
    )


def test_every_tab_marks_the_changed_object(world) -> None:
    world.edit_qualifier("Two")

    for tab in (world.first, world.second):
        assert world.color_in_tab(tab, "qualifier", "Qualifier 0") == (
            CHANGED_BLUE
        )
        assert world.color_in_tab(tab, "qualifier") == CHANGED_BLUE


def test_an_added_element_is_new_and_the_tree_above_it_is_changed(
    world,
) -> None:
    added = make_property("Added")

    world.stack.push(AddMember(world.observer, world.group.value, added))

    assert world.color_in_tree("submodels", "Submodel", "Group", "Added") == (
        NEW_GREEN
    )
    assert world.color_in_tree("submodels", "Submodel", "Group") == CHANGED_BLUE


def test_a_save_clears_the_marker_in_the_tree_and_in_every_tab(world) -> None:
    world.edit_qualifier("Two")

    world.stack.mark_saved()

    assert world.color_in_tree("submodels", "Submodel", "Group", "Pump") is None
    assert world.package_color() is None
    for tab in (world.first, world.second):
        assert world.color_in_tab(tab, "qualifier", "Qualifier 0") is None


def test_undo_to_the_saved_state_clears_the_marker(world) -> None:
    world.edit_qualifier("Two")

    world.stack.undo()

    assert world.color_in_tree("submodels", "Submodel", "Group", "Pump") is None
    assert world.package_color() is None
    assert world.color_in_tab(world.second, "qualifier", "Qualifier 0") is None


def test_redo_marks_again_after_undo_cleared_the_marker(world) -> None:
    world.edit_qualifier("Two")
    world.stack.undo()

    world.stack.redo()

    assert world.color_in_tree("submodels", "Submodel", "Group", "Pump") == (
        CHANGED_BLUE
    )
    assert world.color_in_tab(world.first, "qualifier", "Qualifier 0") == (
        CHANGED_BLUE
    )


def test_undo_to_a_state_after_a_save_clears_the_marker(world) -> None:
    world.edit_qualifier("Two")
    world.stack.mark_saved()
    world.edit_qualifier("Three")
    assert world.color_in_tree("submodels", "Submodel") == CHANGED_BLUE

    world.stack.undo()

    assert world.color_in_tree("submodels", "Submodel") is None
    assert world.color_in_tab(world.first, "qualifier", "Qualifier 0") is None


def test_undo_past_the_saved_state_marks_the_tree(world) -> None:
    world.edit_qualifier("Two")
    world.stack.mark_saved()

    world.stack.undo()

    assert world.color_in_tree("submodels", "Submodel", "Group", "Pump") == (
        CHANGED_BLUE
    )


def test_the_tree_is_repainted_when_a_save_clears_the_marker(
    world, qtbot: QtBot
) -> None:
    world.edit_qualifier("Two")
    qtbot.wait(5)

    with qtbot.waitSignal(world.table.dataChanged, timeout=1000):
        world.stack.mark_saved()


def test_the_index_row_of_a_list_item_that_was_removed_can_still_be_painted(
    model_support,
) -> None:
    from tests.factories import make_list

    first = model.Property(None, value_type=model.datatypes.String, value="a")
    second = model.Property(None, value_type=model.datatypes.String, value="b")
    items = make_list("Items", [first, second])
    pack = model_support.pack_table(make_submodel(elements=[items]))
    from aas_editor.models import DetailedInfoTable

    list_index = model_support.find_path(
        pack, "", "submodels", "Submodel", "Items"
    )
    tab = DetailedInfoTable(pack.index(1, 0, list_index))
    index_row = model_support.find(tab, "index")
    items.value.remove(second)

    shown = index_row.siblingAtColumn(1).data(Qt.ItemDataRole.DisplayRole)

    assert shown == "-1"
