"""Makes the square PNG icon of the AppImage from the logo of the project.

The logo is 500 by 504 pixels. Desktops expect a square icon, so the logo is
scaled to fit and centered on a transparent square. It needs PyQt6 only, which
the project installs, and no display: images are drawn with `QImage`.

Usage:
    uv run python packaging/linux/make_icon.py LOGO.png OUTPUT.png [SIZE]
"""

import sys

from PyQt6.QtCore import QPoint
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QImage
from PyQt6.QtGui import QPainter

DEFAULT_SIZE = 512


def make_icon(logo_path: str, output_path: str, size: int) -> None:
    """Writes the logo, centered on a transparent square.

    Args:
        logo_path: The PNG of the logo.
        output_path: Where to write the icon.
        size: The side of the icon in pixels.

    Raises:
        SystemExit: The logo cannot be read or the icon cannot be written.
    """
    logo = QImage(logo_path)
    if logo.isNull():
        raise SystemExit(f"Cannot read the logo: {logo_path}")
    scaled = logo.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    icon = QImage(size, size, QImage.Format.Format_ARGB32)
    icon.fill(QColor(0, 0, 0, 0))
    painter = QPainter(icon)
    painter.drawImage(
        QPoint((size - scaled.width()) // 2, (size - scaled.height()) // 2),
        scaled,
    )
    painter.end()
    if not icon.save(output_path, "PNG"):
        raise SystemExit(f"Cannot write the icon: {output_path}")


def main(argv: list[str]) -> None:
    """Reads the command line and makes the icon."""
    if len(argv) not in (3, 4):
        raise SystemExit(__doc__)
    size = int(argv[3]) if len(argv) == 4 else DEFAULT_SIZE
    make_icon(argv[1], argv[2], size)


if __name__ == "__main__":
    main(sys.argv)
