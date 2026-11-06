"""The design tokens of the editor: colors, spacing, type, and density.

This is the one table that the style sheet, the palette, and the colors of
dialogs are made from (see ADR 0025). It holds data and the contrast formula
and no Qt, so the pairs of colors that carry text and icons can be checked
without a window.

The neutrals follow the alias tokens of Fluent 2 (MIT), and the accent, the
status colors, and the selection are this project's own. The numbers are in
the plan, `docs/planning/ui-ux-plan.md`, section 2.

Attributes of `ColorTokens` are named by role, `<group>_<role>`: `bg_` is a
surface, `fg_` is text and icons, `stroke_` is a line, and `status_` and
`mark_` color a state. Every value is a `#rrggbb` string.
"""

from dataclasses import dataclass
from dataclasses import fields
from enum import StrEnum
import re
from typing import Final

_HEX = re.compile(r"#[0-9a-f]{6}")


@dataclass(frozen=True)
class ColorTokens:
    """The colors of one theme.

    Attributes:
        name: `light` or `dark`.
        is_dark: Whether the surfaces are darker than the text.
        bg_content: Trees, tables, and inputs.
        bg_chrome: Toolbars, menu bar, dialogs, and the status bar.
        bg_sunken: The dock strip and the preview.
        bg_hover: A row or a button under the pointer.
        bg_pressed: A button that is pressed.
        bg_selected: A selected row.
        fg_primary: Names and values.
        fg_secondary: Labels and icons.
        fg_muted: The Type column and `(not set)`.
        fg_disabled: Disabled text and icons. Exempt from the contrast rule.
        stroke_strong: The edge of an input, which must be seen.
        stroke_default: The outline of a control.
        stroke_subtle: A divider.
        focus: The focus ring.
        accent: The primary button, the active tab, and the selection bar.
        accent_hover: The primary button under the pointer or pressed.
        accent_on: Text on `accent` and on `accent_hover`.
        link: A link.
        mark_changed: A row that was changed.
        status_error: An error.
        status_warning: A warning, or text of a hint.
        status_success: A success.
        mark_new: A row that was added.
        bg_error: The strip behind an error.
        bg_warning: The strip behind a hint.
        bg_find: A match of the search.
    """

    name: str
    is_dark: bool
    bg_content: str
    bg_chrome: str
    bg_sunken: str
    bg_hover: str
    bg_pressed: str
    bg_selected: str
    fg_primary: str
    fg_secondary: str
    fg_muted: str
    fg_disabled: str
    stroke_strong: str
    stroke_default: str
    stroke_subtle: str
    focus: str
    accent: str
    accent_hover: str
    accent_on: str
    link: str
    mark_changed: str
    status_error: str
    status_warning: str
    status_success: str
    mark_new: str
    bg_error: str
    bg_warning: str
    bg_find: str

    def __post_init__(self) -> None:
        """Refuses a value that is not `#rrggbb`, so a typo fails early."""
        for token in self.color_names():
            value = str(getattr(self, token))
            if not _HEX.fullmatch(value):
                raise ValueError(f"Not a color: '{value}' for '{token}'")

    def color_names(self) -> tuple[str, ...]:
        """Lists the names of the tokens that hold a color."""
        return tuple(
            field.name
            for field in fields(self)
            if field.name not in ("name", "is_dark")
        )

    def color(self, token: str) -> str:
        """Reads one color by the name of its token.

        Args:
            token: A name from `color_names`.

        Returns:
            The `#rrggbb` value.

        Raises:
            KeyError: If there is no such token.
        """
        if token not in self.color_names():
            raise KeyError(f"Unknown color token: '{token}'")
        return str(getattr(self, token))


LIGHT: Final = ColorTokens(
    name="light",
    is_dark=False,
    bg_content="#ffffff",
    bg_chrome="#fafafa",
    bg_sunken="#f5f5f5",
    bg_hover="#f0f0f0",
    bg_pressed="#e0e0e0",
    bg_selected="#d6e6f8",
    fg_primary="#242424",
    fg_secondary="#424242",
    fg_muted="#616161",
    fg_disabled="#bdbdbd",
    stroke_strong="#616161",
    stroke_default="#d1d1d1",
    stroke_subtle="#e0e0e0",
    focus="#000000",
    accent="#0f62b8",
    accent_hover="#0c5299",
    accent_on="#ffffff",
    link="#0f62b8",
    mark_changed="#0f62b8",
    status_error="#b3261e",
    status_warning="#8a5a00",
    status_success="#0e700e",
    mark_new="#0e700e",
    bg_error="#fdf0f0",
    bg_warning="#fff8e6",
    bg_find="#fef7b2",
)
"""The light theme, which is the default."""

DARK: Final = ColorTokens(
    name="dark",
    is_dark=True,
    bg_content="#292929",
    bg_chrome="#1f1f1f",
    bg_sunken="#141414",
    bg_hover="#383838",
    bg_pressed="#404040",
    bg_selected="#1f3f63",
    fg_primary="#ffffff",
    fg_secondary="#d6d6d6",
    fg_muted="#adadad",
    fg_disabled="#5c5c5c",
    stroke_strong="#adadad",
    stroke_default="#666666",
    stroke_subtle="#525252",
    focus="#ffffff",
    accent="#6cb0f5",
    accent_hover="#8cc2f7",
    accent_on="#141414",
    link="#8cc2f7",
    mark_changed="#8cc2f7",
    status_error="#ff8a85",
    status_warning="#f2c661",
    status_success="#7dd87d",
    mark_new="#7dd87d",
    bg_error="#3b1f1f",
    bg_warning="#3a2f12",
    bg_find="#5c4f00",
)
"""The dark theme."""

THEMES: Final = {LIGHT.name: LIGHT, DARK.name: DARK}


