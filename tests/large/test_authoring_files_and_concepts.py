"""Files, a thumbnail, a Blob, and a concept description made from a semantic id.

The package is built from nothing as in `test_authoring_from_nothing.py`. Then a
person adds a PDF and a picture from disk, links a File element to the PDF,
makes the picture the thumbnail of the AAS, converts a Blob to Base64 text and
back, and creates a concept description from the semantic id of an element.
The package is saved and opened again, and what the editor showed must be in
the file.
"""

from pathlib import Path
import zipfile

from basyx.aas import model
import pytest
from tests.authoring import Author
from tests.authoring_builders import SUBMODEL
from tests.authoring_builders import build_everything
from tests.authoring_elements import external
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PDF = b"%PDF-1.4 a datasheet"
PNG = b"\x89PNG\r\n\x1a\n pump"


def _add_file_from_disk(author: Author, source: Path) -> None:
    """Presses Add file on the files of the package, and picks a file."""
    author.pick_open_path(source)
    author.answer_text_question()
    author.select_path("fileStore")
    assert author.act("files.add")


def test_a_file_is_added_linked_and_made_the_thumbnail_and_the_package_keeps_them(
    author: Author, tmp_path: Path
) -> None:
    from aas_editor.ui.file_dialogs import FileChoiceDialog

    build_everything(author, tmp_path)
    (tmp_path / "datasheet.pdf").write_bytes(PDF)
    (tmp_path / "pump.png").write_bytes(PNG)

    _add_file_from_disk(author, tmp_path / "datasheet.pdf")
    _add_file_from_disk(author, tmp_path / "pump.png")

    stored = sorted(author.package.fileStore)
    assert stored == ["/aasx/files/datasheet.pdf", "/aasx/files/pump.png"]

    # Link the File element Datasheet to the PDF.
    def pick_pdf(dialog: FileChoiceDialog) -> None:
        item = next(
            dialog.files_list.item(row)
            for row in range(dialog.files_list.count())
            if dialog.files_list.item(row)
            .text()
            .startswith("/aasx/files/datasheet")
        )
        dialog.files_list.setCurrentItem(item)

    author.select_path(*SUBMODEL, "Datasheet")
    with author.answering(FileChoiceDialog, pick_pdf) as answer:
        assert author.act("files.choose")
    author.assert_accepted(answer)
    datasheet = author.package.objStore.get_item(
        "urn:example:sm:everything"
    ).get_referable("Datasheet")
    assert datasheet.value == "/aasx/files/datasheet.pdf"

    # Make the picture the default thumbnail of the AAS.
    def pick_png(dialog: FileChoiceDialog) -> None:
        item = next(
            dialog.files_list.item(row)
            for row in range(dialog.files_list.count())
            if dialog.files_list.item(row).text().startswith("/aasx/files/pump")
        )
        dialog.files_list.setCurrentItem(item)

    author.select_path("shells", "Pump")
    with author.answering(FileChoiceDialog, pick_png) as answer:
        assert author.act("files.choose_thumbnail")
    author.assert_accepted(answer)
    shell = author.package.objStore.get_item("urn:example:aas:pump")
    assert shell.asset_information.default_thumbnail.path == (
        "/aasx/files/pump.png"
    )
    assert shell.asset_information.default_thumbnail.content_type == "image/png"

    # The package saved and read again holds the files, and the links.
    path = tmp_path / "pump.aasx"
    author.select_path()
    author.view.saveAct.trigger()
    assert not author.window.isWindowModified(), author.errors
    with zipfile.ZipFile(path) as archive:
        assert archive.read("aasx/files/datasheet.pdf") == PDF
        assert archive.read("aasx/files/pump.png") == PNG
    built = snapshot(author.package.objStore)
    author.view.closeAct.trigger()
    author.pick_open_path(path)
    author.view.openPackAct.trigger()
    assert snapshot(author.package.objStore) == built
    assert sorted(author.package.fileStore) == stored


def test_a_blob_is_converted_to_base64_text_and_back_in_two_undoable_steps(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    certificate = author.package.objStore.get_item(
        "urn:example:sm:everything"
    ).get_referable("Certificate")
    assert certificate.value == b"hello"
    author.stack.mark_saved()

    author.select_path(*SUBMODEL, "Certificate")
    assert author.act("blob.to_base64")

    assert certificate.value == b"aGVsbG8="
    assert author.act("blob.from_base64")
    assert certificate.value == b"hello"
    assert author.stack.can_undo
    author.view.onUndo()
    assert certificate.value == b"aGVsbG8="
    author.view.onUndo()
    assert certificate.value == b"hello"
    assert author.stack.is_clean


def test_text_that_is_not_base64_is_refused_with_a_message_and_changes_nothing(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    certificate = author.package.objStore.get_item(
        "urn:example:sm:everything"
    ).get_referable("Certificate")
    author.stack.mark_saved()
    author.select_path(*SUBMODEL, "Certificate")

    assert author.act("blob.from_base64")

    assert certificate.value == b"hello"
    assert author.stack.is_clean
    assert len(author.errors) == 1
    assert "not changed" in author.errors[0]


def test_a_concept_description_is_created_from_the_semantic_id_of_an_element(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)

    def fill(form) -> None:
        form.type_text("value", "x")
        form.fill_reference("semantic_id", external("urn:example:cd:current"))

    answer = author.add_element(SUBMODEL, model.Property, "Current", fill)
    author.assert_accepted(answer)
    before = len(
        [
            o
            for o in author.package.objStore
            if isinstance(o, model.ConceptDescription)
        ]
    )

    author.select_path(*SUBMODEL, "Current")
    assert author.act("concepts.create")

    created = author.package.objStore.get_item("urn:example:cd:current")
    assert isinstance(created, model.ConceptDescription)
    assert (
        len(
            [
                o
                for o in author.package.objStore
                if isinstance(o, model.ConceptDescription)
            ]
        )
        == before + 1
    )
    assert created.id_short in author.names("concept_descriptions") or (
        "urn:example:cd:current" in author.names("concept_descriptions")
    )
    # It exists now, so a second try says so and creates nothing.
    author.errors.clear()
    author.act("concepts.create")
    assert len(author.errors) == 1
    assert "has already" in author.errors[0]
