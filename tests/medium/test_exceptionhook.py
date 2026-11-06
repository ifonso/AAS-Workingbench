"""The hook for uncaught exceptions."""

import sys

import pytest


@pytest.fixture
def exceptionhook(qapp: object, monkeypatch: pytest.MonkeyPatch):
    # Importing the module installs its hook. The patch restores the previous
    # hook when the test ends.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    from aas_editor.utils import exceptionhook

    monkeypatch.setattr(exceptionhook, "_on_crash_callback", None)
    return exceptionhook


@pytest.fixture
def shown_boxes(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Collects the text of message boxes instead of opening them."""
    from PyQt6.QtWidgets import QMessageBox

    texts: list[str] = []

    def fake_exec(box: QMessageBox) -> int:
        texts.append(box.text())
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    return texts


def test_hook_shows_error_and_returns_when_application_runs(
    exceptionhook, shown_boxes: list[str]
) -> None:
    error = ValueError("disk full")

    exceptionhook.handle_exception(ValueError, error, error.__traceback__)

    assert shown_boxes == [
        "An Exception was raised. Caught Exception: disk full"
    ]


def test_hook_saves_recovery_files_when_exception_is_raised(
    exceptionhook, shown_boxes: list[str]
) -> None:
    calls: list[str] = []
    exceptionhook.set_crash_callback(lambda: calls.append("recovery"))
    error = ValueError("disk full")

    exceptionhook.handle_exception(ValueError, error, error.__traceback__)

    assert calls == ["recovery"]


def test_hook_shows_traceback_text_when_exception_has_one(
    exceptionhook, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtWidgets import QMessageBox

    details: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: details.append(box.detailedText())
    )
    try:
        raise KeyError("missing")
    except KeyError as error:
        exceptionhook.handle_exception(KeyError, error, error.__traceback__)

    assert "KeyError: 'missing'" in details[0]
    assert "test_hook_shows_traceback_text" in details[0]
