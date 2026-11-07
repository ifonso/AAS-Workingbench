"""The command bar acts on the view that has the focus.

The buttons of the bar and the entries of the Edit menu are mirrors of the
actions of a view. They run the action of the view that the user works in, show
its state and its key, and never run the key themselves.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.ui.command_bar import COMMANDS
from aas_workingbench.ui.command_bar import CommandSpec
from aas_workingbench.ui.command_bar import FocusedViewActions
from aas_workingbench.ui.command_bar import MirroredAction


class FakeView(QTreeView):
    """A tree view with the actions that the editor's views have."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.runs: list[str] = []
        self.undoAct = QAction("Undo", self)
        self.undoAct.setShortcut(QKeySequence("Ctrl+Z"))
        self.undoAct.triggered.connect(lambda: self.runs.append("undo"))
        self.redoAct = QAction("Redo", self)
        self.redoAct.setEnabled(False)


class FakeTab(QWidget):
    """What the bar reads of a tab: its back and forward actions."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = FakeView(self)
        self.backAct = QAction("Back", self)
        self.forwardAct = QAction("Forward", self)


@dataclass
class Window:
    window: QMainWindow
    tree: FakeView
    tabs: QTabWidget
    tab: FakeTab
    actions: FocusedViewActions


@pytest.fixture
def parts(qapp: object, qtbot: QtBot) -> Iterator[Window]:
    """A window with a tree of packages and one tab, with the bar's actions."""
    window = QMainWindow()
    tree = FakeView()
    tabs = QTabWidget()
    tab = FakeTab()
    tabs.addTab(tab, "tab")
    central = QWidget()
    layout = QVBoxLayout(central)
    layout.addWidget(tree)
    layout.addWidget(tabs)
    window.setCentralWidget(central)
    qtbot.addWidget(window)
    window.show()
    yield Window(
        window, tree, tabs, tab, FocusedViewActions(window, tree, tabs)
    )


def _spec(key: str) -> CommandSpec:
    return next(spec for spec in COMMANDS if spec.key == key)


def test_a_mirror_runs_the_action_that_it_follows(
    qapp: object, qtbot: QtBot
) -> None:
    view = FakeView()
    qtbot.addWidget(view)
    mirror = MirroredAction(_spec("undo"), view)

    mirror.follow(view.undoAct)
    mirror.trigger()

    assert view.runs == ["undo"]


def test_a_mirror_is_enabled_as_the_action_it_follows(
    qapp: object, qtbot: QtBot
) -> None:
    view = FakeView()
    qtbot.addWidget(view)
    mirror = MirroredAction(_spec("redo"), view)

    mirror.follow(view.redoAct)
    assert not mirror.isEnabled()
    view.redoAct.setEnabled(True)

    assert mirror.isEnabled()


def test_a_mirror_with_nothing_to_follow_is_disabled(
    qapp: object, qtbot: QtBot
) -> None:
    view = FakeView()
    qtbot.addWidget(view)
    mirror = MirroredAction(_spec("undo"), view)
    mirror.follow(view.undoAct)

    mirror.follow(None)

    assert not mirror.isEnabled()
    mirror.trigger()
    assert view.runs == []


def test_a_mirror_shows_the_key_but_does_not_own_it(
    qapp: object, qtbot: QtBot
) -> None:
    view = FakeView()
    qtbot.addWidget(view)
    mirror = MirroredAction(_spec("undo"), view)

    mirror.follow(view.undoAct)

    assert mirror.shortcut() == QKeySequence("Ctrl+Z")
    assert mirror.shortcutContext() == Qt.ShortcutContext.WidgetShortcut
    assert "Ctrl+Z" in mirror.toolTip()


def test_a_mirror_forgets_an_action_that_was_deleted(
    qapp: object, qtbot: QtBot
) -> None:
    view = FakeView()
    qtbot.addWidget(view)
    mirror = MirroredAction(_spec("undo"), view)
    mirror.follow(view.undoAct)

    view.undoAct.deleteLater()
    qtbot.wait(10)
    mirror.follow(None)

    assert mirror.source is None


def test_the_bar_follows_the_tree_of_packages_at_first(parts: Window) -> None:
    assert parts.actions.actions["undo"].source is parts.tree.undoAct


def test_the_bar_follows_the_tab_for_back_and_forward(parts: Window) -> None:
    assert parts.actions.actions["back"].source is parts.tab.backAct
    assert parts.actions.actions["forward"].source is parts.tab.forwardAct


def test_an_action_that_the_view_does_not_have_is_disabled(
    parts: Window,
) -> None:
    # The fake views have no add action, so the entry has nothing to run.
    assert parts.actions.actions["add"].source is None
    assert not parts.actions.actions["add"].isEnabled()


def test_the_bar_follows_the_view_that_got_the_focus(
    parts: Window, qtbot: QtBot
) -> None:
    parts.window.activateWindow()
    qtbot.waitActive(parts.window)

    parts.tab.view.setFocus()
    qtbot.waitUntil(parts.tab.view.hasFocus)

    assert parts.actions.actions["undo"].source is parts.tab.view.undoAct
    assert parts.actions.actions["redo"].source is parts.tab.view.redoAct
    assert parts.actions.target().tab is parts.tab


def test_the_bar_returns_to_the_tree_when_the_view_is_hidden(
    parts: Window, qtbot: QtBot
) -> None:
    parts.window.activateWindow()
    qtbot.waitActive(parts.window)
    parts.tab.view.setFocus()
    qtbot.waitUntil(parts.tab.view.hasFocus)

    parts.tab.view.hide()
    parts.actions.refresh()

    assert parts.actions.actions["undo"].source is parts.tree.undoAct
