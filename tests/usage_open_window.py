"""Opens the real main window for a test that uses it as a person would.

The window is the one that `__main__` builds: every feature registers its
actions first, and the window opens a file as the File menu does. Native file
dialogs and modal dialogs cannot run offscreen, so they are replaced by a
`Screen` that writes down what the person would have seen and answers with
what the test says. The test never calls the model or the operations.
"""

from collections.abc import Callable
from collections.abc import Iterator
import contextlib
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from types import SimpleNamespace

from basyx.aas import model
import pyecma376_2
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.factories import make_asset_information
from tests.factories import make_concept_description
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx


@dataclass
class Shown:
    """What one dialog showed the person."""

    kind: str
    title: str
    texts: list[str] = field(default_factory=list)
    details: str = ""

    @property
    def text(self) -> str:
        """All the words of the dialog, in one string."""
        return "\n".join(self.texts)


class Screen:
    """What the person saw, and what they answered.

    Attributes:
        shown: Every dialog that opened, in order.
        box_answer: The button that a message box is closed with.
        dialog_accepts: Whether other dialogs are accepted.
        open_paths: The files that the Open dialog returns, one for each call.
        save_paths: The files that the Save dialog returns, one for each call.
    """

    def __init__(self) -> None:
        self.shown: list[Shown] = []
        self.box_answer = QMessageBox.StandardButton.Yes
        self.dialog_accepts = True
        self.open_paths: list[str] = []
        self.save_paths: list[str] = []

    def titles(self) -> list[str]:
        """The titles of the dialogs that opened."""
        return [entry.title for entry in self.shown]

    def last(self) -> Shown:
        """The dialog that opened last."""
        return self.shown[-1]

    def forget(self) -> None:
        """Clears the list, to look at what the next step shows."""
        self.shown.clear()


def _words_of(dialog: QDialog) -> list[str]:
    words = [label.text() for label in dialog.findChildren(QLabel)]
    for listing in dialog.findChildren(QListWidget):
        words += [
            listing.item(row).text()  # pyright: ignore[reportOptionalMemberAccess]
            for row in range(listing.count())
        ]
    return [word for word in words if word]


def install_screen(monkeypatch: pytest.MonkeyPatch) -> Screen:
    """Replaces the modal dialogs and the native file dialogs by a `Screen`."""
    screen = Screen()

    def box_exec(box: QMessageBox) -> int:
        screen.shown.append(
            Shown(
                "message box",
                box.windowTitle(),
                [box.text(), box.informativeText()],
                box.detailedText(),
            )
        )
        return screen.box_answer.value

    def static_box(kind: str) -> Callable[..., QMessageBox.StandardButton]:
        def show(
            parent: object = None,
            title: str = "",
            text: str = "",
            *args: object,
            **kwargs: object,
        ) -> QMessageBox.StandardButton:
            screen.shown.append(Shown(kind, title, [text]))
            return screen.box_answer

        return show

    def dialog_exec(dialog: QDialog) -> int:
        screen.shown.append(
            Shown(
                type(dialog).__name__, dialog.windowTitle(), _words_of(dialog)
            )
        )
        result = (
            QDialog.DialogCode.Accepted
            if screen.dialog_accepts
            else QDialog.DialogCode.Rejected
        )
        dialog.setResult(result.value)
        return result.value

    def next_path(paths: list[str]) -> tuple[str, str]:
        if not paths:
            raise AssertionError("A file dialog opened and no path was set")
        return paths.pop(0), ""

    monkeypatch.setattr(QMessageBox, "exec", box_exec)
    for kind in ("question", "warning", "information", "critical"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(static_box(kind)))
    monkeypatch.setattr(QDialog, "exec", dialog_exec)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *a, **k: next_path(screen.open_paths)),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: next_path(screen.save_paths)),
    )
    return screen


