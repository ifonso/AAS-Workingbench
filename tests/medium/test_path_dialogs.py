"""The dialogs that ask for a path use the dialog of Qt on Linux."""

from pathlib import Path
import sys

from PyQt6.QtWidgets import QFileDialog
import pytest


@pytest.mark.parametrize(
    ("platform", "environ", "native"),
    [
        ("linux", {}, False),
        ("freebsd14", {}, False),
        ("linux", {"FLATPAK_ID": "org.example.App"}, True),
        ("linux", {"SNAP": "/snap/app/1"}, True),
        ("win32", {}, True),
        ("darwin", {}, True),
    ],
)
def test_the_desktop_dialog_is_used_only_where_it_is_safe(
    qapp: object, platform: str, environ: dict[str, str], native: bool
) -> None:
    from aas_workingbench.ui.path_dialogs import uses_native_dialog

    assert uses_native_dialog(platform, environ) is native


@pytest.fixture
def asked(monkeypatch: pytest.MonkeyPatch) -> list[QFileDialog.Option]:
    """Records the options that each file dialog is opened with."""
    options: list[QFileDialog.Option] = []

    def answer(*args: object, **kwargs: object) -> tuple[str, str]:
        options.append(kwargs["options"])
        return "/chosen/file.aasx", ""

    def answer_folder(*args: object, **kwargs: object) -> str:
        options.append(kwargs["options"])
        return "/chosen"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(answer))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(answer))
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(answer_folder)
    )
    return options


def test_every_path_dialog_is_the_one_of_qt_on_linux(
    qapp: object,
    asked: list[QFileDialog.Option],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aas_workingbench.ui import path_dialogs

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.delenv("SNAP", raising=False)

    path_dialogs.get_open_file_name(None, "Open")
    path_dialogs.get_save_file_name(None, "Save")
    path_dialogs.get_existing_directory(None, "Folder")

    assert len(asked) == 3
    assert all(
        option & QFileDialog.Option.DontUseNativeDialog for option in asked
    )


def test_the_path_dialogs_keep_the_desktop_dialog_on_windows(
    qapp: object,
    asked: list[QFileDialog.Option],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aas_workingbench.ui import path_dialogs

    monkeypatch.setattr(sys, "platform", "win32")

    path_dialogs.get_open_file_name(None, "Open")
    path_dialogs.get_save_file_name(None, "Save")

    assert not any(
        option & QFileDialog.Option.DontUseNativeDialog for option in asked
    )


def test_the_path_dialogs_return_the_chosen_path(
    qapp: object, asked: list[QFileDialog.Option]
) -> None:
    from aas_workingbench.ui import path_dialogs

    assert path_dialogs.get_open_file_name(None) == "/chosen/file.aasx"
    assert path_dialogs.get_save_file_name(None) == "/chosen/file.aasx"
    assert path_dialogs.get_existing_directory(None) == "/chosen"


def test_no_module_opens_a_file_dialog_of_its_own() -> None:
    source = Path(__file__).parents[2] / "src" / "aas_workingbench"
    callers = [
        path.relative_to(source).as_posix()
        for path in source.rglob("*.py")
        if "QFileDialog.get" in path.read_text(encoding="utf-8")
        and path.name != "path_dialogs.py"
    ]

    assert callers == []
