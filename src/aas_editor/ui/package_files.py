"""The panel of the supplementary files of the current package.

It lists every stored file with its media type, its size, and what refers to
it, and has a button for each function of `FileController`. A file that
nothing refers to is marked, because a save to AASX drops it. The panel follows
the package of the current row of the package tree, refreshes when the history
of that package changes, and disables the buttons that change the package in
Read mode.
"""

from collections.abc import Callable

from PyQt6.QtCore import QTimer
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QDockWidget
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QTableWidgetSelectionRange
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.changes import observer_for
from aas_editor.application.editing import edit_mode
from aas_editor.application.listeners import Subscription
from aas_editor.application.supplementary_files import StoredFileInfo
from aas_editor.domain import part_names
from aas_editor.ui.file_controller import FileController
from aas_editor.ui.file_controller import FilePackage

NAME_COLUMN = 0
COLUMNS = 4
UNUSED_TEXT = "Not referenced: not saved in AASX"
# How long the panel waits for more changes before it reads the files again.
REFRESH_DELAY_MS = 50
BUTTONS_PER_ROW = 4


class PackageFilesPanel(QWidget):
    """Lists the supplementary files of a package, with buttons.

    Attributes:
        table: One row for each stored file.
        summary_label: How many files, and how many references dangle.
        add_button: Add a file from disk.
        new_button: Create a text file.
        edit_button: Edit the selected text file.
        rename_button: Rename the selected file.
        move_button: Move the selected file to a folder.
        remove_button: Remove the selected file.
        save_button: Write the selected file to disk.
        dangling_button: Find the references to files that are not stored.
    """

    def __init__(
        self,
        package_provider: Callable[[], FilePackage | None],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the panel.

        Args:
            package_provider: Returns the package to show, or None.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._provider = package_provider
        self._package: FilePackage | None = None
        self._subscriptions: list[Subscription] = []
        self._stale = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_DELAY_MS)
        self._timer.timeout.connect(self.refresh)

        self.summary_label = QLabel()
        self.table = QTableWidget(0, COLUMNS)
        self.table.setHorizontalHeaderLabels(
            ["Name", "Media type", "Size", "Used by"]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        # Several files can be removed at once (F-EDT-09 AC18). The other
        # buttons work on one file.
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(
                NAME_COLUMN, QHeaderView.ResizeMode.Stretch
            )
            header.setStretchLastSection(True)
        vertical = self.table.verticalHeader()
        if vertical is not None:
            vertical.setVisible(False)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)

        self.add_button = self._button("Add file...", self._add)
        self.new_button = self._button("New text file...", self._new_text)
        self.edit_button = self._button("Edit text...", self._edit)
        self.rename_button = self._button("Rename...", self._rename)
        self.move_button = self._button("Move...", self._move)
        self.remove_button = self._button("Remove", self._remove)
        self.save_button = self._button("Save as...", self._save)
        self.dangling_button = self._button(
            "Find dangling references...", self._dangling
        )
        self.thumbnail_button = self._button(
            "Package thumbnail...", self._thumbnail
        )
        self._mutating = (
            self.add_button,
            self.new_button,
            self.edit_button,
            self.rename_button,
            self.move_button,
            self.remove_button,
            self.thumbnail_button,
        )

        # Two rows, because eight buttons in one row need more than a dock is
        # wide, and the labels were cut off.
        buttons = QGridLayout()
        for position, button in enumerate(
            (
                self.add_button,
                self.new_button,
                self.edit_button,
                self.rename_button,
                self.move_button,
                self.remove_button,
                self.save_button,
            )
        ):
            buttons.addWidget(button, *divmod(position, BUTTONS_PER_ROW))
        # Their labels are long, so they have a row of their own.
        half = BUTTONS_PER_ROW // 2
        buttons.addWidget(self.dangling_button, 2, 0, 1, half)
        buttons.addWidget(self.thumbnail_button, 2, half, 1, half)
        layout = QVBoxLayout(self)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        edit_mode().subscribe(self._on_mode_changed)
        self.set_package(None)

    def _button(self, text: str, slot: Callable[[], None]) -> QPushButton:
        button = QPushButton(text)
        button.clicked.connect(lambda: slot())
        return button

    # -- following the package -------------------------------------------------

    @property
    def package(self) -> FilePackage | None:
        """The package that the panel shows."""
        return self._package

    def follow_current_package(self) -> None:
        """Shows the package that the provider returns now."""
        provided = self._provider()
        if provided is not self._package:
            self.set_package(provided)

    def set_package(self, package: FilePackage | None) -> None:
        """Shows the files of a package, and follows its changes."""
        for subscription in self._subscriptions:
            subscription.cancel()
        self._subscriptions = []
        self._package = package
        if package is not None:
            self._subscriptions = [
                observer_for(package).subscribe(self._on_change),
                package.commandStack.subscribe(self._on_history),
            ]
        if package is None or self.isVisible():
            self.refresh()
        else:
            # A hidden panel reads the files when it is shown.
            self._stale = True

    def _on_change(self, change: object) -> None:
        del change
        self._schedule_refresh()

    def _on_history(self) -> None:
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        # Reading every file costs time, so a hidden panel waits until it is
        # shown.
        if self.isVisible():
            self._timer.start()
        else:
            self._stale = True

    def showEvent(self, event: QShowEvent | None) -> None:  # noqa: N802
        """Reads the files again if they changed while the panel was hidden."""
        super().showEvent(event)
        self.follow_current_package()
        if self._stale:
            self.refresh()

    def _on_mode_changed(self, editing: bool) -> None:
        del editing
        self._update_buttons()

    # -- showing -------------------------------------------------------------

    def refresh(self) -> None:
        """Reads the files of the package again."""
        self._stale = False
        package = self._package
        # The rows are rebuilt, and the files that were selected stay so.
        selected = set(self.selected_names())
        self.table.setRowCount(0)
        if package is None:
            self.summary_label.setText("No package is selected.")
            self._update_buttons()
            return
        controller = FileController(package, self)
        infos = controller.infos()
        self.table.setRowCount(len(infos))
        for row, info in enumerate(infos):
            self._fill_row(row, info)
            if info.name in selected:
                self.table.setRangeSelected(
                    QTableWidgetSelectionRange(row, 0, row, COLUMNS - 1), True
                )
        dangling = len(controller.dangling())
        text = f"{len(infos)} file(s) in the package."
        thumbnail = package.thumbnail
        text += (
            f" Package thumbnail: {thumbnail.name}."
            if thumbnail is not None
            else " No package thumbnail."
        )
        if dangling:
            text += (
                f" {dangling} reference(s) point to a file that is not in the "
                "package."
            )
        self.summary_label.setText(text)
        self._update_buttons()

    def _fill_row(self, row: int, info: StoredFileInfo) -> None:
        used = (
            ", ".join(ref.location for ref in info.references)
            if info.is_referenced
            else UNUSED_TEXT
        )
        cells = (info.name, info.content_type, _format_size(info.size), used)
        for column, text in enumerate(cells):
            item = QTableWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, info.name)
            if not info.is_referenced:
                font = QFont(item.font())
                font.setItalic(True)
                item.setFont(font)
            self.table.setItem(row, column, item)

    def selected_names(self) -> list[str]:
        """The names of the selected files, in the order of the rows."""
        names: list[str] = []
        for item in sorted(
            self.table.selectedItems(), key=QTableWidgetItem.row
        ):
            name = item.data(Qt.ItemDataRole.UserRole)
            if isinstance(name, str) and name not in names:
                names.append(name)
        return names

    def selected_name(self) -> str | None:
        """The name of the selected file, or None unless exactly one is."""
        names = self.selected_names()
        return names[0] if len(names) == 1 else None

    def _update_buttons(self) -> None:
        has_package = self._package is not None
        editing = edit_mode().is_editing
        name = self.selected_name()
        text = bool(
            has_package
            and name is not None
            and self._package is not None
            and name in self._package.fileStore
            and part_names.is_text_type(
                self._package.fileStore.get_content_type(name)
            )
        )
        self.add_button.setEnabled(has_package and editing)
        self.new_button.setEnabled(has_package and editing)
        self.edit_button.setEnabled(text and editing)
        for button in (self.rename_button, self.move_button):
            button.setEnabled(name is not None and editing)
        self.remove_button.setEnabled(bool(self.selected_names()) and editing)
        self.save_button.setEnabled(name is not None)
        self.dangling_button.setEnabled(has_package)
        self.thumbnail_button.setEnabled(has_package and editing)

    # -- the buttons -------------------------------------------------------------

    def _controller(self) -> FileController | None:
        if self._package is None:
            return None
        return FileController(self._package, self)

    def _add(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.add_from_disk()

    def _new_text(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.new_text_file()

    def _edit(self) -> None:
        controller = self._controller()
        name = self.selected_name()
        if controller is not None and name is not None:
            controller.edit_text(name)

    def _rename(self) -> None:
        controller = self._controller()
        name = self.selected_name()
        if controller is not None and name is not None:
            controller.rename(name)

    def _move(self) -> None:
        controller = self._controller()
        name = self.selected_name()
        if controller is not None and name is not None:
            controller.move(name)

    def _remove(self) -> None:
        controller = self._controller()
        names = self.selected_names()
        if controller is not None and names:
            controller.remove_many(names)

    def _save(self) -> None:
        controller = self._controller()
        name = self.selected_name()
        if controller is not None and name is not None:
            controller.save_to_disk(name)

    def _thumbnail(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.change_package_thumbnail()

    def _dangling(self) -> None:
        controller = self._controller()
        if controller is not None:
            controller.repair_dangling()

    def _on_double_clicked(self, item: QTableWidgetItem) -> None:
        del item
        if self.edit_button.isEnabled():
            self._edit()


def _format_size(size: int) -> str:
    """Shows a number of bytes as text, such as `1.5 KiB`."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KiB"
    return f"{size / (1024 * 1024):.1f} MiB"


class PackageFilesDock(QDockWidget):
    """The panel in a dock window, hidden until the user asks for it.

    Attributes:
        panel: The panel of the files.
    """

    def __init__(
        self,
        package_provider: Callable[[], FilePackage | None],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dock.

        Args:
            package_provider: Returns the package to show, or None.
            parent: The main window.
        """
        super().__init__("Package files", parent)
        self.setObjectName("packageFilesDock")
        self.panel = PackageFilesPanel(package_provider, self)
        self.setWidget(self.panel)
        self.hide()

    def show_package(self, package: FilePackage | None) -> None:
        """Shows the dock with the files of a package."""
        self.panel.set_package(package)
        self.show()
        self.raise_()
