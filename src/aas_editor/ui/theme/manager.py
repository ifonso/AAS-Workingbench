"""The theme of the application: which one is on, and how to switch it.

The new themes are Fusion with a palette and a style sheet made from the
design tokens (ADR 0025). Old themes are style sheets of the vendored Breeze
set. They stay until the phase that removes them, so the manager can also put
one of them on, and then restores the native style and palette that the
application started with.

Code that needs a color reads `current_tokens()` when it draws or styles, and
connects to `ThemeManager.changed` when it has to follow a switch.
"""

from functools import cache
from pathlib import Path
from typing import Final

from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtGui import QStyleHints
from PyQt6.QtWidgets import QApplication

from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import DEFAULT_DENSITY
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.domain.design_tokens import ROW_HEIGHTS
from aas_editor.ui.theme.palette import build_palette
from aas_editor.ui.theme.stylesheet import build_stylesheet

FLUENT_LIGHT: Final = "fluent-light"
FLUENT_DARK: Final = "fluent-dark"
FLUENT_SYSTEM: Final = "fluent-system"

FLUENT_THEMES: Final = {
    FLUENT_LIGHT: "Fluent light",
    FLUENT_DARK: "Fluent dark",
    FLUENT_SYSTEM: "Fluent, follow the system",
}
"""The ids of the new themes, as saved in the settings, and their labels."""

# The old themes that are light. Every other old theme is dark.
_LIGHT_LEGACY: Final = frozenset({"light", "default"})
_STYLE: Final = "Fusion"


class ThemeManager(QObject):
    """Puts a theme on the application and tells who follows it.

    Attributes:
        changed: Emitted after a theme was put on, when colors have to be read
            again.
    """

    changed = pyqtSignal()

    def __init__(self, app: QApplication) -> None:
        """Remembers the native look, which an old theme restores.

        Args:
            app: The application whose style is managed.
        """
        super().__init__(app)
        style = app.style()
        hints = app.styleHints()
        if style is None or hints is None:
            raise RuntimeError("The application has no style yet")
        self._app = app
        self._hints: QStyleHints = hints
        self._native_style = style.objectName()
        # With a style sheet on, `app.style()` is the style of the sheet and
        # does not name the style under it, so the name is kept here.
        self._base_style = self._native_style
        self._native_palette = QPalette(app.palette())
        self._choice = ""
        self._tokens: ColorTokens = LIGHT
        self._density = DEFAULT_DENSITY
        self._applying = False
        hints.colorSchemeChanged.connect(self._on_scheme_changed)

    @property
    def choice(self) -> str:
        """The id of the theme that is on, or an empty text before any."""
        return self._choice

    @property
    def base_style(self) -> str:
        """The name of the Qt style under the style sheet, in lower case."""
        return self._base_style.lower()

    @property
    def tokens(self) -> ColorTokens:
        """The colors in use. Old themes count as light or dark."""
        return self._tokens

    @property
    def density(self) -> Density:
        """How tightly rows sit."""
        return self._density

    @property
    def row_height(self) -> int:
        """The height of a row of a tree or a table, in pixels."""
        return ROW_HEIGHTS[self._density]

    def apply(self, choice: str, density: Density | None = None) -> None:
        """Puts a new theme on the application.

        Args:
            choice: `FLUENT_LIGHT`, `FLUENT_DARK`, or `FLUENT_SYSTEM`.
            density: How tightly rows sit. The density of the last call stays
                when this is None.

        Raises:
            ValueError: If the choice is not a new theme.
        """
        if choice not in FLUENT_THEMES:
            raise ValueError(f"Unknown theme: '{choice}'")
        if density is not None:
            self._density = density
        self._choice = choice
        self._apply_fluent()

    def apply_legacy(self, name: str, stylesheet: Path) -> None:
        """Puts an old theme on the application.

        Args:
            name: The name of the theme, such as `grey`.
            stylesheet: The style sheet of the theme.
        """
        self._choice = name
        self._tokens = LIGHT if name in _LIGHT_LEGACY else DARK
        self._put_native(stylesheet.read_text(encoding="utf-8"))

    def reset_to_native(self) -> None:
        """Gives back the style and palette of the platform, and no sheet."""
        self._choice = ""
        self._tokens = LIGHT
        self._put_native("")

    def _put_native(self, stylesheet: str) -> None:
        self._applying = True
        try:
            self._set_scheme(Qt.ColorScheme.Unknown)
            self._set_base_style(self._native_style)
            self._app.setPalette(self._native_palette)
            self._app.setStyleSheet(stylesheet)
        finally:
            self._applying = False
        self.changed.emit()

    def _apply_fluent(self) -> None:
        self._applying = True
        try:
            tokens = self._resolve_tokens()
            self._tokens = tokens
            self._set_base_style(_STYLE)
            self._app.setPalette(build_palette(tokens))
            self._app.setStyleSheet(build_stylesheet(tokens, self._density))
        finally:
            self._applying = False
        self.changed.emit()

    def _set_base_style(self, name: str) -> None:
        if name.lower() != self._base_style.lower():
            self._app.setStyle(name)
            self._base_style = name

    def _resolve_tokens(self) -> ColorTokens:
        """Picks the tokens, and tells Qt which scheme native parts draw in."""
        if self._choice == FLUENT_DARK:
            self._set_scheme(Qt.ColorScheme.Dark)
            return DARK
        if self._choice == FLUENT_LIGHT:
            self._set_scheme(Qt.ColorScheme.Light)
            return LIGHT
        # Unknown hands the decision back to the system, which is then read.
        self._set_scheme(Qt.ColorScheme.Unknown)
        if self._hints.colorScheme() == Qt.ColorScheme.Dark:
            return DARK
        return LIGHT

    def _set_scheme(self, scheme: Qt.ColorScheme) -> None:
        """Sets the scheme of native parts, such as title bars and dialogs."""
        self._hints.setColorScheme(scheme)

    def _on_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._choice == FLUENT_SYSTEM and not self._applying:
            self._apply_fluent()


@cache
def theme_manager() -> ThemeManager:
    """Gives the manager of the application, which is made on first use.

    Returns:
        The one manager.

    Raises:
        RuntimeError: If there is no `QApplication` yet.
    """
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        raise RuntimeError("No QApplication: make it before the theme")
    return ThemeManager(app)


def current_tokens() -> ColorTokens:
    """Gives the colors of the theme in use.

    Returns:
        The tokens of the theme that is on. The light tokens before any theme
        is on, and when there is no application, so that text can be colored
        in code that runs before a window.
    """
    if QApplication.instance() is None:
        return LIGHT
    return theme_manager().tokens
