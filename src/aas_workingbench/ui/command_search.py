"""The search box and the mode switch at the right end of the command bar.

The command palette (Ctrl+K) finds elements and commands, and was behind the
Navigate menu, where few found it. The command bar now has a box that says so,
"Search or go to…", and opens the palette (proposal 4.1). Read and Edit mode
were a text in the status bar and two entries of the View menu. They are now a
switch of two buttons in the command bar (proposal 4.4), which run the same
actions as the menu.
"""

from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget

from aas_workingbench.domain.design_tokens import ICON_SIZE
from aas_workingbench.ui.theme.icons import tabler_icon

SEARCH_TEXT = "Search or go to…"
"""What the search box of the command bar reads."""

SEARCH_WIDTH = 360
"""The width of the search box, in pixels."""


class SearchBox(QPushButton):
    """A box that looks like a field and opens the command palette.

    It is a button, because the palette is where the typing happens. It shows
    the key of the palette at its right end.
    """

    def __init__(self, palette: QAction, parent: QWidget | None = None) -> None:
        """Builds the box.

        Args:
            palette: The action that opens the command palette.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("commandSearch")
        self.setCursor(Qt.CursorShape.IBeamCursor)
        self.setFixedWidth(SEARCH_WIDTH)
        key = palette.shortcut().toString(
            QKeySequence.SequenceFormat.NativeText
        )
        self.setToolTip(f"Find an element or a command ({key})")
        self.setAccessibleName("Search or go to")
        self.setAccessibleDescription(f"Opens the command palette, {key}")
        icon = QLabel(self)
        icon.setPixmap(
            tabler_icon("search").pixmap(QSize(ICON_SIZE, ICON_SIZE))
        )
        self.label = QLabel(SEARCH_TEXT, self)
        self.label.setObjectName("commandSearchText")
        self.key = QLabel(key, self)
        self.key.setObjectName("commandSearchKey")
        self.key.setFixedHeight(20)
        for part in (icon, self.label, self.key):
            part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 4, 0)
        layout.setSpacing(8)
        layout.addWidget(icon)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.key)
        self.clicked.connect(palette.trigger)


class ModeSwitch(QWidget):
    """Two buttons, Read and Edit, of which one is on.

    Attributes:
        read: The button of Read mode.
        edit: The button of Edit mode.
    """

    def __init__(
        self, read: QAction, edit: QAction, parent: QWidget | None = None
    ) -> None:
        """Builds the switch over the actions of the two modes.

        Args:
            read: The checkable action of Read mode, in an exclusive group
                with `edit`.
            edit: The checkable action of Edit mode.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("modeSwitch")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        read.setIcon(tabler_icon("eye"))
        edit.setIcon(tabler_icon("pencil"))
        self.read = self._button(read, "Read", "modeSwitchRead")
        self.edit = self._button(edit, "Edit", "modeSwitchEdit")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)
        layout.addWidget(self.read)
        layout.addWidget(self.edit)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def _button(self, action: QAction, text: str, name: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(name)
        button.setDefaultAction(action)
        # The menu says "Read mode"; the switch says "Read", as the bar is
        # short and the pair tells that it is a mode.
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAutoRaise(True)
        action.changed.connect(lambda: button.setText(text))
        return button
