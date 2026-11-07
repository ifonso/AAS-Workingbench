"""Icons that take their color from the theme, drawn sharp at any size.

An icon is one SVG file that draws in `currentColor`, as the Tabler icons do.
The engine of `QIcon` replaces `currentColor` with a color token when it
draws, and draws at the size that Qt asks for times the device pixel ratio.
So a switch of theme needs only a repaint, and a high resolution screen gets
sharp lines (ADR 0027).

To add an icon of the editor, such as a kind of AAS element, put an SVG file
that draws in `currentColor` in a folder, and call `svg_icon` with its path
and a role. An icon of the Tabler set is made with `tabler_icon`.
"""

from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import cast

from PyQt6.QtCore import QByteArray
from PyQt6.QtCore import QRect
from PyQt6.QtCore import QRectF
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QIconEngine
from PyQt6.QtGui import QPainter
from PyQt6.QtGui import QPixmap
from PyQt6.QtGui import QPixmapCache
from PyQt6.QtSvg import QSvgRenderer

from aas_workingbench.domain.design_tokens import ColorTokens
from aas_workingbench.ui.theme.manager import current_tokens

TABLER_FOLDER = Path(__file__).parents[2] / "icons" / "tabler"
"""The Tabler icons (MIT) that the editor bundles, as outline SVG files."""

_CURRENT_COLOR = "currentColor"


class IconRole(StrEnum):
    """What an icon says, which sets its color. Values are color tokens.

    Every role has its contrast measured against the surfaces it is drawn on
    in `CONTRAST_PAIRS`, in both themes.
    """

    DEFAULT = "fg_secondary"
    MUTED = "fg_muted"
    ACCENT = "accent"
    ERROR = "status_error"
    WARNING = "status_warning"
    SUCCESS = "status_success"


def icon_color(tokens: ColorTokens, role: IconRole, mode: QIcon.Mode) -> str:
    """Picks the color of an icon in a state.

    Args:
        tokens: The colors of the theme.
        role: What the icon says.
        mode: How Qt draws the icon: Normal, Active (under the pointer),
            Selected (in a selected row), or Disabled.

    Returns:
        A `#rrggbb` string. A disabled icon is `fg_disabled`. The default
        role becomes `fg_primary` under the pointer and in a selected row.
        The other roles keep their color, so an error stays an error.
    """
    if mode == QIcon.Mode.Disabled:
        return tokens.fg_disabled
    if role is IconRole.DEFAULT and mode in (
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        return tokens.fg_primary
    return tokens.color(role.value)


@cache
def _svg_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _draw(path: Path, color: str, size: QSize, ratio: float) -> QPixmap:
    """Draws an icon at a size in device independent pixels, with a ratio.

    Pixmaps are kept in the cache of Qt, which Qt owns and bounds, so the
    icons of a table of rows are drawn once. A Python cache would keep
    pixmaps beyond the `QApplication`, which is unsafe.
    """
    key = f"aas-icon:{path.as_posix()}:{color}:{size.width()}x{size.height()}@{ratio}"
    # The stub says QPixmap, but PyQt6 returns None for a key that is not there.
    cached = cast("QPixmap | None", QPixmapCache.find(key))
    if cached is not None and not cached.isNull():
        return cached
    renderer = QSvgRenderer(
        QByteArray(_svg_text(path).replace(_CURRENT_COLOR, color).encode())
    )
    pixmap = QPixmap(
        max(1, round(size.width() * ratio)),
        max(1, round(size.height() * ratio)),
    )
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(QColor(Qt.GlobalColor.transparent))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size.width(), size.height()))
    painter.end()
    QPixmapCache.insert(key, pixmap)
    return pixmap


class ThemedIconEngine(QIconEngine):
    """Draws one SVG file in a color of the theme in use.

    The theme is read when the icon draws, so one `QIcon` made at import
    follows every switch of theme.
    """

    def __init__(self, path: Path, role: IconRole = IconRole.DEFAULT) -> None:
        """Remembers the file and the role.

        Args:
            path: An SVG file that draws in `currentColor`.
            role: What the icon says.
        """
        super().__init__()
        self._path = path
        self._role = role

    def _color(self, mode: QIcon.Mode) -> str:
        return icon_color(current_tokens(), self._role, mode)

    def paint(
        self,
        painter: QPainter | None,
        rect: QRect,
        mode: QIcon.Mode,
        state: QIcon.State,
    ) -> None:
        """Draws the icon in a rectangle, at the ratio of the device."""
        if painter is None:
            return
        device = painter.device()
        ratio = device.devicePixelRatioF() if device is not None else 1.0
        painter.drawPixmap(
            rect, _draw(self._path, self._color(mode), rect.size(), ratio)
        )

    def pixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State
    ) -> QPixmap:
        """Draws the icon at a size in pixels, with a ratio of 1."""
        return _draw(self._path, self._color(mode), size, 1.0)

    def scaledPixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float
    ) -> QPixmap:
        """Draws the icon for a screen with a device pixel ratio.

        Args:
            size: The size in device independent pixels.
            mode: How Qt draws the icon.
            state: On or Off, which make no difference here.
            scale: The device pixel ratio.

        Returns:
            A pixmap of `size` times `scale`, which has that ratio set.
        """
        return _draw(self._path, self._color(mode), size, scale)

    def actualSize(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State
    ) -> QSize:
        """Gives a square, because the icons are square and scale freely."""
        side = min(size.width(), size.height())
        return QSize(side, side)

    def clone(self) -> "ThemedIconEngine":
        """Makes a copy, as Qt asks when it detaches an icon."""
        return ThemedIconEngine(self._path, self._role)

    def key(self) -> str:
        """Names this kind of engine."""
        return "aas-themed-svg"


def svg_icon(path: Path, role: IconRole = IconRole.DEFAULT) -> QIcon:
    """Makes an icon of an SVG file that draws in `currentColor`.

    Args:
        path: The file.
        role: What the icon says, which sets its color.

    Returns:
        The icon. It can be made before the `QApplication` exists.

    Raises:
        FileNotFoundError: If there is no such file, so a wrong name fails
            when the icon is made, and not as a blank button.
    """
    if not path.is_file():
        raise FileNotFoundError(f"No icon file: '{path}'")
    return QIcon(ThemedIconEngine(path, role))


def tabler_icon(name: str, role: IconRole = IconRole.DEFAULT) -> QIcon:
    """Makes an icon of the Tabler set.

    Args:
        name: The name of the icon, such as `device-floppy`.
        role: What the icon says, which sets its color.

    Returns:
        The icon.

    Raises:
        FileNotFoundError: If the editor does not bundle that icon.
    """
    return svg_icon(TABLER_FOLDER / f"{name}.svg", role)
