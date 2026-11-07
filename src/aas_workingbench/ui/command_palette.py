"""The command palette: one field for the commands and the elements (Ctrl+K).

The field lists the actions of the editor with their keys, the ones that cannot
run now with the reason when it is known, and the ones used last first. A name
that is typed also finds the elements of the open packages, and picking one
selects it in the tree. The palette replaces no search: the search of the tree
and of a tab stay as they are.

The look follows the design tokens. The widget paints its rows from the tokens
of the theme in use, and the style sheet has one block for its frame.
"""

from collections.abc import Callable
from typing import Any
from typing import cast

from PyQt6.QtCore import QAbstractListModel
from PyQt6.QtCore import QEvent
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QObject
from PyQt6.QtCore import QPoint
from PyQt6.QtCore import QRect
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QTimer
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListView
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QStyle
from PyQt6.QtWidgets import QStyledItemDelegate
from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.command_palette import EntryKind
from aas_workingbench.application.command_palette import PaletteEntry
from aas_workingbench.application.command_palette import RecentCommands
from aas_workingbench.application.command_palette import rank
from aas_workingbench.application.editing import edit_mode
from aas_workingbench.settings.app_settings import OPENED_PACKS_ROLE
from aas_workingbench.settings.app_settings import recent_settings
from aas_workingbench.ui.palette_sources import element_entries
from aas_workingbench.ui.palette_sources import menu_entries
from aas_workingbench.ui.palette_sources import registered_entries
from aas_workingbench.ui.palette_sources import tree_entries
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.tree_navigation import select_object

PALETTE_KEY = QKeySequence("Ctrl+K")
PLACEHOLDER = "Type a command, or the name of an element"
HELP = "Type to search. A name also finds elements."
VISIBLE_ROWS = 9
_ENTRY_ROLE = Qt.ItemDataRole.UserRole
_RECENT_KEY = "commandPaletteRecent"
_NOTE_MS = 6000
_STEPS = {
    Qt.Key.Key_Down.value: 1,
    Qt.Key.Key_Up.value: -1,
    Qt.Key.Key_PageDown.value: VISIBLE_ROWS,
    Qt.Key.Key_PageUp.value: -VISIBLE_ROWS,
}


