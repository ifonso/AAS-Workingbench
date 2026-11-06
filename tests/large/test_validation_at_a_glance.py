"""The counts, F8 and the palette key in the real main window."""

from pathlib import Path
import shutil
from types import SimpleNamespace

from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
import pytest
from tests.conftest import TEST_DATA_DIR

from aas_editor.settings.app_settings import OBJECT_ROLE

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path):
    """The main window with one package that has findings."""
    from aas_editor.editorApp import EditorApp

    source = tmp_path / PACKAGE
    shutil.copy(TEST_DATA_DIR / PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitActive(window)

    editor = SimpleNamespace()
    editor.window = window
    editor.view = window.mainTreeView
    editor.controller = window.validationController
    (editor.package,) = window.packTreeModel.openedPacks()
    yield editor
    window._recoveryTimer.stop()
    window.close()


def test_the_counts_are_in_the_status_bar_with_the_panel_hidden(editor) -> None:
    from aas_editor.application.validation import count_findings
    from aas_editor.ui.validation_service import service_for

    status = editor.controller.status
    counts = count_findings(service_for(editor.package).hint_report)

    assert not editor.controller.dock.isVisible()
    assert status.parent() is editor.window.statusBar()
    assert status.isVisible()
    assert status.counts == counts
    assert counts.findings > 0


def test_f8_goes_to_a_finding_in_the_package_tree(editor) -> None:
    from aas_editor.ui.validation_service import service_for

    first = service_for(editor.package).report.findings[0]
    editor.view.setFocus()

    QTest.keySequence(editor.view, QKeySequence("F8"))

    assert editor.view.currentIndex().data(OBJECT_ROLE) is first.anchor


def test_a_click_on_the_counts_shows_the_panel(editor) -> None:
    from PyQt6.QtCore import Qt

    QTest.mouseClick(
        editor.controller.status.findings_button, Qt.MouseButton.LeftButton
    )

    assert editor.controller.dock.isVisible()
    assert editor.controller.dock.report.findings
