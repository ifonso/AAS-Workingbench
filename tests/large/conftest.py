"""Keeps what one large test leaves behind from reaching the next one."""

from collections.abc import Iterator

import pytest


@pytest.fixture(autouse=True)
def forget_saved_docks(qapp: object) -> Iterator[None]:
    """Removes the saved arrangement of the docks before and after a test.

    A window that closes saves where its docks are, in the settings file that
    the program uses, and the next window restores it. A test that showed a
    panel would then start the next test with that panel open.
    """
    from aas_editor.settings.app_settings import SETTINGS
    from aas_editor.settings.app_settings import AppSettings

    SETTINGS.remove(AppSettings.DOCK_STATE.name)
    yield
    SETTINGS.remove(AppSettings.DOCK_STATE.name)


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
