"""What the detail draws beside a value: badges, a link, and a second line.

A value is read in the color of text, and what comes from elsewhere is drawn
beside it smaller and quieter, so that the two are not taken for one
(proposals 3.4, 3.5 and 3.7):

* a badge with the languages of a text, such as `en +2`,
* a badge with the unit that the concept description gives a value, such as
  `unit s`, followed by a link to that concept,
* under the name of a concept, the id that the semanticId holds.

The functions draw in the coordinates of the view and return where they end,
so that a delegate can put one after the other.
"""

from PyQt6.QtCore import QRect
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPainter

from aas_workingbench.domain.design_tokens import RADIUS_BADGE
from aas_workingbench.ui.empty_state import role_font
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.theme.icons import IconRole
from aas_workingbench.ui.theme.icons import tabler_icon

MARK_GAP = 8
"""The room between a value and what is drawn beside it, in pixels."""

BADGE_PADDING = 4
"""The room inside a badge, left and right of its text, in pixels."""

BADGE_ICON = 12
"""The size of the icon of a badge or a link, in pixels."""

SUBTEXT_GAP = 2
"""The room between a value and its second line, in pixels."""


def caption_font() -> QFont:
    """The font of what is drawn beside a value: the caption of the ramp."""
    return role_font("caption")


def subtext_height() -> int:
    """The height that the second line of a row adds to it, in pixels."""
    return QFontMetrics(caption_font()).height() + SUBTEXT_GAP


def badge_width(text: str, icon: str | None = None) -> int:
    """Gives the width of a badge, to tell whether it fits."""
    width = QFontMetrics(caption_font()).horizontalAdvance(text)
    if icon is not None:
        width += BADGE_ICON + BADGE_PADDING
    return width + 2 * BADGE_PADDING


def paint_badge(
    painter: QPainter,
    line: QRect,
    x: int,
    text: str,
    icon: str | None = None,
) -> int:
    """Draws a quiet badge, such as `unit s` or the languages `en +2`.

    Args:
        painter: The painter of the view.
        line: The line of the value: the badge is centered in its height.
        x: Where the badge starts.
        text: What it says.
        icon: The name of a Tabler icon drawn before the text, or None.

    Returns:
        Where the badge ends.
    """
    tokens = current_tokens()
    font = caption_font()
    metrics = QFontMetrics(font)
    width = badge_width(text, icon)
    height = metrics.height() + 2
    top = line.center().y() - height // 2 + 1
    box = QRect(x, top, width, height)
    painter.save()
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(tokens.stroke_default))
        painter.setBrush(QColor(tokens.bg_content))
        painter.drawRoundedRect(box, RADIUS_BADGE, RADIUS_BADGE)
        text_x = x + BADGE_PADDING
        if icon is not None:
            tabler_icon(icon).paint(
                painter,
                QRect(
                    text_x,
                    box.center().y() - BADGE_ICON // 2 + 1,
                    BADGE_ICON,
                    BADGE_ICON,
                ),
            )
            text_x += BADGE_ICON + BADGE_PADDING
        painter.setFont(font)
        painter.setPen(QColor(tokens.fg_secondary))
        painter.drawText(
            QRect(text_x, box.top(), box.right() - text_x, box.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )
    finally:
        painter.restore()
    return box.right()


def paint_link(painter: QPainter, line: QRect, x: int, text: str) -> QRect:
    """Draws a link with its icon, such as `from concept CycleTimeTarget`.

    Args:
        painter: The painter of the view.
        line: The line of the value.
        x: Where the link starts.
        text: What it says.

    Returns:
        The room of the link, which a click on opens it.
    """
    tokens = current_tokens()
    font = caption_font()
    width = QFontMetrics(font).horizontalAdvance(text)
    icon_rect = QRect(
        x, line.center().y() - BADGE_ICON // 2 + 1, BADGE_ICON, BADGE_ICON
    )
    text_rect = QRect(
        x + BADGE_ICON + BADGE_PADDING, line.top(), width + 1, line.height()
    )
    painter.save()
    try:
        tabler_icon("link", IconRole.ACCENT).paint(painter, icon_rect)
        painter.setFont(font)
        painter.setPen(QColor(tokens.link))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            text,
        )
    finally:
        painter.restore()
    return QRect(x, line.top(), text_rect.right() - x + 1, line.height())


def paint_subtext(painter: QPainter, cell: QRect, x: int, text: str) -> None:
    """Draws the second line of a row, such as the id of a semanticId.

    Args:
        painter: The painter of the view.
        cell: The whole cell, whose bottom the line takes.
        x: Where the line starts, under the value.
        text: What it says. It is cut at the edge of the cell.
    """
    font = caption_font()
    metrics = QFontMetrics(font)
    room = cell.right() - x
    shown = metrics.elidedText(text, Qt.TextElideMode.ElideRight, room)
    height = metrics.height()
    painter.save()
    try:
        painter.setFont(font)
        painter.setPen(QColor(current_tokens().fg_muted))
        painter.drawText(
            QRect(x, cell.bottom() - height - SUBTEXT_GAP, room, height),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            shown,
        )
    finally:
        painter.restore()
