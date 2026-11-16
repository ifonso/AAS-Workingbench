"""Finding and going to elements: the pane of the tree and the command bar.

Proposals 2.2, 2.4, 4.1, 4.3 and 4.4 of `design/ui-proposals.md`: the pane of
the package tree names its package and has a filter that is always there, the
groups of the tree read as titles of sections, the command bar has a search
box that opens the palette and a switch of Read and Edit mode, and a link of
the detail opens its target in the same tab.
"""

from collections.abc import Iterator
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_submodel

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.settings.app_settings import ATTRIBUTE_COLUMN
from aas_workingbench.settings.app_settings import GROUP_TITLE_ROLE
from aas_workingbench.ui.tree_pane import match_text


_owners: list[Any] = []


@pytest.fixture
def shown(views):
    speed = make_property("Speed")
    view = views()
    view.open_package(
        make_submodel(
            elements=[speed, make_property("Spindle"), make_property("Other")]
        )
    )
    return view


@pytest.fixture
def pane(shown, qtbot: QtBot):
    from aas_workingbench.ui.tree_pane import TreePaneHeader

    from PyQt6.QtWidgets import QWidget

    owner = QWidget()
    qtbot.addWidget(owner)
    close = QAction("Close", owner)
    header = TreePaneHeader(shown.view, ATTRIBUTE_COLUMN, [close], owner)
    # qtbot keeps no reference, and the header lives as long as its owner.
    _owners.append(owner)
    return header


def test_the_filter_keeps_the_rows_that_match_and_says_how_many(
    shown, pane
) -> None:
    pane.filter.set_text("Sp")

    assert pane.filter.count == 2
    assert pane.filter.result.text() == "2 elements match, with their parents"
    assert not pane.filter.clear_button.isHidden()
    names = [i.data() for i in shown.view.model().iterItems()]
    assert "Speed" in names and "Spindle" in names
    assert "Other" not in names


def test_clear_shows_every_row_again(shown, pane) -> None:
    pane.filter.set_text("Sp")

    pane.filter.clear_button.click()

    names = [i.data() for i in shown.view.model().iterItems()]
    assert "Other" in names
    assert pane.filter.result.isHidden()


def test_the_filter_opens_the_branches_that_hold_a_match(shown, pane) -> None:
    shown.view.collapseAll()

    pane.filter.set_text("Spindle")

    assert shown.view.isExpanded(shown.index("submodels", "Submodel"))


@pytest.mark.parametrize(
    ("count", "text"),
    [
        (0, "No element matches"),
        (1, "1 element matches, with its parents"),
        (5, "5 elements match, with their parents"),
    ],
)
def test_the_sentence_of_the_matches(count: int, text: str) -> None:
    assert match_text(count) == text


def test_the_pane_names_the_package_of_the_tree(shown, pane) -> None:
    from aas_workingbench.ui.tree_pane import package_name_of

    # The model gives the open packages as a set.
    packages = shown.table.openedPacks()
    (package,) = packages
    name = package_name_of(shown.view, packages)
    pane.set_package_name(name)

    assert pane.name.text() == package.name
    assert pane.more.menu().actions()[0].text() == "Close"


def test_a_group_of_the_tree_reads_as_a_title_with_its_count(shown) -> None:
    from aas_workingbench.ui.compact_rows import child_count_text

    group = shown.index("submodels")
    shown.view.expand(group)

    assert group.data(GROUP_TITLE_ROLE)
    assert child_count_text(shown.view, group) == "1"
    assert not shown.index("submodels", "Submodel").data(GROUP_TITLE_ROLE)


def test_a_group_title_is_semibold(shown) -> None:
    from PyQt6.QtGui import QFont

    font = shown.index("submodels").data(Qt.ItemDataRole.FontRole)

    assert font.weight() == QFont.Weight.DemiBold


# ---------------------------------------------------------------------------
# The command bar
# ---------------------------------------------------------------------------


def test_the_search_box_opens_the_palette(qtbot: QtBot) -> None:
    from PyQt6.QtGui import QKeySequence

    from aas_workingbench.ui.command_search import SEARCH_TEXT
    from aas_workingbench.ui.command_search import SearchBox

    palette = QAction("Command palette...")
    palette.setShortcut(QKeySequence("Ctrl+K"))
    opened: list[bool] = []
    palette.triggered.connect(lambda: opened.append(True))
    box = SearchBox(palette)
    qtbot.addWidget(box)

    box.click()

    assert opened == [True]
    assert box.label.text() == SEARCH_TEXT == "Search or go to…"
    assert box.key.text() == "Ctrl+K"


@pytest.fixture
def modes(qtbot: QtBot) -> Iterator[Any]:
    from PyQt6.QtGui import QActionGroup

    from aas_workingbench.ui.command_search import ModeSwitch

    read = QAction("Read mode", checkable=True)
    edit = QAction("Edit mode", checkable=True, checked=True)
    read.triggered.connect(lambda: edit_mode().set_editing(False))
    edit.triggered.connect(lambda: edit_mode().set_editing(True))
    group = QActionGroup(None)
    group.addAction(read)
    group.addAction(edit)
    switch = ModeSwitch(read, edit)
    qtbot.addWidget(switch)
    yield switch
    edit_mode().set_editing(True)
    del group


def test_the_switch_reads_read_and_edit(modes) -> None:
    assert (modes.read.text(), modes.edit.text()) == ("Read", "Edit")
    assert modes.edit.isChecked()


def test_a_click_on_read_turns_read_mode_on(modes) -> None:
    modes.read.click()

    assert not edit_mode().is_editing
    assert modes.read.isChecked() and not modes.edit.isChecked()


# ---------------------------------------------------------------------------
# A link opens its target in the same tab
# ---------------------------------------------------------------------------


@pytest.fixture
def tab(views, qtbot: QtBot):
    from aas_workingbench.widgets.tab import TabWidget

    target = make_property("Target")
    submodel = make_submodel(elements=[target])
    submodel.submodel_element.add(
        model.ReferenceElement("Link", value=make_reference_to(target))
    )
    shown = views()
    shown.open_package(submodel)
    widget = TabWidget(unclosable=True)
    qtbot.addWidget(widget)
    widget.addTab(widget.tabCls(parent=widget), "Welcome")
    widget.openItemInNewTab(shown.index("submodels", "Submodel", "Link"))
    return widget


def test_a_click_on_a_reference_opens_its_target_in_the_tab(tab) -> None:
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.settings.app_settings import VALUE_COLUMN

    current = tab.currentWidget()
    count = tab.count()
    proxy = current.attrsTreeView.model()
    value = next(
        proxy.index(row, VALUE_COLUMN)
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(NAME_ROLE) == "value"
    )

    current.attrsTreeView.clicked.emit(value)

    assert tab.count() == count
    assert current.packItemObj.id_short == "Target"
    current.openPrevItem()
    assert current.packItemObj.id_short == "Link"


def test_every_button_of_the_pane_has_a_name(pane) -> None:
    from PyQt6.QtWidgets import QToolButton

    pane.filter.set_text("Sp")

    for button in pane.findChildren(QToolButton):
        assert button.accessibleName() or button.text(), button


def test_the_icon_and_the_clear_button_of_the_filter_have_their_names(
    pane,
) -> None:
    from PyQt6.QtWidgets import QToolButton

    names = {
        b.accessibleName() for b in pane.filter.field.findChildren(QToolButton)
    }

    assert {"Filter", "Clear the filter"} <= names
