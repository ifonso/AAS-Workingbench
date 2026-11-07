"""Makes the Qt palette from design tokens.

Widgets that no style sheet rule reaches, and the parts that Fusion draws
itself, read the palette. It has to agree with the style sheet.
"""

from PyQt6.QtGui import QColor
from PyQt6.QtGui import QPalette

from aas_editor.domain.design_tokens import ColorTokens


def build_palette(tokens: ColorTokens) -> QPalette:
    """Makes the palette of a theme.

    Args:
        tokens: The colors of the theme.

    Returns:
        A palette whose Active, Inactive, and Disabled groups follow the
        tokens. A selection keeps its color when the window loses focus,
        because the tree is read while another window is in front.
    """
    palette = QPalette()
    roles = {
        QPalette.ColorRole.Window: tokens.bg_chrome,
        QPalette.ColorRole.WindowText: tokens.fg_primary,
        QPalette.ColorRole.Base: tokens.bg_content,
        QPalette.ColorRole.AlternateBase: tokens.bg_chrome,
        QPalette.ColorRole.Text: tokens.fg_primary,
        QPalette.ColorRole.Button: tokens.bg_content,
        QPalette.ColorRole.ButtonText: tokens.fg_primary,
        QPalette.ColorRole.BrightText: tokens.fg_primary,
        QPalette.ColorRole.Highlight: tokens.bg_selected,
        QPalette.ColorRole.HighlightedText: tokens.fg_primary,
        QPalette.ColorRole.ToolTipBase: tokens.bg_content,
        QPalette.ColorRole.ToolTipText: tokens.fg_primary,
        QPalette.ColorRole.PlaceholderText: tokens.fg_muted,
        QPalette.ColorRole.Link: tokens.link,
        QPalette.ColorRole.LinkVisited: tokens.link,
        QPalette.ColorRole.Accent: tokens.accent,
        # The bevels of Fusion, which draws lines from these.
        QPalette.ColorRole.Light: tokens.bg_content,
        QPalette.ColorRole.Midlight: tokens.bg_hover,
        QPalette.ColorRole.Mid: tokens.stroke_default,
        QPalette.ColorRole.Dark: tokens.stroke_strong,
        QPalette.ColorRole.Shadow: tokens.stroke_strong,
    }
    for role, value in roles.items():
        palette.setColor(role, QColor(value))
    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(
            QPalette.ColorGroup.Disabled, role, QColor(tokens.fg_disabled)
        )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.HighlightedText,
        QColor(tokens.fg_muted),
    )
    return palette