class _EntryModel(QAbstractListModel):
    """The entries of the list, in the order to show."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: list[PaletteEntry] = []

    def set_entries(self, entries: list[PaletteEntry]) -> None:
        self.beginResetModel()
        self._entries = entries
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._entries)

    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid():
            return None
        entry = self._entries[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.title
        if role == _ENTRY_ROLE:
            return entry
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return _spoken(entry)
        if role == Qt.ItemDataRole.ToolTipRole:
            return _spoken(entry)
        return None


def _spoken(entry: PaletteEntry) -> str:
    parts = [entry.title]
    if entry.detail:
        parts.append(entry.detail)
    if entry.shortcut:
        parts.append(entry.shortcut)
    if not entry.enabled:
        parts.append(f"not available. {entry.reason}".strip())
    return ", ".join(parts)


class _EntryDelegate(QStyledItemDelegate):
    """Paints a row: the title, where it is, and the keys at the right.

    The colors come from the tokens of the theme at the time of painting, so a
    change of theme needs no work here.
    """

    PAD = 12
    GAP = 12

    def paint(
        self,
        painter: QPainter | None,
        option: QStyleOptionViewItem,
        index: QModelIndex,
    ) -> None:
        entry = index.data(_ENTRY_ROLE)
        if painter is None or not isinstance(entry, PaletteEntry):
            return
        tokens = current_tokens()
        rect = option.rect  # type: ignore[attr-defined]
        state = option.state  # type: ignore[attr-defined]
        painter.save()
        if state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor(tokens.bg_selected))
            painter.fillRect(
                QRect(rect.left(), rect.top() + 4, 3, rect.height() - 8),
                QColor(tokens.accent),
            )
        elif state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(rect, QColor(tokens.bg_hover))
        metrics = QFontMetrics(option.font)  # type: ignore[attr-defined]
        left = rect.left() + self.PAD
        right = rect.right() - self.PAD
        keys_width = 0
        if entry.shortcut:
            keys_width = metrics.horizontalAdvance(entry.shortcut)
            painter.setPen(QColor(tokens.fg_muted))
            painter.drawText(
                QRect(
                    right - keys_width, rect.top(), keys_width, rect.height()
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                entry.shortcut,
            )
            keys_width += self.GAP
        title_width = min(
            metrics.horizontalAdvance(entry.title), (right - left) * 2 // 3
        )
        painter.setPen(
            QColor(tokens.fg_primary if entry.enabled else tokens.fg_muted)
        )
        painter.drawText(
            QRect(left, rect.top(), title_width, rect.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(
                entry.title, Qt.TextElideMode.ElideRight, title_width
            ),
        )
        # The reason takes the place of the detail for a command that cannot
        # run, because that is what the user needs to read there.
        secondary = entry.detail
        if not entry.enabled and entry.reason:
            secondary = entry.reason
        room = right - keys_width - (left + title_width + self.GAP)
        if secondary and room > metrics.averageCharWidth() * 4:
            painter.setPen(QColor(tokens.fg_muted))
            painter.drawText(
                QRect(
                    left + title_width + self.GAP,
                    rect.top(),
                    room,
                    rect.height(),
                ),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                metrics.elidedText(
                    secondary, Qt.TextElideMode.ElideRight, room
                ),
            )
        painter.restore()

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        metrics = QFontMetrics(option.font)  # type: ignore[attr-defined]
        return QSize(0, metrics.height() + 12)


class CommandPalette(QDialog):
    """The field and the list of the palette.

    The palette does not know where its entries come from, or what picking one
    does. The caller gives it the entries when it opens, and runs the entry
    that `chosen` carries.

    Attributes:
        input: The field that the user types in.
        results: The list of entries that fit.
        note: The line under the list. It says why a command cannot run.
        chosen: Emitted with the `PaletteEntry` that the user picked. A
            command that cannot run is not emitted, and the note says why.
    """

    chosen = pyqtSignal(object)

    def __init__(
        self, recent: RecentCommands, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
        )
        self.setObjectName("commandPalette")
        self.setAccessibleName("Command palette")
        self._recent = recent
        self._commands: list[PaletteEntry] = []
        self._elements_source: Callable[[], list[PaletteEntry]] | None = None
        self._elements: list[PaletteEntry] | None = None

        self.input = QLineEdit(self)
        self.input.setObjectName("commandPaletteInput")
        self.input.setPlaceholderText(PLACEHOLDER)
        self.input.setAccessibleName("Search commands and elements")
        self.input.setClearButtonEnabled(True)
        self.input.textChanged.connect(self._refresh)
        self.input.installEventFilter(self)

        self._model = _EntryModel(self)
        self.results = QListView(self)
        self.results.setObjectName("commandPaletteList")
        self.results.setAccessibleName("Matching commands and elements")
        self.results.setModel(self._model)
        self.results.setItemDelegate(_EntryDelegate(self.results))
        self.results.setMouseTracking(True)
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.results.clicked.connect(self._pick)
        self.results.activated.connect(self._pick)

        self.note = QLabel(HELP, self)
        self.note.setObjectName("commandPaletteNote")
        self.note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        layout.addWidget(self.input)
        layout.addWidget(self.results)
        layout.addWidget(self.note)
        self.setFocusProxy(self.input)
        self.setTabOrder(self.input, self.results)

    # -- what the caller sees -------------------------------------------

    @property
    def shown_entries(self) -> list[PaletteEntry]:
        """The entries listed now, best first."""
        model = self._model
        return [
            cast("PaletteEntry", model.index(row).data(_ENTRY_ROLE))
            for row in range(model.rowCount())
        ]

    @property
    def current_entry(self) -> PaletteEntry | None:
        """The entry that Enter would pick, or None."""
        entry = self.results.currentIndex().data(_ENTRY_ROLE)
        return entry if isinstance(entry, PaletteEntry) else None

    def open_over(
        self,
        window: QWidget,
        commands: list[PaletteEntry],
        elements: Callable[[], list[PaletteEntry]],
    ) -> None:
        """Shows the palette at the top of a window, with an empty field.

        Args:
            window: The window to center on.
            commands: The commands, as they are now.
            elements: Makes the elements. It is called when the first word is
                typed, and not before, because a package can be large.
        """
        self._commands = commands
        self._elements_source = elements
        self._elements = None
        self.input.clear()
        self._refresh()
        metrics = self.fontMetrics()
        width = min(
            max(metrics.averageCharWidth() * 90, 560), window.width() - 40
        )
        row = metrics.height() + 12
        self.results.setFixedHeight(row * VISIBLE_ROWS)
        self.setFixedWidth(max(width, 200))
        self.adjustSize()
        top = window.mapToGlobal(QPoint(0, 0))
        self.move(top.x() + (window.width() - self.width()) // 2, top.y() + 56)
        self.show()
        self.input.setFocus()

    def choose_current(self) -> bool:
        """Picks the entry that is selected, as Enter does.

        Returns:
            True if the palette picked a command or an element. False when
            there is nothing selected, or the command cannot run now.
        """
        entry = self.current_entry
        if entry is None:
            return False
        return self._choose(entry)

    # -- internals ------------------------------------------------------

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        """Lets the arrow keys and Enter work while the field has the focus."""
        if a0 is self.input and a1 is not None:
            if a1.type() == QEvent.Type.KeyPress:
                key = cast("QKeyEvent", a1).key()
                # By number, so that a letter of any script passes through.
                step = _STEPS.get(key)
                if step is not None:
                    self._move(step)
                    return True
                if key in (Qt.Key.Key_Return.value, Qt.Key.Key_Enter.value):
                    self.choose_current()
                    return True
        return super().eventFilter(a0, a1)

    def _move(self, step: int) -> None:
        count = self._model.rowCount()
        if count == 0:
            return
        row = self.results.currentIndex().row()
        row = max(0, min(count - 1, row + step if row >= 0 else 0))
        self.results.setCurrentIndex(self._model.index(row))
        self._explain()

    def _entries(self, query: str) -> list[PaletteEntry]:
        entries = list(self._commands)
        if query.strip():
            if self._elements is None and self._elements_source is not None:
                self._elements = self._elements_source()
            entries += self._elements or []
        return entries

    def _refresh(self) -> None:
        query = self.input.text()
        found = rank(self._entries(query), query, self._recent.keys())
        self._model.set_entries(found)
        if found:
            self.results.setCurrentIndex(self._model.index(0))
        if query.strip() and not found:
            self.note.setText(f"Nothing matches '{query.strip()}'")
        else:
            self._explain()

    def _explain(self) -> None:
        entry = self.current_entry
        if entry is not None and not entry.enabled:
            reason = entry.reason or "It is not available now"
            self.note.setText(f"Not available: {reason}")
        else:
            self.note.setText(HELP)

    def _pick(self, index: QModelIndex) -> None:
        entry = index.data(_ENTRY_ROLE)
        if isinstance(entry, PaletteEntry):
            self.results.setCurrentIndex(index)
            self._choose(entry)

    def _choose(self, entry: PaletteEntry) -> bool:
        if not entry.enabled:
            self._explain()
            return False
        self.close()
        self.chosen.emit(entry)
        return True


def _stored_recent() -> list[str]:
    settings = recent_settings()
    keys: object = settings.value(_RECENT_KEY, [])
    if not isinstance(keys, list):
        return []
    return [str(key) for key in cast("list[object]", keys)]


def _store_recent(keys: list[str]) -> None:
    recent_settings().setValue(_RECENT_KEY, keys)


class PaletteController(QObject):
    """Opens the palette on Ctrl+K and does what the picked entry says.

    Attributes:
        action: The action with the key. The window lists it in a menu.
        palette: The palette widget.
        recent: The commands used last.
    """

    def __init__(
        self,
        window: QMainWindow,
        recent: RecentCommands | None = None,
    ) -> None:
        """Adds the key to a window.

        Args:
            window: The main window. It needs `mainTreeView` and
                `packTreeModel`, as `EditorApp` has them, and a menu bar.
            recent: Where the commands used last are kept. By default they are
                stored with the settings of the application.
        """
        super().__init__(window)
        self._window = window
        self._tree = cast("Any", window).mainTreeView
        self._pack_model = cast("Any", window).packTreeModel
        self.recent = recent or RecentCommands(_stored_recent, _store_recent)
        self.palette = CommandPalette(self.recent, window)
        self.palette.chosen.connect(self._run_later)
        self.action = QAction("Command palette...", window)
        self.action.setShortcut(PALETTE_KEY)
        self.action.setStatusTip(
            "Search the commands and the elements of the open packages"
        )
        self.action.triggered.connect(self.open)
        window.addAction(self.action)

    def open(self) -> None:
        """Shows the palette over the window."""
        self.palette.open_over(self._window, self.commands(), self.elements)

    def commands(self) -> list[PaletteEntry]:
        """Gathers the commands: the registered actions and the menu actions."""
        taken = {id(self.action)}
        # The registered actions go first in the work, so that an action that
        # a menu lists too keeps the reason that its spec gives. They come
        # last in the list, because the menus are the order that users know.
        registered = registered_entries(self._tree.registeredActions, taken)
        menu_bar = self._window.menuBar()
        entries = [] if menu_bar is None else menu_entries(menu_bar, taken)
        entries += tree_entries(self._tree, taken, edit_mode().is_editing)
        return [*entries, *registered]

    def elements(self) -> list[PaletteEntry]:
        """Gathers the elements of the open packages."""
        packages = list(self._pack_model.data(QModelIndex(), OPENED_PACKS_ROLE))
        return element_entries(packages, show_package=len(packages) > 1)

    def run(self, entry: PaletteEntry) -> bool:
        """Does what an entry says.

        A command runs its action, and an element becomes the current row of
        the package tree.

        Args:
            entry: The entry that the user picked.

        Returns:
            True if the command ran or the element was selected.
        """
        if entry.kind is EntryKind.COMMAND:
            action = entry.payload
            if not isinstance(action, QAction) or not action.isEnabled():
                return False
            self.recent.used(entry.key)
            action.trigger()
            return True
        package, obj = cast("tuple[object, object]", entry.payload)
        shown = select_object(self._tree, obj, package)
        status = self._window.statusBar()
        if shown:
            self._tree.setFocus()
        elif status is not None:
            status.showMessage(
                f"The tree does not show {entry.title}. A search may hide it",
                _NOTE_MS,
            )
        return shown

    def _run_later(self, entry: PaletteEntry) -> None:
        # The palette is closing, and a command may open a dialog, so it runs
        # when the palette is gone.
        QTimer.singleShot(0, lambda: self.run(entry))


def install_palette(
    window: QMainWindow, recent: RecentCommands | None = None
) -> PaletteController:
    """Adds the palette and its key to the main window.

    Args:
        window: The main window.
        recent: Where the commands used last are kept. By default they are
            stored with the settings of the application.

    Returns:
        The controller, which the window should keep. Its `action` goes into a
        menu so that the command can be found there.
    """
    return PaletteController(window, recent)


__all__ = [
    "PALETTE_KEY",
    "CommandPalette",
    "PaletteController",
    "install_palette",
]
