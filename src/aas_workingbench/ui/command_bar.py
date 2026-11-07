"""The command bar and the Edit menu, which act on the view with the focus.

The window has one bar of buttons, and the tree of packages and each tab have
their own undo, redo, add, edit and delete. A button of the bar must run the
action of the view that the user works in, so each entry is a `MirroredAction`:
it follows an action of the focused view (its enabled state and its shortcut)
and triggers it. The mirror shows the key but never runs it, because the
shortcut of the view already does, inside the view (`WidgetShortcut` context),
and two owners of one key would make it ambiguous.

The focused view is the last tree view of the window that had the focus. The
tree of packages is the one before any other, and when the tab of the last
view is gone.
"""

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6 import sip
from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.settings.icons import ADD_ICON
from aas_workingbench.settings.icons import BACK_ICON
from aas_workingbench.settings.icons import COLLAPSE_ALL_ICON
from aas_workingbench.settings.icons import COPY_ICON
from aas_workingbench.settings.icons import CUT_ICON
from aas_workingbench.settings.icons import DEL_ICON
from aas_workingbench.settings.icons import EDIT_ICON
from aas_workingbench.settings.icons import EXPAND_ALL_ICON
from aas_workingbench.settings.icons import FORWARD_ICON
from aas_workingbench.settings.icons import PASTE_ICON
from aas_workingbench.settings.icons import REDO_ICON
from aas_workingbench.settings.icons import UNDO_ICON
from aas_workingbench.ui.actions import READ_MODE_REASON
from aas_workingbench.ui.paste_actions import ABOVE_ID
from aas_workingbench.ui.paste_actions import BELOW_ID
from aas_workingbench.ui.paste_actions import INTO_ID


@dataclass(frozen=True)
class FocusTarget:
    """What the bar acts on.

    Attributes:
        view: The tree view with the focus.
        tab: The tab that holds the view, or the current tab of the window
            when the view is the tree of packages. None if there is none.
    """

    view: QTreeView
    tab: QWidget | None


Resolve = Callable[[FocusTarget], QAction | None]


def _on_view(name: str) -> Resolve:
    return lambda target: getattr(target.view, name, None)


def _registered(action_id: str) -> Resolve:
    def resolve(target: FocusTarget) -> QAction | None:
        registered = getattr(target.view, "registeredActions", None)
        return None if registered is None else registered.find(action_id)

    return resolve


def _on_tab(name: str) -> Resolve:
    return lambda target: getattr(target.tab, name, None)


@dataclass(frozen=True)
class CommandSpec:
    """One entry of the bar or of the Edit menu.

    Attributes:
        key: What the window calls the entry.
        text: The text of the menu entry.
        tip: What the button does, which its tooltip and the status bar say.
        icon: The icon, if any.
        resolve: Finds the action of the focused view that the entry runs.
    """

    key: str
    text: str
    tip: str
    icon: QIcon | None
    resolve: Resolve


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "undo", "Undo", "Undo the last change", UNDO_ICON, _on_view("undoAct")
    ),
    CommandSpec(
        "redo",
        "Redo",
        "Redo the last undone change",
        REDO_ICON,
        _on_view("redoAct"),
    ),
    CommandSpec(
        "cut", "Cut", "Cut the selected items", CUT_ICON, _on_view("cutAct")
    ),
    CommandSpec(
        "copy",
        "Copy",
        "Copy the selected items",
        COPY_ICON,
        _on_view("copyAct"),
    ),
    CommandSpec(
        "paste",
        "Paste",
        "Paste from the clipboard",
        PASTE_ICON,
        _on_view("pasteAct"),
    ),
    CommandSpec(
        "paste_above",
        "Paste above",
        "Insert the pasted elements before the selected one",
        None,
        _registered(ABOVE_ID),
    ),
    CommandSpec(
        "paste_below",
        "Paste below",
        "Insert the pasted elements after the selected one",
        None,
        _registered(BELOW_ID),
    ),
    CommandSpec(
        "paste_into",
        "Paste into",
        "Add the pasted elements at the end of the selected one",
        None,
        _registered(INTO_ID),
    ),
    CommandSpec(
        "add",
        "Add",
        "Add an item to the selected one",
        ADD_ICON,
        _on_view("addAct"),
    ),
    CommandSpec(
        "edit",
        "Edit in dialog",
        "Edit or create the selected item in a dialog",
        EDIT_ICON,
        _on_view("editCreateInDialogAct"),
    ),
    CommandSpec(
        "delete",
        "Delete",
        "Delete or clear the selected items",
        DEL_ICON,
        _on_view("delClearAct"),
    ),
    CommandSpec(
        "back",
        "Back",
        "Go back one item in this tab",
        BACK_ICON,
        _on_tab("backAct"),
    ),
    CommandSpec(
        "forward",
        "Forward",
        "Go forward one item in this tab",
        FORWARD_ICON,
        _on_tab("forwardAct"),
    ),
    CommandSpec(
        "collapse_all",
        "Collapse all",
        "Collapse all items of the view",
        COLLAPSE_ALL_ICON,
        _on_view("collapseAllAct"),
    ),
    CommandSpec(
        "expand_all",
        "Expand all",
        "Expand all items of the view",
        EXPAND_ALL_ICON,
        _on_view("expandAllAct"),
    ),
)


