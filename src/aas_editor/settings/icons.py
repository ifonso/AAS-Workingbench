#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap, QFont

from aas_editor.settings.colors import LIGHT_BLUE
from aas_editor.ui.theme.icons import tabler_icon


def getCharsIcon(
    chars: str,
    font_size: int = 24,
    color: QColor = LIGHT_BLUE,
    background_color: QColor = QColor("transparent"),
):
    """
    Generate a QIcon from a string of characters.

    Args:
        chars (str): The characters to render as an icon (max 4 characters).
        font_size (int): The font size for the characters.
        color (QColor): The color of the characters.
        background_color (QColor): The background color of the icon.

    Returns:
        QIcon: An icon created from the characters.
    """
    if len(chars) > 4:
        raise ValueError("Max 4 characters allowed for an icon")

    # Create a pixmap to render the characters
    size = font_size * 2  # Adjust size based on font size
    pixmap = QPixmap(size, size)
    pixmap.fill(background_color)  # Set background color

    # Set up the painter
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    # Set font
    font = QFont("Monospace")
    font.setPointSize(font_size)
    font.setBold(True)
    painter.setFont(font)

    # Set pen color
    painter.setPen(color)

    # Draw each character individually with tight spacing
    char_width = font_size * 0.6  # Adjusted for a compact font
    x_offset = 0  # Start drawing from the left padding
    y_offset = (size - font_size) / 2  # Center vertically
    char_spacing: int = 2
    for char in chars:
        # Draw the character at the current position
        painter.drawText(int(x_offset), int(y_offset + font_size), char)
        # Move the x_offset for the next character
        x_offset += char_width + char_spacing
    painter.end()

    # Convert the pixmap to a QIcon
    return QIcon(pixmap)


# The action icons are Tabler icons (MIT) that draw in a color of the theme in
# use, and so follow a switch of theme and a high resolution screen. They are
# made at import, which needs no QApplication. A new icon of an action is one
# more line here, with a file of `icons/tabler`.
EXIT_ICON = tabler_icon("logout")
NEW_PACK_ICON = tabler_icon("folder-plus")
OPEN_ICON = tabler_icon("folder-open")
OPEN_DRAG_ICON = tabler_icon("external-link")
SAVE_ICON = tabler_icon("device-floppy")
SAVE_ALL_ICON = tabler_icon("stack-2")
SETTINGS_ICON = tabler_icon("settings")
COPY_ICON = tabler_icon("copy")
PASTE_ICON = tabler_icon("clipboard")
CUT_ICON = tabler_icon("cut")
ADD_ICON = tabler_icon("plus")
DEL_ICON = tabler_icon("trash")
UPDATE_ICON = tabler_icon("refresh")
EDIT_ICON = tabler_icon("pencil")
EDIT_JSON_ICON = tabler_icon("json")
UNDO_ICON = tabler_icon("arrow-back-up")
REDO_ICON = tabler_icon("arrow-forward-up")
FORWARD_ICON = tabler_icon("arrow-right")
BACK_ICON = tabler_icon("arrow-left")
SPLIT_VERT_ICON = tabler_icon("layout-columns")
SPLIT_HORIZ_ICON = tabler_icon("layout-rows")
ZOOM_IN_ICON = tabler_icon("zoom-in")
ZOOM_OUT_ICON = tabler_icon("zoom-out")
NEXT_ICON = tabler_icon("arrow-down")
PREV_ICON = tabler_icon("arrow-up")
FILTER_ICON = tabler_icon("filter")
REGEX_ICON = tabler_icon("regex")
CASE_ICON = tabler_icon("letter-case")
CLOSE_ICON = tabler_icon("x")
EXPAND_ALL_ICON = tabler_icon("arrows-vertical")
COLLAPSE_ALL_ICON = tabler_icon("fold")
AUTOSCROLL_TO_SRC_ICON = tabler_icon("focus-2")
AUTOSCROLL_FROM_SRC_ICON = tabler_icon("current-location")
FILE_ICON = tabler_icon("file")
MIME_PDF_ICON = tabler_icon("file-type-pdf")
MIME_IMAGE_ICON = tabler_icon("photo")
MIME_TEXT_ICON = tabler_icon("file-text")
INFO_ICON = tabler_icon("info-circle")

MIME_TYPE_ICON_DICT = {
    "application/pdf": MIME_PDF_ICON,
    "image": MIME_IMAGE_ICON,
    "text": MIME_TEXT_ICON,
}
