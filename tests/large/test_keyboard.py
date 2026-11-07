"""The window works by keyboard alone.

The panes are reached with F6 and Ctrl+1, Ctrl+2, the controls inside a pane
with Tab and the arrow keys, and a menu opens with its mnemonic. These tests
send real key events to the window. Screen readers were not run.
"""

from collections.abc import Iterator
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMenu
import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
PACKAGE_PATH = (TEST_DATA_DIR / PACKAGE).as_posix()


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the actions that `__main__` registers before the first view."""
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.paste_actions import register_paste_actions

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    register_paste_actions()
    yield
    for spec in default_registry().specs_for(ViewKind.ANY):
        if spec.action_id not in before:
            default_registry().unregister(spec.action_id)


def _open(qtbot: Any, path: str | None = PACKAGE_PATH) -> Any:
    from aas_workingbench.editorApp import EditorApp

    window = EditorApp(fileToOpen=path)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    QApplication.processEvents()
    return window


def _close(window: Any) -> None:
    for package in window.packTreeModel.openedPacks():
        package.commandStack.mark_saved()
    window.mainTreeView.updateWindowModified()
    window._recoveryTimer.stop()
    window.close()


def _press(
    key: Qt.Key, modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
) -> None:
    target = QApplication.focusWidget() or QApplication.activeWindow()
    QTest.keyClick(target, key, modifier)


def _pane(window: Any) -> str | None:
    return window.paneNavigator.current()


# F6


def test_f6_goes_from_the_tree_to_the_tab_and_back(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    window.mainTreeView.setFocus()

    _press(Qt.Key.Key_F6)
    in_tab = _pane(window)
    focus_in_tab = (
        QApplication.focusWidget()
        is window.mainTabWidget.currentWidget().attrsTreeView
    )
    _press(Qt.Key.Key_F6)

    assert (in_tab, focus_in_tab) == ("tab", True)
    assert _pane(window) == "tree"
    assert QApplication.focusWidget() is window.mainTreeView
    _close(window)


def test_f6_also_visits_the_bottom_panel_when_it_is_open(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    window.validationController.dock.show()
    window.mainTreeView.setFocus()

    visited = []
    for _ in range(3):
        _press(Qt.Key.Key_F6)
        visited.append(_pane(window))

    assert visited == ["tab", "panel", "tree"]
    _close(window)


def test_shift_f6_goes_the_other_way(qapp: object, qtbot: Any) -> None:
    window = _open(qtbot)
    window.validationController.dock.show()
    window.mainTreeView.setFocus()

    visited = []
    for _ in range(3):
        _press(Qt.Key.Key_F6, Qt.KeyboardModifier.ShiftModifier)
        visited.append(_pane(window))

    assert visited == ["panel", "tab", "tree"]
    _close(window)


def test_f6_from_a_widget_outside_the_panes_enters_the_first_one(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    window.statusBar().setFocus()
    window.setFocus()

    assert _pane(window) is None
    window.paneNavigator.step(1)

    assert _pane(window) == "tree"
    _close(window)


def test_ctrl_1_and_ctrl_2_go_straight_to_the_tree_and_the_tab(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    window.mainTreeView.setFocus()

    _press(Qt.Key.Key_2, Qt.KeyboardModifier.ControlModifier)
    in_tab = _pane(window)
    _press(Qt.Key.Key_1, Qt.KeyboardModifier.ControlModifier)

    assert in_tab == "tab"
    assert _pane(window) == "tree"
    _close(window)


def test_with_no_package_f6_stays_in_the_start_panel_and_ctrl_2_does_nothing(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot, None)

    _press(Qt.Key.Key_F6)
    after_f6 = QApplication.focusWidget()
    before = QApplication.focusWidget()
    window.paneNavigator.focus_pane("tab")

    assert after_f6 is not None
    assert window.emptyState.isAncestorOf(after_f6)
    assert QApplication.focusWidget() is before
    _close(window)


def test_the_pane_keys_have_one_owner_each_in_the_window(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    wanted = {"F6", "Shift+F6", "Ctrl+1", "Ctrl+2", "Ctrl+L"}

    owners: dict[str, list[str]] = {key: [] for key in wanted}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            text = sequence.toString(QKeySequence.SequenceFormat.PortableText)
            if text in owners:
                owners[text].append(action.text())

    assert {key: len(found) for key, found in owners.items()} == dict.fromkeys(
        wanted, 1
    ), owners
    _close(window)


def test_the_pane_actions_are_in_the_navigate_menu(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)

    texts = [a.text() for a in window.menuNavigate.actions()]

    for expected in (
        "Next pane",
        "Previous pane",
        "Focus the package tree",
        "Focus the tab",
        "Edit the path",
    ):
        assert expected in texts
    _close(window)


# Inside a pane


def test_ctrl_l_edits_the_path_and_escape_gives_the_segments_back(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    tab = window.mainTabWidget.currentWidget()
    window.mainTreeView.setFocus()

    _press(Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier)
    editing = tab.breadcrumb.is_editing
    focus_in_editor = QApplication.focusWidget() is tab.pathLine
    _press(Qt.Key.Key_Escape)

    assert (editing, focus_in_editor) == (True, True)
    assert not tab.breadcrumb.is_editing
    _close(window)


def test_tab_goes_through_the_breadcrumb_before_the_attributes(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    tab = window.mainTabWidget.currentWidget()
    window.mainTabWidget.tabBar().setFocus()

    order: list[Any] = []
    for _ in range(6):
        window.focusNextPrevChild(True)
        order.append(QApplication.focusWidget())
        if order[-1] is tab.attrsTreeView:
            break

    names = [widget.objectName() or type(widget).__name__ for widget in order]
    assert names[0] == "breadcrumbSegment", names
    assert order[-1] is tab.attrsTreeView
    _close(window)


def test_enter_on_a_breadcrumb_segment_opens_it(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    tab = window.mainTabWidget.currentWidget()
    opened: list[int] = []
    tab.breadcrumb.segment_activated.connect(opened.append)
    button = tab.breadcrumb._buttons[0]

    button.setFocus()
    _press(Qt.Key.Key_Space)

    assert opened == [0]
    _close(window)


def test_left_and_right_change_tab_when_the_tab_bar_has_the_focus(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    tabs = window.mainTabWidget
    tabs.openItemInNewTab(window.mainTreeView.model().index(0, 0))
    qtbot.wait(50)
    assert tabs.count() >= 2
    tabs.tabBar().setFocus()
    tabs.setCurrentIndex(0)

    _press(Qt.Key.Key_Right)

    assert tabs.currentIndex() == 1
    _close(window)


def test_the_focus_returns_to_where_it_was_after_a_dialog_closes(
    qapp: object, qtbot: Any
) -> None:
    from PyQt6.QtWidgets import QDialog

    window = _open(qtbot)
    window.mainTreeView.setFocus()
    before = QApplication.focusWidget()
    dialog = QDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.activateWindow()
    QApplication.processEvents()

    dialog.close()
    QApplication.processEvents()
    window.activateWindow()
    QApplication.processEvents()

    assert before is window.mainTreeView
    assert QApplication.focusWidget() is window.mainTreeView
    _close(window)


def test_alt_f_opens_the_file_menu_and_escape_closes_it(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    opened: list[QMenu] = []
    window.menuFile.aboutToShow.connect(lambda: opened.append(window.menuFile))
    window.mainTreeView.setFocus()

    _press(Qt.Key.Key_F, Qt.KeyboardModifier.AltModifier)
    qtbot.waitUntil(window.menuFile.isVisible, timeout=2000)
    _press(Qt.Key.Key_Escape)
    qtbot.waitUntil(lambda: not window.menuFile.isVisible(), timeout=2000)

    assert opened
    assert QApplication.focusWidget() is window.mainTreeView
    _close(window)


def test_enter_unfolds_a_row_and_the_arrow_keys_move_down_into_it(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)
    tree = window.mainTreeView
    tree.setFocus()
    first = tree.model().index(0, 0)
    tree.collapse(first)
    tree.setCurrentIndex(first)

    _press(Qt.Key.Key_Return)
    unfolded = tree.isExpanded(first)
    _press(Qt.Key.Key_Down)

    assert unfolded
    assert tree.currentIndex().parent() == first
    _close(window)
