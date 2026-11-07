"""The look of the window, and what a restart brings back.

A large package is open. The theme, the row density, the zoom, the columns, the
panels, the orientation and the size are changed through the menus and the
settings, the window is closed, and a new one is opened with the settings that
the first one saved, in a temporary file.
"""

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
import re
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QWidget
import pytest
from tests import usage_window as uw

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the actions that `__main__` registers before the first view."""
    added = uw.register_all_actions()
    yield
    uw.unregister_actions(added)


@pytest.fixture
def large(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[uw.UsageWindow]:
    """The main window on a copy of the Technical Data template."""
    yield from uw.open_window(qtbot, monkeypatch, tmp_path, uw.TECHNICAL_DATA)


def _choose_theme(window: Any, label: str) -> None:
    for action in window.menuChooseTheme.actions():
        if action.text() == label:
            action.trigger()
            QApplication.processEvents()
            return
    raise LookupError(label)


def _hex_colors(sheet: str) -> set[str]:
    return {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", sheet)}


def _own_sheets(window: Any) -> dict[str, str]:
    return {
        f"{type(w).__name__}:{w.objectName()}": w.styleSheet()
        for w in window.findChildren(QWidget)
        if w.styleSheet()
    }


# Theme


def test_the_theme_menu_switches_the_whole_application_and_back(
    large: uw.UsageWindow,
) -> None:
    from aas_workingbench.ui.theme import current_tokens

    window = large.window
    light = current_tokens()

    _choose_theme(window, "Dark")
    dark = current_tokens()
    in_dark = QApplication.palette().window().color().name()
    _choose_theme(window, "Light")

    assert dark != light
    assert in_dark == dark.bg_chrome.lower()
    assert QApplication.palette().window().color().name() == (
        light.bg_chrome.lower()
    )


def test_a_tab_window_and_a_dialog_that_are_open_follow_the_theme(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_workingbench.ui.theme import current_tokens
    from aas_workingbench.widgets.settingWidgets import SettingsDialog
    from aas_workingbench.widgets.tab import TabWidget

    large.view.expandAll()
    row = uw.find_first(large.view, "TechnicalData")
    other = TabWidget.openItemInNewWindow(row)
    qtbot.addWidget(other)
    dialog = SettingsDialog(large.window)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    _choose_theme(large.window, "Dark")
    expected = current_tokens().bg_chrome.lower()

    assert other.isVisible()
    assert other.palette().window().color().name() == expected
    assert dialog.palette().window().color().name() == expected
    assert large.window.palette().window().color().name() == expected
    other.close()
    dialog.close()
    _choose_theme(large.window, "Light")


def test_no_widget_keeps_a_light_color_of_its_own_after_the_dark_theme(
    large: uw.UsageWindow,
) -> None:
    from aas_workingbench.domain.design_tokens import DARK
    from aas_workingbench.domain.design_tokens import LIGHT

    window = large.window
    window.validationController.dock.show()
    window.selectionDock.show()
    window.filesDock.show()
    light = {
        v.lower() for v in asdict(LIGHT).values() if str(v).startswith("#")
    }
    dark = {v.lower() for v in asdict(DARK).values() if str(v).startswith("#")}
    light_only = light - dark

    _choose_theme(window, "Dark")
    stale = {
        name: sheet
        for name, sheet in _own_sheets(window).items()
        if _hex_colors(sheet) & light_only
    }
    _choose_theme(window, "Light")

    assert stale == {}


def test_the_highlight_of_the_search_matches_follows_the_theme(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_workingbench.ui.theme import current_tokens

    bar = large.window.searchBarPack
    bar.showFocused()
    qtbot.keyClicks(bar.searchLine, "Manufacturer")
    delegate = large.view.itemDelegate()

    _choose_theme(large.window, "Dark")
    colors = {brush.color().name() for brush in delegate.indexColors.values()}
    expected = current_tokens().bg_find.lower()
    _choose_theme(large.window, "Light")

    assert colors == {expected}


# Row density, zoom, columns


def test_the_settings_dialog_changes_the_row_density_of_the_open_trees(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.domain.design_tokens import ROW_HEIGHTS
    from aas_workingbench.domain.design_tokens import Density
    from aas_workingbench.widgets.settingWidgets import SettingsDialog

    def choose_dense(dialog: Any) -> Any:
        box = next(
            b for b in dialog.optionGroupBoxes if b.title() == "Row density"
        )
        next(r for r in box.radiobtns if r.text() == "Dense").setChecked(True)
        dialog.accept()
        return dialog.DialogCode.Accepted

    large.view.expandAll()
    monkeypatch.setattr(SettingsDialog, "exec", choose_dense)
    tab_view = large.tab.attrsTreeView
    tab_view.expandAll()

    large.window.settingsDialogAct.trigger()
    QApplication.processEvents()
    first = large.view.model().index(0, 0)

    assert large.view.visualRect(first).height() == ROW_HEIGHTS[Density.DENSE]
    assert (
        tab_view.visualRect(tab_view.model().index(0, 0)).height()
        == (ROW_HEIGHTS[Density.DENSE])
    )


def test_zoom_in_and_out_of_the_tree_and_of_the_tab_by_key_and_menu(
    large: uw.UsageWindow,
) -> None:
    from aas_workingbench.models import DetailedInfoTable
    from aas_workingbench.models import PacksTable

    tree_size = PacksTable.currFont.pointSize()
    tab_size = DetailedInfoTable.currFont.pointSize()

    large.view.zoomInAct.trigger()
    large.view.zoomInAct.trigger()
    large.window.mainTabWidget.zoomInAct.trigger()
    zoomed = (
        PacksTable.currFont.pointSize(),
        DetailedInfoTable.currFont.pointSize(),
    )
    large.view.zoomOutAct.trigger()
    large.view.zoomOutAct.trigger()
    large.window.mainTabWidget.zoomOutAct.trigger()

    assert zoomed[0] > tree_size
    assert zoomed[1] > tab_size
    assert PacksTable.currFont.pointSize() == tree_size
    assert DetailedInfoTable.currFont.pointSize() == tab_size


# A restart


def _restart(qtbot: Any, first: uw.UsageWindow) -> Any:
    """Closes the window, so that it saves, and opens another on the file."""
    from aas_workingbench.editorApp import EditorApp

    first.window._recoveryTimer.stop()
    first.window.close()
    second = EditorApp(fileToOpen=first.path.as_posix())
    qtbot.addWidget(second)
    second.show()
    qtbot.waitExposed(second)
    return second


def test_the_look_of_the_window_comes_back_after_a_restart(
    large: uw.UsageWindow,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aas_workingbench.domain.design_tokens import Density
    from aas_workingbench.models import DetailedInfoTable
    from aas_workingbench.models import PacksTable
    from aas_workingbench.ui.theme import theme_manager
    from aas_workingbench.widgets.settingWidgets import SettingsDialog

    window = large.window

    def choose_dense(dialog: Any) -> Any:
        box = next(
            b for b in dialog.optionGroupBoxes if b.title() == "Row density"
        )
        next(r for r in box.radiobtns if r.text() == "Dense").setChecked(True)
        dialog.accept()
        return dialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", choose_dense)
    _choose_theme(window, "Dark")
    window.settingsDialogAct.trigger()
    large.view.zoomInAct.trigger()
    large.view.zoomInAct.trigger()
    window.mainTabWidget.zoomInAct.trigger()
    header = large.view.header()
    hidden_before = {
        header.model().headerData(i, Qt.Orientation.Horizontal)
        for i in range(header.count())
        if header.isSectionHidden(i)
    }
    window.validationController.dock.show()
    window.filesDock.show()
    window.setVOrientationAct.trigger()
    window.resize(1000, 640)
    tree_font = PacksTable.currFont.pointSize()
    tab_font = DetailedInfoTable.currFont.pointSize()
    docks = (
        window.validationController.dock.isVisible(),
        window.filesDock.isVisible(),
    )

    second = _restart(qtbot, large)

    assert second.currTheme == "dark"
    assert theme_manager().density is Density.DENSE
    assert PacksTable.currFont.pointSize() == tree_font
    assert DetailedInfoTable.currFont.pointSize() == tab_font
    assert second.splitter.orientation() == Qt.Orientation.Vertical
    assert docks == (True, True)
    assert second.validationController.dock.isVisible()
    assert second.filesDock.isVisible()
    assert second.selectionDock.isHidden()
    assert (second.width(), second.height()) == (1000, 640)
    second_header = second.mainTreeView.header()
    assert {
        second_header.model().headerData(i, Qt.Orientation.Horizontal)
        for i in range(second_header.count())
        if second_header.isSectionHidden(i)
    } == hidden_before
    assert [p.file for p in second.packTreeModel.openedPacks()] == [large.path]
    second._recoveryTimer.stop()
    second.close()
    _choose_theme(second, "Light")


def test_the_columns_that_the_user_hid_stay_hidden_after_a_restart(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    header = large.view.header()
    column = next(
        action
        for action in header.actions()
        if action.isCheckable()
        and action.isChecked()
        and action.text() != ("Package")
    )
    name = column.text()

    column.trigger()
    second = _restart(qtbot, large)
    again = {a.text(): a for a in second.mainTreeView.header().actions()}

    assert not again[name].isChecked()
    second._recoveryTimer.stop()
    second.close()
