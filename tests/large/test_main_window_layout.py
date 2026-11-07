"""The layout of the main window: one command bar, tabbed panels, the start.

These tests open the real main window with a real package. The settings of a
session are kept in memory, so a test neither reads nor writes the settings file
of the program.
"""

from collections.abc import Iterator
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QTabBar
from PyQt6.QtWidgets import QToolButton
import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
PACKAGE_PATH = (TEST_DATA_DIR / PACKAGE).as_posix()


class MemorySettings:
    """The settings of sessions, kept in a dictionary instead of a file."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aas_workingbench.settings.app_settings import NOT_GIVEN
        from aas_workingbench.settings.app_settings import Setting

        self.saved: dict[str, Any] = {}

        def value(setting: Setting) -> Any:
            if setting.name in self.saved:
                return self.saved[setting.name]
            return None if setting.default is NOT_GIVEN else setting.default

        def set_value(setting: Setting, new: Any) -> None:
            self.saved[setting.name] = new

        monkeypatch.setattr(Setting, "value", value)
        monkeypatch.setattr(Setting, "setValue", set_value)
        monkeypatch.setattr(
            Setting, "isSaved", lambda setting: setting.name in self.saved
        )


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the paste actions, as `__main__` does before the first view.

    The registry is global, so what this module added is taken out again for
    the modules after it, as the other large tests do.
    """
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.paste_actions import register_paste_actions

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    register_paste_actions()
    yield
    for spec in default_registry().specs_for(ViewKind.ANY):
        if spec.action_id not in before:
            default_registry().unregister(spec.action_id)


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemorySettings:
    return MemorySettings(monkeypatch)


def _open(qtbot: Any, path: str | None = PACKAGE_PATH) -> Any:
    from aas_workingbench.editorApp import EditorApp

    window = EditorApp(fileToOpen=path)
    qtbot.addWidget(window)
    window.show()
    return window


def _close(window: Any) -> None:
    for package in window.packTreeModel.openedPacks():
        package.commandStack.mark_saved()
    window.mainTreeView.updateWindowModified()
    window._recoveryTimer.stop()
    window.close()


@pytest.fixture(scope="module")
def shared(qapp: object) -> Iterator[Any]:
    """One window with a package, for the tests that only look at it.

    A window takes seconds to open with a real package, so the tests that
    change nothing share one. A test that changes the window asks for `window`.
    """
    patches = pytest.MonkeyPatch()
    MemorySettings(patches)
    from aas_workingbench.editorApp import EditorApp

    opened = EditorApp(fileToOpen=PACKAGE_PATH)
    opened.show()
    yield opened
    _close(opened)
    patches.undo()


@pytest.fixture
def window(qapp: object, qtbot: Any, memory: MemorySettings) -> Iterator[Any]:
    """The main window with one package, as a first run opens it."""
    opened = _open(qtbot)
    yield opened
    _close(opened)


def _entries(menu: QMenu) -> list[str]:
    return [
        action.text() for action in menu.actions() if not action.isSeparator()
    ]


def _menu(window: Any, title: str) -> QMenu:
    for action in window.menuBar().actions():
        if action.text().replace("&", "") == title:
            menu = action.menu()
            assert menu is not None
            return menu
    raise LookupError(title)


def _find(menu: QMenu, text: str) -> Any:
    for action in menu.actions():
        if action.text().replace("&", "") == text:
            return action
    raise LookupError(text)


def test_the_menus_come_in_the_order_of_the_plan(shared: Any) -> None:
    titles = [
        action.text().replace("&", "") for action in shared.menuBar().actions()
    ]

    assert titles == [
        "File",
        "Edit",
        "View",
        "Navigate",
        "Validate",
        "Tools",
        "Help",
    ]


def test_the_edit_menu_has_what_the_bar_and_the_context_menu_have(
    shared: Any,
) -> None:
    edit = _menu(shared, "Edit")

    assert _entries(edit) == [
        "Undo",
        "Redo",
        "Cut",
        "Copy",
        "Paste",
        "Paste above",
        "Paste below",
        "Paste into",
        "Add",
        "Edit in dialog",
        "Delete",
    ]


