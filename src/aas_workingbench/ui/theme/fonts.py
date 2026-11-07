"""The bundled font, and the font of the application.

Inter (SIL Open Font License 1.1) is one variable file in `fonts/`. It is
registered with Qt, and the application font is set to it, so that every
widget that does not set a font of its own gets it (see ADR 0027).

The size of the font is the body size of the type ramp, in pixels. The zoom of
the trees is a point size that the models set on the font of their rows, so it
does not depend on this font, and it is not touched here.
"""

import logging
from pathlib import Path

from PyQt6.QtGui import QFont
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtWidgets import QApplication

from aas_workingbench.domain.design_tokens import FONT_FAMILY
from aas_workingbench.domain.design_tokens import TYPE_RAMP

FONTS_FOLDER = Path(__file__).parents[2] / "fonts"
FONT_FILES = ("Inter-Variable.ttf",)
"""The font files of `FONTS_FOLDER`. Each one is licensed in `OFL.txt`."""

_LOGGER = logging.getLogger(__name__)


def install_fonts(folder: Path = FONTS_FOLDER) -> bool:
    """Registers the bundled fonts with Qt.

    Needs a `QApplication`. A file that cannot be loaded is logged, and the
    system font then stands in for it.

    Args:
        folder: Where the font files are.

    Returns:
        Whether every font file was registered.
    """
    done = True
    for name in FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(folder / name))
        if font_id < 0:
            _LOGGER.warning("The font file '%s' did not load", folder / name)
            done = False
        else:
            families = QFontDatabase.applicationFontFamilies(font_id)
            _LOGGER.info("Font %s loaded from '%s'", families, folder / name)
    return done


def application_font() -> QFont:
    """Makes the font of the application.

    Returns:
        The family `FONT_FAMILY` at the body size of the type ramp, in pixels,
        in Regular.
    """
    body = TYPE_RAMP["body"]
    font = QFont(FONT_FAMILY)
    font.setPixelSize(body.size)
    font.setWeight(QFont.Weight(body.weight))
    return font


def apply_application_font(app: QApplication) -> bool:
    """Registers the bundled fonts and sets the application font.

    Call it before any module that reads `QFont()` at import is imported.
    Setting the font of the application also drops the fonts that the
    platform gave to menus and tooltips, so those follow it too.

    Args:
        app: The application.

    Returns:
        Whether the bundled fonts were registered.
    """
    done = install_fonts()
    app.setFont(application_font())
    return done
