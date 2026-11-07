"""A save that fails leaves the file as it was and says why in plain words.

The target is made read-only, locked by another program (Windows only), or put
in a folder that does not exist. The package is changed in the window and saved
through the Save and Save As actions. Afterwards the original is compared byte
for byte, no temporary file is left, the window still holds the change, and a
save that can work does work.
"""

from collections.abc import Callable
from collections.abc import Iterator
import ctypes
from pathlib import Path
import shutil
import stat
import sys

from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_window import close_window
from tests.usage_window import column_of
from tests.usage_window import every_action  # noqa: F401
from tests.usage_window import open_window
from tests.usage_window import row_named
from tests.usage_window import screen  # noqa: F401

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

THREAD_SYSTEM = (
    "submodels",
    "CapabilityDescription",
    "CapabilitySet",
    "ScrewingRequestedContainer",
    "ScrewingFastenerRequirementSet",
    "ThreadSystemContainer",
    "ThreadSystem",
)


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, screen, every_action):  # noqa: F811
    """The window with a package that has an unsaved change."""
    source = tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", source)
    shown = open_window(qtbot)
    screen.open_paths.append(source.as_posix())
    shown.view.openPackAct.trigger()
    shown.source = source
    shown.screen = screen
    shown.tmp_path = tmp_path
    shown.before = source.read_bytes()
    (shown.package,) = shown.model.openedPacks()
    view = shown.view
    cell = row_named(view, *THREAD_SYSTEM).siblingAtColumn(
        column_of(view, "value")
    )
    assert view.model().setData(cell, "other", Qt.ItemDataRole.EditRole)
    view.setCurrentIndex(row_named(view, *THREAD_SYSTEM))
    assert shown.package.changed
    yield shown
    close_window(shown)


@pytest.fixture
def locked() -> Iterator[object]:
    """Locks a file as a program that has it open does, until the end."""
    if sys.platform != "win32":
        pytest.skip("Another program locks a file like this on Windows only")
    held: list[int] = []

    def release() -> None:
        while held:
            ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(held.pop()))

    def lock(path: Path) -> Callable[[], None]:
        kernel = ctypes.windll.kernel32
        kernel.CreateFileW.restype = ctypes.c_void_p
        handle = kernel.CreateFileW(
            str(path), 0x80000000 | 0x40000000, 0, None, 3, 0x80, None
        )
        assert handle not in (None, ctypes.c_void_p(-1).value)
        held.append(handle)
        return release

    yield lock
    release()


def _leftovers(editor) -> list[str]:
    return sorted(p.name for p in editor.tmp_path.iterdir())


def test_a_read_only_file_is_not_saved_and_the_reason_is_said(editor) -> None:
    editor.source.chmod(stat.S_IREAD)

    try:
        editor.view.saveAct.trigger()
    finally:
        editor.source.chmod(stat.S_IWRITE | stat.S_IREAD)

    refusal = editor.screen.last()
    assert refusal.title == "Package was not saved"
    assert "Requester_screwing.aasx could not be written" in refusal.texts[0]
    assert "read-only, or another program has it open" in refusal.texts[0]
    assert "Your changes are still in the editor" in refusal.texts[0]
    assert editor.source.read_bytes() == editor.before
    assert _leftovers(editor) == ["Requester_screwing.aasx"]
    assert editor.package.changed
    assert editor.package.file == editor.source.absolute()


def test_a_file_that_another_program_has_open_is_not_saved_and_then_is(
    editor, locked
) -> None:
    release = locked(editor.source)

    editor.view.saveAct.trigger()
    release()

    assert editor.screen.last().title == "Package was not saved"
    assert editor.source.read_bytes() == editor.before
    assert _leftovers(editor) == ["Requester_screwing.aasx"]
    assert editor.package.changed
    editor.view.saveAct.trigger()
    assert not editor.package.changed


def test_a_folder_that_is_gone_is_said_and_the_package_keeps_its_file(
    editor,
) -> None:
    gone = editor.tmp_path / "gone" / "copy.aasx"
    # The Save As dialog comes back after a failure, and the person gives up.
    editor.screen.save_paths.extend([gone.as_posix(), ""])

    editor.view.saveAsAct.trigger()

    refusal = editor.screen.last()
    assert refusal.title == "Package was not saved"
    assert f"The folder {gone.parent}" in refusal.texts[0]
    assert "does not exist" in refusal.texts[0]
    assert editor.package.file == editor.source.absolute()
    assert editor.source.read_bytes() == editor.before
    assert editor.package.changed


def test_the_save_that_failed_works_when_the_cause_is_gone(editor) -> None:
    editor.source.chmod(stat.S_IREAD)
    editor.view.saveAct.trigger()
    editor.source.chmod(stat.S_IWRITE | stat.S_IREAD)
    assert editor.package.changed

    editor.view.saveAct.trigger()

    assert not editor.package.changed
    assert editor.source.read_bytes() != editor.before
