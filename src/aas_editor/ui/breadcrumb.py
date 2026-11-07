"""The path of the object of a tab, read as segments that can be clicked.

A tab used to show the path as the text of an input field that was far too
narrow for it, and the type of the object in a second field. The breadcrumb
shows each name of the path as a button that opens that object, and the type
at the end. A click on the blank area, which is where a person expects to type,
swaps the segments for the field with its completer, and Enter, Escape, or
leaving the field swaps them back.

When the path is too long for the room, the first segments are folded into a
button with a menu, and the last ones, which tell where the user is, stay.
"""

from collections.abc import Callable

from PyQt6.QtCore import QEvent
from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtGui import QResizeEvent
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QSizePolicy
from PyQt6.QtWidgets import QStackedLayout
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget

SEPARATOR = "/"
FOLDED_TEXT = "…"


class _SegmentsPage(QWidget):
    """The page with the segments. A click that hits no button edits."""

    blank_clicked = pyqtSignal()

    def mousePressEvent(self, event: QMouseEvent | None) -> None:  # noqa: N802
        """Asks to edit the text when the click is on the blank area."""
        if event is not None and event.button() == Qt.MouseButton.LeftButton:
            self.blank_clicked.emit()
        super().mousePressEvent(event)


class Breadcrumb(QWidget):
    """The segments of a path, the type at its end, and the field to edit it.

    Attributes:
        editor: The field that edits the path as text.
        segment_activated: Emitted with the position of a segment that the
            user clicked, the first one being 0.
    """

    segment_activated = pyqtSignal(int)

    def __init__(
        self, editor: QLineEdit, parent: QWidget | None = None
    ) -> None:
        """Builds the breadcrumb around a field.

        Args:
            editor: The field that edits the path as text. The breadcrumb owns
                its place and its visibility, and the caller its text and what
                Enter does.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("breadcrumb")
        self.editor = editor
        self._names: list[str] = []
        self._buttons: list[QToolButton] = []
        self._separators: list[QLabel] = []

        self._page = _SegmentsPage(self)
        self._page.setObjectName("breadcrumbSegments")
        self._row = QHBoxLayout(self._page)
        self._row.setContentsMargins(4, 0, 4, 0)
        self._row.setSpacing(0)
        self._folded = QToolButton(self._page)
        self._folded.setObjectName("breadcrumbSegment")
        self._folded.setText(FOLDED_TEXT)
        self._folded.setToolTip("The first parts of the path")
        self._folded.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._folded.setMenu(QMenu(self._folded))
        self._folded.setAccessibleName("Parts of the path that do not fit")
        self._folded.hide()
        self._row.addWidget(self._folded)
        self._row.addStretch(1)
        self._type = QLabel(self._page)
        self._type.setObjectName("breadcrumbType")
        self._type.setAccessibleName("Type of the object")
        self._row.addWidget(self._type)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self._page)
        self._stack.addWidget(editor)

        self._page.blank_clicked.connect(self.start_editing)
        editor.editingFinished.connect(self.stop_editing)
        editor.installEventFilter(self)
        # The room, not the width of the path, is what the tab gives.
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.setMinimumWidth(40)

    @property
    def names(self) -> list[str]:
        """The names of the segments, from the package to the object."""
        return list(self._names)

    @property
    def is_editing(self) -> bool:
        """Whether the text field is shown instead of the segments."""
        return self._stack.currentWidget() is self.editor

    def focus_widgets(self) -> list[QWidget]:
        """Lists what Tab stops at in the breadcrumb, from the left.

        The segments are made again for every path, so Qt puts them at the end
        of the focus chain of the window, after everything that was made
        earlier. The tab sets their order from this list.
        """
        return [self._folded, *self._buttons, self.editor]

    def set_path(self, names: list[str], type_text: str = "") -> None:
        """Shows a path.

        Args:
            names: The names from the package down to the object. The last one
                is the object, which opens nothing, because it is open.
            type_text: The type of the object, shown at the end.
        """
        self._names = list(names)
        self._type.setText(type_text)
        self._type.setToolTip(type_text)
        for widget in (*self._buttons, *self._separators):
            self._row.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._buttons = []
        self._separators = []
        position = 1
        for place, name in enumerate(names):
            if place:
                separator = QLabel(SEPARATOR, self._page)
                separator.setObjectName("breadcrumbSeparator")
                self._row.insertWidget(position, separator)
                self._separators.append(separator)
                position += 1
            button = QToolButton(self._page)
            button.setObjectName("breadcrumbSegment")
            button.setText(name)
            button.setAutoRaise(True)
            is_last = place == len(names) - 1
            button.setProperty("current", is_last)
            button.setToolTip(name)
            button.setAccessibleName(name)
            button.clicked.connect(self._activator(place))
            self._row.insertWidget(position, button)
            self._buttons.append(button)
            position += 1
        self._fit()

    def _activator(self, position: int) -> Callable[[], None]:
        """Makes the function that asks to open the segment at a position."""

        def activate() -> None:
            self.segment_activated.emit(position)

        return activate

    def start_editing(self) -> None:
        """Shows the text field, with the text selected."""
        if self.is_editing:
            return
        self._stack.setCurrentWidget(self.editor)
        self.editor.setFocus()
        self.editor.selectAll()

    def stop_editing(self) -> None:
        """Shows the segments again."""
        if self.is_editing:
            self._stack.setCurrentWidget(self._page)

    def eventFilter(
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:  # noqa: N802
        """Leaves the text field at Escape."""
        if (
            watched is self.editor
            and isinstance(event, QKeyEvent)
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
        ):
            self.stop_editing()
            return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent | None) -> None:  # noqa: N802
        """Folds the first segments that do not fit."""
        super().resizeEvent(event)
        self._fit()

    def _fit(self) -> None:
        """Hides the first segments until the last ones and the type fit."""
        for widget in (*self._buttons, *self._separators):
            widget.show()
        room = self.width() - self._type.sizeHint().width() - 16
        if not self._buttons or room <= 0:
            self._folded.hide()
            return
        widths: list[int] = []
        for place, button in enumerate(self._buttons):
            width = button.sizeHint().width()
            if place:
                width += self._separators[place - 1].sizeHint().width()
            widths.append(width)
        folded_width = self._folded.sizeHint().width()
        hidden = 0
        while (
            hidden < len(widths) - 1
            and sum(widths[hidden:]) + (folded_width if hidden else 0) > room
        ):
            hidden += 1
        # The separator before the first segment shown stays, after the fold.
        for place in range(hidden):
            self._buttons[place].hide()
            if place:
                self._separators[place - 1].hide()
        self._folded.setVisible(bool(hidden))
        menu = self._folded.menu()
        if menu is not None:
            menu.clear()
            for place in range(hidden):
                menu.addAction(self._names[place], self._activator(place))
