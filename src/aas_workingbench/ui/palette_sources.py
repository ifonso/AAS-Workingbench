"""Gathers what the command palette lists from the main window.

The commands are the actions that the window already has: the entries of its
menus, and the registered actions of the package tree, which live in the
context menu. The palette does not keep a list of its own, so a new action
shows up in it as soon as a menu or the registry has it. The elements are the
shells, submodels, concept descriptions and submodel elements of the open
packages.
"""

from collections.abc import Collection
from collections.abc import Iterable
import re

from basyx.aas import model
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QMenuBar
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.command_palette import EntryKind
from aas_workingbench.application.command_palette import PaletteEntry
from aas_workingbench.domain.walking import walk_elements
from aas_workingbench.ui.actions import READ_MODE_REASON
from aas_workingbench.ui.actions import ViewActions
from aas_workingbench.ui.actions import menu_title

CONTEXT_MENU = "Context menu"
TREE_MENU = "Package tree"
_MNEMONIC = re.compile(r"&(.)")
_PATH_SEPARATOR = " > "


def action_title(action: QAction) -> str:
    """Gives the text of an action as a line reads it, without the mnemonic."""
    return _MNEMONIC.sub(r"\1", action.text())


def registered_entries(
    actions: ViewActions, taken: set[int]
) -> list[PaletteEntry]:
    """Makes an entry for each registered action of a view.

    Args:
        actions: The registered actions of the package tree.
        taken: The ids of the `QAction` objects that have an entry. The ones
            made here are added, so that a menu does not list them twice.

    Returns:
        The entries, each with its action as the payload. A disabled action
        says why when its spec knows.
    """
    entries: list[PaletteEntry] = []
    for spec, action in actions.entries:
        title = action_title(action) or spec.text
        taken.add(id(action))
        place = menu_title(spec.action_id)
        reason = "" if action.isEnabled() else actions.disabled_reason(action)
        entries.append(
            PaletteEntry(
                spec.action_id,
                title,
                EntryKind.COMMAND,
                detail=_PATH_SEPARATOR.join(
                    part for part in (CONTEXT_MENU, place) if part
                ),
                shortcut=_keys(action),
                enabled=action.isEnabled(),
                reason=reason,
                payload=action,
            )
        )
    return entries


def menu_entries(
    menu_bar: QMenuBar, taken: Collection[int] = ()
) -> list[PaletteEntry]:
    """Makes an entry for each action in the menus of a menu bar.

    Args:
        menu_bar: The menu bar of the main window.
        taken: The ids of the `QAction` objects to leave out, such as the ones
            that have an entry already, and the action of the palette itself.

    Returns:
        The entries, each with its action as the payload and its menu path as
        the detail. A submenu is walked, and has no entry of its own.
    """
    entries: list[PaletteEntry] = []
    seen = set(taken)
    for action in menu_bar.actions():
        menu = _submenu(action)
        if menu is not None:
            _walk(menu, [action_title(action)], seen, entries)
    return entries


def tree_entries(
    view: QWidget, taken: set[int], editing: bool
) -> list[PaletteEntry]:
    """Makes an entry for each other action that the package tree has.

    These are Copy, Cut, Paste, Delete, Undo, Redo, the expand and collapse
    actions, and the like. They are in the context menu and have keys, but a
    menu of the window does not list them, and the registry does not know them.

    Args:
        view: The package tree view.
        taken: The ids of the `QAction` objects that have an entry. The ones
            made here are added.
        editing: Whether the editor is in Edit mode. In Read mode an action
            that edits is disabled, and the entry says so.

    Returns:
        The entries, each with its action as the payload.
    """
    changing = {id(a) for a in getattr(view, "editingActions", ())}
    entries: list[PaletteEntry] = []
    for action in view.actions():
        title = action_title(action)
        if not title or action.isSeparator() or id(action) in taken:
            continue
        taken.add(id(action))
        enabled = action.isEnabled()
        reason = ""
        if not enabled and not editing and id(action) in changing:
            reason = READ_MODE_REASON
        entries.append(
            PaletteEntry(
                f"tree:{title}",
                title,
                EntryKind.COMMAND,
                detail=TREE_MENU,
                shortcut=_keys(action),
                enabled=enabled,
                reason=reason,
                payload=action,
            )
        )
    return entries


def element_entries(
    packages: Iterable[object], show_package: bool
) -> list[PaletteEntry]:
    """Makes an entry for each object of the open packages that has a name.

    Args:
        packages: The open packages, each with an `objStore`.
        show_package: Whether the detail names the package, which is useful
            when more than one is open.

    Returns:
        One entry for each shell, submodel, concept description and element.
        The payload is the pair of the package and the object. The title is
        the idShort, and the id is matched too.
    """
    entries: list[PaletteEntry] = []
    for package in packages:
        store = getattr(package, "objStore", ())
        where = f" in {getattr(package, 'name', '')}" if show_package else ""
        for obj in store:
            entries.append(_element_entry(package, obj, where))
            if isinstance(obj, model.Submodel):
                entries.extend(
                    _element_entry(package, element, where)
                    for element in walk_elements(obj)
                )
    return entries


# -- internals --------------------------------------------------------------


def _walk(
    menu: QMenu, path: list[str], seen: set[int], entries: list[PaletteEntry]
) -> None:
    for action in menu.actions():
        if action.isSeparator() or not action.isVisible():
            continue
        title = action_title(action)
        submenu = _submenu(action)
        if submenu is not None:
            _walk(submenu, [*path, title], seen, entries)
            continue
        if not title or id(action) in seen:
            continue
        seen.add(id(action))
        entries.append(
            PaletteEntry(
                f"menu:{_PATH_SEPARATOR.join([*path, title])}",
                title,
                EntryKind.COMMAND,
                detail=_PATH_SEPARATOR.join(path),
                shortcut=_keys(action),
                enabled=action.isEnabled(),
                payload=action,
            )
        )


def _submenu(action: QAction) -> QMenu | None:
    found: object = action.menu()  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return found if isinstance(found, QMenu) else None


def _keys(action: QAction) -> str:
    return action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)


def _element_entry(package: object, obj: object, where: str) -> PaletteEntry:
    kind = type(obj).__name__
    name = getattr(obj, "id_short", None) or ""
    identifier = getattr(obj, "id", "")
    parent = getattr(obj, "parent", None)
    parent_name = ""
    if parent is not None:
        parent_name = getattr(parent, "id_short", None) or getattr(
            parent, "id", ""
        )
    inside = f" in {parent_name}" if parent_name else ""
    return PaletteEntry(
        f"element:{id(obj)}",
        name or identifier,
        EntryKind.ELEMENT,
        detail=f"{kind}{inside}{where}",
        keywords=identifier,
        payload=(package, obj),
    )
