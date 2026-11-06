"""The look of the application: tokens turned into a palette and a style sheet.

Use `theme_manager()` to switch a theme and `current_tokens()` to read the
colors of the theme in use. See ADR 0025.
"""

from aas_editor.ui.theme.manager import current_tokens
from aas_editor.ui.theme.manager import FLUENT_DARK
from aas_editor.ui.theme.manager import FLUENT_LIGHT
from aas_editor.ui.theme.manager import FLUENT_SYSTEM
from aas_editor.ui.theme.manager import FLUENT_THEMES
from aas_editor.ui.theme.manager import theme_manager
from aas_editor.ui.theme.manager import ThemeManager

__all__ = [
    "FLUENT_DARK",
    "FLUENT_LIGHT",
    "FLUENT_SYSTEM",
    "FLUENT_THEMES",
    "ThemeManager",
    "current_tokens",
    "theme_manager",
]
