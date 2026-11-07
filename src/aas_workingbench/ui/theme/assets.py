"""Writes the small images that a style sheet needs, colored by tokens.

A style sheet can draw boxes and borders, but a tick, a dot, and an arrow need
image files. They are drawn here from the tokens of the theme and written to
the cache folder of the user, one folder for each theme, and the style sheet
points at them.
"""

from pathlib import Path

from PyQt6.QtCore import QStandardPaths

from aas_workingbench.domain.design_tokens import ColorTokens

_HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" '
    'viewBox="0 0 16 16">'
)


def _stroke(path: str, color: str, width: float = 1.6) -> str:
    return (
        f'{_HEAD}<path d="{path}" fill="none" stroke="{color}" '
        f'stroke-width="{width}" stroke-linecap="round" '
        'stroke-linejoin="round"/></svg>'
    )


def images(tokens: ColorTokens) -> dict[str, str]:
    """Draws the images of a theme.

    Args:
        tokens: The colors of the theme.

    Returns:
        The SVG text of each image, by file name. A tick, a dash, and a dot
        are in the color of text on the accent. The arrows are in the color of
        labels, and the cross of a tab is muted until the pointer is on it.
    """
    return {
        "check.svg": _stroke("M3.5 8.5l3 3 6-6.5", tokens.accent_on, 1.8),
        "dash.svg": _stroke("M4 8h8", tokens.accent_on, 1.8),
        "radio-dot.svg": (
            f'{_HEAD}<circle cx="8" cy="8" r="3" '
            f'fill="{tokens.accent_on}"/></svg>'
        ),
        "chevron-down.svg": _stroke("M4 6l4 4 4-4", tokens.fg_secondary),
        "chevron-right.svg": _stroke("M6 4l4 4-4 4", tokens.fg_secondary),
        "close.svg": _stroke("M4.5 4.5l7 7M11.5 4.5l-7 7", tokens.fg_muted),
        "close-hover.svg": _stroke(
            "M4.5 4.5l7 7M11.5 4.5l-7 7", tokens.fg_primary
        ),
        "chevron-up.svg": _stroke("M4 10l4-4 4 4", tokens.fg_secondary),
        "chevron-down-disabled.svg": _stroke(
            "M4 6l4 4 4-4", tokens.fg_disabled
        ),
        "chevron-up-disabled.svg": _stroke("M4 10l4-4 4 4", tokens.fg_disabled),
    }


def write_images(tokens: ColorTokens) -> Path:
    """Writes the images of a theme, and tells where they are.

    Args:
        tokens: The colors of the theme.

    Returns:
        The folder that holds them. A file is written only when its text
        differs from the one on disk.
    """
    cache = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.CacheLocation
    )
    folder = Path(cache) / "aas_workingbench" / "theme" / tokens.name
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in images(tokens).items():
        target = folder / name
        # A second instance may hold the file open, and the text is the same.
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
    return folder
