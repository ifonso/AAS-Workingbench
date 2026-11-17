"""The header of the detail: which element the tab shows.

The tab used to say what it shows in one row with the path, and the summary of
an element repeated its name four times. The detail now has two levels
(proposal 3.1): the path bar says where the element is, and below it this
block says which element it is, with room around it: the icon of its kind, its
idShort as the title (the name of the tree and of the tab), and its type as a
badge. The display name and the value are rows of the sections, so they are
not repeated here.

The widget knows no tree: the tab gives it the icon, the name and the type.
"""

from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtWidgets import QWidget

from aas_workingbench.domain.design_tokens import ICON_SIZE
from aas_workingbench.ui.empty_state import role_font

HEADER_PADDING = 20
"""The room above and below the title, in pixels (proposal 3.1)."""

HEADER_SIDE = 16
"""The room left of the icon and right of the badge, in pixels."""


class ElementHeader(QWidget):
    """The icon, the title and the type badge of the element of a tab.

    Attributes:
        icon: The icon of the kind of the element.
        title: The idShort, or the name of the tree for what has none.
        badge: The type, such as `Property`. Hidden for no type.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Builds an empty header.

        Args:
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("elementHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.icon = QLabel(self)
        self.icon.setObjectName("elementHeaderIcon")
        self.icon.setFixedSize(QSize(ICON_SIZE, ICON_SIZE))
        self.title = QLabel(self)
        self.title.setObjectName("elementHeaderTitle")
        self.title.setFont(role_font("title"))
        self.title.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.title.setAccessibleName("Element")
        self.badge = QLabel(self)
        self.badge.setObjectName("elementHeaderBadge")
        self.badge.setFont(role_font("caption"))
        self.badge.setAccessibleName("Type")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            HEADER_SIDE, HEADER_PADDING, HEADER_SIDE, HEADER_PADDING
        )
        layout.setSpacing(8)
        layout.addWidget(self.icon)
        layout.addWidget(self.title)
        layout.addWidget(self.badge)
        layout.addStretch(1)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Maximum
        )

    def minimumSizeHint(self) -> QSize:
        """Lets a short window take the room around the title first.

        The 20 pixels above and below the title are room to read, not
        content, so a window that is short of height gives them up before
        the attributes below shrink.
        """
        hint = super().minimumSizeHint()
        title = max(self.title.sizeHint().height(), ICON_SIZE)
        return QSize(hint.width(), title + 8)

    def set_element(
        self, icon: QIcon | None, title: str, type_text: str
    ) -> None:
        """Shows an element.

        Args:
            icon: The icon of its kind, or None.
            title: Its idShort, or the name that the tree gives it.
            type_text: Its type, such as `Property`, or an empty string.
        """
        if icon is not None and not icon.isNull():
            self.icon.setPixmap(icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)))
            self.icon.show()
        else:
            self.icon.clear()
            self.icon.hide()
        self.title.setText(title)
        self.title.setToolTip(title)
        self.badge.setText(type_text)
        self.badge.setVisible(bool(type_text))
