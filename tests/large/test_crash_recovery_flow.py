"""Work that was not saved when the editor died comes back at the next start.

The first window is edited, and the recovery write that its timer and its crash
handler make is called. The window is then left as a crash leaves it: no close,
no question, no cleanup. A second window starts the way the program starts with
no file given, finds the recovery file, and asks. The answers of the person
decide what is restored and what is thrown away.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_open_window import DOCUMENT
from tests.usage_open_window import close_window
from tests.usage_open_window import column_of
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import row_named
from tests.usage_open_window import screen  # noqa: F401
from tests.usage_open_window import write_pump_package

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

THREAD_SYSTEM = (
    "submodels",
    "CapabilityDescription",
    "CapabilitySet",
    "ScrewingRequestedContainer",
    "ScrewingFastenerRequirementSet",
    "ThreadSystemContainer",
    "ThreadSystem",
)
PUMP_NAME = ("submodels", "Submodel", "Name")


@pytest.fixture
def session(
    qapp: object,
    qtbot,
    tmp_path: Path,
    screen,  # noqa: F811
    every_action,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
):
    """A folder for the recovery files, and a way to start and crash a window."""
    recovery = tmp_path / "recovery"
    monkeypatch.setattr("aas_editor.editorApp.RECOVERY_DIR", recovery)
    monkeypatch.setattr(
        "aas_editor.treeviews.treeview_pack.RECOVERY_DIR", recovery
    )
    windows: list[SimpleNamespace] = []

    def start(path: Path | None = None) -> SimpleNamespace:
        shown = open_window(qtbot, path)
        windows.append(shown)
        return shown

    shown = SimpleNamespace(
        start=start,
        recovery=recovery,
        tmp_path=tmp_path,
        screen=screen,
    )
    yield shown
    # Closing a window that holds changes asks. The answer is to discard.
    screen.box_answer = QMessageBox.StandardButton.No
    for window in windows:
        window.window._recoveryTimer.stop()
        for package in window.model.openedPacks():
            package.commandStack.mark_saved()
        close_window(window)


def _set(window: SimpleNamespace, names: tuple[str, ...], text: str) -> None:
    view = window.view
    cell = row_named(view, *names).siblingAtColumn(column_of(view, "value"))
    assert view.model().setData(cell, text, Qt.ItemDataRole.EditRole)
    view.setCurrentIndex(row_named(view, *names))


def _value(package, names: tuple[str, ...]) -> object:
    (submodel,) = list(package.submodels)
    return submodel.get_referable(list(names[2:])).value


def _crash_with_change(session, source: Path, names, text: str) -> None:
    """Opens the file, changes it, writes the recovery, and drops the window."""
    first = session.start(source)
    _set(first, names, text)
    first.window._save_recovery_files()
    first.window._recoveryTimer.stop()


def _restart(session) -> SimpleNamespace:
    session.screen.forget()
    return session.start()


@pytest.fixture
def requester(session) -> Path:
    path = session.tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", path)
    return path


def test_the_recovery_file_is_written_for_a_package_with_changes_only(
    session, requester
) -> None:
    first = session.start(requester)
    first.window._save_recovery_files()
    nothing_yet = (
        list(session.recovery.glob("*")) if session.recovery.exists() else []
    )

    _set(first, THREAD_SYSTEM, "other")
    first.window._save_recovery_files()

    assert nothing_yet == []
    assert sorted(p.suffix for p in session.recovery.glob("*.json")) == [
        ".json",
        ".json",
    ]


def test_yes_restores_the_unsaved_change_and_leaves_the_file_alone(
    session, requester
) -> None:
    before = requester.read_bytes()
    _crash_with_change(session, requester, THREAD_SYSTEM, "other")

    second = _restart(session)

    question = session.screen.shown[0]
    assert question.kind == "question"
    assert question.title == "Restore unsaved changes"
    assert "Requester_screwing.aasx" in question.text
    (package,) = second.model.openedPacks()
    assert _value(package, THREAD_SYSTEM) == "other"
    assert package.changed
    assert second.window.isWindowModified()
    assert (
        second.window._unsavedStatusLabel.text()
        == "1 package with unsaved changes"
    )
    assert requester.read_bytes() == before


def test_saving_the_restored_package_writes_the_change_and_clears_the_recovery(
    session, requester
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _crash_with_change(session, requester, THREAD_SYSTEM, "other")
    second = _restart(session)
    second.view.setCurrentIndex(row_named(second.view))

    second.view.saveAct.trigger()

    (package,) = second.model.openedPacks()
    assert not package.changed
    (saved,) = [
        o
        for o in read_package(requester).objects
        if isinstance(o, model.Submodel)
    ]
    assert saved.get_referable(list(THREAD_SYSTEM[2:])).value == "other"
    assert list(session.recovery.glob("*.json")) == []


def test_no_opens_the_saved_version_and_throws_the_recovery_away(
    session, requester
) -> None:
    _crash_with_change(session, requester, THREAD_SYSTEM, "other")
    session.screen.box_answer = QMessageBox.StandardButton.No

    second = _restart(session)

    (package,) = second.model.openedPacks()
    assert _value(package, THREAD_SYSTEM) != "other"
    assert not package.changed
    assert list(session.recovery.glob("*.json")) == []


def test_a_package_with_a_stored_file_comes_back_with_its_file(session) -> None:
    from aas_editor.infrastructure.package_io import read_package

    pump = write_pump_package(session.tmp_path / "pump.aasx")
    _crash_with_change(session, pump, PUMP_NAME, "motor")
    second = _restart(session)
    second.view.setCurrentIndex(row_named(second.view))

    second.view.saveAct.trigger()

    saved = read_package(pump)
    assert sorted(saved.files) == [DOCUMENT, "/aasx/files/shell.png"]
    (submodel,) = [o for o in saved.objects if isinstance(o, model.Submodel)]
    assert submodel.get_referable("Name").value == "motor"  # pyright: ignore[reportAttributeAccessIssue]


def test_a_recovery_of_a_file_that_is_gone_still_restores_the_change(
    session, requester
) -> None:
    _crash_with_change(session, requester, THREAD_SYSTEM, "other")
    requester.unlink()

    second = _restart(session)

    (package,) = second.model.openedPacks()
    assert _value(package, THREAD_SYSTEM) == "other"
    assert package.changed
    assert package.file == requester.absolute()
