"""Tabs follow the objects they show when the package changes.

A tab shows one object of a package. When that object is deleted, in this tab
or another one, or its package is closed, the tab closes. Deleting a child of
the object, or anything else, leaves the tab alone.
"""

import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture
def tabs(views, qtbot: QtBot):
    """A tab widget with a first tab that is empty, like the main window."""
    from aas_editor.widgets.tab import TabWidget

    shown = views()
    shown.package = shown.open_package(
        make_submodel(
            elements=[
                make_collection(
                    "Collection", [make_property("x"), make_property("y")]
                ),
                make_property("other"),
            ]
        )
    )
    tab_widget = TabWidget(unclosable=True)
    qtbot.addWidget(tab_widget)
    tab_widget.addTab(tab_widget.tabCls(parent=tab_widget), "Welcome")

    class Tabs:
        views = shown
        widget = tab_widget
        package = shown.package

        @staticmethod
        def open(*names: str, package: int = 0) -> None:
            tab_widget.openItemInNewTab(shown.index(*names, package=package))

        @staticmethod
        def delete(*names: str, package: int = 0) -> None:
            from aas_editor.settings.app_settings import CLEAR_ROW_ROLE

            shown.view.model().setData(
                shown.index(*names, package=package), None, CLEAR_ROW_ROLE
            )
            # A tab closes right after the change, not during it.
            qtbot.wait(5)

        @staticmethod
        def titles() -> list[str]:
            return [
                tab_widget.tabText(index) for index in range(tab_widget.count())
            ]

    return Tabs


def test_tab_closes_when_its_object_is_deleted_in_the_package_tree(
    tabs,
) -> None:
    tabs.open("submodels", "Submodel", "Collection", "x")
    assert "x" in tabs.titles()

    tabs.delete("submodels", "Submodel", "Collection", "x")

    assert "x" not in tabs.titles()


def test_tab_stays_open_when_a_child_of_its_object_is_deleted(tabs) -> None:
    tabs.open("submodels", "Submodel", "Collection")

    tabs.delete("submodels", "Submodel", "Collection", "x")

    assert "Collection" in tabs.titles()


def test_tab_stays_open_when_a_sibling_of_its_object_is_deleted(tabs) -> None:
    tabs.open("submodels", "Submodel", "Collection", "y")

    tabs.delete("submodels", "Submodel", "Collection", "x")

    assert "y" in tabs.titles()


def test_tab_closes_when_a_container_of_its_object_is_deleted(tabs) -> None:
    tabs.open("submodels", "Submodel", "Collection", "x")
    tabs.open("submodels", "Submodel", "Collection")

    tabs.delete("submodels", "Submodel", "Collection")

    assert "x" not in tabs.titles()
    assert "Collection" not in tabs.titles()


def test_tab_in_another_window_closes_when_its_object_is_deleted(
    tabs, qtbot
) -> None:
    from aas_editor.widgets.tab import TabWidget

    window = TabWidget(unclosable=True)
    qtbot.addWidget(window)
    window.openItemInNewTab(
        tabs.views.index("submodels", "Submodel", "Collection", "x")
    )
    window.openItemInNewTab(tabs.views.index("submodels", "Submodel", "other"))

    tabs.delete("submodels", "Submodel", "Collection", "x")

    assert [window.tabText(i) for i in range(window.count())] == ["other"]


def test_tab_closes_when_undo_takes_back_the_creation_of_its_object(
    tabs, qtbot
) -> None:
    from aas_editor.settings.app_settings import ADD_ITEM_ROLE

    tabs.views.view.model().setData(
        tabs.views.index("submodels", "Submodel", "Collection"),
        make_property("n"),
        ADD_ITEM_ROLE,
    )
    tabs.open("submodels", "Submodel", "Collection", "n")
    assert "n" in tabs.titles()

    tabs.package.commandStack.undo()
    qtbot.wait(5)

    assert "n" not in tabs.titles()


def test_last_tab_of_an_unclosable_widget_is_emptied_not_removed(tabs) -> None:
    tabs.widget.removeTab(0)
    tabs.widget.openItemInNewTab(
        tabs.views.index("submodels", "Submodel", "Collection", "y")
    )
    tabs.widget.removeTab(0)
    assert tabs.widget.count() == 1

    tabs.delete("submodels", "Submodel", "Collection", "y")

    assert tabs.widget.count() == 1
    assert tabs.widget.widget(0).packItemObj is None


def test_tab_closes_when_its_package_is_closed(tabs) -> None:
    from aas_editor.settings import NOT_GIVEN
    from aas_editor.settings.app_settings import CLEAR_ROW_ROLE

    tabs.open("submodels", "Submodel", "Collection", "x")

    tabs.views.view.model().setData(
        tabs.views.index(), NOT_GIVEN, CLEAR_ROW_ROLE
    )
    tabs.widget.removeTabsOfClosedPackages(tabs.views.table.openedPacks())

    assert "x" not in tabs.titles()
