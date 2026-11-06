"""The rows of the trees: height by density, one level of emphasis, no stripes.

The signs of a row, the bar of the selection and the dot of a change, are read
from a picture of the view, because that is what a person sees. They have to be
there in the light and the dark theme.
"""

from collections.abc import Iterator
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import DEFAULT_DENSITY
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import INDENT
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.domain.design_tokens import ROW_HEIGHTS
from aas_editor.ui.theme import FLUENT_DARK
from aas_editor.ui.theme import FLUENT_LIGHT
from aas_editor.ui.theme import theme_manager

SUBMODEL = ("submodels", "Submodel")
FOREGROUND = Qt.ItemDataRole.ForegroundRole
FONT = Qt.ItemDataRole.FontRole
# The cell of a name is wider than its dot and the margin around it.
DOT_ROOM = 16

THEMES = [(FLUENT_LIGHT, LIGHT), (FLUENT_DARK, DARK)]
THEME_IDS = ["light", "dark"]


@pytest.fixture(autouse=True)
def light_theme(qapp: QApplication) -> Iterator[None]:
    """Puts the light theme on, and the look of the platform back after."""
    QStandardPaths.setTestModeEnabled(True)
    theme_manager().apply(FLUENT_LIGHT, DEFAULT_DENSITY)
    yield
    theme_manager().reset_to_native()
    theme_manager().set_density(DEFAULT_DENSITY)
    QStandardPaths.setTestModeEnabled(False)


@pytest.fixture
def restored_zoom() -> Iterator[None]:
    """Gives the font size of the models back after a test zoomed it."""
    from aas_editor.models import DetailedInfoTable
    from aas_editor.models import PacksTable

    sizes = (
        PacksTable.currFont.pointSize(),
        DetailedInfoTable.currFont.pointSize(),
    )
    yield
    PacksTable.currFont.setPointSize(sizes[0])
    DetailedInfoTable.currFont.setPointSize(sizes[1])


def _package_tree(
    views: Any,
    qtbot: QtBot,
    *elements: model.SubmodelElement,
    link_to: model.Property | None = None,
):
    """Shows the package tree over a submodel with the elements.

    Args:
        views: The fixture that builds views.
        qtbot: The Qt bot.
        elements: What the submodel holds.
        link_to: A property of the elements that gets a ReferenceElement
            `Link`, which is a link in the attributes of that element.
    """
    submodel = make_submodel(elements=elements)
    if link_to is not None:
        submodel.submodel_element.add(
            model.ReferenceElement(
                id_short="Link", value=make_reference_to(link_to)
            )
        )
    shown = views()
    package = shown.open_package(submodel)
    shown.window.resize(640, 420)
    shown.view.resize(620, 400)
    shown.window.show()
    qtbot.waitExposed(shown.window)
    return shown, package


def _cell_has_color(view: Any, index: QModelIndex, color: str) -> bool:
    """Whether a pixel of the right end of a cell has exactly this color."""
    image = view.viewport().grab().toImage()
    rect = view.visualRect(index)
    wanted = QColor(color).rgb()
    return any(
        image.pixelColor(x, y).rgb() == wanted
        for x in range(max(rect.right() - DOT_ROOM, 0), rect.right())
        for y in range(rect.top(), rect.bottom())
    )


def _edit(package: Any, element: model.Property, value: str) -> None:
    package.commandStack.push(
        SetAttribute(observer_for(package), element, "value", value)
    )


