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


@pytest.fixture(scope="session")
def qapp() -> Iterator[QApplication]:
    """Provides the session-wide QApplication.

    Every test that imports aas_editor must request it, because
    aas_editor.settings.app_settings creates QFont, QSize and QIcon objects at
    import time, which require an active QApplication.
    """
    app = QApplication.instance() or QApplication(sys.argv)
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
