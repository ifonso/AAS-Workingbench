"""The context menu of an element is short, and Paste is at its top."""

from typing import Any

import pytest
from tests.factories import make_property
from tests.factories import make_submodel
from tests.menus import entry_paths
from tests.menus import find_action
from tests.menus import visible_actions

# The menu had 28 entries for a property before the sections of structure,
# names and location became submenus.
MOST_ENTRIES_FOR_A_PROPERTY = 21
CLIPBOARD_ENTRIES = ("Cut", "Copy", "Paste", "Delete/clear")


@pytest.fixture
def shown(views: Any) -> Any:
    from aas_editor.ui.location_actions import register_location_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions
    from aas_editor.ui.reference_actions import register_reference_actions

    register_move_actions()
    register_paste_actions()
    register_reference_actions()
    register_location_actions()
    package_views = views()
    package_views.open_package(make_submodel(elements=[make_property("Speed")]))
    package_views.select(package_views.index("submodels", "Submodel", "Speed"))
    return package_views


def test_a_property_has_about_twenty_entries_at_the_top(shown: Any) -> None:
    entries = visible_actions(shown.view.attrsMenu)

    assert len(entries) <= MOST_ENTRIES_FOR_A_PROPERTY


def test_cut_copy_paste_and_delete_stay_at_the_top_level(shown: Any) -> None:
    paths = entry_paths(shown.view.attrsMenu)

    assert [paths[text] for text in CLIPBOARD_ENTRIES] == [()] * 4


def test_the_structure_actions_are_in_one_submenu(shown: Any) -> None:
    paths = entry_paths(shown.view.attrsMenu)

    for text in ("Move up", "Move down", "Paste above", "Paste below"):
        assert paths[text] == ("Move and paste",)


def test_an_action_in_a_submenu_is_found_by_its_text(shown: Any) -> None:
    menu = shown.view.attrsMenu

    action = find_action(menu, "Paste below")

    assert action is shown.view.registeredActions.find("structure.paste_below")


def test_the_submenus_hold_the_registered_actions_that_were_at_the_top(
    shown: Any,
) -> None:
    paths = entry_paths(shown.view.attrsMenu)

    assert paths["Rename idShort..."] == ("Rename and references",)
    assert paths["Push location"] == ("Location",)


def test_the_submenu_of_a_row_is_hidden_when_nothing_in_it_applies(
    shown: Any,
) -> None:
    shown.select(shown.index("submodels"))

    paths = entry_paths(shown.view.attrsMenu)

    assert "Location" in paths  # Pop location applies to every row
    assert "Rename idShort..." not in paths


def test_every_registered_action_stays_reachable_in_the_menu(
    shown: Any,
) -> None:
    menu = shown.view.attrsMenu
    shown.view.updateActions(shown.index("submodels", "Submodel", "Speed"))

    reachable = entry_paths(menu)

    for action in shown.view.registeredActions.actions:
        if action.isVisible():
            assert action.text() in reachable