def test_a_row_of_the_package_tree_is_as_high_as_the_compact_density(
    views, qtbot: QtBot
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed"))

    row = shown.view.visualRect(shown.index(*SUBMODEL, "Speed")).height()

    assert row == ROW_HEIGHTS[Density.COMPACT]


@pytest.mark.parametrize("density", list(Density))
def test_a_row_follows_the_density_that_is_on(
    views, qtbot: QtBot, density: Density
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed"))

    theme_manager().set_density(density)
    qtbot.wait(20)
    row = shown.view.visualRect(shown.index(*SUBMODEL, "Speed")).height()

    assert row == ROW_HEIGHTS[density]


def test_a_row_of_the_attributes_is_as_high_as_the_density(
    views, qtbot: QtBot
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed"))
    attrs = shown.attrs_view(*SUBMODEL, "Speed")
    attrs.resize(500, 400)
    attrs.show()
    qtbot.waitExposed(attrs)

    row = attrs.visualRect(attrs.model().index(0, 0)).height()

    assert row == ROW_HEIGHTS[Density.COMPACT]


def test_a_zoomed_font_makes_the_rows_taller_than_the_density(
    views, qtbot: QtBot, restored_zoom: None
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed"))
    index = shown.index(*SUBMODEL, "Speed")

    for _ in range(5):
        shown.view.zoomIn()
    qtbot.wait(20)

    assert shown.view.visualRect(index).height() > ROW_HEIGHTS[Density.COMPACT]


def test_the_trees_have_no_stripes_and_the_indent_of_the_tokens(
    views, qtbot: QtBot
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed"))
    attrs = shown.attrs_view(*SUBMODEL, "Speed")

    for view in (shown.view, attrs):
        assert not view.alternatingRowColors()
        assert view.indentation() == INDENT


def test_names_and_values_are_regular_and_only_a_link_is_underlined(
    views, qtbot: QtBot
) -> None:
    speed = make_property("Speed")
    shown, _ = _package_tree(views, qtbot, speed, link_to=speed)
    attrs = shown.attrs_view(*SUBMODEL, "Link")
    proxy = attrs.model()
    rows = {
        proxy.index(row, 0).data(Qt.ItemDataRole.DisplayRole): row
        for row in range(proxy.rowCount())
    }
    name = proxy.index(rows["idShort"], 0)
    text = proxy.index(rows["idShort"], 1)
    reference = proxy.index(rows["value"], 1)

    for cell in (name, text, reference):
        assert not cell.data(FONT).bold()
        assert not cell.data(FONT).italic()
    assert not name.data(FONT).underline()
    assert not text.data(FONT).underline()
    assert reference.data(FONT).underline()


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_a_link_has_the_color_of_links(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    speed = make_property("Speed")
    shown, _ = _package_tree(views, qtbot, speed, link_to=speed)
    attrs = shown.attrs_view(*SUBMODEL, "Link")
    proxy = attrs.model()
    reference = next(
        proxy.index(row, 1)
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(Qt.ItemDataRole.DisplayRole) == "value"
    )

    theme_manager().apply(theme)

    assert reference.data(FOREGROUND) == QColor(tokens.link)


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_the_type_and_a_missing_value_are_muted(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed", value=None))
    attrs = shown.attrs_view(*SUBMODEL, "Speed")
    proxy = attrs.model()
    value_row = next(
        row
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(Qt.ItemDataRole.DisplayRole) == "value"
    )

    theme_manager().apply(theme)

    muted = QColor(tokens.fg_muted)
    assert proxy.index(value_row, 1).data(Qt.ItemDataRole.DisplayRole) == (
        "(not set)"
    )
    assert proxy.index(value_row, 1).data(FOREGROUND) == muted
    assert proxy.index(value_row, 2).data(FOREGROUND) == muted
    assert proxy.index(value_row, 0).data(FOREGROUND) is None


def test_a_value_that_is_set_has_the_color_of_text(views, qtbot: QtBot) -> None:
    shown, _ = _package_tree(views, qtbot, make_property("Speed", value="fast"))
    attrs = shown.attrs_view(*SUBMODEL, "Speed")
    proxy = attrs.model()
    value_row = next(
        row
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(Qt.ItemDataRole.DisplayRole) == "value"
    )

    assert proxy.index(value_row, 1).data(FOREGROUND) is None


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_a_changed_name_has_the_mark_color_and_a_dot(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    speed = make_property("Speed")
    other = make_property("Other")
    shown, package = _package_tree(views, qtbot, speed, other)
    theme_manager().apply(theme)

    _edit(package, speed, "fast")
    qtbot.wait(20)
    changed = shown.index(*SUBMODEL, "Speed")
    untouched = shown.index(*SUBMODEL, "Other")

    assert changed.data(FOREGROUND) == QColor(tokens.mark_changed)
    assert _cell_has_color(shown.view, changed, tokens.mark_changed)
    assert untouched.data(FOREGROUND) is None
    assert not _cell_has_color(shown.view, untouched, tokens.mark_changed)


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_a_row_without_changes_has_no_dot_after_the_save(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    speed = make_property("Speed")
    shown, package = _package_tree(views, qtbot, speed)
    theme_manager().apply(theme)
    _edit(package, speed, "fast")
    qtbot.wait(20)
    index = shown.index(*SUBMODEL, "Speed")
    assert _cell_has_color(shown.view, index, tokens.mark_changed)

    package.commandStack.mark_saved()
    qtbot.wait(20)

    assert not _cell_has_color(shown.view, index, tokens.mark_changed)


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_a_selected_row_has_a_bar_at_its_left_edge(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    shown, _ = _package_tree(
        views, qtbot, make_property("Speed"), make_property("Other")
    )
    theme_manager().apply(theme)
    selected = shown.index(*SUBMODEL, "Speed")
    other = shown.index(*SUBMODEL, "Other")

    shown.select(selected)
    qtbot.wait(20)
    image = shown.view.viewport().grab().toImage()

    bar_y = shown.view.visualRect(selected).center().y()
    other_y = shown.view.visualRect(other).center().y()
    assert image.pixelColor(0, bar_y) == QColor(tokens.link)
    assert image.pixelColor(0, other_y) != QColor(tokens.link)


@pytest.mark.parametrize(("theme", "tokens"), THEMES, ids=THEME_IDS)
def test_a_match_of_the_search_has_the_find_color(
    views, qtbot: QtBot, theme: str, tokens: ColorTokens
) -> None:
    from aas_editor.widgets.search import SearchBar

    shown, _ = _package_tree(views, qtbot, make_property("Speed"))
    theme_manager().apply(theme)
    bar = SearchBar(shown.view, [0], shown.window)
    qtbot.addWidget(bar)

    bar.searchLine.setText("Speed")
    match = shown.index(*SUBMODEL, "Speed")

    brush = shown.view.itemDelegate().bgColor(match)
    assert brush.color() == QColor(tokens.bg_find)
