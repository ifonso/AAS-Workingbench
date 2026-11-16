"""The header of the pane of the package tree: the package, and a filter.

The tree had no title, and its search was a bar behind View > SearchBar that
highlighted rows. The pane now says which package the tree is on, with a menu
of what can be done with the package, and has a filter that is always there
(proposal 2.4). Typing in the filter keeps the rows that match and their
parents, opens the branches that hold them, and says how many match, with a
way to clear it (screen 03 of the mockup).

The header knows no package: the window gives it the name, the actions of the
menu, and the view whose rows it filters.
"""

from collections.abc import Iterable
from collections.abc import Sequence

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QSize
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.domain.design_tokens import ICON_SIZE
from aas_workingbench.ui.empty_state import role_font
from aas_workingbench.ui.theme.icons import tabler_icon

FILTER_DELAY_MS = 150
"""How long the filter waits after a key, so that a long name is not searched
for at every letter."""

FILTER_PLACEHOLDER = "Filter elements"


def match_text(count: int) -> str:
    """Says how many rows match the filter.

    Args:
        count: The rows that match themselves, not the parents kept for them.

    Returns:
        A sentence such as `5 elements match, with their parents`.
    """
    if count == 0:
        return "No element matches"
    if count == 1:
        return "1 element matches, with its parents"
    return f"{count} elements match, with their parents"


def add_filter_icon(field: QLineEdit) -> None:
    """Puts the filter icon at the start of a field.

    Qt draws the icon as a button inside the field, which a screen reader
    reaches, so it gets a name and a tooltip too.
    """
    action = field.addAction(
        tabler_icon("filter"), QLineEdit.ActionPosition.LeadingPosition
    )
    if action is None:
        return
    action.setText("Filter")
    action.setToolTip(field.placeholderText() or "Filter")
    for button in field.findChildren(QToolButton):
        if button.defaultAction() is action:
            button.setAccessibleName("Filter")
            button.setToolTip(action.toolTip())
        elif not button.accessibleName():
            # The button that empties the field, which Qt adds.
            button.setAccessibleName("Clear the filter")
            button.setToolTip("Clear the filter")


class TreeFilter(QWidget):
    """A field that filters the rows of a tree as the user types.

    Attributes:
        field: The text field.
        result: The sentence that says how many rows match. Hidden while the
            field is empty.
        clear_button: Empties the field, and shows all rows again.
    """

    def __init__(
        self, view: QTreeView, column: int, parent: QWidget | None = None
    ) -> None:
        """Builds the filter of a tree.

        Args:
            view: The tree. Its model is a `SearchProxyModel`.
            column: The column whose text is matched.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._view = view
        self._column = column
        self._count = 0
        self.field = QLineEdit(self)
        self.field.setObjectName("treeFilterField")
        self.field.setPlaceholderText(FILTER_PLACEHOLDER)
        self.field.setClearButtonEnabled(True)
        add_filter_icon(self.field)
        self.field.setAccessibleName("Filter the package tree")
        self.result = QLabel(self)
        self.result.setObjectName("treeFilterResult")
        self.clear_button = QToolButton(self)
        self.clear_button.setObjectName("treeFilterClear")
        self.clear_button.setText("Clear")
        self.clear_button.setAutoRaise(True)
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self.clear)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(FILTER_DELAY_MS)
        self._timer.timeout.connect(self.apply)
        self.field.textChanged.connect(self._schedule)
        result_row = QHBoxLayout()
        result_row.setContentsMargins(0, 0, 0, 0)
        result_row.addWidget(self.result, 1)
        result_row.addWidget(self.clear_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.field)
        layout.addLayout(result_row)
        self._show_result(False)

    def _schedule(self, _text: str) -> None:
        self._timer.start()

    @property
    def count(self) -> int:
        """How many rows match the text of the field now."""
        return self._count

    def text(self) -> str:
        """The text of the field."""
        return self.field.text()

    def set_text(self, text: str) -> None:
        """Puts a text in the field and filters at once."""
        self.field.setText(text)
        self.apply()

    def clear(self) -> None:
        """Empties the field and shows every row again."""
        self.field.clear()
        self.apply()

    def apply(self) -> None:
        """Filters the rows of the tree by the text of the field."""
        self._timer.stop()
        model = self._view.model()
        search = getattr(model, "search", None)
        if search is None:
            return
        # A parent stays for a row below it that matches.
        recursive = getattr(model, "setRecursiveFilteringEnabled", None)
        if recursive is not None:
            recursive(True)
        text = self.field.text().strip()
        found: Sequence[object] = search(
            text, [self._column], regExp=False, filter=bool(text)
        )
        self._count = len(found)
        if text:
            # The branches that hold a match open, so the matches are seen.
            self._view.expandAll()
            current = self._view.currentIndex()
            if current.isValid():
                self._view.scrollTo(current)
        self.result.setText(match_text(self._count) if text else "")
        self._show_result(bool(text))

    def _show_result(self, shown: bool) -> None:
        self.result.setVisible(shown)
        self.clear_button.setVisible(shown)


class TreePaneHeader(QWidget):
    """The name of the package of the tree, its menu, and the filter.

    Attributes:
        name: The name of the package that the tree is on.
        more: Opens the menu of the package.
        filter: The filter of the rows of the tree.
    """

    def __init__(
        self,
        view: QTreeView,
        column: int,
        actions: Sequence[QAction],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the header of the pane.

        Args:
            view: The package tree.
            column: The column whose text the filter matches.
            actions: What the menu of the package offers, such as Save and
                Close.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setObjectName("treePaneHeader")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon = QLabel(self)
        icon.setPixmap(tabler_icon("file").pixmap(QSize(ICON_SIZE, ICON_SIZE)))
        self.name = QLabel(self)
        self.name.setObjectName("treePaneName")
        self.name.setFont(role_font("body_strong"))
        self.name.setAccessibleName("Package")
        self.more = QToolButton(self)
        self.more.setObjectName("treePaneMore")
        self.more.setIcon(tabler_icon("dots"))
        self.more.setAutoRaise(True)
        self.more.setToolTip("What can be done with the package")
        self.more.setAccessibleName("Package menu")
        self.more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(self.more)
        for action in actions:
            menu.addAction(action)
        self.more.setMenu(menu)
        self.filter = TreeFilter(view, column, self)
        title = QHBoxLayout()
        title.setContentsMargins(0, 0, 0, 0)
        title.setSpacing(8)
        title.addWidget(icon)
        title.addWidget(self.name, 1)
        title.addWidget(self.more)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addLayout(title)
        layout.addWidget(self.filter)

    def set_package_name(self, name: str) -> None:
        """Shows the name of the package that the tree is on, or none."""
        self.name.setText(name)
        self.name.setToolTip(name)
        self.more.setEnabled(bool(name))


def package_name_of(view: QTreeView, packages: Iterable[object]) -> str:
    """Names the package of the pane: of the current row, or the only one.

    Args:
        view: The package tree.
        packages: The open packages, in any collection, such as the set
            that the model of the tree gives.

    Returns:
        The name, `2 packages` for several without a current row, or an empty
        string for none.
    """
    from aas_workingbench.settings.app_settings import PACKAGE_ROLE

    packages = list(packages)
    current: QModelIndex = view.currentIndex()
    package = current.data(PACKAGE_ROLE) if current.isValid() else None
    if package is None and len(packages) == 1:
        package = packages[0]
    if package is not None:
        return str(getattr(package, "name", ""))
    if packages:
        return f"{len(packages)} packages"
    return ""
