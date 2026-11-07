"""Moving between the panes of the window by key.

`F6` goes to the next pane and `Shift+F6` to the one before it, as in Explorer
and most Windows applications. A pane is a region that holds the focus for a
while: the tree of packages (or the start panel while no package is open), the
tab, and the bottom panel. `Ctrl+1` and `Ctrl+2` go straight to the tree and to
the tab. A pane that is not on show, such as a hidden bottom panel, is skipped.

The menu bar and the command bar are not panes. The menus open with `Alt`, and
every button of the command bar is an entry of a menu with its own key.
"""

from collections.abc import Callable
from collections.abc import Sequence
from dataclasses import dataclass

from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QWidget

TREE = "tree"
TAB = "tab"
PANEL = "panel"
"""The keys of the panes, in the order that `F6` visits them."""

NEXT_KEY = "F6"
PREVIOUS_KEY = "Shift+F6"
TREE_KEY = "Ctrl+1"
TAB_KEY = "Ctrl+2"


@dataclass(frozen=True)
class Pane:
    """One region of the window that can hold the focus.

    Attributes:
        key: What the window calls the pane.
        holders: The widgets that hold the pane. The focus is in the pane when
            it is in one of them, or in a widget below one of them.
        target: Finds the widget that takes the focus when the pane is
            entered, or None while the pane is not on show.
    """

    key: str
    holders: Callable[[], Sequence[QWidget]]
    target: Callable[[], QWidget | None]


def first_focusable(root: QWidget | None) -> QWidget | None:
    """Finds the first widget under the root that a Tab stops at.

    Args:
        root: The widget to look under, or None.

    Returns:
        The first visible, enabled widget of the root that accepts the focus by
        Tab, in the order that the Tab key follows, or None.
    """
    if root is None or not root.isVisible():
        return None
    candidate: QWidget | None = root
    # The chain is a ring over the whole window, so go round once.
    while candidate is not None:
        if (
            (candidate is root or root.isAncestorOf(candidate))
            and candidate.isVisible()
            and candidate.isEnabled()
            and candidate.focusPolicy() & Qt.FocusPolicy.TabFocus
        ):
            return candidate
        candidate = candidate.nextInFocusChain()
        if candidate is root:
            return None
    return None


class PaneNavigator(QObject):
    """The keys that move the focus between the panes of a window.

    Attributes:
        next_action: Goes to the next pane (`F6`).
        previous_action: Goes to the pane before (`Shift+F6`).
        tree_action: Goes to the tree of packages (`Ctrl+1`).
        tab_action: Goes to the tab (`Ctrl+2`).
    """

    def __init__(self, window: QWidget, panes: Sequence[Pane]) -> None:
        """Builds the actions. The window shows them in a menu.

        Args:
            window: The window whose panes these are, which owns the actions
                and receives their keys.
            panes: The panes in the order that `F6` visits them.
        """
        super().__init__(window)
        self._panes = list(panes)
        self.next_action = self._action(
            "Next pane",
            "Move the focus to the next pane",
            NEXT_KEY,
            lambda: self.step(1),
            window,
        )
        self.previous_action = self._action(
            "Previous pane",
            "Move the focus to the pane before",
            PREVIOUS_KEY,
            lambda: self.step(-1),
            window,
        )
        self.tree_action = self._action(
            "Focus the package tree",
            "Move the focus to the tree of packages",
            TREE_KEY,
            lambda: self.focus_pane(TREE),
            window,
        )
        self.tab_action = self._action(
            "Focus the tab",
            "Move the focus to the tab",
            TAB_KEY,
            lambda: self.focus_pane(TAB),
            window,
        )

    @property
    def actions(self) -> list[QAction]:
        """The four actions, in the order that a menu lists them."""
        return [
            self.next_action,
            self.previous_action,
            self.tree_action,
            self.tab_action,
        ]

    def current(self) -> str | None:
        """Returns the key of the pane that has the focus, or None."""
        focus = QApplication.focusWidget()
        if focus is None:
            return None
        for pane in self._panes:
            for holder in pane.holders():
                if focus is holder or holder.isAncestorOf(focus):
                    return pane.key
        return None

    def step(self, direction: int) -> bool:
        """Moves the focus to the next or the previous pane that is on show.

        Args:
            direction: 1 for the next pane and -1 for the one before.

        Returns:
            Whether the focus moved. When it is in none of the panes, it goes
            to the first one, or to the last one when going back.
        """
        shown = [
            (pane.key, target)
            for pane in self._panes
            if (target := pane.target()) is not None
        ]
        if not shown:
            return False
        keys = [key for key, _ in shown]
        here = self.current()
        if here in keys:
            place = (keys.index(here) + direction) % len(shown)
        else:
            place = 0 if direction > 0 else len(shown) - 1
        shown[place][1].setFocus(Qt.FocusReason.ShortcutFocusReason)
        return True

    def focus_pane(self, key: str) -> bool:
        """Moves the focus to a pane.

        Args:
            key: The key of the pane.

        Returns:
            Whether the pane is on show, and so has the focus now.
        """
        for pane in self._panes:
            if pane.key == key:
                target = pane.target()
                if target is None:
                    return False
                target.setFocus(Qt.FocusReason.ShortcutFocusReason)
                return True
        return False

    @staticmethod
    def _action(
        text: str,
        tip: str,
        key: str,
        run: Callable[[], object],
        window: QWidget,
    ) -> QAction:
        action = QAction(text, window)
        action.setStatusTip(tip)
        action.setShortcut(QKeySequence(key))
        action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)

        def trigger(_checked: bool = False) -> None:
            run()

        action.triggered.connect(trigger)
        # The menu that lists it may be built later, and the key must work
        # before that and while the menu is hidden.
        window.addAction(action)
        return action
