"""The context menu of an element holds what an element needs.

Save, Close, Zoom, Folding and Open in belong to the package or to the view.
They are in submenus, and the actions keep their shortcuts.
"""

from typing import Any

import pytest
from tests.factories import make_property
from tests.factories import make_submodel

# The menu had 38 entries for a property, before the entries of the editor
# were moved out of it.
MOST_ENTRIES_FOR_AN_ELEMENT = 26
FROM_THE_EDITOR = (
    "Save As...",
    "Save in JSON/XML/AASX",
    "Close AAS file",
    "Close all",
    "Zoom in",
    "Zoom out",
    "Folding",
    "Open in...",
    "Update/reload",
    "Add references to all Submodels to the first AAS",
)


def _top_level(menu: Any) -> list[str]:
    return [
        action.text()
        for action in menu.actions()
        if action.isVisible() and not action.isSeparator()
    ]


def _entry(menu: Any, text: str) -> Any:
    for action in menu.actions():
        if action.text() == text:
            return action
    raise LookupError(text)


@pytest.fixture
def shown(views: Any) -> Any:
    package_views = views()
    package_views.open_package(make_submodel(elements=[make_property("Speed")]))
    return package_views


def test_an_element_has_fewer_entries_than_before(shown: Any) -> None:
    shown.select(shown.index("submodels", "Submodel", "Speed"))

    entries = _top_level(shown.view.attrsMenu)

    assert len(entries) <= MOST_ENTRIES_FOR_AN_ELEMENT


def test_the_entries_of_the_editor_are_not_in_the_menu_of_an_element(
    shown: Any,
) -> None:
    shown.select(shown.index("submodels", "Submodel", "Speed"))

    entries = _top_level(shown.view.attrsMenu)

    assert [text for text in entries if text in FROM_THE_EDITOR] == []
    assert not [text for text in entries if text.startswith(("Save ", "Close"))]


def test_zoom_folding_update_and_open_in_are_in_the_view_submenu(
    shown: Any,
) -> None:
    shown.select(shown.index("submodels", "Submodel", "Speed"))
    view_menu = _entry(shown.view.attrsMenu, "View").menu()

    names = {action.text() for action in view_menu.actions()}

    assert {
        "Zoom in",
        "Zoom out",
        "Update/reload",
        "Folding",
        "Open in...",
    } <= (names)


def test_the_actions_in_the_submenu_keep_their_shortcuts(shown: Any) -> None:
    view = shown.view
    shown.select(shown.index("submodels", "Submodel", "Speed"))
    view_menu = _entry(view.attrsMenu, "View").menu()
    zoom_in = _entry(view_menu, "Zoom in")

    assert zoom_in is view.zoomInAct
    assert not zoom_in.shortcut().isEmpty()
    # A shortcut works for the actions of the widget that has the focus.
    assert zoom_in in view.actions()
    assert view.expandAllAct in view.actions()
    assert view.collapseAllAct in view.actions()


def test_the_package_entry_is_for_the_package_and_not_for_an_element(
    shown: Any,
) -> None:
    view = shown.view

    shown.select(shown.index("submodels", "Submodel", "Speed"))
    on_element = _entry(view.attrsMenu, "Package").isVisible()
    shown.select(shown.index())
    on_package = _entry(view.attrsMenu, "Package").isVisible()

    assert (on_element, on_package) == (False, True)


def test_the_package_entry_holds_save_and_close(shown: Any) -> None:
    shown.select(shown.index())
    package_menu = _entry(shown.view.attrsMenu, "Package").menu()

    texts = {action.text() for action in package_menu.actions()}

    assert {
        "Save As...",
        "Save in JSON/XML/AASX",
        "&Save All",
        "Close AAS file",
        "Close all",
    } <= texts
    assert any(text.startswith("Save ") for text in texts)


def test_save_and_close_stay_in_the_file_menu_and_the_toolbar_actions(
    shown: Any,
) -> None:
    view = shown.view

    # The same action objects are in the menu of the package and in the File
    # menu, which hides nothing: only the entry of the submenu is hidden.
    shown.select(shown.index("submodels", "Submodel", "Speed"))

    assert view.saveAct.isVisible()
    assert view.saveAsAct.isVisible()
    assert view.closeAct.isVisible()
    assert view.saveAllAct.isVisible()


def test_the_long_list_of_existing_submodels_shows_for_the_submodels_node_only(
    shown: Any,
) -> None:
    view = shown.view

    shown.select(shown.index("submodels", "Submodel", "Speed"))
    on_element = _entry(view.attrsMenu, "Add existing submodel").isVisible()
    shown.select(shown.index("submodels"))
    on_submodels = _entry(view.attrsMenu, "Add existing submodel").isVisible()

    assert (on_element, on_submodels) == (False, True)


def test_add_as_json_is_hidden_where_nothing_can_be_added(shown: Any) -> None:
    view = shown.view

    shown.select(shown.index("submodels", "Submodel", "Speed"))
    on_property = view.addAsJsonAct.isVisible()
    shown.select(shown.index("submodels", "Submodel"))
    on_submodel = view.addAsJsonAct.isVisible()

    assert (on_property, on_submodel) == (False, True)


def test_the_menu_of_a_tab_has_the_view_submenu_and_no_package_entries(
    shown: Any,
) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")

    entries = _top_level(attrs.attrsMenu)

    assert "View" in entries
    assert not [text for text in entries if text.startswith(("Save", "Close"))]
    assert "Package" not in entries


def test_open_in_is_shown_only_for_a_link(shown: Any) -> None:
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")
    attrs.setCurrentIndex(attrs.model().index(0, 0))

    view_menu = _entry(attrs.attrsMenu, "View").menu()

    assert not _entry(view_menu, "Open in...").isVisible()
