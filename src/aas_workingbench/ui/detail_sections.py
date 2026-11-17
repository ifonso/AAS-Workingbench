"""The sections of the detail of an object, as bands over the rows of a tab.

The rows of a tab are the attributes of the object, one level of a model that
the editor finds and edits by name. The sections (proposals 3.2 and 3.3) do not
change that model: the rows come in the order of their sections
(`domain.attribute_sections`), and the view draws a band above the first row of
each section, with a chevron, the title and the count. A click on a band opens
or closes its section. The rows of a closed section are hidden, and its first
row keeps only the band, so the section is still there to be opened.

This module has what the view needs to do that without knowing the sections:
`SectionBands` reads them from the rows, and `paint_band` draws one.
"""

from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field

from PyQt6.QtCore import QAbstractItemModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QRect
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QPainter

from aas_workingbench.domain.attribute_sections import Section
from aas_workingbench.domain.attribute_sections import header_text
from aas_workingbench.domain.attribute_sections import starts_open
from aas_workingbench.domain.design_tokens import ICON_SIZE
from aas_workingbench.settings.app_settings import HOLDS_NOTHING_ROLE
from aas_workingbench.settings.app_settings import SECTION_ROLE
from aas_workingbench.ui.empty_state import role_font
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.theme.icons import tabler_icon

BAND_PADDING = 8
"""The room above the line of a band, in pixels, which separates sections."""

BAND_LEFT = 8
"""The room left of the chevron of a band, in pixels."""

BAND_GAP = 6
"""The room between the parts of a band, in pixels."""


@dataclass
class Band:
    """One section as the rows of a tab hold it.

    Attributes:
        section: The section.
        first_row: The row of the model whose band it is.
        rows: The rows of the section, in order.
        names: What the first column of each row reads.
    """

    section: Section
    first_row: int
    rows: list[int] = field(default_factory=lambda: list[int]())
    names: list[str] = field(default_factory=lambda: list[str]())


class SectionBands:
    """The sections of the rows of a tab, and which of them are open.

    The open and closed state is kept by section, so a tab that shows the next
    object keeps the empty attributes closed, or open, as the user left them.
    """

    def __init__(self) -> None:
        self._open: dict[Section, bool] = {}
        self._bands: list[Band] = []
        self._by_row: dict[int, Band] = {}
        self._section_of_row: dict[int, Section] = {}
        self._has_content: dict[Section, bool] = {}

    @property
    def bands(self) -> list[Band]:
        """The sections that the rows have, in order. Empty for no sections."""
        return list(self._bands)

    def read(self, model: QAbstractItemModel | None) -> None:
        """Reads the sections of the top rows of a model.

        A model whose rows are not all attributes with a section, such as the
        entries of a list, has no sections, and is shown as before.

        Args:
            model: The model of the view, or None.
        """
        self._bands = []
        self._by_row = {}
        self._section_of_row = {}
        self._has_content = {}
        if model is None:
            return
        root = QModelIndex()
        sections: list[tuple[int, Section, str]] = []
        for row in range(model.rowCount(root)):
            index = model.index(row, 0, root)
            section = index.data(SECTION_ROLE)
            if not isinstance(section, Section):
                return
            name = index.data(Qt.ItemDataRole.DisplayRole)
            sections.append((row, section, str(name or "")))
            if index.data(HOLDS_NOTHING_ROLE) is False:
                self._has_content[section] = True
        for row, section, name in sections:
            if not self._bands or self._bands[-1].section is not section:
                self._bands.append(Band(section, row))
            band = self._bands[-1]
            band.rows.append(row)
            band.names.append(name)
            self._section_of_row[row] = section
        self._by_row = {band.first_row: band for band in self._bands}

    def is_open(self, section: Section) -> bool:
        """Tells whether a section shows its rows.

        A section that the user opened or closed stays so. Otherwise it is
        open or closed as `starts_open` says for what it holds.
        """
        if section in self._open:
            return self._open[section]
        return starts_open(
            section, has_content=self._has_content.get(section, False)
        )

    def toggle(self, section: Section) -> None:
        """Opens a closed section, or closes an open one."""
        self._open[section] = not self.is_open(section)

    def band_at(self, index: QModelIndex) -> Band | None:
        """Gives the band that is drawn above a row, if any.

        Args:
            index: A cell of the view. Only a top row has a band.
        """
        if not index.isValid() or index.parent().isValid():
            return None
        return self._by_row.get(index.row())

    def is_hidden(self, row: int) -> bool:
        """Tells whether a top row is hidden because its section is closed.

        The first row of a closed section is not hidden: it holds the band.
        """
        section = self._section_of_row.get(row)
        if section is None or self.is_open(section):
            return False
        return row not in self._by_row

    def shows_only_band(self, index: QModelIndex) -> bool:
        """Tells whether a row is the first of a closed section."""
        band = self.band_at(index)
        return band is not None and not self.is_open(band.section)


