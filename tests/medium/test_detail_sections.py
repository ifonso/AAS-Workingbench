"""The detail of an element reads in sections, under a header in two levels.

Proposals 3.1 to 3.3 and 4.2 of `design/ui-proposals.md`: the path bar says
where the element is, a header which element it is, and the attributes come in
sections that a click on their band opens and closes. In Read mode the
attributes that hold nothing are in a closed section of their own.
"""

from collections.abc import Iterator
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QPoint
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.domain.attribute_sections import Section

SPEED = ("submodels", "Submodel", "Speed")


@pytest.fixture
def read_mode() -> Iterator[None]:
    edit_mode().set_editing(False)
    yield
    edit_mode().set_editing(True)


def _speed(*, qualified: bool = False) -> model.Property:
    prop = make_property("Speed", value="1")
    if qualified:
        prop.qualifier.add(
            model.Qualifier("Cardinality", model.datatypes.String, "One")
        )
    return prop


@pytest.fixture
def attrs(views, qtbot: QtBot):
    def make(prop: model.Property | None = None) -> Any:
        shown = views()
        shown.open_package(make_submodel(elements=[prop or _speed()]))
        view = shown.attrs_view(*SPEED)
        view.resize(700, 600)
        view.show()
        qtbot.waitExposed(view)
        return view

    return make


def _sections(view: Any) -> list[Section]:
    return [band.section for band in view.bands.bands]


def _rows_of(view: Any, section: Section) -> list[int]:
    (band,) = [b for b in view.bands.bands if b.section is section]
    return band.rows


def _band_point(view: Any, section: Section) -> QPoint:
    (band,) = [b for b in view.bands.bands if b.section is section]
    index = view.model().index(band.first_row, 0)
    rect = view.visualRect(index)
    # The cell of an open section is below its band, and the first row of a
    # closed one is all band.
    top = rect.top()
    if not view.bands.shows_only_band(index):
        top -= view.bandOffset(index)
    return QPoint(rect.left() + 40, top + 12)


def test_read_mode_reads_value_identification_and_the_empty_ones_last(
    read_mode: None, attrs: Any
) -> None:
    view = attrs()

    assert _sections(view) == [
        Section.VALUE,
        Section.IDENTIFICATION,
        Section.EMPTY,
    ]


def test_edit_mode_keeps_the_empty_ones_in_their_sections(attrs: Any) -> None:
    view = attrs()

    assert _sections(view) == [
        Section.VALUE,
        Section.IDENTIFICATION,
        Section.SEMANTICS,
        Section.ADVANCED,
    ]


def test_the_empty_attributes_start_closed_with_one_row_for_their_band(
    read_mode: None, attrs: Any
) -> None:
    view = attrs()
    first, *others = _rows_of(view, Section.EMPTY)

    assert not view.isRowHidden(first, QModelIndex())
    assert others
    assert all(view.isRowHidden(row, QModelIndex()) for row in others)


def test_a_click_on_the_band_opens_the_empty_attributes(
    read_mode: None, attrs: Any
) -> None:
    view = attrs()

    QTest.mouseClick(
        view.viewport(),
        Qt.MouseButton.LeftButton,
        pos=_band_point(view, Section.EMPTY),
    )

    rows = _rows_of(view, Section.EMPTY)
    assert not any(view.isRowHidden(row, QModelIndex()) for row in rows)


def test_a_second_click_closes_the_section_again(attrs: Any) -> None:
    view = attrs()
    point = _band_point(view, Section.IDENTIFICATION)

    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)

    first, *others = _rows_of(view, Section.IDENTIFICATION)
    assert all(view.isRowHidden(row, QModelIndex()) for row in others)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
    assert not any(view.isRowHidden(row, QModelIndex()) for row in others)


def test_space_on_the_band_of_a_closed_section_opens_it(
    read_mode: None, attrs: Any
) -> None:
    view = attrs()
    first, *others = _rows_of(view, Section.EMPTY)
    view.setCurrentIndex(view.model().index(first, 0))

    QTest.keyClick(view, Qt.Key.Key_Space)

    assert not any(view.isRowHidden(row, QModelIndex()) for row in others)