def register_every_action() -> Callable[[], None]:
    """Registers what `__main__.main` registers, and returns the way to undo it."""
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.blob_actions import register_blob_actions
    from aas_workingbench.ui.bulk_actions import register_bulk_actions
    from aas_workingbench.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_workingbench.ui.concept_actions import register_concept_actions
    from aas_workingbench.ui.conversion_actions import (
        register_conversion_actions,
    )
    from aas_workingbench.ui.create_actions import register_create_actions
    from aas_workingbench.ui.file_actions import register_file_actions
    from aas_workingbench.ui.load_report_actions import (
        register_load_report_actions,
    )
    from aas_workingbench.ui.location_actions import register_location_actions
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions
    from aas_workingbench.ui.preset_actions import register_preset_actions
    from aas_workingbench.ui.reference_actions import register_reference_actions
    from aas_workingbench.ui.reference_jump import register_jump_actions
    from aas_workingbench.ui.shell_copy_actions import (
        register_shell_copy_actions,
    )

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
        # A ValueError says that an earlier test did not undo its actions.
        with contextlib.suppress(ValueError):
            register()

    def undo() -> None:
        for spec in default_registry().specs_for(ViewKind.ANY):
            if spec.action_id not in before:
                default_registry().unregister(spec.action_id)

    return undo


def open_window(qtbot: object, path: Path | None = None) -> SimpleNamespace:
    """Opens the main window, with one file when `path` is given."""
    from aas_workingbench.editorApp import EditorApp

    window = EditorApp(fileToOpen=path.as_posix() if path else None)
    qtbot.addWidget(window)  # pyright: ignore[reportAttributeAccessIssue]
    window.show()
    return SimpleNamespace(
        window=window,
        view=window.mainTreeView,
        tabs=window.mainTabWidget,
        model=window.packTreeModel,
    )


def close_window(editor: SimpleNamespace) -> None:
    """Closes a window that may hold changes, without asking to save them."""
    for package in editor.model.openedPacks():
        package.commandStack.mark_saved()
    editor.view.updateWindowModified()
    editor.window._recoveryTimer.stop()
    editor.window.close()


@pytest.fixture
def screen(monkeypatch: pytest.MonkeyPatch) -> Screen:
    """The dialogs of one test."""
    return install_screen(monkeypatch)


@pytest.fixture
def every_action(qapp: object) -> Iterator[None]:
    """Gives the window every action that the program registers."""
    undo = register_every_action()
    yield
    undo()


def all_rows(view: object) -> Iterator[QModelIndex]:
    """Walks the visible tree, depth first, and expands what it passes."""
    proxy = view.model()  # pyright: ignore[reportAttributeAccessIssue]

    def walk(parent: QModelIndex) -> Iterator[QModelIndex]:
        for row in range(proxy.rowCount(parent)):
            child = proxy.index(row, 0, parent)
            yield child
            yield from walk(child)

    yield from walk(QModelIndex())


def row_named(view: object, *names: str, package: int = 0) -> QModelIndex:
    """Finds a row below a package by the names that the editor finds it by."""
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = view.model()  # pyright: ignore[reportAttributeAccessIssue]
    index = proxy.index(package, 0)
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(NAME_ROLE) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def column_of(view: object, title: str) -> int:
    """The number of a column of the tree, by its title."""
    source = view.sourceModel()  # pyright: ignore[reportAttributeAccessIssue]
    titles = [
        source.headerData(i, Qt.Orientation.Horizontal, 0)
        for i in range(source.columnCount())
    ]
    return titles.index(title)


DOCUMENT = "/aasx/files/document.pdf"
SHELL_THUMBNAIL = "/aasx/files/shell.png"
PACKAGE_THUMBNAIL = "/package-thumbnail.png"


def write_pump_package(path: Path) -> Path:
    """Writes an AASX with a stored file, thumbnails and package properties."""
    submodel = make_submodel(
        elements=[
            make_property("Name", "pump"),
            make_file_element("Manual", DOCUMENT, "application/pdf"),
        ]
    )
    shell = make_shell(
        submodels=[submodel],
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(SHELL_THUMBNAIL, "image/png")
        ),
    )
    properties = pyecma376_2.OPCCoreProperties()
    properties.title = "Pump package"
    properties.creator = "The owner"
    return write_aasx(
        path,
        make_store(shell, submodel, make_concept_description()),
        files={
            DOCUMENT: (b"%PDF-1.4 manual", "application/pdf"),
            SHELL_THUMBNAIL: (b"\x89PNG shell", "image/png"),
        },
        thumbnail=(PACKAGE_THUMBNAIL, b"\x89PNG package", "image/png"),
        core_properties=properties,
    )
