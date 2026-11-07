"""Save As and the other ways out of a package, in the real main window.

A package with a stored file, a file for the shell's thumbnail, a package
thumbnail and package properties is opened. It is saved as JSON, as XML, and
as an AASX with JSON inside, through the File menu, and each result is read
again. The test looks at what is kept, and at what the dialog told the person
before content was dropped.
"""

import json
from pathlib import Path
import zipfile

from basyx.aas.adapter.json import AASToJsonEncoder
import pytest
from tests.usage_open_window import DOCUMENT
from tests.usage_open_window import SHELL_THUMBNAIL
from tests.usage_open_window import close_window
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import row_named
from tests.usage_open_window import screen  # noqa: F401
from tests.usage_open_window import write_pump_package

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


def _dump(objects: object) -> dict[str, str]:
    """The SDK's JSON of every object, by id."""
    return {
        obj.id: json.dumps(obj, cls=AASToJsonEncoder, sort_keys=True)  # pyright: ignore[reportAttributeAccessIssue]
        for obj in objects  # pyright: ignore[reportGeneralTypeIssues]
    }


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, screen, every_action):  # noqa: F811
    """The main window with the package open, opened from the File menu."""
    source = write_pump_package(tmp_path / "pump.aasx")
    shown = open_window(qtbot)
    screen.open_paths.append(source.as_posix())
    shown.view.openPackAct.trigger()
    shown.view.expandAll()
    shown.source = source
    shown.screen = screen
    shown.tmp_path = tmp_path
    (shown.package,) = shown.model.openedPacks()
    shown.view.setCurrentIndex(row_named(shown.view))
    yield shown
    close_window(shown)


def _save_as(editor, target: Path) -> None:
    editor.screen.save_paths.append(target.as_posix())
    editor.view.setCurrentIndex(row_named(editor.view))
    editor.view.saveAsAct.trigger()


def _warning(editor) -> object:
    (shown,) = [s for s in editor.screen.shown if s.title == "Save package"]
    return shown


def test_saving_as_json_warns_about_the_files_and_the_package_data(
    editor,
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    target = editor.tmp_path / "pump.json"

    _save_as(editor, target)

    warning = _warning(editor)
    assert "JSON files cannot hold supplementary files" in warning.text
    assert DOCUMENT in warning.text
    assert SHELL_THUMBNAIL in warning.text
    assert "The package thumbnail" in warning.text
    assert "The package properties" in warning.text
    saved = read_package(target)
    assert list(saved.files) == []
    assert _dump(saved.objects) == _dump(read_package(editor.source).objects)
    assert editor.package.file == target
    # The open package still holds its files, so a later Save As AASX keeps them.
    assert sorted(editor.package.fileStore) == [DOCUMENT, SHELL_THUMBNAIL]


def test_saving_as_xml_warns_and_keeps_every_object(editor) -> None:
    from aas_editor.infrastructure.package_io import read_package

    target = editor.tmp_path / "pump.xml"

    _save_as(editor, target)

    assert "XML files cannot hold supplementary files" in _warning(editor).text
    saved = read_package(target)
    assert _dump(saved.objects) == _dump(read_package(editor.source).objects)
    assert list(saved.files) == []


def test_declining_the_warning_writes_nothing_and_keeps_the_package(
    editor,
) -> None:
    target = editor.tmp_path / "pump.json"
    editor.screen.dialog_accepts = False
    before = editor.source.read_bytes()
    # The file dialog comes back after a declined warning. The person gives up.
    editor.screen.save_paths.append("")

    _save_as(editor, target)

    assert not target.exists()
    assert editor.package.file == editor.source
    assert editor.source.read_bytes() == before


def test_json_and_xml_go_back_to_aasx_with_the_objects_and_without_the_files(
    editor, qtbot
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    original = _dump(read_package(editor.source).objects)
    _save_as(editor, editor.tmp_path / "pump.json")
    _save_as(editor, editor.tmp_path / "again.aasx")

    again = read_package(editor.tmp_path / "again.aasx")

    assert _dump(again.objects) == original
    # The package kept its files in memory through the JSON save, and the AASX
    # writes the ones that an element refers to.
    assert sorted(again.files) == [DOCUMENT, SHELL_THUMBNAIL]


def test_an_aasx_with_json_inside_keeps_everything_and_opens_again(
    editor,
) -> None:
    from aas_editor.infrastructure.package_io import read_package
    from aas_editor.settings.app_settings import AppSettings

    AppSettings.WRITE_JSON_IN_AASX.setValue(True)
    target = editor.tmp_path / "with_json.aasx"

    _save_as(editor, target)

    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
    assert "aasx/data.json" in names
    assert "aasx/data.xml" not in names
    assert "Save package" not in editor.screen.titles()
    saved = read_package(target)
    assert _dump(saved.objects) == _dump(read_package(editor.source).objects)
    assert sorted(saved.files) == [DOCUMENT, SHELL_THUMBNAIL]
    assert saved.thumbnail is not None
    assert saved.core_properties is not None
    assert saved.core_properties.title == "Pump package"


def test_the_save_in_menu_offers_the_three_formats(editor) -> None:
    assert [act.text() for act in editor.view.saveInActs] == [
        "Save in json",
        "Save in xml",
        "Save in aasx",
    ]
    assert all(act.isEnabled() for act in editor.view.saveInActs)


def test_saving_an_aasx_drops_a_file_that_nothing_refers_to_with_a_warning(
    editor, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    spare = editor.tmp_path / "spare.txt"
    spare.write_text("nothing refers to me")
    editor.screen.open_paths.append(spare.as_posix())
    monkeypatch.setattr(
        file_dialogs, "ask_text", lambda parent, title, label, text="": text
    )
    editor.view.setCurrentIndex(row_named(editor.view, "fileStore"))
    editor.view.updateActions(editor.view.currentIndex())
    editor.view.registeredActions.find("files.add").trigger()
    target = editor.tmp_path / "copy.aasx"

    _save_as(editor, target)

    warning = _warning(editor)
    assert "no File element or thumbnail refers to them" in warning.text
    assert "/aasx/files/spare.txt" in warning.text
    with zipfile.ZipFile(target) as archive:
        assert "aasx/files/spare.txt" not in archive.namelist()
        assert "aasx/files/document.pdf" in archive.namelist()
