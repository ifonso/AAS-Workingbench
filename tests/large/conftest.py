"""Keeps what one large test leaves behind from reaching the next one."""

from collections.abc import Iterator

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
