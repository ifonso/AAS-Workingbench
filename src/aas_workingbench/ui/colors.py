"""The colors of problems and advisories in dialogs, for the theme in use.

They are read from the design tokens when a widget is styled, so a dialog that
opens after a switch of theme has the colors of the new theme. A widget that
stays open across a switch is styled with `keep_styled`, `style_as_problem`,
or `style_as_advisory`, which style it again after each switch. Each color has the contrast of text on the surfaces of its theme, which
`tests/small/test_design_tokens.py` checks.
"""

from collections.abc import Callable

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.theme import theme_manager


def problem_color() -> str:
    """Gives the color of text that says why an input is refused."""
    return current_tokens().status_error


def advisory_color() -> str:
    """Gives the color of text that advises, and does not refuse."""
    return current_tokens().status_warning


def problem_style() -> str:
    """Gives the style sheet that colors text as a problem."""
    return f"color: {problem_color()};"


def advisory_style() -> str:
    """Gives the style sheet that colors text as an advisory."""
    return f"color: {advisory_color()};"


def problem_border_style() -> str:
    """Gives the style sheet that outlines an input as a problem."""
    return f"border: 1px solid {problem_color()};"


def keep_styled(widget: QWidget, style: Callable[[], str]) -> None:
    """Styles a widget now, and again after every switch of theme.

    A style that was read when the widget was made keeps the colors of the old
    theme while a dialog is open. This asks `style` again after each switch,
    so the widget follows. The connection ends with the widget.

    Args:
        widget: The widget to style.
        style: Gives the style sheet, such as `problem_style`.
    """
    _Restyler(widget, style)


def style_as_problem(label: QWidget) -> None:
    """Colors a label as a problem, for the theme in use and the next ones."""
    keep_styled(label, problem_style)


def style_as_advisory(label: QWidget) -> None:
    """Colors a label as an advisory, for the theme in use and the next ones."""
    keep_styled(label, advisory_style)


class _Restyler(QObject):
    """Puts a style on its parent widget when the theme changes."""

    def __init__(self, widget: QWidget, style: Callable[[], str]) -> None:
        super().__init__(widget)
        self._widget = widget
        self._style = style
        theme_manager().changed.connect(self.restyle)
        self.restyle()

    def restyle(self) -> None:
        """Sets the style that the theme in use gives."""
        self._widget.setStyleSheet(self._style())
