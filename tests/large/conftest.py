"""Keeps what one large test leaves behind from reaching the next one."""

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def settings_of_the_test(empty_settings: None) -> None:
    """Gives each test settings of its own, empty at the start.

    A window that closes saves where its docks are, and the next window
    restores it, so a test that showed a panel would start the next test with
    that panel open. The settings file and the recent files were the user's
    own, and a test wrote its temporary paths into them: the start panel of
    the person who ran the tests then listed files that no longer exist.
    """


@pytest.fixture(autouse=True)
def release_modifier_keys(qapp: object) -> Iterator[None]:
    """Lets go of the modifier keys that a test left held down.

    `QTest.keySequence` presses Ctrl for a shortcut and does not release it on
    the offscreen platform, so `QGuiApplication.keyboardModifiers()` says Ctrl
    until the end of the process. A later test then selects and clicks with
    Ctrl held: `selectRow` toggles instead of selecting, and a dialog that a
    test drives does nothing. This showed only when a file that sends a key was
    followed by a file that drives a selection.
    """
    yield
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QWidget

    held = QGuiApplication.keyboardModifiers()
    if held == Qt.KeyboardModifier.NoModifier:
        return
    target = QWidget()
    for modifier, key in (
        (Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Control),
        (Qt.KeyboardModifier.ShiftModifier, Qt.Key.Key_Shift),
        (Qt.KeyboardModifier.AltModifier, Qt.Key.Key_Alt),
        (Qt.KeyboardModifier.MetaModifier, Qt.Key.Key_Meta),
    ):
        if held & modifier:
            QTest.keyRelease(target, key, Qt.KeyboardModifier.NoModifier)
    target.deleteLater()


@pytest.fixture
def author(
    qapp: object, qtbot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[object]:
    """The main window with no package open, as the application starts.

    The window is wrapped in an `Author`, which drives it as a person does.
    """
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from PyQt6.QtWidgets import QMessageBox
    from tests.authoring import Author
    from tests.authoring import register_every_action

    from aas_workingbench.editorApp import EditorApp

    register_every_action()
    # A window with changes asks whether to save when it closes, and waits.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
    )
    # A tab of a File or a Blob opens a preview in a Qt WebEngine view. Its
    # renderer crashes the process when it exits, so offscreen the tab keeps
    # the preview closed. The preview is not under test.
    from aas_workingbench.widgets.tab import TabWithTreeView

    monkeypatch.setattr(
        TabWithTreeView,
        "updateMediaWidget",
        lambda self: self.mediaViewWidget.hide(),
    )
    window = EditorApp()
    qtbot.addWidget(window)
    window.show()
    person = Author(window, monkeypatch, tmp_path)
    yield person
    # Closing must not ask about changes that the test left unsaved.
    for package in window.packTreeModel.openedPacks():
        package.commandStack.mark_saved()
    window._recoveryTimer.stop()
    window.close()
