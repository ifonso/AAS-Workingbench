"""The keys of Save, Save All and Find, and the status bar, in the real window."""

from pathlib import Path
import shutil
from types import SimpleNamespace

from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QShortcut
from PyQt6.QtTest import QTest
import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, monkeypatch):
    """The main window with one package, copied so a save cannot touch data."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui.save_warnings import IssuesDialog

    # A save that warns would wait for a person. Here the answer is yes.
    monkeypatch.setattr(IssuesDialog, "exec", lambda dialog: dialog.accept())

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
    editor.source = source
    (editor.package,) = window.packTreeModel.openedPacks()
    yield editor
    editor.package.commandStack.mark_saved()
    # Closing the window must not ask whether to save.
    editor.view.updateWindowModified()
    window._recoveryTimer.stop()
    window.close()


def _owners(window, key: str) -> list[object]:
    """Everything in the window that the key would run."""
    wanted = QKeySequence(key)
    owners: list[object] = [
        action
        for action in window.findChildren(QAction)
        if wanted in action.shortcuts()
    ]
    owners += [
        shortcut
        for shortcut in window.findChildren(QShortcut)
        if shortcut.key() == wanted
    ]
    return owners


def test_each_save_key_has_one_owner_in_the_window(editor) -> None:
    save = _owners(editor.window, "Ctrl+S")
    save_all = _owners(editor.window, "Ctrl+Shift+S")

    assert save == [editor.view.saveAct]
    assert save_all == [editor.view.saveAllAct]


def test_ctrl_s_saves_the_package(editor) -> None:
    editor.package.changed = True
    before = editor.source.stat().st_mtime_ns

    QTest.keySequence(editor.view, QKeySequence("Ctrl+S"))

    assert editor.source.stat().st_mtime_ns != before
    assert not editor.package.changed


def test_ctrl_shift_s_saves_all_packages(editor) -> None:
    editor.package.changed = True

    QTest.keySequence(editor.view, QKeySequence("Ctrl+Shift+S"))

    assert not editor.package.changed


def test_save_is_on_the_bar_and_save_all_is_in_the_file_menu(editor) -> None:
    # The plan keeps one Save on the bar, and Save All in File (phase H).
    bar = editor.window.toolBar.actions()
    file_menu = editor.window.menuFile.actions()

    assert editor.view.saveAct in bar
    assert editor.view.saveAllAct not in bar
    assert file_menu.index(editor.view.saveAct) < file_menu.index(
        editor.view.saveAllAct
    )


def test_the_status_bar_shows_the_mode_and_the_unsaved_packages(
    editor,
) -> None:
    window = editor.window
    saved = (
        window._modeStatusLabel.text(),
        window._unsavedStatusLabel.text(),
    )
    editor.package.changed = True
    editor.view.updateWindowModified()
    unsaved = window._unsavedStatusLabel.text()
    window.onEditModeChanged(False)
    mode = window._modeStatusLabel.text()
    # pytest-qt closes the window before the fixture ends, and a window with
    # unsaved changes would ask a question.
    editor.package.commandStack.mark_saved()
    editor.view.updateWindowModified()

    assert saved == ("Edit mode", "All changes saved")
    assert unsaved == "1 package with unsaved changes"
    assert mode == "Read mode"


def test_find_in_the_tree_opens_the_bar_of_the_tree(editor) -> None:
    window = editor.window
    editor.view.setFocus()

    QTest.keySequence(editor.view, QKeySequence("Ctrl+F"))

    assert window.searchBarPack.isVisible()
    assert window.searchBarPack.searchLine.hasFocus()


def test_find_in_a_tab_opens_the_bar_of_the_tab(editor) -> None:
    tab = editor.window.mainTabWidget.currentWidget()
    tab.attrsTreeView.setFocus()

    QTest.keySequence(tab.attrsTreeView, QKeySequence("Ctrl+F"))

    assert tab.searchBar.isVisible()
    assert not editor.window.searchBarPack.isVisible()
