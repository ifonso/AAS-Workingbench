"""Which theme a saved name stands for.

The editor has four themes: Follow system, Light, Dark, and Native. A user may
have saved the name of one of the old themes (`grey`, `dark`, `light`, or
`default`, style sheets of the Breeze set that are gone), or one of the ids of
the builds that came before the release (`fluent-light` and so on). Both map
to a theme here, and a name that is unknown becomes the default.

This module has no Qt, so the mapping is tested alone.
"""

from typing import Final

THEME_SYSTEM: Final = "system"
THEME_LIGHT: Final = "light"
THEME_DARK: Final = "dark"
THEME_NATIVE: Final = "native"

THEME_LABELS: Final = {
    THEME_SYSTEM: "Follow system",
    THEME_LIGHT: "Light",
    THEME_DARK: "Dark",
    THEME_NATIVE: "Native",
}
"""The ids of the themes, as saved in the settings, with their labels, in the
order of the theme menu."""

DEFAULT_THEME: Final = THEME_LIGHT
"""The theme of a first run, and of a saved name that is not known."""

_RENAMED: Final = {
    # The old themes. `grey` was dark, and `default` was the sheet of a light
    # window, so the owner decided that it becomes Light.
    "grey": THEME_DARK,
    "dark": THEME_DARK,
    "light": THEME_LIGHT,
    "default": THEME_LIGHT,
    # The ids of the builds before the release.
    "fluent-light": THEME_LIGHT,
    "fluent-dark": THEME_DARK,
    "fluent-system": THEME_SYSTEM,
}


def theme_from_saved(name: str) -> str:
    """Gives the theme that a saved name stands for.

    Args:
        name: The text of the setting `theme`, from this release or an older
            one.

    Returns:
        The id of a theme in `THEME_LABELS`: the same name when it is one,
        the theme that an old name maps to, and `DEFAULT_THEME` otherwise.
    """
    if name in THEME_LABELS:
        return name
    return _RENAMED.get(name, DEFAULT_THEME)
