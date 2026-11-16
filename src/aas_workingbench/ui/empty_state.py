"""The start of the window while no package is open.

The tree used to show a drop target in a web view, and the tab beside it an
empty table with a Welcome title. The start is one centered column in the place
of the tree: what the editor is for, the two ways to start (New and Open), the
recent files, and a hint that files can be dropped. The right side of the window
is blank until a package is open.

The widget knows no tree. The window gives it the actions that it shows and the
function that opens a dropped file.
"""

from collections.abc import Callable
from collections.abc import Sequence

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QDragEnterEvent
from PyQt6.QtGui import QDragMoveEvent
from PyQt6.QtGui import QDropEvent
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.save import first_package_file
from aas_workingbench.domain.design_tokens import FONT_FAMILY
from aas_workingbench.domain.design_tokens import TYPE_RAMP

COLUMN_WIDTH = 360
"""The width of the column of the start, in pixels."""


def role_font(role: str) -> QFont:
    """Makes the font of a role of the type ramp.

    Args:
        role: A key of `TYPE_RAMP`, such as `display`.

    Returns:
        The family of the editor at the size and weight of the role.
    """
    style = TYPE_RAMP[role]
    font = QFont(FONT_FAMILY)
    font.setPixelSize(style.size)
    font.setWeight(QFont.Weight(style.weight))
    # The bundled Inter is a variable font. Qt draws a weight below Bold from
    # it as Regular unless the axis of the weight is set too.
    font.setVariableAxis(QFont.Tag("wght"), float(style.weight))
    return font


def _has_files(event: QDragEnterEvent | QDragMoveEvent | QDropEvent) -> bool:
    mime = event.mimeData()
    return mime is not None and mime.hasUrls()


class EmptyState(QWidget):
    """What the window shows in place of the tree before a package is open.

    Attributes:
        open_button: Opens a file. It is the main action.
        new_button: Opens a menu with the kinds of new file.
        recent_buttons: One button for each recent file.
    """

    def __init__(
        self,
        open_action: QAction,
        new_actions: Sequence[QAction],
        recent_actions: Sequence[QAction],
        open_file: Callable[[str], object],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the start.

        Args:
            open_action: Asks for a file and opens it.
            new_actions: Create a new file, one for each kind.
            recent_actions: The actions of the recent files. Their text and
                visibility are followed, so the list stays current.
            open_file: Opens the file of a path, for a drop.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("emptyState")
        self.setAcceptDrops(True)
        self._open_file = open_file
        # The surface of the trees, not of the chrome around them.
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)

        title = QLabel("Open an AAS package", self)
        title.setObjectName("emptyTitle")
        title.setFont(role_font("display"))
        subtitle = QLabel(
            "Look at and edit Asset Administration Shells in an AASX, JSON, "
            "or XML file.",
            self,
        )
        subtitle.setObjectName("emptyHint")
        subtitle.setWordWrap(True)

        self.open_button = QPushButton("Open...", self)
        self.open_button.setProperty("primary", True)
        self.open_button.setToolTip(open_action.statusTip())
        self.open_button.clicked.connect(open_action.trigger)
        self.new_button = QPushButton("New", self)
        self.new_button.setToolTip("Create a new AAS file")
        menu = QMenu(self.new_button)
        for action in new_actions:
            menu.addAction(action)
        self.new_button.setMenu(menu)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.new_button)
        buttons.addStretch(1)

        self._recent_title = QLabel("Recent", self)
        self._recent_title.setFont(role_font("subtitle"))
        self._recent_title.setObjectName("emptyRecentTitle")
        self.recent_buttons: list[QToolButton] = []
        self._recent_actions = list(recent_actions)
        recent = QVBoxLayout()
        recent.setSpacing(0)
        for action in self._recent_actions:
            button = QToolButton(self)
            button.setObjectName("recentFile")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            button.setAutoRaise(True)
            button.clicked.connect(action.trigger)
            recent.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
            self.recent_buttons.append(button)
            action.changed.connect(self.refresh)

        drop = QLabel("You can also drop files here.", self)
        drop.setObjectName("emptyHint")

        column = QVBoxLayout()
        column.setSpacing(12)
        column.addWidget(title)
        column.addWidget(subtitle)
        column.addLayout(buttons)
        column.addSpacing(8)
        column.addWidget(self._recent_title)
        column.addLayout(recent)
        column.addSpacing(8)
        column.addWidget(drop)

        holder = QWidget(self)
        # No wider than the column, and as narrow as the room: the sizes of the
        # zones are restored while this is shown, before a package opens.
        holder.setMaximumWidth(COLUMN_WIDTH)
        holder.setLayout(column)
        outer = QHBoxLayout(self)
        outer.addStretch(1)
        outer.addWidget(holder, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        """Shows the recent files that the actions hold now."""
        shown = 0
        for action, button in zip(
            self._recent_actions, self.recent_buttons, strict=True
        ):
            visible = action.isVisible() and bool(action.text())
            button.setVisible(visible)
            # A file name with an ampersand is no mnemonic.
            button.setText(action.text().replace("&", "&&"))
            button.setToolTip(action.statusTip())
            shown += visible
        self._recent_title.setVisible(bool(shown))

    def dragEnterEvent(self, event: QDragEnterEvent | None) -> None:  # noqa: N802
        """Accepts files."""
        if event is not None and _has_files(event):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent | None) -> None:  # noqa: N802
        """Accepts files."""
        if event is not None and _has_files(event):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:  # noqa: N802
        """Opens one dropped file: one package is open at a time.

        The first package of the drop opens, and a drop of no package tries
        the first file, which says why it does not open.
        """
        if event is None or not _has_files(event):
            return
        mime = event.mimeData()
        urls = [] if mime is None else mime.urls()
        chosen = first_package_file([url.toLocalFile() for url in urls])
        if chosen is not None:
            self._open_file(chosen)
        event.acceptProposedAction()


NOTHING_SELECTED_TITLE = "Select an element"
NOTHING_SELECTED_HINT = (
    "Its attributes show here. Ctrl+K finds an element by name."
)


class NothingSelected(QWidget):
    """What the detail shows while it has no element to show (screen 02).

    A tab that shows nothing used to be an empty grid, which says neither
    what goes there nor how to get something there.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Builds the message.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("nothingSelected")
        self.setBackgroundRole(QPalette.ColorRole.Base)
        self.setAutoFillBackground(True)
        from aas_workingbench.ui.theme.icons import tabler_icon

        icon = QLabel(self)
        icon.setPixmap(tabler_icon("info-circle").pixmap(16, 16))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel(NOTHING_SELECTED_TITLE, self)
        self.title.setObjectName("nothingSelectedTitle")
        self.title.setFont(role_font("body_strong"))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel(NOTHING_SELECTED_HINT, self)
        self.hint.setObjectName("emptyHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addStretch(1)
        layout.addWidget(icon)
        layout.addSpacing(4)
        layout.addWidget(self.title)
        layout.addWidget(self.hint)
        layout.addStretch(1)
