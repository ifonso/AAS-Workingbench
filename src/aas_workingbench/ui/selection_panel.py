"""The panel that shows what is selected in the package tree.

Package Explorer replaces its editor with a panel when several nodes are
selected: the header `Several elements selected`, and the buttons that apply
to all of them. This editor shows the same in a dock below the tree, because
the tabs on the right keep showing the current object.

The panel does not repeat the context menu. It has the actions that work on a
whole selection: the four moves, Cut, Copy and Delete, and the changes of many
objects at once. Each button is the action of the tree view, so a button is
enabled, disabled or hidden exactly when the menu entry is, and a click does
what the menu entry does, in one undo step.

The facts shown come from `aas_workingbench.domain.selection`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6 import sip
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDockWidget
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.domain.selection import SelectionSummary
from aas_workingbench.domain.selection import summarize
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui.actions import READ_MODE_REASON

HINT_TEXT = (
    "Select several rows with Ctrl+click or Shift+click to move, copy, "
    "delete or change them together."
)
MIXED_TEXT = (
    "These variables have different directions, so Move and Delete are not "
    "offered. Cut and Copy are."
)


@dataclass(frozen=True)
class _ButtonSpec:
    text: str
    find: Callable[[QTreeView], QAction | None]
    not_for_mixed: bool = False


def _registered(action_id: str) -> Callable[[QTreeView], QAction | None]:
    def find(view: QTreeView) -> QAction | None:
        actions = getattr(view, "registeredActions", None)
        return actions.find(action_id) if actions is not None else None

    return find


def _attribute(name: str) -> Callable[[QTreeView], QAction | None]:
    def find(view: QTreeView) -> QAction | None:
        action = getattr(view, name, None)
        return action if isinstance(action, QAction) else None

    return find


# The rows of buttons, with the label of the row. A button whose action the
# view does not have is left out.
_GROUPS: tuple[tuple[str, tuple[_ButtonSpec, ...]], ...] = (
    (
        "Order",
        (
            _ButtonSpec("Move up", _registered("structure.move_up"), True),
            _ButtonSpec("Move down", _registered("structure.move_down"), True),
            _ButtonSpec("Move to top", _registered("structure.move_top"), True),
            _ButtonSpec("Move to end", _registered("structure.move_end"), True),
        ),
    ),
    (
        "Buffer",
        (
            _ButtonSpec("Cut", _attribute("cutAct")),
            _ButtonSpec("Copy", _attribute("copyAct")),
            _ButtonSpec("Delete", _attribute("delClearAct"), True),
        ),
    ),
    (
        "Change",
        (
            _ButtonSpec(
                "Change attribute...", _registered("bulk.change_attribute")
            ),
            _ButtonSpec(
                "Remove extensions...", _registered("bulk.remove_extensions")
            ),
        ),
    ),
)


def selection_of(view: QTreeView) -> SelectionSummary:
    """Describes the selected rows of a tree view.

    Args:
        view: The package tree view.

    Returns:
        The summary. A row counts once, however many of its cells are
        selected.
    """
    seen: set[tuple[QModelIndex, int]] = set()
    chosen: list[tuple[object, object | None]] = []
    for index in view.selectedIndexes():
        key = (index.parent(), index.row())
        obj = index.data(OBJECT_ROLE)
        if not index.isValid() or key in seen or obj is None:
            continue
        seen.add(key)
        chosen.append((obj, index.parent().data(OBJECT_ROLE)))
    return summarize(chosen)


class SelectionPanel(QWidget):
    """Names the selection and holds the buttons for it.

    Attributes:
        header_label: The title, `Several elements selected` for several rows.
        detail_label: The kinds, the parent, and what is not offered.
        buttons: The buttons by their text.
    """

    def __init__(self, view: QTreeView, parent: QWidget | None = None) -> None:
        """Builds the panel for a tree view.

        Args:
            view: The package tree view, whose selection the panel follows.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._view = view
        self._bound: list[tuple[QPushButton, QAction, bool]] = []
        self.buttons: dict[str, QPushButton] = {}
        self._rows: list[tuple[QWidget, list[QPushButton]]] = []
        self._summary = summarize([])

        self.header_label = QLabel()
        font = self.header_label.font()
        font.setBold(True)
        self.header_label.setFont(font)
        self.detail_label = QLabel()
        self.detail_label.setWordWrap(True)
        self.detail_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.header_label)
        layout.addWidget(self.detail_label)
        for title, specs in _GROUPS:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            caption = QLabel(f"{title}:")
            caption.setMinimumWidth(52)
            row_layout.addWidget(caption)
            made: list[QPushButton] = []
            for spec in specs:
                action = spec.find(view)
                if action is None:
                    continue
                button = QPushButton(spec.text)
                button.clicked.connect(action.trigger)
                action.changed.connect(self._sync_buttons)
                row_layout.addWidget(button)
                self._bound.append((button, action, spec.not_for_mixed))
                self.buttons[spec.text] = button
                made.append(button)
            row_layout.addStretch(1)
            layout.addWidget(row)
            self._rows.append((row, made))
        layout.addStretch(1)

        selection = view.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self.refresh)
            selection.currentChanged.connect(self.refresh)
        edit_mode().subscribe(self._on_mode)
        self.refresh()

    def _on_mode(self, editing: bool) -> None:
        del editing
        if not sip.isdeleted(self):
            self._sync_buttons()

    @property
    def summary(self) -> SelectionSummary:
        """What the panel shows now."""
        return self._summary

    def refresh(self, *_: object) -> None:
        """Reads the selection of the view again."""
        self._summary = selection_of(self._view)
        self.header_label.setText(self._summary.header)
        self.detail_label.setText(self._detail(self._summary))
        self._sync_buttons()

    @staticmethod
    def _detail(summary: SelectionSummary) -> str:
        if not summary.is_multiple:
            return HINT_TEXT
        text = f"{summary.kinds_text}. {summary.parent_line}"
        if summary.mixed_directions:
            text += f"\n{MIXED_TEXT}"
        return text

    def _sync_buttons(self, *_: object) -> None:
        """Shows each button as its action is, for a multiple selection."""
        multiple = self._summary.is_multiple
        mixed = self._summary.mixed_directions
        for button, action, not_for_mixed in self._bound:
            shown = (
                multiple
                and action.isVisible()
                and not (mixed and not_for_mixed)
            )
            button.setVisible(shown)
            button.setEnabled(action.isEnabled())
            # Copy and the like change nothing, and are on in Read mode.
            off_by_mode = not action.isEnabled() and not edit_mode().is_editing
            button.setToolTip(READ_MODE_REASON if off_by_mode else "")
        for row, buttons in self._rows:
            row.setVisible(multiple and any(not b.isHidden() for b in buttons))


