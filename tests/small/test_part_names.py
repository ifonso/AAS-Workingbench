"""The names of stored files: what is accepted, made, and refused."""

import pytest

from aas_editor.domain import part_names
from aas_editor.domain.part_names import InvalidPartNameError


@pytest.mark.parametrize(
    "name",
    [
        "/aasx/files/a.pdf",
        "/a",
        "/aasx/files/with space.txt",
        "/aasx/files/%C3%A4.txt",
    ],
)
def test_valid_names_are_accepted(name: str) -> None:
    assert part_names.validate(name) == name
    assert part_names.is_valid(name)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "relative.txt",
        "/",
        "/aasx/",
        "/aasx//a.txt",
        "/../evil.txt",
        "/aasx/../../evil.txt",
        "/aasx/./a.txt",
        "/aasx\\a.txt",
        "/aasx/a%2Fb.txt",
        "/aasx/files/ä.txt",
        "/aasx/segment./a.txt",
        "C:/evil.txt",
    ],
)
def test_names_that_could_leave_the_package_or_break_the_writer_are_refused(
    name: str,
) -> None:
    assert not part_names.is_valid(name)
    with pytest.raises(InvalidPartNameError):
        part_names.validate(name)


@pytest.mark.parametrize(
    ("folder", "file_name", "expected"),
    [
        ("/aasx/files", "report final.pdf", "/aasx/files/report_final.pdf"),
        ("aasx\\files\\", "a.txt", "/aasx/files/a.txt"),
        ("/", "a.txt", "/a.txt"),
        (
            "/aasx/files",
            "C:\\Users\\me\\Daten (1).pdf",
            "/aasx/files/Daten_1_.pdf",
        ),
        ("/aasx/files", "../../evil.txt", "/aasx/files/evil.txt"),
        ("/aasx/files", ".hidden", "/aasx/files/hidden"),
        ("/aasx/files", "ü.txt", "/aasx/files/_.txt"),
    ],
)
def test_a_name_is_made_from_a_folder_and_a_local_file_name(
    folder: str, file_name: str, expected: str
) -> None:
    assert part_names.part_name(folder, file_name) == expected


@pytest.mark.parametrize(
    ("folder", "file_name"),
    [
        ("/aasx/..", "a.txt"),
        ("/aasx/files", ""),
        ("/aasx/files", "..."),
        ("/aasx/files", "///"),
        ("/aasx/files", "ü"),
    ],
)
def test_a_name_that_leaves_nothing_usable_is_refused(
    folder: str, file_name: str
) -> None:
    with pytest.raises(InvalidPartNameError):
        part_names.part_name(folder, file_name)


def test_the_folder_and_the_file_name_are_told_apart() -> None:
    assert part_names.folder_of("/aasx/files/a.txt") == "/aasx/files"
    assert part_names.folder_of("/a.txt") == "/"
    assert part_names.file_name_of("/aasx/files/a.txt") == "a.txt"


def test_names_that_differ_only_in_case_are_the_same_part() -> None:
    assert part_names.same_part("/aasx/A.TXT", "/aasx/a.txt")
    assert (
        part_names.find_clash("/AASX/a.txt", ["/aasx/A.txt"]) == "/aasx/A.txt"
    )
    assert part_names.find_clash("/aasx/b.txt", ["/aasx/A.txt"]) is None


def test_a_taken_name_gets_a_number_as_the_sdk_does() -> None:
    assert part_names.unique_name("/a/x.txt", []) == "/a/x.txt"
    assert part_names.unique_name("/a/x.txt", ["/a/x.txt"]) == "/a/x_0001.txt"
    assert (
        part_names.unique_name("/a/x.txt", ["/a/x.txt", "/a/X_0001.txt"])
        == "/a/x_0002.txt"
    )
    assert part_names.unique_name("/a/x_0001.txt", ["/a/x_0001.txt"]) == (
        "/a/x_0002.txt"
    )
    assert part_names.unique_name("/a/noext", ["/A/NOEXT"]) == "/a/noext_0001"


def test_the_media_type_is_guessed_and_unknown_is_binary() -> None:
    assert part_names.guess_content_type("report.pdf") == "application/pdf"
    assert part_names.guess_content_type("a.PNG") == "image/png"
    assert part_names.guess_content_type("a.zip") != "text/plain"
    assert part_names.guess_content_type("a.unknownext") == (
        "application/octet-stream"
    )


def test_text_media_types_are_recognized() -> None:
    assert part_names.is_text_type("text/plain; charset=utf-8")
    assert part_names.is_text_type("application/json")
    assert part_names.is_text_type("image/svg+xml")
    assert not part_names.is_text_type("application/pdf")


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("/aasx/files/a.pdf", "a.pdf"),
        ("/../../Windows/evil.dll", "evil.dll"),
        ("\\\\server\\share\\x.txt", "x.txt"),
        ("/aasx/CON.txt", "_CON.txt"),
        ("/aasx/a:b?.txt", "a_b_.txt"),
        ("/aasx/...", "file"),
    ],
)
def test_the_name_on_disk_never_chooses_a_folder(
    stored: str, expected: str
) -> None:
    assert part_names.local_file_name(stored) == expected