def relative_luminance(color: str) -> float:
    """Computes the relative luminance of WCAG 2.

    Args:
        color: A `#rrggbb` string.

    Returns:
        A number from 0 (black) to 1 (white).
    """
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    red, green, blue = (
        value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Computes the contrast of two colors, as WCAG 2 defines it.

    Args:
        foreground: A `#rrggbb` string.
        background: A `#rrggbb` string.

    Returns:
        A ratio from 1 (no contrast) to 21 (black on white).
    """
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


TEXT_CONTRAST: Final = 4.5
"""The least contrast of text, as Fluent's accessibility page asks."""

ICON_CONTRAST: Final = 3.0
"""The least contrast of an icon or of the edge of a control."""


@dataclass(frozen=True)
class ContrastPair:
    """A color on a surface, which has to be read there.

    Attributes:
        foreground: The token of the text, icon, or line.
        background: The token of the surface under it.
        minimum: The least contrast, `TEXT_CONTRAST` or `ICON_CONTRAST`.
    """

    foreground: str
    background: str
    minimum: float

    @property
    def name(self) -> str:
        """Names the pair, such as `fg_primary on bg_content`."""
        return f"{self.foreground} on {self.background}"

    def ratio(self, tokens: ColorTokens) -> float:
        """Measures the pair in a theme."""
        return contrast_ratio(
            tokens.color(self.foreground), tokens.color(self.background)
        )


def _text(foreground: str, *backgrounds: str) -> list[ContrastPair]:
    return [ContrastPair(foreground, b, TEXT_CONTRAST) for b in backgrounds]


def _icon(foreground: str, *backgrounds: str) -> list[ContrastPair]:
    return [ContrastPair(foreground, b, ICON_CONTRAST) for b in backgrounds]


_SURFACES: Final = (
    "bg_content",
    "bg_chrome",
    "bg_sunken",
    "bg_hover",
    "bg_pressed",
    "bg_selected",
)

CONTRAST_PAIRS: Final = (
    # Names and values, on every surface and on the strips and the match.
    *_text("fg_primary", *_SURFACES, "bg_error", "bg_warning", "bg_find"),
    # Labels, which also color the icons of actions.
    *_text("fg_secondary", *_SURFACES),
    # The Type column and `(not set)`, which are text.
    *_text("fg_muted", *_SURFACES),
    # Links and changed rows.
    *_text("link", *_SURFACES[:2], "bg_hover", "bg_selected"),
    *_text("mark_changed", *_SURFACES[:2], "bg_hover", "bg_selected"),
    # States that are text. Hint text is `status_warning`.
    *_text("status_error", "bg_content", "bg_chrome", "bg_error"),
    *_text("status_error", "bg_selected"),
    *_text("status_warning", "bg_content", "bg_chrome", "bg_warning"),
    *_text("status_warning", "bg_selected"),
    *_text("status_success", "bg_content", "bg_chrome", "bg_selected"),
    *_text("mark_new", "bg_content", "bg_chrome", "bg_selected"),
    # Text on the primary button and its hover.
    *_text("accent_on", "accent", "accent_hover"),
    # Icons and the edges of controls.
    *_icon("fg_secondary", *_SURFACES),
    *_icon("accent", "bg_content", "bg_chrome", "bg_sunken", "bg_selected"),
    *_icon("accent_hover", "bg_content"),
    *_icon("stroke_strong", "bg_content", "bg_chrome"),
    *_icon("focus", "bg_content", "bg_chrome", "bg_selected"),
)
"""Every color that carries text, an icon, or the edge of an input, on every
surface that it is drawn on. `fg_disabled` and the decorative strokes are
exempt, and are never the only edge of a control."""


SPACING: Final = (0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 32)
"""The ramp of spacing in pixels. Fluent's, on a base of 4."""

RADIUS_BADGE: Final = 2
RADIUS_CONTROL: Final = 4
RADIUS_OVERLAY: Final = 8
"""Radii in pixels. Rows and panels have none."""

CONTROL_HEIGHT: Final = 28
"""The height of a control in a toolbar or a form, in pixels."""

ICON_SIZE: Final = 16
"""The size of an icon in a toolbar or a tree, in pixels."""

INDENT: Final = 16
"""The indent of one level of a tree, in pixels."""

STROKE: Final = 1
FOCUS_STROKE: Final = 2
"""The width of an outline, and of the focus ring, the active tab, and the
selection bar, in pixels."""


class Density(StrEnum):
    """How tightly the rows of trees and tables sit."""

    COMFORTABLE = "comfortable"
    COMPACT = "compact"
    DENSE = "dense"


DEFAULT_DENSITY: Final = Density.COMPACT

ROW_HEIGHTS: Final = {
    Density.COMFORTABLE: 28,
    Density.COMPACT: 24,
    Density.DENSE: 20,
}
"""The height of a row of a tree or a table in pixels, for each density."""


@dataclass(frozen=True)
class TypeStyle:
    """A named role of text.

    Attributes:
        size: The font size in pixels.
        line: The line height in pixels, on the base of 4.
        weight: 400 for Regular and 600 for SemiBold.
    """

    size: int
    line: int
    weight: int


FONT_FAMILY: Final = "Inter"
"""The family of the bundled font that all text is set in (see ADR 0027)."""


TYPE_RAMP: Final = {
    "caption": TypeStyle(12, 16, 400),
    "body": TypeStyle(13, 18, 400),
    "body_strong": TypeStyle(13, 18, 600),
    "subtitle": TypeStyle(14, 20, 600),
    "title": TypeStyle(16, 22, 600),
    "display": TypeStyle(20, 26, 600),
}
"""The roles of text. The style sheet does not apply them: a font in a style
sheet would take precedence over the zoom of the trees. The code that sets a
font reads them here."""
