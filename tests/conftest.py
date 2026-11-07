"""Shared fixtures and test-size classification for the whole test suite."""

from collections.abc import Iterator
import contextlib
import os
from pathlib import Path
import sys

import pytest

# Must be set before Qt loads so tests never need a real display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# QtWebEngine must be imported before any QApplication exists, or importing the
# widgets and tree views later fails. Without it, only those tests are skipped.
with contextlib.suppress(ImportError):
    import PyQt6.QtWebEngineWidgets  # noqa: E402, F401

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtWidgets import QDialog  # noqa: E402
from PyQt6.QtWidgets import QMessageBox  # noqa: E402

TESTS_DIR = Path(__file__).parent
TEST_DATA_DIR = TESTS_DIR / "data"
SIZE_MARKERS = ("small", "medium", "large")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Marks each test with its size, taken from its directory under tests/."""
    for item in items:
        relative_path = item.path.relative_to(TESTS_DIR)
        size = relative_path.parts[0]
        if size not in SIZE_MARKERS:
            raise pytest.UsageError(
                f"Test outside a size directory: '{relative_path}'"
            )
        item.add_marker(size)


@pytest.fixture(autouse=True)
def stub_modal_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dismisses modal dialogs as if the user had cancelled them.

    A modal dialog blocks the event loop for good, so a test that opens one
    would hang. This includes the error box of the exception hook. A test that
    needs the dialog's text replaces `exec` itself.
    """
    for dialog_class in (QDialog, QMessageBox):
        monkeypatch.setattr(
            dialog_class, "exec", lambda self: QDialog.DialogCode.Rejected
        )


@pytest.fixture(autouse=True)
def edit_mode_on() -> Iterator[None]:
    """Starts every test in Edit mode, which is global state of the editor."""
    from aas_editor.application.editing import edit_mode

    edit_mode().set_editing(True)
    yield
    edit_mode().set_editing(True)


@pytest.fixture(autouse=True)
def hints_mode_on() -> Iterator[None]:
    """Starts every test with hints on, which is global state of the editor."""
    from aas_editor.application.hints import hints_mode

    hints_mode().set_on(True)
    yield
    hints_mode().set_on(True)


@pytest.fixture(autouse=True)
def hint_kinds_on() -> Iterator[None]:
    """Starts every test with every kind of hint on, which is global state.

    It is set without saving, so a test that saves kinds to its own settings
    can load them again as a new session does.
    """
    from aas_editor.application.hints import hint_kinds

    hint_kinds().load(())
    yield
    hint_kinds().load(())


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Provides the session-wide QApplication.

    Every test that imports aas_editor must request it, because
    aas_editor.settings.app_settings creates QFont, QSize and QIcon objects at
    import time, which require an active QApplication.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    # The editor names Inter, which Qt finds only once the file is registered.
    # Without it a test that measures text would measure a fallback font, and
    # the numbers would depend on which test registered the font first.
    from aas_editor.ui.theme.fonts import install_fonts

    install_fonts()
    yield app


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    return TEST_DATA_DIR


@pytest.fixture(scope="session")
def aasx_file() -> Path:
    return TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture(scope="session")
def json_file() -> Path:
    return TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.json"


@pytest.fixture(scope="session")
def own_settings(
    qapp: QApplication, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    """Points the program's settings at files of the test session.

    The program keeps its settings in `settings.ini` next to the code, and the
    recent files and recent commands of the user in the registry on Windows. A
    test that opens a window or a package writes there, and what it writes then
    shows up in the start panel of the person who ran the tests. Both stores
    are replaced for the whole session, because a window of a module-scoped
    fixture writes when it closes, after the test that made it.
    """
    from PyQt6.QtCore import QSettings

    from aas_editor.settings import app_settings

    folder = tmp_path_factory.mktemp("settings")
    patches = pytest.MonkeyPatch()
    patches.setattr(
        app_settings,
        "SETTINGS",
        QSettings(str(folder / "settings.ini"), QSettings.Format.IniFormat),
    )
    patches.setattr(
        app_settings,
        "RECENT_SETTINGS",
        QSettings(str(folder / "recent.ini"), QSettings.Format.IniFormat),
    )
    yield
    patches.undo()


@pytest.fixture
def empty_settings(own_settings: None) -> Iterator[None]:
    """Starts a test with nothing saved, and leaves nothing for the next."""
    from aas_editor.settings import app_settings

    app_settings.SETTINGS.clear()
    app_settings.RECENT_SETTINGS.clear()
    yield
    app_settings.SETTINGS.clear()
    app_settings.RECENT_SETTINGS.clear()
