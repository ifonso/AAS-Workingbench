"""What a row of a tree is made of besides its text: height and signs.

Qt ignores the height of a row in a style sheet (ADR 0025), so the delegate of
the trees gives it, from the density of the theme and the font of the row. The
signs are what a row says without words, and color is never alone: a selected
row has a bar at its left edge, and a row that was changed or added since the
save has a dot at the right edge of its name, beside the color of the name.
"""

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QPointF
from PyQt6.QtCore import QRect
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QStyle
from PyQt6.QtWidgets import QStyleOptionViewItem

from aas_workingbench.domain.design_tokens import fitting_row_height
from aas_workingbench.domain.design_tokens import FOCUS_STROKE
from aas_workingbench.settings.app_settings import ATTRIBUTE_COLUMN
from aas_workingbench.settings.app_settings import CHANGE_MARK_ROLE
from aas_workingbench.settings.app_settings import MARK_CHANGED
from aas_workingbench.settings.app_settings import MARK_NEW
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.theme import theme_manager

MARK_DOT_DIAMETER = 6
"""The width of the dot of a changed or added row, in pixels."""

MARK_DOT_MARGIN = 6
"""The room between the dot and the right edge of the cell, in pixels."""

COUNT_MARGIN = 8
"""The room between the count of a closed row and the right edge of the cell,
or the dot of a mark, in pixels."""

COUNT_GAP = 12
"""The least room between the name of a row and its count, in pixels. A name
that would come closer hides the count, so the two never touch."""


def row_size_hint(font: QFont) -> QSize:
    """Gives the size that a row asks for.

    Args:
        font: The font of the row.

    Returns:
        The height of the density of the theme, or more for a font that is
        zoomed. The width is -1, so the column width of the header decides, as
        it did when the model gave the size.
    """
    height = fitting_row_height(
        theme_manager().density, QFontMetrics(font).height()
    )
    return QSize(-1, height)


def paint_row_signs(
    painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
) -> None:
    """Paints the bar of a selected row and the dot of a changed one.

    Args:
        painter: The painter of the view.
        option: What the delegate was asked to paint.
        index: The cell. The bar is drawn with the first column, and the dot
            with the name.
    """
    state = option.state
    if index.column() != ATTRIBUTE_COLUMN:
        return
    tokens = current_tokens()
    rect: QRect = option.rect
    painter.save()
    try:
        painter.setPen(Qt.PenStyle.NoPen)
        if state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(tokens.link))
            painter.drawRect(0, rect.top(), FOCUS_STROKE, rect.height())
        mark = index.data(CHANGE_MARK_ROLE)
        if mark in (MARK_NEW, MARK_CHANGED):
            color = tokens.mark_new if mark == MARK_NEW else tokens.mark_changed
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor(color))
            center = QPointF(
                rect.right() - MARK_DOT_MARGIN - MARK_DOT_DIAMETER / 2,
                rect.center().y() + 0.5,
            )
            radius = MARK_DOT_DIAMETER / 2
            painter.drawEllipse(center, radius, radius)
    finally:
        painter.restore()


def child_count_text(view: object, index: QModelIndex) -> str:
    """Gives the count that a closed row of a tree shows, such as `18`.

    A closed row hides what is below it, so its count says how much is there
    without opening it (proposal 2.3). An open row shows its rows, and a row
    without rows has nothing to count.

    Args:
        view: The tree that draws the row. Only a view whose
            `showsChildCounts` is true shows counts.
        index: The cell. Only the name column has a count.

    Returns:
        The count as text, or an empty string for no count.
    """
    if index.column() != ATTRIBUTE_COLUMN or not getattr(
        view, "showsChildCounts", False
    ):
        return ""
    model = index.model()
    if model is None or not model.hasChildren(index):
        return ""
    is_expanded = getattr(view, "isExpanded", None)
    if is_expanded is None or is_expanded(index):
        return ""
    count = model.rowCount(index)
    return str(count) if count else ""


def paint_child_count(
    painter: QPainter,
    option: QStyleOptionViewItem,
    index: QModelIndex,
    text: str,
    name_end: int,
) -> None:
    """Paints the count of a closed row at the right edge of its name cell.

    Args:
        painter: The painter of the view.
        option: What the delegate was asked to paint.
        index: The cell, which tells whether a dot of a mark is there too.
        text: What `child_count_text` gave.
        name_end: Where the text of the name ends, in the coordinates of the
            view. The count is left out when it would touch the name.
    """
    if not text:
        return
    metrics = QFontMetrics(option.font)
    rect: QRect = option.rect
    right = rect.right() - COUNT_MARGIN
    if index.data(CHANGE_MARK_ROLE) in (MARK_NEW, MARK_CHANGED):
        right -= MARK_DOT_MARGIN + MARK_DOT_DIAMETER
    left = right - metrics.horizontalAdvance(text)
    if left - COUNT_GAP < name_end:
        return
    painter.save()
    try:
        painter.setFont(option.font)
        painter.setPen(QColor(current_tokens().fg_muted))
        painter.drawText(
            QRect(left, rect.top(), right - left + 1, rect.height()),
            int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
            text,
        )
    finally:
        painter.restore()
