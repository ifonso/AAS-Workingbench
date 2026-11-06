from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_collection
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.package_factories import make_annotated_relationship

from aas_editor.domain.file_references import FileReference
from aas_editor.domain.file_references import file_references
from aas_editor.domain.file_references import is_package_path
from aas_editor.domain.file_references import missing_files
from aas_editor.domain.file_references import unreferenced_files


@pytest.mark.parametrize(
    "path",
    [
        "/aasx/files/a.pdf",
        "files/a.pdf",
        "a.pdf",
        "../a.pdf",
        "/aasx/a:b.pdf",
    ],
)
def test_is_package_path_is_true_when_path_is_inside_the_package(
    path: str,
) -> None:
    assert is_package_path(path) is True


@pytest.mark.parametrize(
    "path",
    [
        None,
        "",
        "https://example.com/a.pdf",
        "file:///c:/a.pdf",
        "urn:example:a",
        "//server/share/a.pdf",
        "c:/a.pdf",
    ],
)
def test_is_package_path_is_false_when_path_points_outside_the_package(
    path: str | None,
) -> None:
    assert is_package_path(path) is False


def test_file_references_lists_files_in_nested_collections() -> None:
    submodel = make_submodel(
        elements=[
            make_file_element("Top", "/aasx/files/top.pdf"),
            make_collection(
                "Group",
                [make_file_element("Inner", "/aasx/files/inner.pdf")],
            ),
        ]
    )

    references = file_references([submodel])

    assert references == [
        FileReference("/aasx/files/top.pdf", submodel.id, "Top", False),
        FileReference(
            "/aasx/files/inner.pdf", submodel.id, "Group.Inner", False
        ),
    ]


def test_file_references_marks_file_when_it_is_an_annotation() -> None:
    note = make_file_element("Note", "/aasx/files/note.txt")
    submodel = make_submodel(
        elements=[make_annotated_relationship(annotations=(note,))]
    )

    references = file_references([submodel])

    assert references == [
        FileReference(
            "/aasx/files/note.txt", submodel.id, "Annotated.Note", True
        )
    ]


def test_file_references_lists_default_thumbnail_of_shell() -> None:
    shell = make_shell(
        asset_information=make_asset_information(
            default_thumbnail=model.Resource("/aasx/files/asset.png")
        )
    )

    references = file_references([shell])

    assert references == [
        FileReference(
            "/aasx/files/asset.png", shell.id, "Default thumbnail", False
        )
    ]


def test_file_references_skips_urls_and_empty_values() -> None:
    submodel = make_submodel(
        elements=[
            make_file_element("Web", "https://example.com/a.pdf"),
            make_file_element("Empty", None),
        ]
    )

    assert file_references([submodel]) == []


def test_missing_files_selects_paths_that_are_not_stored() -> None:
    references = [
        FileReference("/aasx/files/a.pdf", "id", "A"),
        FileReference("/aasx/files/b.pdf", "id", "B"),
    ]

    missing = missing_files(references, {"/aasx/files/a.pdf"})

    assert [ref.location for ref in missing] == ["B"]


def test_missing_files_matches_exactly_when_case_differs() -> None:
    references = [FileReference("/aasx/files/A.pdf", "id", "A")]

    assert len(missing_files(references, {"/aasx/files/a.pdf"})) == 1


def test_unreferenced_files_selects_stored_files_nothing_refers_to() -> None:
    references = [FileReference("/aasx/files/a.pdf", "id", "A")]

    unreferenced = unreferenced_files(
        references, ["/aasx/files/b.pdf", "/aasx/files/a.pdf", "/aasx/c.pdf"]
    )

    assert unreferenced == ["/aasx/c.pdf", "/aasx/files/b.pdf"]
