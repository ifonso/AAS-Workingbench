"""The theme of the application: which one is on, and how to switch it.

Light, Dark, and Follow system are Fusion with a palette and a style sheet
made from the design tokens (ADR 0025). Native gives back the style and the
palette that the application started with, and no style sheet.

Code that needs a color reads `current_tokens()` when it draws or styles, and
connects to `ThemeManager.changed` when it has to follow a switch.
"""

from functools import cache
from typing import Final

from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtGui import QStyleHints
from PyQt6.QtWidgets import QApplication

from aas_editor.application.theme_choice import THEME_DARK
from aas_editor.application.theme_choice import THEME_LABELS
from aas_editor.application.theme_choice import THEME_LIGHT
from aas_editor.application.theme_choice import THEME_NATIVE
from aas_editor.application.theme_choice import THEME_SYSTEM
from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import DEFAULT_DENSITY
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.domain.design_tokens import ROW_HEIGHTS
from aas_editor.ui.theme.palette import build_palette
from aas_editor.ui.theme.stylesheet import build_stylesheet

_STYLE: Final = "Fusion"
_SHEET_THEMES: Final = frozenset({THEME_SYSTEM, THEME_LIGHT, THEME_DARK})


class ThemeManager(QObject):
    """Puts a theme on the application and tells who follows it.

    Attributes:
        changed: Emitted after a theme was put on, when colors have to be read
            again.
    """

    changed = pyqtSignal()

    def __init__(self, app: QApplication) -> None:
        """Remembers the native look, which the Native theme restores.

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
        """The colors in use. Native counts as light or dark, as the system is."""
        return self._tokens

    @property
    def density(self) -> Density:
        """How tightly rows sit."""
        return self._density

    @property
    def row_height(self) -> int:
        """The height of a row of a tree or a table, in pixels."""
        return ROW_HEIGHTS[self._density]

    def set_density(self, density: Density) -> None:
        """Changes how tightly rows sit.

        The sheet of a new theme is made again, because the padding of menu
        items follows the density. Whatever else shows rows reads the density
        when it is told that the theme changed.

        Args:
            density: The new density.
        """
        if density == self._density:
            return
        self._density = density
        if self._choice in _SHEET_THEMES:
            self._apply_fluent()
        else:
            self.changed.emit()

    def apply(self, choice: str, density: Density | None = None) -> None:
        """Puts a new theme on the application.

        Args:
            choice: `THEME_SYSTEM`, `THEME_LIGHT`, `THEME_DARK`, or
                `THEME_NATIVE`.
            density: How tightly rows sit. The density of the last call stays
                when this is None.

        Raises:
            ValueError: If the choice is not a theme.
        """
        if choice not in THEME_LABELS:
            raise ValueError(f"Unknown theme: '{choice}'")
        if density is not None:
            self._density = density
        self._choice = choice
        if choice == THEME_NATIVE:
            self._put_native()
        else:
            self._apply_fluent()

    def reset_to_native(self) -> None:
        """Gives back the style and palette of the platform, and no choice."""
        self._put_native()
        self._choice = ""

    def _put_native(self) -> None:
        self._applying = True
        try:
            self._set_scheme(Qt.ColorScheme.Unknown)
            self._set_base_style(self._native_style)
            self._app.setPalette(self._native_palette)
            self._app.setStyleSheet("")
            # Native draws what the system draws, so code that colors by
            # token follows the system's scheme.
            self._tokens = self._system_tokens()
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
        if self._choice == THEME_DARK:
            self._set_scheme(Qt.ColorScheme.Dark)
            return DARK
        if self._choice == THEME_LIGHT:
            self._set_scheme(Qt.ColorScheme.Light)
            return LIGHT
        # Unknown hands the decision back to the system, which is then read.
        self._set_scheme(Qt.ColorScheme.Unknown)
        return self._system_tokens()

    def _system_tokens(self) -> ColorTokens:
        if self._hints.colorScheme() == Qt.ColorScheme.Dark:
            return DARK
        return LIGHT

    def _set_scheme(self, scheme: Qt.ColorScheme) -> None:
        """Sets the scheme of native parts, such as title bars and dialogs."""
        self._hints.setColorScheme(scheme)

    def _on_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        if self._choice == THEME_SYSTEM and not self._applying:
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
