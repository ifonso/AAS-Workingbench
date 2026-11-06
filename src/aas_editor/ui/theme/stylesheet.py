"""Fills the template of the style sheet with design tokens."""

from pathlib import Path
from string import Template

from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import DEFAULT_DENSITY
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import FOCUS_STROKE
from aas_editor.domain.design_tokens import RADIUS_BADGE
from aas_editor.domain.design_tokens import RADIUS_CONTROL
from aas_editor.domain.design_tokens import ROW_HEIGHTS
from aas_editor.ui.theme.assets import write_images

TEMPLATE_PATH = Path(__file__).with_name("app.qss.template")

# The height of one line of text in a menu, which a row grows from.
_MENU_TEXT_HEIGHT = 18


def template_values(
    tokens: ColorTokens,
    image_dir: Path,
    density: Density = DEFAULT_DENSITY,
) -> dict[str, str]:
    """Gathers the names that the template may use, with their values.

    Args:
        tokens: The colors of the theme.
        image_dir: The folder of the images that the sheet points at.
        density: How tightly rows sit. It sets the padding of menu items.

    Returns:
        Each color token by name, and `radius_control`, `radius_badge`,
        `focus_stroke`, `menu_pad`, `image_dir`, and `scroll_handle`. The
        scroll handle is `fg_disabled`, which is quiet and seen on every
        surface.
    """
    values = {name: tokens.color(name) for name in tokens.color_names()}
    values["radius_control"] = str(RADIUS_CONTROL)
    values["radius_badge"] = str(RADIUS_BADGE)
    values["focus_stroke"] = str(FOCUS_STROKE)
    values["menu_pad"] = str((ROW_HEIGHTS[density] - _MENU_TEXT_HEIGHT) // 2)
    values["scroll_handle"] = tokens.fg_disabled
    values["image_dir"] = image_dir.as_posix()
    return values


def build_stylesheet(
    tokens: ColorTokens,
    density: Density = DEFAULT_DENSITY,
    image_dir: Path | None = None,
) -> str:
    """Makes the style sheet of the application.

    Args:
        tokens: The colors of the theme.
        density: How tightly rows sit.
        image_dir: Where the images of the sheet are. None writes them to
            the cache folder of the user.

    Returns:
        The text for `QApplication.setStyleSheet`.

    Raises:
        KeyError: If the template uses a name that has no value.
    """
    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
    folder = write_images(tokens) if image_dir is None else image_dir
    return template.substitute(template_values(tokens, folder, density))