def band_height(row_height: int) -> int:
    """Gives the height of a band, from the height of a row."""
    return row_height + BAND_PADDING


def band_font() -> QFont:
    """The font of the title of a band: the strong body of the type ramp."""
    return role_font("body_strong")


def paint_band(
    painter: QPainter,
    rect: QRect,
    band: Band,
    *,
    is_open: bool,
    draw_line: bool,
    font: QFont,
) -> None:
    """Draws the band of a section: a line, the chevron, the title, the count.

    A closed section that starts closed, such as the empty attributes, also
    names its attributes after the count, so the reader knows what is inside.

    Args:
        painter: The painter of the view.
        rect: The room of the band, the whole width of the view.
        band: The section and its rows.
        is_open: Whether the section shows its rows.
        draw_line: Whether a line separates the band from the section above.
        font: The font of the rows, which the count and the names take.
    """
    tokens = current_tokens()
    title, count, names = header_text(band.section, band.names, is_open=is_open)
    painter.save()
    try:
        if draw_line:
            painter.setPen(QColor(tokens.stroke_subtle))
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
        text_rect = QRect(
            rect.left(),
            rect.top() + BAND_PADDING,
            rect.width(),
            rect.height() - BAND_PADDING,
        )
        chevron = tabler_icon("chevron-down" if is_open else "chevron-right")
        icon_top = text_rect.center().y() - ICON_SIZE // 2 + 1
        chevron.paint(
            painter,
            QRect(rect.left() + BAND_LEFT, icon_top, ICON_SIZE, ICON_SIZE),
        )
        x = rect.left() + BAND_LEFT + ICON_SIZE + BAND_GAP
        strong = band_font()
        x = _draw_text(painter, strong, tokens.fg_primary, text_rect, x, title)
        x = _draw_text(
            painter, font, tokens.fg_muted, text_rect, x + BAND_GAP, count
        )
        if names:
            room = text_rect.right() - x - BAND_GAP
            elided = QFontMetrics(font).elidedText(
                f"·  {names}", Qt.TextElideMode.ElideRight, room
            )
            _draw_text(
                painter, font, tokens.fg_muted, text_rect, x + BAND_GAP, elided
            )
    finally:
        painter.restore()


def _draw_text(
    painter: QPainter,
    font: QFont,
    color: str,
    rect: QRect,
    x: int,
    text: str,
) -> int:
    """Draws text from x, centered in the height of rect, and says where it ends."""
    if not text:
        return x
    painter.setFont(font)
    painter.setPen(QColor(color))
    width = QFontMetrics(font).horizontalAdvance(text)
    painter.drawText(
        QRect(x, rect.top(), width + 1, rect.height()),
        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
        text,
    )
    return x + width


def band_size(
    base: QSize, index: QModelIndex, bands: SectionBands, row_height: int
) -> QSize:
    """Gives the size of a row with the band above it, if it has one.

    Args:
        base: The size of the row alone.
        index: The cell.
        bands: The sections of the view.
        row_height: The height of a row of the density in use.

    Returns:
        The row alone, the band and the row, or the band alone for the first
        row of a closed section.
    """
    band = bands.band_at(index)
    if band is None:
        return base
    height = band_height(row_height)
    if bands.shows_only_band(index):
        return QSize(base.width(), height)
    return QSize(base.width(), base.height() + height)


Toggle = Callable[[Section], None]
"""What the view does when a band is clicked."""