def test_each_entry_of_the_edit_menu_shows_the_key_of_its_action(
    shared: Any,
) -> None:
    edit = _menu(shared, "Edit")

    assert _find(edit, "Undo").shortcut() == QKeySequence(
        QKeySequence.StandardKey.Undo
    )
    assert _find(edit, "Paste above").shortcut() == QKeySequence("Ctrl+Alt+V")
    assert _find(edit, "Paste below").shortcut() == QKeySequence("Ctrl+Shift+V")
    assert _find(edit, "Edit in dialog").shortcut() == QKeySequence("Ctrl+E")


def test_the_validate_menu_has_the_panel_the_hints_and_the_test_tool(
    shared: Any,
) -> None:
    validate = _menu(shared, "Validate")

    assert _entries(validate) == [
        "Validation",
        "Hints",
        "AAS Test tool (V3.0)",
    ]


def test_the_columns_are_a_submenu_of_the_view_menu(shared: Any) -> None:
    top_level = [
        action.text().replace("&", "") for action in shared.menuBar().actions()
    ]
    columns = _find(_menu(shared, "View"), "Columns").menu()
    assert columns is not None
    columns.aboutToShow.emit()

    assert "Columns" not in top_level
    assert "Package" in _entries(columns)
    assert "Type" in _entries(columns)


def test_the_appearance_section_has_no_second_menu_of_that_name(
    shared: Any,
) -> None:
    view = _menu(shared, "View")

    names = [
        action.text() for action in view.actions() if action.menu() is not None
    ]
    assert "Appearance" not in names
    assert "Command bar" in _entries(view)
    assert "Tab bar" in _entries(view)


def test_the_command_bar_is_one_bar_with_the_actions_of_the_plan(
    shared: Any,
) -> None:
    bar = shared.toolBar
    texts = [
        action.text() for action in bar.actions() if not action.isSeparator()
    ]

    # The text of Save names the package that it saves.
    assert texts[1].startswith("Save")
    texts[1] = "Save"
    assert texts[:9] == [
        "&Open AAS file",
        "Save",
        "Undo",
        "Redo",
        "Add",
        "Edit in dialog",
        "Delete",
        "Back",
        "Forward",
    ]
    assert shared.findChildren(type(bar), "commandBar") == [bar]


def test_the_bar_has_no_gear_and_no_text_buttons(shared: Any) -> None:
    bar = shared.toolBar
    texts = [action.text() for action in bar.actions()]

    assert "Paste above" not in texts
    assert "Paste below" not in texts
    assert not [
        button
        for button in bar.findChildren(QToolButton)
        if button.menu() is not None
    ]


def test_save_all_is_in_the_file_menu_and_not_on_the_bar(shared: Any) -> None:
    file_menu = _menu(shared, "File")

    assert shared.mainTreeView.saveAllAct in file_menu.actions()
    assert shared.mainTreeView.saveAllAct not in shared.toolBar.actions()
    assert shared.mainTreeView.saveAct in shared.toolBar.actions()


def test_the_tab_has_no_toolbar_of_its_own(shared: Any) -> None:
    tab = shared.mainTabWidget.currentWidget()

    assert not hasattr(tab, "toolBar")
    assert tab.pathToolBar.isHidden()


def test_the_undo_of_the_bar_undoes_the_change_of_the_view(
    window: Any, qtbot: Any
) -> None:
    from aas_workingbench.application.changes import observer_for
    from aas_workingbench.application.edits import SetAttribute

    (package,) = window.packTreeModel.openedPacks()
    target = next(
        obj for obj in package.objStore if hasattr(obj, "submodel_element")
    )
    window.mainTreeView.setFocus()
    package.commandStack.push(
        SetAttribute(observer_for(package), target, "category", "PARAMETER")
    )
    undo = window.focusedActs.actions["undo"]
    qtbot.waitUntil(undo.isEnabled)

    undo.trigger()

    assert not package.commandStack.can_undo
    assert target.category is None


