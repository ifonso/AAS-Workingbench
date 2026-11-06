"""The colors of problems and advisories in dialogs, for the theme in use.

They are read from the design tokens when a widget is styled, so a dialog that
opens after a switch of theme has the colors of the new theme. A widget that
stays open across a switch connects `ThemeManager.changed` and styles itself
again. Each color has the contrast of text on the surfaces of its theme, which
`tests/small/test_design_tokens.py` checks.
"""

from aas_editor.ui.theme import current_tokens


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
