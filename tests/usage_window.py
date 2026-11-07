"""Opens the real main window on a copy of a package, for the usage tests.

The usage tests in `tests/large` go through the window as a person does: menus,
keys, panels, tabs. They share how the window is made, what is replaced so that
no real dialog blocks offscreen, and how a row of the tree is found.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
import shutil
from typing import Any

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "aas_editor"
TEMPLATES = SOURCE_ROOT / "submodel_templates"

# The largest templates that open without a load report: 30 objects with
# 800 rows, and 251 objects. See `tests/large/test_usage_navigation.py`.
TECHNICAL_DATA = (
    TEMPLATES
    / "Technical_Data"
    / "2"
    / "0"
    / "1"
    / "IDTA 02003_2-0-1_Template_TechnicalData.aasx"
)
INFORMATION_FOR_USE = (
    TEMPLATES
    / "Intelligent Information  for Use"
    / "1"
    / "0"
    / "IDTA 02063-1-0_Template__IntelligentInformationForUse.aasx"
)


def _owner_package() -> Path:
    """Finds the package of the owner, one folder above the repository.

    It is looked for above this file, so a worktree finds it as well. Without
    it the tests that need it are skipped.
    """
    for folder in Path(__file__).resolve().parents:
        candidate = folder / "Requester_screwing.aasx"
        if candidate.exists():
            return candidate
    return Path("Requester_screwing.aasx")


REQUESTER = _owner_package()
CONTACT_INFORMATION = (
    TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"
)


@dataclass
class Box:
    """A message box that the window would have shown."""

    kind: str
    title: str
    text: str


@dataclass
class UsageWindow:
    """The window under test, and what it said in boxes.

    Attributes:
        window: The main window.
        view: The tree of packages.
        path: The copy of the package that the window opened.
        boxes: The message boxes in the order they were asked for.
    """

    window: Any
    view: Any
    path: Path
    boxes: list[Box] = field(default_factory=list)

    @property
    def package(self) -> Any:
        """The only package that the window has open."""
        (package,) = self.window.packTreeModel.openedPacks()
        return package

    @property
    def tab(self) -> Any:
        """The current tab."""
        return self.window.mainTabWidget.currentWidget()

    @property
    def status(self) -> str:
        """The message in the status bar now."""
        return self.window.statusBar().currentMessage()


def register_all_actions() -> list[str]:
    """Registers what `__main__` registers before the first window.

    Returns:
        The ids of the actions that this call added, so that a test can take
        them out again.
    """
    from aas_editor.ui.actions import ViewKind
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.blob_actions import register_blob_actions
    from aas_editor.ui.bulk_actions import register_bulk_actions
    from aas_editor.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_editor.ui.concept_actions import register_concept_actions
    from aas_editor.ui.conversion_actions import register_conversion_actions
    from aas_editor.ui.create_actions import register_create_actions
    from aas_editor.ui.file_actions import register_file_actions
    from aas_editor.ui.load_report_actions import register_load_report_actions
    from aas_editor.ui.location_actions import register_location_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions
    from aas_editor.ui.preset_actions import register_preset_actions
    from aas_editor.ui.reference_actions import register_reference_actions
    from aas_editor.ui.reference_jump import register_jump_actions
    from aas_editor.ui.shell_copy_actions import register_shell_copy_actions

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    for register in (
        register_blob_actions,
        register_file_actions,
        register_reference_actions,
        register_move_actions,
        register_paste_actions,
        register_jump_actions,
        register_create_actions,
        register_shell_copy_actions,
        register_bulk_actions,
        register_concept_actions,
        register_conversion_actions,
        register_bulk_edit_actions,
        register_preset_actions,
        register_load_report_actions,
        register_location_actions,
    ):
        register()
    after = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    return sorted(after - before)


def unregister_actions(action_ids: list[str]) -> None:
    """Takes actions out of the registry again."""
    from aas_editor.ui.actions import default_registry

    for action_id in action_ids:
        default_registry().unregister(action_id)


def stub_message_boxes(
    monkeypatch: pytest.MonkeyPatch, answer: Any = None
) -> list[Box]:
    """Replaces the static message boxes, which `exec` stubs do not reach.

    Args:
        monkeypatch: The fixture of the test.
        answer: The button that every box returns. By default `No`.

    Returns:
        The list that each box is appended to.
    """
    boxes: list[Box] = []
    reply = QMessageBox.StandardButton.No if answer is None else answer

    def make(kind: str) -> Any:
        def box(
            parent: Any = None,
            title: str = "",
            text: str = "",
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            boxes.append(Box(kind, title, text))
            return reply

        return staticmethod(box)

    for kind in ("critical", "information", "warning", "question"):
        monkeypatch.setattr(QMessageBox, kind, make(kind))
    # The pickers of the system block the event loop as well. A person who
    # cancels them gets an empty answer.
    for name in ("getItem", "getText", "getInt", "getDouble"):
        monkeypatch.setattr(
            QInputDialog, name, staticmethod(lambda *a, **k: ("", False))
        )
    for name in ("getOpenFileName", "getSaveFileName"):
        monkeypatch.setattr(
            QFileDialog, name, staticmethod(lambda *a, **k: ("", ""))
        )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "")
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([], ""))
    )
    return boxes


def record_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Notes every dialog that opens, and cancels it as a person can.

    Args:
        monkeypatch: The fixture of the test.

    Returns:
        The list that each dialog is appended to: the class name of a dialog,
        and `box: ` followed by the text of a message box.
    """
    from PyQt6.QtWidgets import QDialog

    seen: list[str] = []

    def dialog(self: Any) -> Any:
        seen.append(type(self).__name__)
        return QDialog.DialogCode.Rejected

    def box(self: Any) -> Any:
        seen.append(f"box: {self.text()} {self.detailedText()}")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QDialog, "exec", dialog)
    monkeypatch.setattr(QMessageBox, "exec", box)
    return seen


