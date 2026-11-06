"""Finds the entries of a context menu, whether they are in a submenu or not."""

from typing import Any


def visible_actions(menu: Any) -> list[Any]:
    """Returns the visible entries of a menu, without its separators."""
    return [
        action
        for action in menu.actions()
        if action.isVisible() and not action.isSeparator()
    ]


def entry_paths(menu: Any) -> dict[str, tuple[str, ...]]:
    """Maps the text of every visible action to the submenus that hold it.

    The path of an entry at the top of the menu is empty. A submenu is listed
    by its own text, with the path that leads to it.
    """
    found: dict[str, tuple[str, ...]] = {}

    def walk(current: Any, path: tuple[str, ...]) -> None:
        for action in visible_actions(current):
            found[action.text()] = path
            if action.menu() is not None:
                walk(action.menu(), (*path, action.text()))

    walk(menu, ())
    return found


def find_action(menu: Any, text: str) -> Any:
    """Finds a visible action in a menu or in any submenu below it.

    Raises:
        LookupError: If no visible action has the text.
    """
    stack = [menu]
    while stack:
        current = stack.pop()
        for action in visible_actions(current):
            if action.text() == text and action.menu() is None:
                return action
            if action.menu() is not None:
                stack.append(action.menu())
    raise LookupError(text)