class SelectionDock(QDockWidget):
    """The selection panel in a dock window below the tree.

    The dock opens by itself when a multiple selection is made. When the user
    closes it, with its button or with the entry of the View menu, it stays
    closed until they open it from that menu.

    Attributes:
        panel: The panel in the dock.
    """

    def __init__(self, view: QTreeView, parent: QWidget | None = None) -> None:
        """Builds the dock, hidden.

        Args:
            view: The package tree view.
            parent: The main window.
        """
        super().__init__("Selection", parent)
        self.setObjectName("selectionDock")
        self.panel = SelectionPanel(view, self)
        self.setWidget(self.panel)
        self._declined = False
        self.toggleViewAction().triggered.connect(self._on_toggled)  # pyright: ignore[reportOptionalMemberAccess]
        selection = view.selectionModel()
        if selection is not None:
            selection.selectionChanged.connect(self._open_for_multiple)
        self.hide()

    def _open_for_multiple(self, *_: object) -> None:
        if not self._declined and self.panel.summary.is_multiple:
            if not self.isVisible():
                self.show()

    def _on_toggled(self, shown: bool) -> None:
        self._declined = not shown

    def closeEvent(self, event: QCloseEvent | None) -> None:  # noqa: N802
        """Remembers that the user closed the dock."""
        self._declined = True
        super().closeEvent(event)
