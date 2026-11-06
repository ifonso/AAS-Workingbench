"""The seam where later features add actions to the views.

A feature that needs an action in the context menu or the toolbar describes it
with an `ActionSpec` and registers it. It does not edit `treeview_pack.py` or
`base.py`: every tree view builds its actions from the registry when it is
created, shows the ones that fit it, enables them with the rule of the spec,
and disables the ones that change a package while the editor is in Read mode.

Example:
    Registering an action that moves the current element to the top::

        def move_to_top(context: ActionContext) -> None:
            element = context.index.data(OBJECT_ROLE)
            context.push(MoveMember(observer_for(context.package), ...))


        register_action(
            ActionSpec(
                action_id="structure.move_to_top",
                text="Move to top",
                run=move_to_top,
                is_enabled=lambda context: context.index.isValid(),
                views=ViewKind.PACKAGES,
                toolbar=True,
            )
        )

    The module that registers must be imported before the first view is
    created, for example from `aas_editor/ui/__init__.py`.
"""

from collections.abc import Callable
from dataclasses import dataclass
import enum

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QTreeView

from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack


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
        return sorted(wanted, key=lambda spec: spec.order)


_registry = ActionRegistry()


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
    def mutating_actions(self) -> list[QAction]:
        """The actions that change a package."""
        return [action for spec, action in self._entries if spec.mutates]

    @property
    def toolbar_actions(self) -> list[QAction]:
        """The actions that the main toolbar shows as well."""
        return [action for spec, action in self._entries if spec.toolbar]

    def add_to_menu(self, menu: QMenu) -> None:
        """Appends the actions to a menu, after a separator."""
        if not self._entries:
            return
        menu.addSeparator()
        for action in self.actions:
            menu.addAction(action)

    def update(self) -> None:
        """Enables each action by the rule of its spec and the editing state."""
        context = self._context()
        for spec, action in self._entries:
            allowed = not spec.mutates or self._can_edit()
            action.setEnabled(allowed and spec.is_enabled(context))

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
