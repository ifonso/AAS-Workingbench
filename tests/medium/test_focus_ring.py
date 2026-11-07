"""The focus ring is a token, two pixels wide, and fits the control under it.

The ring on a button that is filled with the accent takes the color of its
text, because the ring of the page is heavy on the accent and hides where the
button ends. Pixels are read from the picture that a control draws.
"""

from collections.abc import Iterator

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QRadioButton
from PyQt6.QtWidgets import QTabBar
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.domain.design_tokens import DARK
from aas_workingbench.domain.design_tokens import FOCUS_STROKE
from aas_workingbench.domain.design_tokens import LIGHT
from aas_workingbench.domain.design_tokens import ColorTokens
from aas_workingbench.ui.theme import THEME_DARK
from aas_workingbench.ui.theme import THEME_LIGHT
from aas_workingbench.ui.theme import theme_manager

THEMES = [(THEME_LIGHT, LIGHT), (THEME_DARK, DARK)]
_HOLDERS: list[QWidget] = []


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look of the platform back."""
    QStandardPaths.setTestModeEnabled(True)
    yield
    _HOLDERS.clear()
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


def _focused(qtbot: QtBot, widget: QWidget) -> QWidget:
    """Shows the widget in a window of its own, and gives it the focus."""
    window = QWidget()
    qtbot.addWidget(window)
    QVBoxLayout(window).addWidget(widget)
    # qtbot holds its widgets weakly, so the test holds the window.
    _HOLDERS.append(window)
    window.show()
    qtbot.waitExposed(window)
    window.activateWindow()
    widget.setFocus()
    QApplication.processEvents()
    assert widget.hasFocus()
    return widget


def _edge(widget: QWidget, inset: int) -> QColor:
    """The color at the middle of the left edge, `inset` pixels in."""
    image = widget.grab().toImage()
    return image.pixelColor(inset, image.height() // 2)


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
def test_a_button_has_a_ring_of_the_focus_token_two_pixels_wide(
    qtbot: QtBot, choice: str, tokens: ColorTokens
) -> None:
    theme_manager().apply(choice)
    button = _focused(qtbot, QPushButton("Plain"))

    ring = [_edge(button, inset) for inset in range(FOCUS_STROKE)]
    inside = _edge(button, FOCUS_STROKE + 2)

    assert ring == [QColor(tokens.focus)] * FOCUS_STROKE
    assert inside != QColor(tokens.focus)


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
def test_the_ring_inside_the_filled_button_takes_the_color_of_its_text(
    qtbot: QtBot, choice: str, tokens: ColorTokens
) -> None:
    theme_manager().apply(choice)
    primary = QPushButton("Save")
    primary.setProperty("primary", True)
    button = _focused(qtbot, primary)

    ring = [_edge(button, inset) for inset in range(FOCUS_STROKE)]

    assert ring == [QColor(tokens.focus_on_accent)] * FOCUS_STROKE


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
@pytest.mark.parametrize("kind", [QCheckBox, QRadioButton])
@pytest.mark.parametrize("checked", [False, True])
def test_a_check_box_or_radio_button_rings_its_indicator_and_keeps_its_size(
    qtbot: QtBot,
    choice: str,
    tokens: ColorTokens,
    kind: type[QCheckBox] | type[QRadioButton],
    checked: bool,
) -> None:
    theme_manager().apply(choice)
    box = kind("Option")
    box.setChecked(checked)
    window = QWidget()
    qtbot.addWidget(window)
    QVBoxLayout(window).addWidget(box)
    _HOLDERS.append(window)
    window.show()
    qtbot.waitExposed(window)
    size_without_focus = box.sizeHint()
    window.activateWindow()
    box.setFocus()
    QApplication.processEvents()
    assert box.hasFocus()

    ring = [_edge(box, inset) for inset in range(FOCUS_STROKE)]

    assert ring == [QColor(tokens.focus)] * FOCUS_STROKE
    assert box.sizeHint() == size_without_focus


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
def test_a_tab_that_has_the_focus_shows_the_ring_and_keeps_its_size(
    qtbot: QtBot, choice: str, tokens: ColorTokens
) -> None:
    theme_manager().apply(choice)
    bar = QTabBar()
    bar.addTab("First")
    bar.addTab("Second")
    window = QWidget()
    qtbot.addWidget(window)
    QVBoxLayout(window).addWidget(bar)
    window.show()
    qtbot.waitExposed(window)
    size_without_focus = bar.tabSizeHint(0)
    window.activateWindow()
    bar.setFocus()
    QApplication.processEvents()
    assert bar.hasFocus()
    rect = bar.tabRect(bar.currentIndex())
    image = bar.grab().toImage()

    ring = [
        image.pixelColor(rect.left() + inset, rect.center().y())
        for inset in range(FOCUS_STROKE)
    ]

    assert ring == [QColor(tokens.focus)] * FOCUS_STROKE
    assert bar.tabSizeHint(0) == size_without_focus