def open_window(
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    source: Path,
) -> Iterator[UsageWindow]:
    """Opens the main window on a copy of a package, and closes it after.

    The save asks nothing, so a test that saves is not blocked.

    Args:
        qtbot: The pytest-qt fixture.
        monkeypatch: The fixture of the test.
        tmp_path: Where the copy goes.
        source: The package to copy. It is never written.

    Yields:
        The window with its copy.
    """
    from aas_editor.editorApp import EditorApp

    boxes = stub_message_boxes(monkeypatch)
    monkeypatch.setattr(
        "aas_editor.treeviews.treeview_pack.confirm_save",
        lambda check, parent=None, extra=None: True,
    )
    copy = tmp_path / source.name
    shutil.copy(source, copy)
    window = EditorApp(fileToOpen=copy.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitActive(window)
    QApplication.processEvents()
    opened = UsageWindow(window, window.mainTreeView, copy, boxes)
    yield opened
    for package in window.packTreeModel.openedPacks():
        package.commandStack.mark_saved()
    window.mainTreeView.updateWindowModified()
    window._recoveryTimer.stop()
    window.close()


def find_row(view: Any, *names: str) -> QModelIndex:
    """Finds a row by the names of its path, from the package down.

    A name is the name role of a row, the idShort or the id, or its text.

    Raises:
        LookupError: If a name is not below the one before it.
    """
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    index = QModelIndex()
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if name in (child.data(NAME_ROLE), child.data()):
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def find_first(view: Any, name: str) -> QModelIndex:
    """Finds the first row of a name, looking wide before deep."""
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    queue = [QModelIndex()]
    while queue:
        parent = queue.pop(0)
        for row in range(proxy.rowCount(parent)):
            child = proxy.index(row, 0, parent)
            if name in (child.data(NAME_ROLE), child.data()):
                return child
            queue.append(child)
    raise LookupError(name)


def all_rows(view: Any) -> list[QModelIndex]:
    """Lists every row of a tree that is built, in the order of the tree."""
    proxy = view.model()
    found: list[QModelIndex] = []

    def walk(parent: QModelIndex) -> None:
        for row in range(proxy.rowCount(parent)):
            child = proxy.index(row, 0, parent)
            found.append(child)
            walk(child)

    walk(QModelIndex())
    return found


def select(view: Any, *indexes: QModelIndex) -> None:
    """Selects rows as a click with Ctrl does, and makes the last current."""
    selection = view.selectionModel()
    selection.clear()
    for index in indexes:
        selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(
        indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
    )
    view.updateActions(view.currentIndex())
    QApplication.processEvents()


def release_clipboard() -> None:
    """Empties the clipboard, which the whole process shares."""
    QApplication.clipboard().clear()


def press(
    key: Qt.Key,
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    """Sends a key to the widget that has the focus."""
    target = QApplication.focusWidget() or QApplication.activeWindow()
    QTest.keyClick(target, key, modifier)
