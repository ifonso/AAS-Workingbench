"""The counts and F8 in the real main window."""

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
    counts = count_findings(service_for(editor.package).report)

    assert not editor.controller.dock.isVisible()
    assert status.parent() is editor.window.statusBar()
    assert status.isVisible()
    assert status.counts == counts
    assert counts.findings > 0
    # The package has hints, and the status bar does not count them: the
    # package row is current, which has none of its own.
    assert status.hints_button.isHidden()


def test_f8_and_shift_f8_have_one_owner_each_in_the_window(editor) -> None:
    from PyQt6.QtGui import QAction
    from PyQt6.QtGui import QShortcut

    def owners(key: str) -> list[object]:
        wanted = QKeySequence(key)
        found: list[object] = [
            a
            for a in editor.window.findChildren(QAction)
            if wanted in a.shortcuts()
        ]
        found += [
            s
            for s in editor.window.findChildren(QShortcut)
            if s.key() == wanted
        ]
        return found

    assert owners("F8") == [editor.controller.next_finding_action]
    assert owners("Shift+F8") == [editor.controller.previous_finding_action]


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


def _hints_of(editor, obj: object) -> int:
    """How many hints the SDK-level report has about an object."""
    from aas_editor.application.validation import is_hint
    from aas_editor.ui.validation_service import service_for

    report = service_for(editor.package).hint_report
    return sum(1 for f in report.findings if is_hint(f) and f.anchor is obj)


def _rows_with_and_without_hints(editor) -> tuple[list, list]:
    from tests.usage_open_window import all_rows

    editor.view.expandAll()
    # The row of the package has no hint of its own, and every element of this
    # template has some.
    with_hints, without = [], [editor.view.model().index(0, 0)]
    for index in all_rows(editor.view):
        obj = index.data(OBJECT_ROLE)
        if obj is None or not hasattr(obj, "id_short"):
            continue
        (with_hints if _hints_of(editor, obj) else without).append(index)
    return with_hints, without


def test_the_status_bar_counts_the_hints_of_the_row_that_is_current(
    editor,
) -> None:
    from PyQt6.QtTest import QTest

    QTest.qWait(300)
    with_hints, without = _rows_with_and_without_hints(editor)
    assert with_hints

    for index in with_hints[:5]:
        editor.view.setCurrentIndex(index)
        expected = _hints_of(editor, index.data(OBJECT_ROLE))
        status = editor.controller.status
        assert (
            status.hints_button.text()
            == f"{expected} hint{'' if expected == 1 else 's'} here"
        )
        assert status.hints_button.isVisible()
    assert without
    for index in without:
        editor.view.setCurrentIndex(index)
        assert not editor.controller.status.hints_button.isVisible()


def test_the_status_bar_follows_the_tab_when_the_tab_has_the_focus(
    editor,
) -> None:
    from PyQt6.QtTest import QTest

    QTest.qWait(300)
    with_hints, without = _rows_with_and_without_hints(editor)
    assert with_hints and without
    tabs = editor.window.mainTabWidget
    status = editor.controller.status
    # The tree no longer opens its row in the tab, so the two can differ.
    editor.view.autoScrollToSrcAct.setChecked(False)
    tabs.openItem(with_hints[0])
    editor.view.setCurrentIndex(without[0])

    editor.view.setFocus()
    QTest.qWait(50)
    in_tree = status.hints_here
    tabs.currentWidget().attrsTreeView.setFocus()
    QTest.qWait(50)
    in_tab = status.hints_here

    assert in_tree == 0
    assert in_tab == _hints_of(editor, with_hints[0].data(OBJECT_ROLE))
    assert in_tab > 0


def test_a_click_on_the_hints_of_the_row_opens_the_hints_view_of_the_package(
    editor,
) -> None:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    QTest.qWait(300)
    with_hints, _ = _rows_with_and_without_hints(editor)
    editor.view.setCurrentIndex(with_hints[0])

    QTest.mouseClick(
        editor.controller.status.hints_button, Qt.MouseButton.LeftButton
    )

    from aas_editor.ui.validation_dock import HINTS_VIEW

    dock = editor.controller.dock
    assert dock.isVisible()
    assert dock.current_view == HINTS_VIEW
    assert dock.hints_view.shown_count > _hints_of(
        editor, with_hints[0].data(OBJECT_ROLE)
    )