def test_the_key_of_undo_still_runs_once_with_the_mirrors_in_the_window(
    window: Any, qtbot: Any
) -> None:
    from PyQt6.QtTest import QTest

    from aas_workingbench.application.changes import observer_for
    from aas_workingbench.application.edits import SetAttribute

    (package,) = window.packTreeModel.openedPacks()
    target = next(
        obj for obj in package.objStore if hasattr(obj, "submodel_element")
    )
    window.activateWindow()
    qtbot.waitActive(window)
    window.mainTreeView.setFocus()
    package.commandStack.push(
        SetAttribute(observer_for(package), target, "category", "PARAMETER")
    )
    undo_key = QKeySequence(QKeySequence.StandardKey.Undo)

    QTest.keySequence(window.mainTreeView, undo_key)

    # The mirror of the bar shows the key, and the view runs it: if the mirror
    # owned it as well, the key would be ambiguous and nothing would run.
    assert window.focusedActs.actions["undo"].shortcut() == undo_key
    assert (
        window.focusedActs.actions["undo"].shortcutContext()
        == Qt.ShortcutContext.WidgetShortcut
    )
    assert not package.commandStack.can_undo


def _strips(window: Any) -> list[Any]:
    """The tab bars that the window makes for tabbed docks."""
    return [
        bar for bar in window.findChildren(QTabBar) if bar.parent() is window
    ]


def _panel_tabs(window: Any) -> tuple[list[str], str]:
    """The titles of the panels that are tabs, and the one on top."""
    (strip,) = _strips(window)
    texts = [strip.tabText(place) for place in range(strip.count())]
    return texts, strip.tabText(strip.currentIndex())


def test_the_panels_share_one_strip_of_tabs(window: Any, qtbot: Any) -> None:
    window.validationController.dock.show()
    window.filesDock.show()
    window.selectionDock.show()

    qtbot.waitUntil(lambda: len(_strips(window)) == 1)
    texts, _ = _panel_tabs(window)
    # One strip for the three, in the order of the plan.
    assert texts == ["Validation", "Package files", "Selection"]


def test_the_panels_are_hidden_until_they_are_asked_for(shared: Any) -> None:
    assert shared.validationController.dock.isHidden()
    assert shared.filesDock.isHidden()
    assert shared.selectionDock.isHidden()


def test_a_tab_is_as_wide_as_its_title_within_the_limits(shared: Any) -> None:
    from aas_workingbench.widgets.tab import TAB_MAX_WIDTH
    from aas_workingbench.widgets.tab import TAB_MIN_WIDTH

    bar = shared.mainTabWidget.tabBar()

    assert TAB_MIN_WIDTH <= bar.tabSizeHint(0).width() <= TAB_MAX_WIDTH
    assert shared.mainTabWidget.styleSheet() == ""


def test_the_last_tab_of_the_main_window_has_no_close_button(
    shared: Any,
) -> None:
    tabs = shared.mainTabWidget

    assert tabs.count() == 1
    assert not tabs.tabBar().tabsClosable()


def test_a_second_tab_brings_the_close_buttons_back(window: Any) -> None:
    tabs = window.mainTabWidget
    tabs.openItemInNewTab(window.mainTreeView.model().index(0, 0))

    assert tabs.count() == 2
    assert tabs.tabBar().tabsClosable()


def test_the_close_button_of_a_tab_closes_it_and_the_last_tab_loses_its_button(
    window: Any, qtbot: Any
) -> None:
    tabs = window.mainTabWidget
    tabs.openItemInNewTab(window.mainTreeView.model().index(0, 0))
    bar = tabs.tabBar()
    button = bar.tabButton(1, QTabBar.ButtonPosition.RightSide)
    assert button is not None

    button.click()

    qtbot.waitUntil(lambda: tabs.count() == 1)
    assert not bar.tabsClosable()


def test_the_header_says_package_and_type_and_keeps_the_names(
    shared: Any,
) -> None:
    header = shared.mainTreeView.header()

    assert [header.label(section) for section in (0, 2)] == ["Package", "Type"]
    assert [header.text(section) for section in (0, 2)] == ["object", "type"]


