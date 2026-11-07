"""Finding the way in a large package, as a person does it.

The package is a copy of the Technical Data template, which has 800 rows and
opens strictly, and a copy of the package of the owner. Each test sends keys or
triggers the action that a menu holds, and reads what the window shows.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
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


def _element(window: uw.UsageWindow, name: str) -> Any:
    """The row of the Property of a name, below the submodels."""
    from aas_editor.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    return next(
        index
        for index in uw.all_rows(window.view)
        if isinstance(index.data(OBJECT_ROLE), model.Property)
        and index.data() == name
    )


def _top_rows(tab: Any) -> dict[str, Any]:
    """The rows at the top of the attributes of a tab, by their text."""
    view = tab.attrsTreeView
    return {
        view.model().index(row, 0).data(): view.model().index(row, 0)
        for row in range(view.model().rowCount())
    }


# Search


def test_ctrl_f_in_the_tree_opens_the_search_and_counts_the_matches(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence.StandardKey.Find)
    qtbot.keyClicks(bar.searchLine, "Manufacturer")

    assert bar.isVisible()
    assert QApplication.focusWidget() is bar.searchLine
    assert bar.resultLabel.text() == "1 of 8"
    assert large.view.currentIndex().data() == "ManufacturerName"


def test_next_goes_through_the_matches_and_wraps_to_the_first(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    bar.showFocused()
    qtbot.keyClicks(bar.searchLine, "Manufacturer")

    labels = []
    for _ in range(8):
        bar.nextBtn.click()
        labels.append(bar.resultLabel.text())

    assert labels == [
        "2 of 8",
        "3 of 8",
        "4 of 8",
        "5 of 8",
        "6 of 8",
        "7 of 8",
        "8 of 8",
        "1 of 8",
    ]


def test_previous_from_the_first_match_wraps_to_the_last(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    bar.showFocused()
    qtbot.keyClicks(bar.searchLine, "Manufacturer")

    bar.prevBtn.click()

    assert bar.resultLabel.text() == "8 of 8"


def test_a_search_with_no_match_says_so_and_leaves_the_row(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    bar.showFocused()

    qtbot.keyClicks(bar.searchLine, "zzzqqq")

    assert bar.resultLabel.text() == "No results"
    assert large.view.currentIndex().data() == "ManufacturerName"


def test_an_invalid_regular_expression_is_not_called_no_results(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    bar.showFocused()
    bar.regexBtn.setChecked(True)

    qtbot.keyClicks(bar.searchLine, "[")

    assert bar.resultLabel.text() == "Not a valid expression"


def test_the_filter_leaves_only_the_matching_rows_and_clearing_brings_back_all(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    bar = large.window.searchBarPack
    large.view.expandAll()
    all_rows = len(uw.all_rows(large.view))
    bar.showFocused()
    bar.filterBtn.setChecked(True)

    qtbot.keyClicks(bar.searchLine, "ManufacturerName")
    filtered = len(uw.all_rows(large.view))
    bar.searchLine.clear()
    large.view.expandAll()

    assert 0 < filtered < all_rows // 4
    assert len(uw.all_rows(large.view)) == all_rows


def test_ctrl_f_in_the_tab_searches_the_attributes_of_that_tab(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    view = large.tab.attrsTreeView
    view.setFocus()
    view.expandAll()

    QTest.keySequence(view, QKeySequence.StandardKey.Find)
    qtbot.keyClicks(large.tab.searchBar.searchLine, "Cardinality")

    assert large.tab.searchBar.isVisible()
    assert not large.window.searchBarPack.isVisible()
    assert large.tab.searchBar.resultLabel.text() == "1 of 5"


# The command palette


def test_ctrl_k_finds_an_element_by_its_name_and_selects_it(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_editor.application.command_palette import EntryKind

    large.view.collapseAll()
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence("Ctrl+K"))
    palette = large.window.commandPalette.palette
    qtbot.keyClicks(palette.input, "ManufacturerArticleNumber")
    elements = [e for e in palette.shown_entries if e.kind is EntryKind.ELEMENT]
    QTest.keyClick(palette.input, Qt.Key.Key_Return)
    qtbot.waitUntil(
        lambda: large.view.currentIndex().data() == "ManufacturerArticleNumber",
        timeout=3000,
    )

    assert len(elements) >= 2
    assert not palette.isVisible()


def test_ctrl_k_runs_a_command_that_the_edit_menu_has(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    large.view.setFocus()
    palette = large.window.commandPalette.palette

    QTest.keySequence(large.view, QKeySequence("Ctrl+K"))
    qtbot.keyClicks(palette.input, "Copy")
    assert palette.current_entry is not None
    assert palette.current_entry.title == "Copy"
    QTest.keyClick(palette.input, Qt.Key.Key_Return)
    qtbot.waitUntil(lambda: bool(QApplication.clipboard().text()), timeout=3000)

    assert "ManufacturerName" in QApplication.clipboard().text()


def test_a_command_that_cannot_run_in_the_palette_says_why(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_editor.application.editing import edit_mode

    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    edit_mode().set_editing(False)
    palette = large.window.commandPalette.palette

    large.window.commandPalette.open()
    qtbot.keyClicks(palette.input, "Delete")
    entry = next(e for e in palette.shown_entries if e.title == "Delete/clear")

    assert not entry.enabled
    assert "Read mode" in entry.reason
    assert palette.choose_current() is False
    assert large.package.commandStack.can_undo is False


# The path of a tab


def test_a_click_on_a_segment_of_the_path_opens_that_object(
    large: uw.UsageWindow,
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    names = large.tab.breadcrumb.names

    large.tab.breadcrumb._buttons[names.index("GeneralInformation")].click()

    assert large.tab.pathLine.text().endswith(
        "/TechnicalData/GeneralInformation"
    )
    assert large.tab.backAct.isEnabled()


def test_ctrl_l_edits_the_path_and_enter_opens_the_address(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    large.view.setFocus()
    package = large.package.name

    QTest.keySequence(large.view, QKeySequence("Ctrl+L"))
    assert large.tab.breadcrumb.is_editing
    large.tab.pathLine.setText(f"{package}/Submodels/TechnicalData")
    QTest.keyClick(large.tab.pathLine, Qt.Key.Key_Return)

    assert not large.tab.breadcrumb.is_editing
    assert large.tab.breadcrumb.names[-1] == "TechnicalData"
    assert large.view.currentIndex().data() == "TechnicalData"


def test_a_path_that_does_not_exist_is_refused_and_the_field_shows_the_real_path(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    real_path = large.tab.pathLine.text()

    large.tab.breadcrumb.start_editing()
    large.tab.pathLine.setText("nowhere/at/all")
    QTest.keyClick(large.tab.pathLine, Qt.Key.Key_Return)

    assert [box.kind for box in large.boxes] == ["critical"]
    assert "nowhere/at/all" in large.boxes[0].text
    assert large.tab.pathLine.text() == real_path


def test_escape_leaves_the_typing_and_the_next_ctrl_l_shows_the_real_path(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    real_path = large.tab.pathLine.text()
    large.tab.breadcrumb.start_editing()
    large.tab.pathLine.setText("half typed")

    QTest.keyClick(large.tab.pathLine, Qt.Key.Key_Escape)
    large.tab.breadcrumb.start_editing()

    assert large.tab.pathLine.text() == real_path


# Back, Forward, Push and Pop, and the jump to a target


def test_back_and_forward_follow_the_rows_that_were_opened(
    large: uw.UsageWindow,
) -> None:
    first = _element(large, "ManufacturerName")
    second = _element(large, "ManufacturerOrderCode")
    large.view.setCurrentIndex(first)
    large.view.setCurrentIndex(second)
    back = [a for a in large.window.toolBar.actions() if a.text() == "Back"][0]
    forward = [
        a for a in large.window.toolBar.actions() if a.text() == "Forward"
    ][0]

    assert back.isEnabled()
    assert not forward.isEnabled()
    large.tab.backAct.trigger()
    on_back = (large.view.currentIndex().data(), forward.isEnabled())
    large.tab.forwardAct.trigger()

    assert on_back == ("ManufacturerName", True)
    assert large.view.currentIndex().data() == "ManufacturerOrderCode"


def test_push_and_pop_location_come_back_to_the_row(
    large: uw.UsageWindow,
) -> None:
    from aas_editor.application.locations import default_stack

    default_stack().clear()
    start = _element(large, "ManufacturerName")
    large.view.setCurrentIndex(start)
    large.view.setFocus()

    QTest.keySequence(large.view, QKeySequence("Ctrl+Shift+P"))
    large.view.setCurrentIndex(_element(large, "ManufacturerOrderCode"))
    QTest.keySequence(large.view, QKeySequence("Ctrl+Shift+O"))

    assert large.view.currentIndex().data() == "ManufacturerName"
    assert large.status == "Editing location restored."
    QTest.keySequence(large.view, QKeySequence("Ctrl+Shift+O"))
    assert large.status == "No editing location is pushed."


def test_jump_to_target_opens_the_description_and_back_returns(
    large: uw.UsageWindow,
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    semantic = _top_rows(large.tab)["semanticId"]
    large.tab.attrsTreeView.setCurrentIndex(semantic)

    large.tab.attrsTreeView.registeredActions.find("reference.jump").trigger()
    after_jump = large.tab.pathLine.text()
    large.tab.backAct.trigger()

    assert after_jump.endswith("/Concept Descriptions/ManufacturerName")
    assert large.tab.pathLine.text().endswith(
        "/TechnicalData/GeneralInformation/ManufacturerName"
    )
    assert large.boxes == []


def test_jump_to_a_target_that_is_not_in_the_package_says_what_to_do(
    large: uw.UsageWindow,
) -> None:
    submodel = _first_submodel_row(large)
    large.view.setCurrentIndex(submodel)
    semantic = _top_rows(large.tab)["semanticId"]
    large.tab.attrsTreeView.setCurrentIndex(semantic)

    large.tab.attrsTreeView.registeredActions.find("reference.jump").trigger()

    (box,) = large.boxes
    assert "0173-1#01-AHX837#002" in box.text
    assert "Dangling" not in box.text


def _first_submodel_row(window: uw.UsageWindow) -> Any:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    return next(
        i
        for i in uw.all_rows(window.view)
        if isinstance(i.data(OBJECT_ROLE), model.Submodel)
    )


# The panes by key


def test_f6_and_ctrl_1_and_ctrl_2_move_between_the_panes_of_a_large_package(
    large: uw.UsageWindow,
) -> None:
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))
    large.view.setFocus()
    navigator = large.window.paneNavigator

    QTest.keySequence(large.view, QKeySequence("Ctrl+2"))
    in_tab = (navigator.current(), QApplication.focusWidget())
    QTest.keySequence(QApplication.focusWidget(), QKeySequence("Ctrl+1"))
    in_tree = (navigator.current(), QApplication.focusWidget())
    uw.press(Qt.Key.Key_F6)

    assert in_tab == ("tab", large.tab.attrsTreeView)
    assert in_tree == ("tree", large.view)
    assert navigator.current() == "tab"


# Findings


def _findings(window: uw.UsageWindow) -> list[Any]:
    from aas_editor.application.validation import stepping_findings

    return list(
        stepping_findings(window.window.validationController.dock.report)
    )


def test_f8_goes_to_the_finding_and_the_status_bar_says_what_it_is(
    large: uw.UsageWindow,
) -> None:
    large.view.setFocus()

    uw.press(Qt.Key.Key_F8)

    assert large.view.currentIndex().data() == "TechnicalData"
    assert large.status.startswith("Warning 1 of 1: EDT-DANGLING-REFERENCE")
    assert not large.window.validationController.dock.isVisible()


def test_the_dock_lists_the_finding_and_a_double_click_goes_to_its_element(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    controller = large.window.validationController
    controller.status.findings_button.click()
    dock = controller.dock
    qtbot.waitUntil(lambda: len(dock.visible_findings()) == 1, timeout=3000)
    large.view.setCurrentIndex(_element(large, "ManufacturerName"))

    dock.activate_row(0)

    assert dock.isVisible()
    assert large.view.currentIndex().data() == "TechnicalData"
    assert dock.counts_label.text() == "1 warning"


def test_the_filters_of_the_dock_hide_rows_and_f8_clears_them(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_editor.domain.validation import Severity

    controller = large.window.validationController
    controller.show_dock()
    dock = controller.dock
    qtbot.waitUntil(lambda: len(dock.visible_findings()) == 1, timeout=3000)

    dock.severity_boxes[Severity.WARNING].setChecked(False)
    hidden = (len(dock.visible_findings()), dock.counts_label.text())
    large.view.setFocus()
    uw.press(Qt.Key.Key_F8)

    assert hidden == (0, "1 warning. Showing 0 of 1")
    assert len(dock.visible_findings()) == 1
    assert dock.severity_boxes[Severity.WARNING].isChecked()


def test_creating_the_description_that_the_finding_names_clears_the_finding(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    status = large.window.validationController.status
    large.view.setFocus()
    uw.press(Qt.Key.Key_F8)
    before = status.findings_button.text()
    create = large.view.registeredActions.find("concepts.create")

    assert create is not None
    assert create.isEnabled()
    create.trigger()
    qtbot.waitUntil(
        lambda: status.findings_button.text() == "0 errors, 0 warnings",
        timeout=4000,
    )

    assert before == "0 errors, 1 warning"
    assert large.package.commandStack.can_undo
    large.view.setFocus()
    uw.press(Qt.Key.Key_F8)
    assert large.status == "No errors or warnings"


@pytest.fixture
def requester(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[uw.UsageWindow]:
    """The main window on a copy of the package of the owner."""
    if not uw.REQUESTER.exists():
        pytest.skip("The package of the owner is not on this machine")
    yield from uw.open_window(qtbot, monkeypatch, tmp_path, uw.REQUESTER)


def test_the_package_of_the_owner_opens_clean_and_its_rows_can_be_found(
    requester: uw.UsageWindow, qtbot: Any
) -> None:
    status = requester.window.validationController.status
    requester.view.setFocus()

    uw.press(Qt.Key.Key_F8)
    bar = requester.window.searchBarPack
    bar.showFocused()
    qtbot.keyClicks(bar.searchLine, "Cutting")

    assert status.findings_button.text() == "0 errors, 0 warnings"
    assert requester.status == "No errors or warnings"
    assert bar.resultLabel.text() == "1 of 2"
    assert requester.view.currentIndex().data() == "Cutting"
