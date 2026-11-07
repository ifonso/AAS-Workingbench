"""Plain words for a file that cannot be opened, and for a save that fails."""

import errno
import json
from pathlib import Path
import zipfile

import pytest

from aas_editor.infrastructure.open_problems import diagnose
from aas_editor.infrastructure.package_io import read_package
from aas_editor.ui.save_warnings import explain_save_error

V2_XML = (
    '<?xml version="1.0"?><aas:aasenv '
    'xmlns:aas="http://www.admin-shell.io/aas/2/0"/>'
)
V1_JSON = '{"assetAdministrationShells": [{"identification": {"id": "x"}}]}'
V3_XML = '<environment xmlns="https://admin-shell.io/aas/3/1"/>'


def _error(path: Path) -> Exception:
    """What the reader raises for the file, as the editor gets it."""
    with pytest.raises(Exception) as caught:
        read_package(path)
    return caught.value


def _diagnosed(path: Path) -> str:
    problem = diagnose(path, _error(path))
    assert problem is not None
    return problem.summary


def test_a_file_with_the_namespace_of_version_2_is_named_as_old(
    tmp_path: Path,
) -> None:
    path = tmp_path / "servo.xml"
    path.write_text(V2_XML)

    assert _diagnosed(path) == (
        "servo.xml was made for version 2.0 of the AAS metamodel."
    )


def test_json_of_version_1_or_2_is_named_as_old(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(V1_JSON)

    assert _diagnosed(path) == (
        "old.json was made for version 1 or 2 of the AAS metamodel."
    )


def test_an_aasx_whose_part_is_version_2_is_named_as_old(
    tmp_path: Path,
) -> None:
    path = tmp_path / "old.aasx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("aasx/old.aas.xml", V2_XML)

    problem = diagnose(path, ValueError("something the SDK says"))

    assert problem is not None
    assert problem.summary == (
        "old.aasx was made for version 2.0 of the AAS metamodel."
    )


def test_a_file_of_version_3_is_not_called_old(tmp_path: Path) -> None:
    path = tmp_path / "new.xml"
    path.write_text(V3_XML)

    assert diagnose(path, KeyError("a constraint of the SDK")) is None


def test_a_version_3_aasx_that_the_sdk_refuses_is_left_to_failsafe_mode(
    tmp_path: Path,
) -> None:
    path = tmp_path / "template.aasx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("aasx/data.xml", V3_XML)

    assert diagnose(path, ValueError("Failed to construct")) is None


@pytest.mark.parametrize(
    ("name", "content", "sentence"),
    [
        (
            "notes.txt",
            b"hi",
            "notes.txt is not a file that the editor opens (.txt).",
        ),
        (
            "data",
            b"{}",
            "data is not a file that the editor opens (without an extension).",
        ),
        ("empty.json", b"", "empty.json is empty."),
        ("text.aasx", b"words", "text.aasx is not an AASX package."),
        (
            "broken.json",
            b'{"a": [',
            "broken.json is not valid JSON: Expecting value, at line 1 column 8.",
        ),
    ],
)
def test_a_file_that_cannot_be_a_package_says_what_it_is(
    tmp_path: Path, name: str, content: bytes, sentence: str
) -> None:
    path = tmp_path / name
    path.write_bytes(content)

    assert _diagnosed(path) == sentence


def test_a_file_with_text_that_is_not_xml_says_so(tmp_path: Path) -> None:
    path = tmp_path / "broken.xml"
    path.write_text("<environment><oops>")

    assert _diagnosed(path).startswith("broken.xml is not well-formed XML")


def test_a_missing_file_says_that_it_does_not_exist(tmp_path: Path) -> None:
    path = tmp_path / "gone.aasx"

    assert _diagnosed(path) == "gone.aasx does not exist."


def test_a_file_that_may_not_be_read_says_so(tmp_path: Path) -> None:
    path = tmp_path / "locked.aasx"
    path.write_bytes(b"x")

    problem = diagnose(path, PermissionError(13, "Permission denied"))

    assert problem is not None
    assert problem.summary == "locked.aasx cannot be read."
    assert "another program has it open" in problem.advice


def test_a_syntax_error_of_json_is_not_confused_with_an_old_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps([1, 2]))

    assert diagnose(path, ValueError("something")) is None


def test_a_read_only_target_says_it_is_read_only_or_open(
    tmp_path: Path,
) -> None:
    text = explain_save_error(
        tmp_path / "a.aasx", PermissionError(13, "Access is denied")
    )

    assert text == (
        "a.aasx could not be written. It is read-only, or another program "
        "has it open. Close it there, or choose Save As and give the copy "
        "another name. Your changes are still in the editor, and the file on "
        "disk is as it was."
    )


def test_a_folder_that_is_gone_is_named(tmp_path: Path) -> None:
    text = explain_save_error(
        tmp_path / "gone" / "a.aasx", FileNotFoundError(2, "No such file")
    )

    assert text is not None
    assert f"The folder {tmp_path / 'gone'} does not exist." in text


def test_a_full_disk_says_so(tmp_path: Path) -> None:
    text = explain_save_error(
        tmp_path / "a.aasx", OSError(errno.ENOSPC, "No space left on device")
    )

    assert text is not None
    assert "no space left" in text.lower()


def test_an_error_that_is_not_about_the_file_system_has_no_explanation(
    tmp_path: Path,
) -> None:
    assert explain_save_error(tmp_path / "a.aasx", KeyError("File")) is None
