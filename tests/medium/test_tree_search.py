"""Searching the package tree finds the rows that match, and says how many."""

from typing import Any

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QShortcut
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture
def searched(views: Any) -> Any:
    """A package tree with a bar that searches its names."""
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.widgets import SearchBar

    package_views = views()
    package_views.open_package(
        make_shell(),
        make_submodel(
            elements=[
                make_property("Speed"),
                make_property("Speed2"),
                make_property("Torque"),
            ]
        ),
    )
    package_views.bar = SearchBar(
        package_views.view,
        filterColumns=[ATTRIBUTE_COLUMN],
        parent=package_views.window,
        closable=True,
    )
    return package_views


def _name(index: QModelIndex) -> str:
    from aas_editor.settings.app_settings import NAME_ROLE

    return str(index.data(NAME_ROLE))


def test_a_search_finds_the_rows_that_match_and_not_their_parents(
    searched: Any,
) -> None:
    searched.bar.searchLine.setText("Torque")

    found = [QModelIndex(item) for item in searched.bar.foundItems]

    assert [_name(item) for item in found] == ["Torque"]


def test_a_search_moves_the_selection_to_the_first_match(
    searched: Any,
) -> None:
    searched.bar.searchLine.setText("Speed")

    assert _name(searched.view.currentIndex()) == "Speed"


def test_a_search_reports_the_position_and_the_number_of_matches(
    searched: Any,
) -> None:
    searched.bar.searchLine.setText("Speed")

    assert searched.bar.resultLabel.text() == "1 of 2"


def test_next_and_previous_move_the_position(searched: Any) -> None:
    searched.bar.searchLine.setText("Speed")

    searched.bar.nextBtn.click()
    second = (
        _name(searched.view.currentIndex()),
        searched.bar.resultLabel.text(),
    )
    searched.bar.prevBtn.click()
    first = (
        _name(searched.view.currentIndex()),
        searched.bar.resultLabel.text(),
    )

    assert (second, first) == (("Speed2", "2 of 2"), ("Speed", "1 of 2"))


def test_a_search_without_a_match_says_so(searched: Any) -> None:
    searched.bar.searchLine.setText("Nothing like this")

    assert searched.bar.resultLabel.text() == "No results"


def test_clearing_the_search_clears_the_count(searched: Any) -> None:
    searched.bar.searchLine.setText("Speed")

    searched.bar.searchLine.setText("")

    assert searched.bar.resultLabel.text() == ""


def test_filtering_still_keeps_the_parents_of_a_match(searched: Any) -> None:
    searched.bar.filterBtn.setChecked(True)
    searched.bar.searchLine.setText("Torque")

    proxy = searched.view.model()
    visible = [_name(index) for index in proxy.iterItems()]

    assert "Submodel" in visible and "Speed" not in visible


def _press_find(qtbot: QtBot, window: QWidget, target: QWidget) -> None:
    """Presses Ctrl+F with the focus on a widget of an active window."""
    window.show()
    window.activateWindow()
    qtbot.waitActive(window)
    target.setFocus()
    qtbot.waitUntil(target.hasFocus)
    QTest.keySequence(target, QKeySequence("Ctrl+F"))


def test_the_find_key_opens_the_bar_of_the_tree(
    searched: Any, qtbot: QtBot
) -> None:
    searched.bar.hide()
    searched.bar.bindFind(searched.window)

    _press_find(qtbot, searched.window, searched.view)

    assert searched.bar.isVisible() and searched.bar.searchLine.hasFocus()


def test_two_bars_in_one_window_do_not_make_the_find_key_ambiguous(
    searched: Any, qtbot: QtBot
) -> None:
    """The key runs in the part of the window that has the focus."""
    from aas_editor.widgets import SearchBar

    side = QWidget(searched.window)
    field = QLineEdit(side)
    other = SearchBar(
        searched.view, filterColumns=[0], parent=side, closable=True
    )
    searched.bar.bindFind(searched.view)
    other.bindFind(side)
    searched.bar.hide()
    other.hide()

    _press_find(qtbot, searched.window, field)

    assert other.isVisible() and not searched.bar.isVisible()


def test_the_find_key_is_limited_to_the_widget_that_owns_it(
    searched: Any,
) -> None:
    shortcut = searched.bar.bindFind(searched.window)

    assert isinstance(shortcut, QShortcut)
    assert shortcut.context() == Qt.ShortcutContext.WidgetWithChildrenShortcut
