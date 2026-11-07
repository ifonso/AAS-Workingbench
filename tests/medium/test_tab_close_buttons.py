"""The close cross of a tab sits at the right edge of its own tab.

A window whose last tab cannot be closed has no cross on that tab. Qt removes
a close button that is no more wanted with `deleteLater()`, so the old cross
stayed on screen at the place where it was made, on the left of a tab that was
since given a longer title, until the event loop came round. A picture taken
at that point read "showcase.aa×sx".
"""

from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QStyle
from PyQt6.QtWidgets import QStyleOptionTab
from PyQt6.QtWidgets import QTabBar
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

THEMES = ["light", "dark"]
LONG_TITLE = "ACollectionWithAVeryLongNameThatHasToBeElidedInItsTab"


@pytest.fixture
def tabs(views, qtbot: QtBot, request: pytest.FixtureRequest):
    """A tab widget with a first tab that is empty, like the main window."""
    from aas_editor.ui.theme import theme_manager
    from aas_editor.widgets.tab import TabWidget

    theme_manager().apply(getattr(request, "param", "light"))
    shown = views()
    shown.open_package(
        make_submodel(
            elements=[
                make_collection(LONG_TITLE, [make_property("x")]),
                make_property("p"),
            ]
        )
    )
    widget = TabWidget(unclosable=True)
    qtbot.addWidget(widget)
    widget.addTab(widget.tabCls(parent=widget), "showcase.aasx")
    widget.resize(1200, 300)
    widget.show()
    qtbot.waitExposed(widget)

    class Tabs:
        views = shown

        @staticmethod
        def open(*names: str) -> None:
            widget.openItemInNewTab(shown.index(*names))
            # Not `qtbot.wait`, which lets the deferred deletes through.
            QApplication.processEvents()

        @staticmethod
        def bar() -> QTabBar:
            return widget.tabBar()

        @staticmethod
        def close_last() -> None:
            widget.removeTab(widget.count() - 1)
            QApplication.processEvents()

    QApplication.processEvents()
    yield Tabs
    theme_manager().reset_to_native()


def _crosses(bar: QTabBar) -> list[QAbstractButton]:
    """The buttons of the bar that are on screen."""
    return [
        button
        for button in bar.findChildren(QAbstractButton)
        if button.isVisible()
    ]


def test_the_only_tab_of_a_window_has_no_cross(tabs) -> None:
    assert _crosses(tabs.bar()) == []


def test_a_window_that_is_back_to_one_tab_has_no_cross(tabs) -> None:
    tabs.open("submodels", "Submodel", "p")
    assert len(_crosses(tabs.bar())) == 2

    tabs.close_last()

    assert tabs.bar().count() == 1
    assert _crosses(tabs.bar()) == []


@pytest.mark.parametrize("tabs", THEMES, indirect=True)
def test_each_tab_has_one_cross_inside_its_right_edge(tabs) -> None:
    tabs.open("submodels", "Submodel", "p")
    tabs.open("submodels", "Submodel", LONG_TITLE)
    bar = tabs.bar()

    crosses = _crosses(bar)

    sides = QTabBar.ButtonPosition
    assert sorted(b.geometry().left() for b in crosses) == sorted(
        bar.tabButton(i, sides.RightSide).geometry().left()
        for i in range(bar.count())
    )
    for index in range(bar.count()):
        rect = bar.tabRect(index)
        cross = bar.tabButton(index, sides.RightSide).geometry()
        assert rect.center().x() < cross.left()
        assert cross.right() <= rect.right()


@pytest.mark.parametrize("tabs", THEMES, indirect=True)
def test_a_title_ends_before_the_cross_of_its_tab(tabs) -> None:
    tabs.open("submodels", "Submodel", "p")
    tabs.open("submodels", "Submodel", LONG_TITLE)
    bar = tabs.bar()

    for index in range(bar.count()):
        option = QStyleOptionTab()
        bar.initStyleOption(option, index)
        text = bar.style().subElementRect(
            QStyle.SubElement.SE_TabBarTabText, option, bar
        )
        cross = bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
        assert text.right() < cross.geometry().left()
