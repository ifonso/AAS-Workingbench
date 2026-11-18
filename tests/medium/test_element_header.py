"""The header of the detail keeps its title whole in a short tab.

The 20 pixels above and below the title are room to read. A tab that is short
of height, such as one above an open panel, takes that room first. It took the
title too: the header got shorter, the room stayed, and the title was cut.
"""

from typing import Any

from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

ATTRIBUTES_HEIGHT = 200
"""The least height of the attributes below the header, in the stand-in tab."""


@pytest.fixture
def tab(qapp: object, qtbot: QtBot) -> Any:
    """A stand-in for a tab: the header above attributes of a least height."""
    from aas_workingbench.ui.element_header import ElementHeader

    tab = QWidget()
    qtbot.addWidget(tab)
    tab.header = ElementHeader(tab)  # type: ignore[attr-defined]
    tab.header.set_element(None, "CycleTimeTarget", "Property")  # type: ignore[attr-defined]
    attributes = QWidget(tab)
    attributes.setMinimumHeight(ATTRIBUTES_HEIGHT)
    layout = QVBoxLayout(tab)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(tab.header)  # type: ignore[attr-defined]
    layout.addWidget(attributes, 1)
    tab.resize(400, 600)
    tab.show()
    return tab


def test_a_tab_with_room_gives_the_header_the_room_around_its_title(
    tab: Any,
) -> None:
    from aas_workingbench.ui.element_header import HEADER_PADDING

    title = tab.header.title.sizeHint().height()

    assert tab.header.height() == title + 2 * HEADER_PADDING


def test_a_short_tab_takes_the_room_and_leaves_the_title_whole(
    tab: Any,
) -> None:
    tab.resize(400, ATTRIBUTES_HEIGHT + tab.header.minimumSizeHint().height())

    assert tab.header.height() == tab.header.minimumSizeHint().height()
    assert tab.header.rect().contains(tab.header.title.geometry())
    assert tab.header.title.height() >= tab.header.title.sizeHint().height()


def test_a_short_tab_leaves_the_type_whole(tab: Any) -> None:
    tab.resize(400, ATTRIBUTES_HEIGHT + tab.header.minimumSizeHint().height())

    assert tab.header.rect().contains(tab.header.badge.geometry())
    assert tab.header.badge.height() >= tab.header.badge.sizeHint().height()


def test_the_type_is_no_taller_than_the_title(tab: Any) -> None:
    assert tab.header.badge.height() <= tab.header.title.sizeHint().height()


def test_a_tab_that_grows_again_gives_the_room_back(tab: Any) -> None:
    full = tab.header.height()

    tab.resize(400, ATTRIBUTES_HEIGHT + tab.header.minimumSizeHint().height())
    tab.resize(400, 600)

    assert tab.header.height() == full
