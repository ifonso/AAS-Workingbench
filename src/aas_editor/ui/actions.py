"""The seam where later features add actions to the views.

A feature that needs an action in the context menu or the toolbar describes it
with an `ActionSpec` and registers it. It does not edit `treeview_pack.py` or
`base.py`: every tree view builds its actions from the registry when it is
created, shows the ones that fit it, enables them with the rule of the spec,
and disables the ones that change a package while the editor is in Read mode.

Example:
    Registering an action that sets the category of the current element::

        def mark_as_parameter(context: ActionContext) -> None:
            element = context.index.data(OBJECT_ROLE)
            context.push(
                SetAttribute(
                    observer_for(context.package),
                    element,
                    "category",
                    "PARAMETER",
                )
            )


        register_action(
            ActionSpec(
                action_id="example.mark_as_parameter",
                text="Mark as parameter",
                run=mark_as_parameter,
                is_enabled=lambda context: context.index.isValid(),
                views=ViewKind.PACKAGES,
                toolbar=True,
            )
        )

    The module that registers must be imported before the first view is
    created, for example by the composition root, `__main__.py`.
"""

from collections.abc import Callable
from dataclasses import dataclass
import enum

from PyQt6 import sip
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QTreeView

from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack


READ_MODE_REASON = "Read mode is on. Switch to Edit mode in the View menu"


class ViewKind(enum.Flag):
    """The tree views that can show an action."""

    PACKAGES = enum.auto()
    """The tree of the open packages, on the left."""
    DETAILS = enum.auto()
    """The attributes of one object, in a tab."""
    ANY = PACKAGES | DETAILS


@dataclass(frozen=True)
class ActionContext:
    """What an action works on when it runs or when its state is updated.

    Attributes:
        view: The tree view that shows the action.
        index: The current index of the view. It may be invalid.
        selection: The selected indexes of the view.
        package: The package of the current index, or None.
        stack: The history of that package, or None.
    """

    view: QTreeView
    index: QModelIndex
    selection: tuple[QModelIndex, ...]
    package: object | None
    stack: CommandStack | None

    def push(self, command: Command) -> None:
        """Applies a command to the package of the context, as one step.

        Raises:
            RuntimeError: If the context has no package.
            ReadOnlyError: If Read mode is on.
        """
        if self.stack is None:
            raise RuntimeError("The current item belongs to no package")
        self.stack.push(command)


def _always(_: ActionContext) -> bool:
    return True


@dataclass(frozen=True)
class ActionSpec:
    """The description of one action.

    Attributes:
        action_id: A unique, stable name such as "structure.move_to_top".
        text: The text of the menu entry and the tooltip.
        run: Called when the user triggers the action.
        is_enabled: Tells whether the action applies to the current item. It
            is asked whenever the current item changes.
        mutates: Whether the action changes a package. Such an action is
            disabled in Read mode and in views that do not allow editing.
        views: The views that show the action.
        icon: The icon, if any.
        shortcut: The key sequence, if any. It works inside the view.
        status_tip: The text for the status bar.
        toolbar: Whether the main toolbar shows the action as well.
        order: Where it goes among the registered actions, lowest first.
    """

    action_id: str
    text: str
    run: Callable[[ActionContext], None]
    is_enabled: Callable[[ActionContext], bool] = _always
    mutates: bool = True
    views: ViewKind = ViewKind.ANY
    icon: QIcon | None = None
    shortcut: QKeySequence | None = None
    status_tip: str = ""
    toolbar: bool = False
    order: int = 100


class ActionRegistry:
    """The actions that features registered, in a stable order."""

    def __init__(self) -> None:
        self._specs: dict[str, ActionSpec] = {}

    def register(self, spec: ActionSpec) -> None:
        """Adds an action.

        Args:
            spec: The action to add.

        Raises:
            ValueError: If an action with the same id exists already.
        """
        if spec.action_id in self._specs:
            raise ValueError(f"Action id already registered: {spec.action_id}")
        self._specs[spec.action_id] = spec

    def unregister(self, action_id: str) -> None:
        """Removes an action. Views created later do not show it."""
        self._specs.pop(action_id, None)

    def specs_for(self, kind: ViewKind) -> list[ActionSpec]:
        """Returns the actions that a kind of view shows, in order."""
        wanted = [spec for spec in self._specs.values() if spec.views & kind]
        return sorted(
            wanted,
            key=lambda spec: (menu_section(spec.action_id), spec.order),
        )


_registry = ActionRegistry()

# The sections of the context menu, in order. An action belongs to the section
# of the prefix of its id, such as "structure" in "structure.move_up", so
# features that register on their own still end up next to related actions,
# whatever `order` they chose. Unknown prefixes go last.
_MENU_SECTIONS: tuple[tuple[str, ...], ...] = (
    ("create", "asset"),
    ("structure",),
    ("references", "reference"),
    ("conversion",),
    ("concepts",),
    ("bulk", "preset", "clipboard"),
    ("files", "blob"),
    ("navigate",),
)


# The sections with many actions are a submenu of the context menu, so that
# the menu of an element is not a list of fifty entries. The others are in the
# menu itself, between separators. Cut, Copy, Paste and Delete are not
# registered actions, so they stay at the top of the menu whatever is here.
_SUBMENU_TITLES = {
    1: "Move and paste",
    2: "Rename and references",
    4: "Concept descriptions",
    5: "Qualifiers, extensions and bulk changes",
    6: "Package files",
    7: "Location",
}