def test_advanced_starts_closed_while_it_holds_nothing(attrs: Any) -> None:
    view = attrs()

    assert not view.bands.is_open(Section.ADVANCED)


def test_advanced_starts_open_when_a_qualifier_is_set(attrs: Any) -> None:
    view = attrs(_speed(qualified=True))

    assert view.bands.is_open(Section.ADVANCED)


def test_a_section_that_was_closed_stays_closed_for_the_next_element(
    attrs: Any,
) -> None:
    view = attrs()
    view.toggleSection(view.model().index(_rows_of(view, Section.VALUE)[0], 0))

    view.readSections()

    assert not view.bands.is_open(Section.VALUE)


def test_the_first_row_of_a_section_is_taller_by_its_band(attrs: Any) -> None:
    view = attrs()
    value, value_type, *_ = _rows_of(view, Section.VALUE)
    first = view.model().index(value, 0)

    height = view.indexRowSizeHint(first)

    assert height == view.indexRowSizeHint(
        view.model().index(value_type, 0)
    ) + view.bandOffset(first)


def test_the_cell_of_the_first_row_is_below_its_band(attrs: Any) -> None:
    view = attrs()
    value, value_type, *_ = _rows_of(view, Section.VALUE)

    cell = view.visualRect(view.model().index(value, 0))
    next_cell = view.visualRect(view.model().index(value_type, 0))

    assert cell.height() == next_cell.height()
    assert cell.bottom() + 1 == next_cell.top()


def test_the_editor_of_the_first_row_goes_below_the_band(
    attrs: Any, qtbot: QtBot
) -> None:
    from aas_workingbench.settings.app_settings import VALUE_COLUMN

    view = attrs()
    index = view.model().index(_rows_of(view, Section.VALUE)[0], VALUE_COLUMN)
    view.setCurrentIndex(index)

    view.edit(index)
    qtbot.wait(20)

    editor = view.indexWidget(index) or view.focusWidget()
    band = view.bandOffset(index)
    assert editor.geometry().top() >= view.visualRect(index).top()
    assert view.visualRect(index).top() >= band


# ---------------------------------------------------------------------------
# The header in two levels, and the path
# ---------------------------------------------------------------------------


@pytest.fixture
def tab(views, qtbot: QtBot):
    from aas_workingbench.widgets.tab import TabWidget

    shown = views()
    group = model.SubmodelElementCollection("Group", value=[_speed()])
    shown.open_package(make_submodel(elements=[group]))
    widget = TabWidget(unclosable=True)
    qtbot.addWidget(widget)
    widget.addTab(widget.tabCls(parent=widget), "Welcome")
    widget.openItemInNewTab(
        shown.index("submodels", "Submodel", "Group", "Speed")
    )
    return widget.currentWidget()


def test_the_header_names_the_element_and_its_type(tab: Any) -> None:
    assert tab.elementHeader.title.text() == "Speed"
    assert tab.elementHeader.badge.text() == "Property"


def test_the_path_starts_at_the_submodel_and_ends_at_the_element(
    tab: Any,
) -> None:
    assert tab.breadcrumb.names == ["Submodel", "Group", "Speed"]


def test_the_path_separates_its_parts_with_a_chevron() -> None:
    from aas_workingbench.ui.breadcrumb import SEPARATOR

    assert SEPARATOR == "›"


def test_a_part_of_the_path_opens_its_object(tab: Any) -> None:
    tab.openSegment(1)

    assert tab.packItemObj.id_short == "Group"
    assert tab.breadcrumb.names == ["Submodel", "Group"]


def test_a_tab_without_an_element_says_what_to_do(tab: Any) -> None:
    tab.openEmptyItem()

    assert not tab.nothingSelected.isHidden()
    assert tab.nothingSelected.title.text() == "Select an element"
    assert tab.splitter.isHidden()


def test_a_tab_with_an_element_hides_the_message(tab: Any) -> None:
    assert tab.nothingSelected.isHidden()
    assert not tab.elementHeader.isHidden()