def test_the_name_of_a_row_is_in_its_tooltip_with_the_path(shared: Any) -> None:
    from PyQt6.QtCore import Qt

    view = shared.mainTreeView
    view.expandAll()
    model = view.model()
    package_row = model.index(0, 0)
    deepest = package_row
    while model.rowCount(deepest):
        deepest = model.index(0, 0, deepest)
    name = deepest.data(Qt.ItemDataRole.DisplayRole)

    tip = deepest.data(Qt.ItemDataRole.ToolTipRole)

    assert tip.splitlines()[0] == name
    assert package_row.data(Qt.ItemDataRole.DisplayRole) in tip.splitlines()[1]


def test_the_breadcrumb_opens_the_object_of_a_segment(window: Any) -> None:
    from PyQt6.QtCore import QModelIndex

    view = window.mainTreeView
    view.expandAll()
    model = view.model()
    deepest = model.index(0, 0)
    while model.rowCount(deepest):
        deepest = model.index(0, 0, deepest)
    tab = window.mainTabWidget.currentWidget()
    tab.openItem(deepest)
    names = tab.breadcrumb.names

    tab.openSegment(1)

    assert len(names) >= 3
    assert tab.breadcrumb.names == names[:2]
    assert QModelIndex(tab.packItem).data() == names[1]


def test_without_a_package_the_window_shows_the_start(
    qapp: object, qtbot: Any, memory: MemorySettings
) -> None:
    window = _open(qtbot, None)

    assert window.emptyState.isVisible()
    assert window.mainTreeView.isHidden()
    assert window.emptyDetail.isVisible()
    assert window.splitterTabWidgets.isHidden()
    _close(window)


def test_opening_a_package_replaces_the_start_and_closing_it_brings_it_back(
    qapp: object, qtbot: Any, memory: MemorySettings
) -> None:
    window = _open(qtbot, None)

    window.openAASFile(PACKAGE_PATH)

    assert window.emptyState.isHidden()
    assert window.mainTreeView.isVisible()
    assert window.splitterTabWidgets.isVisible()
    assert window.emptyDetail.isHidden()

    window.mainTreeView.closeAllAct.trigger()

    assert window.emptyState.isVisible()
    assert window.mainTreeView.isHidden()
    _close(window)


def _show_panels(window: Any) -> None:
    """Opens two panels, so that the files are the tab on top."""
    window.validationController.dock.show()
    window.filesDock.show()
    window.filesDock.raise_()


def test_the_arrangement_of_the_panels_survives_a_restart(
    qapp: object, qtbot: Any, memory: MemorySettings
) -> None:
    first = _open(qtbot, None)
    _show_panels(first)
    first.toolBar.hide()
    qtbot.waitUntil(lambda: len(_strips(first)) == 1)
    assert _panel_tabs(first) == (
        ["Validation", "Package files"],
        "Package files",
    )
    _close(first)

    second = _open(qtbot, None)

    # Two panels are tabs and the files are on top, the third is still hidden,
    # and the command bar that was hidden stays hidden.
    qtbot.waitUntil(lambda: len(_strips(second)) == 1)
    assert _panel_tabs(second) == (
        ["Validation", "Package files"],
        "Package files",
    )
    assert second.selectionDock.isHidden()
    assert second.toolBar.isHidden()
    _close(second)


def test_a_state_of_another_layout_leaves_the_default(
    qapp: object, qtbot: Any, memory: MemorySettings
) -> None:
    from aas_workingbench.settings.app_settings import DOCKS_LAYOUT_VERSION
    from aas_workingbench.settings.app_settings import AppSettings

    first = _open(qtbot, None)
    _show_panels(first)
    stale = first.saveState(DOCKS_LAYOUT_VERSION + 1)
    _close(first)
    # The close of the first window wrote its own state. A session of another
    # layout is the one that wrote this one.
    memory.saved[AppSettings.DOCK_STATE.name] = stale

    second = _open(qtbot, None)

    assert second.filesDock.isHidden()
    assert second.validationController.dock.isHidden()
    assert second.toolBar.isVisible()
    _close(second)