def menu_section(action_id: str) -> int:
    """Returns the section of the context menu that an action belongs to.

    Args:
        action_id: The id of the action, such as "structure.move_up".

    Returns:
        The index of the section, which is also its place in the menu.
    """
    prefix = action_id.partition(".")[0]
    for position, prefixes in enumerate(_MENU_SECTIONS):
        if prefix in prefixes:
            return position
    return len(_MENU_SECTIONS)


def menu_title(action_id: str) -> str:
    """Returns the submenu of the context menu that holds an action.

    Args:
        action_id: The id of the action, such as "structure.move_up".

    Returns:
        The title of the submenu, or an empty text if the action is in the
        menu itself.
    """
    return _SUBMENU_TITLES.get(menu_section(action_id), "")


def default_registry() -> ActionRegistry:
    """Returns the registry that the tree views use."""
    return _registry


def register_action(spec: ActionSpec) -> None:
    """Adds an action to the default registry. See `ActionSpec`."""
    _registry.register(spec)


class ViewActions:
    """The `QAction` objects that the registry gives to one view."""

    def __init__(
        self,
        view: QTreeView,
        kind: ViewKind,
        context: Callable[[], ActionContext],
        can_edit: Callable[[], bool],
        registry: ActionRegistry | None = None,
    ) -> None:
        """Builds an action for each registered spec that fits the view.

        Args:
            view: The tree view, which owns the actions.
            kind: Which kind of view it is.
            context: Returns the context for the current item.
            can_edit: Tells whether the view may change packages now.
            registry: The registry to read, by default the global one.
        """
        self._context = context
        self._can_edit = can_edit
        self._entries: list[tuple[ActionSpec, QAction]] = []
        self._submenus: list[tuple[QMenu, list[QAction]]] = []
        for spec in (registry or _registry).specs_for(kind):
            self._entries.append((spec, self._create(view, spec)))

    def _create(self, view: QTreeView, spec: ActionSpec) -> QAction:
        action = QAction(spec.text, view)
        if spec.icon is not None:
            action.setIcon(spec.icon)
        if spec.shortcut is not None:
            action.setShortcut(spec.shortcut)
            action.setShortcutContext(
                Qt.ShortcutContext.WidgetWithChildrenShortcut
            )
        action.setStatusTip(spec.status_tip)
        action.setToolTip(spec.status_tip or spec.text)
        action.setEnabled(False)
        action.triggered.connect(lambda: spec.run(self._context()))
        view.addAction(action)
        return action

    @property
    def actions(self) -> list[QAction]:
        """All actions of the view, in order."""
        return [action for _, action in self._entries]

    @property
    def entries(self) -> list[tuple[ActionSpec, QAction]]:
        """Each action of the view with the spec that made it, in order."""
        return list(self._entries)

    def disabled_reason(self, action: QAction) -> str:
        """Says why an action of the view is disabled, if the spec knows.

        Args:
            action: An action of this view.

        Returns:
            A sentence, or an empty text when the action is enabled or the
            reason is not known.
        """
        for spec, entry in self._entries:
            if entry is not action:
                continue
            if spec.mutates and not self._can_edit():
                return READ_MODE_REASON
            if not spec.is_enabled(self._context()):
                return "Does not apply to the selected row"
        return ""

    @property
    def mutating_actions(self) -> list[QAction]:
        """The actions that change a package."""
        return [action for spec, action in self._entries if spec.mutates]

    @property
    def toolbar_actions(self) -> list[QAction]:
        """The actions that the main toolbar shows as well."""
        return [action for spec, action in self._entries if spec.toolbar]

    def add_to_menu(self, menu: QMenu) -> None:
        """Appends the actions to a menu, with a separator between sections.

        A menu collapses separators next to each other, so a section whose
        actions are all hidden leaves no gap.
        """
        if not self._entries:
            return
        previous: int | None = None
        target: QMenu = menu
        for spec, action in self._entries:
            section = menu_section(spec.action_id)
            if previous != section:
                previous = section
                title = _SUBMENU_TITLES.get(section)
                if title is None:
                    menu.addSeparator()
                    target = menu
                else:
                    target = QMenu(title, menu)
                    menu.addMenu(target)
                    self._submenus.append((target, []))
            if target is not menu:
                self._submenus[-1][1].append(action)
            target.addAction(action)

    def _forget_deleted_submenus(self) -> None:
        """Drops the submenus whose menu its owner deleted.

        The view outlives a menu that was built for it, and the clipboard
        refreshes the view, so asking a deleted submenu would fail.
        """
        self._submenus = [
            (submenu, actions)
            for submenu, actions in self._submenus
            if not sip.isdeleted(submenu)
        ]

    def update(self) -> None:
        """Shows and enables each action by the rule of its spec.

        An action that does not apply to the current item is hidden, so the
        menu lists what the user can do with it, and not everything that is
        registered. One that applies but changes a package in Read mode stays
        visible and is disabled. Actions of the toolbar are never hidden, so
        the buttons do not move.
        """
        self._forget_deleted_submenus()
        context = self._context()
        for spec, action in self._entries:
            applies = spec.is_enabled(context)
            allowed = not spec.mutates or self._can_edit()
            action.setEnabled(allowed and applies)
            if not spec.toolbar:
                action.setVisible(applies)
        for submenu, actions in self._submenus:
            shown = [a for a in actions if a.isVisible()]
            entry = submenu.menuAction()
            if entry is not None:
                entry.setVisible(bool(shown))
                entry.setEnabled(any(a.isEnabled() for a in shown))

    def disable_mutating(self) -> None:
        """Disables the actions that change a package."""
        for action in self.mutating_actions:
            action.setEnabled(False)

    def find(self, action_id: str) -> QAction | None:
        """Returns the action of an id, or None."""
        for spec, action in self._entries:
            if spec.action_id == action_id:
                return action
        return None
