"""The path of a tab is read as segments, and a click on the blank area edits it."""

from collections.abc import Iterator

from PyQt6.QtCore import QPoint
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.ui.breadcrumb import Breadcrumb

PATH = ["showcase.aasx", "Submodels", "MotorData", "RatedPower"]


@pytest.fixture
def crumb(qapp: object, qtbot: QtBot) -> Iterator[Breadcrumb]:
    """A breadcrumb that is shown, 600 pixels wide, with the path above."""
    editor = QLineEdit()
    widget = Breadcrumb(editor)
    qtbot.addWidget(widget)
    widget.resize(600, 28)
    widget.show()
    widget.set_path(PATH, "Property")
    yield widget


def _segments(crumb: Breadcrumb) -> list[QToolButton]:
    return [
        button
        for button in crumb.findChildren(QToolButton, "breadcrumbSegment")
        if button.isVisibleTo(crumb) and button.text() != "…"
    ]


def test_each_name_of_the_path_is_a_button(crumb: Breadcrumb) -> None:
    assert [button.text() for button in _segments(crumb)] == PATH
    assert crumb.names == PATH


def test_only_the_last_segment_is_marked_as_the_current_one(
    crumb: Breadcrumb,
) -> None:
    marked = [
        button.text()
        for button in _segments(crumb)
        if button.property("current")
    ]

    assert marked == ["RatedPower"]


def test_a_click_on_a_segment_tells_its_position(
    crumb: Breadcrumb, qtbot: QtBot
) -> None:
    second = _segments(crumb)[1]

    with qtbot.waitSignal(crumb.segment_activated) as signal:
        second.click()

    assert signal.args == [1]


def test_a_click_on_the_blank_area_shows_the_text_field(
    crumb: Breadcrumb,
) -> None:
    assert not crumb.is_editing

    page = crumb.findChild(QWidget, "breadcrumbSegments")
    assert page is not None
    QTest.mouseClick(
        page,
        Qt.MouseButton.LeftButton,
        pos=QPoint(crumb.width() - 120, 14),
    )

    assert crumb.is_editing
    assert crumb.editor.isVisibleTo(crumb)


def test_escape_leaves_the_text_field(crumb: Breadcrumb) -> None:
    crumb.start_editing()

    QTest.keyClick(crumb.editor, Qt.Key.Key_Escape)

    assert not crumb.is_editing


def test_the_end_of_an_edit_shows_the_segments_again(crumb: Breadcrumb) -> None:
    crumb.start_editing()

    crumb.editor.editingFinished.emit()

    assert not crumb.is_editing


def test_a_new_path_replaces_the_segments(crumb: Breadcrumb) -> None:
    crumb.set_path(["other.aasx", "Files"], "")

    assert [button.text() for button in _segments(crumb)] == [
        "other.aasx",
        "Files",
    ]


def test_a_path_that_does_not_fit_folds_its_first_segments(
    crumb: Breadcrumb, qtbot: QtBot
) -> None:
    crumb.resize(230, 28)
    crumb.set_path(PATH, "Property")

    shown = [button.text() for button in _segments(crumb)]

    assert shown[-1] == "RatedPower"
    assert "showcase.aasx" not in shown
    folded = crumb.findChildren(QToolButton, "breadcrumbSegment")
    assert any(
        button.text() == "…" and button.isVisibleTo(crumb) for button in folded
    )


def test_a_folded_segment_can_still_be_opened_from_the_menu(
    crumb: Breadcrumb, qtbot: QtBot
) -> None:
    crumb.resize(230, 28)
    crumb.set_path(PATH, "Property")
    fold = next(
        button
        for button in crumb.findChildren(QToolButton, "breadcrumbSegment")
        if button.text() == "…"
    )
    menu = fold.menu()
    assert menu is not None
    first = menu.actions()[0]

    with qtbot.waitSignal(crumb.segment_activated) as signal:
        first.trigger()

    assert signal.args == [0]
    assert first.text() == "showcase.aasx"
