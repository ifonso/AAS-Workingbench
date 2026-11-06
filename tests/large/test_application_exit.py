"""The application closes without an error, through its real entry point.

It runs in its own process, because a failure while Qt destroys the objects of
the application shows only when the process ends. An error then either aborts
the process, or opens a message box that keeps it from ending.
"""

from pathlib import Path
import subprocess
import sys

import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02002-1-0_Template_ContactInformation.aasx"

_DRIVER = """
import sys

from PyQt6 import QtWebEngineWidgets
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox

run_event_loop = QApplication.exec


def quit_soon(*_):
    QTimer.singleShot(1000, QApplication.instance().quit)
    return run_event_loop()


def report(box):
    print("MESSAGE BOX:", box.text(), flush=True)
    return QMessageBox.StandardButton.Ok


QApplication.exec = quit_soon
QMessageBox.exec = report

from aas_editor.__main__ import main

main()
"""


# The order in which Qt destroys the objects varies, so one run can miss an error.
@pytest.mark.parametrize("attempt", range(3))
def test_closing_the_application_with_an_open_package_ends_cleanly(
    attempt: int, tmp_path: Path
) -> None:
    del attempt
    finished = subprocess.run(
        [sys.executable, "-c", _DRIVER, str(TEST_DATA_DIR / PACKAGE)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert "MESSAGE BOX" not in finished.stdout
    assert finished.returncode == 0
