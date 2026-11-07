"""The look of the application: tokens turned into a palette and a style sheet.

Use `theme_manager()` to switch a theme and `current_tokens()` to read the
colors of the theme in use. See ADR 0025.
"""

from aas_editor.application.theme_choice import THEME_DARK
from aas_editor.application.theme_choice import THEME_LABELS
from aas_editor.application.theme_choice import THEME_LIGHT
from aas_editor.application.theme_choice import THEME_NATIVE
from aas_editor.application.theme_choice import THEME_SYSTEM
from aas_editor.ui.theme.manager import current_tokens
from aas_editor.ui.theme.manager import theme_manager
from aas_editor.ui.theme.manager import ThemeManager

__all__ = [
    "THEME_DARK",
    "THEME_LABELS",
    "THEME_LIGHT",
    "THEME_NATIVE",
    "THEME_SYSTEM",
    "ThemeManager",
    "current_tokens",
    "theme_manager",
]