# The entries that change a package. Read mode turns them off, and the tooltip
# of an entry that is off says so.
EDITING_KEYS = frozenset(
    {
        "undo",
        "redo",
        "cut",
        "paste",
        "paste_above",
        "paste_below",
        "paste_into",
        "add",
        "edit",
        "delete",
    }
)


class MirroredAction(QAction):
    """An action that runs another action, and looks like it.

    It is enabled when the other one is, shows its key, and triggers it. With
    no action to follow it is disabled.
    """

    def __init__(self, spec: CommandSpec, parent: QObject) -> None:
        """Creates the action, not yet following any other.

        Args:
            spec: What the entry is called and where it finds its action.
            parent: The owner of the action.
        """
        super().__init__(spec.text, parent)
        self.spec = spec
        self._source: QAction | None = None
        if spec.icon is not None:
            self.setIcon(spec.icon)
        self.setStatusTip(spec.tip)
        # The key is shown, and never run from here: the view runs it.
        self.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.triggered.connect(self._run)
        edit_mode().subscribe(self._on_mode)
        self.follow(None)

    def _on_mode(self, editing: bool) -> None:
        del editing
        if not sip.isdeleted(self):
            self._sync()

    @property
    def source(self) -> QAction | None:
        """The action that this one runs now, or None."""
        return self._source

    def follow(self, source: QAction | None) -> None:
        """Runs another action from now on.

        Args:
            source: The action of the focused view, or None.
        """
        if self._source is not None and not sip.isdeleted(self._source):
            self._source.changed.disconnect(self._sync)
        self._source = source
        if source is not None:
            source.changed.connect(self._sync)
        self._sync()

    def _sync(self) -> None:
        source = self._source
        if source is not None and sip.isdeleted(source):
            source = self._source = None
        enabled = source is not None and source.isEnabled()
        self.setEnabled(enabled)
        keys = source.shortcuts() if source is not None else []
        self.setShortcuts(keys)
        hint = (
            f" ({keys[0].toString(QKeySequence.SequenceFormat.NativeText)})"
            if keys
            else ""
        )
        reason = (
            f". {READ_MODE_REASON}"
            if not enabled
            and not edit_mode().is_editing
            and self.spec.key in EDITING_KEYS
            else ""
        )
        self.setToolTip(f"{self.spec.tip}{hint}{reason}")
        self.setStatusTip(f"{self.spec.tip}{reason}")

    def _run(self) -> None:
        if self._source is not None and self._source.isEnabled():
            self._source.trigger()


class FocusedViewActions(QObject):
    """The actions of the window that follow the view with the focus.

    Attributes:
        actions: The mirrored actions, by the key of their spec.
    """

    def __init__(
        self,
        window: QMainWindow,
        tree_view: QTreeView,
        tabs: QTabWidget,
    ) -> None:
        """Builds the actions and starts following the focus.

        Args:
            window: The main window, which owns the actions.
            tree_view: The tree of packages, which has the focus when no other
                view of the window had it.
            tabs: The main tab widget, whose current tab the tree of packages
                is read with.
        """
        super().__init__(window)
        self._window = window
        self._tree = tree_view
        self._tabs = tabs
        self._last: QTreeView | None = None
        self.actions = {
            spec.key: MirroredAction(spec, self) for spec in COMMANDS
        }
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._on_focus)
        tabs.currentChanged.connect(self.refresh)
        self.refresh()

    def target(self) -> FocusTarget:
        """Returns the view that the actions follow, and its tab."""
        view = self._last
        if view is None or sip.isdeleted(view) or not view.isVisible():
            view = self._tree
        tab = self._tab_of(view)
        return FocusTarget(view, tab)

    def refresh(self, *_: object) -> None:
        """Makes each action follow the action of the focused view."""
        target = self.target()
        for action in self.actions.values():
            action.follow(action.spec.resolve(target))

    def _on_focus(self, _old: QWidget | None, new: QWidget | None) -> None:
        view = self._view_of(new)
        if view is not None and view is not self._last:
            self._last = view
            self.refresh()

    def _view_of(self, widget: QWidget | None) -> QTreeView | None:
        """Returns the tree view of this window that holds the widget."""
        while widget is not None:
            if (
                isinstance(widget, QTreeView)
                and hasattr(widget, "undoAct")
                and widget.window() is self._window
            ):
                return widget
            widget = widget.parentWidget()
        return None

    def _tab_of(self, view: QTreeView) -> QWidget | None:
        if view is self._tree:
            return self._tabs.currentWidget()
        widget = view.parentWidget()
        while widget is not None:
            if hasattr(widget, "backAct"):
                return widget
            widget = widget.parentWidget()
        return None
