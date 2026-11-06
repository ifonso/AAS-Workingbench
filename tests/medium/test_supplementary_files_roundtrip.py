"""Every operation on the supplementary files, through a real AASX file.

Each test does an operation, undoes it, and redoes it. After each of the three
states the package is saved and read again, and the stored files (names, bytes,
media types) and the paths that refer to them are compared. So undo and redo
are checked in the file a user would send, not only in memory.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import zipfile

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_collection
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx

from aas_editor.application import supplementary_files as files
from aas_editor.application.changes import observer_for
from aas_editor.application.save import SaveOptions
from aas_editor.application.save import SaveStatus
from aas_editor.application.save import save
from aas_editor.domain.walking import walk_elements
from aas_editor.infrastructure.package_io import write_package

DOCUMENT = "/aasx/files/document.pdf"
NOTE = "/aasx/files/note.txt"
THUMBNAIL = "/aasx/files/thumbnail.png"
DOCUMENT_BYTES = b"%PDF-1.4 document"
NOTE_BYTES = b"first note"
THUMBNAIL_BYTES = b"\x89PNG thumbnail"
OPTIONS = SaveOptions()


@dataclass(frozen=True)
class State:
    """What a saved package holds about its files."""

    files: dict[str, tuple[bytes, str]]
    paths: dict[str, str | None]
    zip_parts: tuple[str, ...]


def _state(path: Path) -> State:
    from aas_editor.package import Package

    package = Package(path)
    stored = {
        name: (files.read_file(package.fileStore, name), content_type)
        for name in package.fileStore
        for content_type in [package.fileStore.get_content_type(name)]
    }
    paths: dict[str, str | None] = {}
    for submodel in package.submodels:
        for element in walk_elements(submodel):
            if isinstance(element, model.File):
                paths[element.get_id_short_path()] = element.value
    for shell in package.shells:
        thumbnail = shell.asset_information.default_thumbnail
        paths["thumbnail"] = thumbnail.path if thumbnail else None
    with zipfile.ZipFile(path) as archive:
        parts = tuple(
            sorted(
                name
                for name in archive.namelist()
                if name.startswith("aasx/files/")
                or name.startswith("aasx/central/")
            )
        )
    return State(stored, paths, parts)


@pytest.fixture
def package(qapp: object, tmp_path: Path):
    """A package with a document, a note, an annotation file, a thumbnail."""
    from aas_editor.package import Package

    submodel = make_submodel(
        elements=[
            make_file_element("Document", DOCUMENT, "application/pdf"),
            make_file_element("Note", NOTE, "text/plain"),
            make_collection(
                "Group",
                [make_file_element("Appendix", DOCUMENT, "application/pdf")],
            ),
        ]
    )
    shell = make_shell(
        submodels=[submodel],
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(THUMBNAIL, "image/png")
        ),
    )
    source = write_aasx(
        tmp_path / "source.aasx",
        make_store(shell, submodel),
        files={
            DOCUMENT: (DOCUMENT_BYTES, "application/pdf"),
            NOTE: (NOTE_BYTES, "text/plain"),
            THUMBNAIL: (THUMBNAIL_BYTES, "image/png"),
        },
    )
    package = Package(source)
    package.directory = tmp_path
    return package


class Lab:
    """Does an operation, and saves the package in each state."""

    def __init__(self, package, tmp_path: Path) -> None:
        self.package = package
        self.tmp_path = tmp_path
        self.stack = package.commandStack
        self.observer = observer_for(package)
        self.saved = 0

    @property
    def element(self) -> Callable[[str], model.File]:
        def find(id_short: str) -> model.File:
            submodel = next(iter(self.package.submodels))
            element = submodel.submodel_element.get_object_by_attribute(
                "id_short", id_short
            )
            assert isinstance(element, model.File)
            return element

        return find

    def save(self) -> State:
        self.saved += 1
        target = self.tmp_path / f"saved_{self.saved}.aasx"
        outcome = save(
            self.package.save_source(),
            target,
            OPTIONS,
            write_package,
            lambda check: True,
        )
        assert outcome.status is SaveStatus.SAVED
        return _state(target)

    def cycle(self, operation: Callable[[], object]) -> tuple[State, ...]:
        """Returns the states before, after, after undo, and after redo."""
        before = self.save()
        operation()
        done = self.save()
        self.stack.undo()
        undone = self.save()
        self.stack.redo()
        redone = self.save()
        return before, done, undone, redone


@pytest.fixture
def lab(package, tmp_path: Path) -> Lab:
    return Lab(package, tmp_path)


def _assert_cycle(states: tuple[State, ...]) -> State:
    before, done, undone, redone = states
    assert undone == before
    assert redone == done
    assert done != before
    return done


def test_the_saved_package_starts_with_its_files(lab: Lab) -> None:
    state = lab.save()

    assert state.files[DOCUMENT] == (DOCUMENT_BYTES, "application/pdf")
    assert state.files[NOTE] == (NOTE_BYTES, "text/plain")
    assert state.paths["Group.Appendix"] == DOCUMENT
    assert state.paths["thumbnail"] == THUMBNAIL


def test_adding_and_linking_a_file_survives_save_undo_redo(lab: Lab) -> None:
    element = lab.element("Note")

    done = _assert_cycle(
        lab.cycle(
            lambda: files.add_and_link(
                lab.stack,
                lab.observer,
                lab.package.fileStore,
                element,
                "/aasx/files/report_final.pdf",
                b"%PDF report",
                "application/pdf",
            )
        )
    )

    assert done.files["/aasx/files/report_final.pdf"] == (
        b"%PDF report",
        "application/pdf",
    )
    assert done.paths["Note"] == "/aasx/files/report_final.pdf"
    assert NOTE not in done.files


def test_renaming_a_file_moves_every_reference_with_it(lab: Lab) -> None:
    done = _assert_cycle(
        lab.cycle(
            lambda: files.rename_file(
                lab.stack,
                lab.observer,
                lab.package.objStore,
                lab.package.fileStore,
                DOCUMENT,
                "/aasx/files/manual.pdf",
            )
        )
    )

    assert done.files["/aasx/files/manual.pdf"][0] == DOCUMENT_BYTES
    assert DOCUMENT not in done.files
    assert done.paths["Document"] == "/aasx/files/manual.pdf"
    assert done.paths["Group.Appendix"] == "/aasx/files/manual.pdf"


def test_renaming_the_thumbnail_file_keeps_the_thumbnail(lab: Lab) -> None:
    done = _assert_cycle(
        lab.cycle(
            lambda: files.rename_file(
                lab.stack,
                lab.observer,
                lab.package.objStore,
                lab.package.fileStore,
                THUMBNAIL,
                "/aasx/files/logo.png",
            )
        )
    )

    assert done.paths["thumbnail"] == "/aasx/files/logo.png"
    assert done.files["/aasx/files/logo.png"] == (THUMBNAIL_BYTES, "image/png")


def test_moving_a_file_to_a_central_folder(lab: Lab) -> None:
    done = _assert_cycle(
        lab.cycle(
            lambda: files.move_file(
                lab.stack,
                lab.observer,
                lab.package.objStore,
                lab.package.fileStore,
                NOTE,
                "/aasx/central",
            )
        )
    )

    assert done.files["/aasx/central/note.txt"] == (NOTE_BYTES, "text/plain")
    assert done.paths["Note"] == "/aasx/central/note.txt"
    assert "aasx/central/note.txt" in done.zip_parts


def test_removing_a_file_and_its_paths(lab: Lab) -> None:
    done = _assert_cycle(
        lab.cycle(
            lambda: files.remove_file(
                lab.stack,
                lab.observer,
                lab.package.objStore,
                lab.package.fileStore,
                DOCUMENT,
                files.ReferenceChoice.CLEAR,
            )
        )
    )

    assert DOCUMENT not in done.files
    assert done.paths["Document"] is None
    assert done.paths["Group.Appendix"] is None


def test_editing_a_text_file_keeps_utf8_text(lab: Lab) -> None:
    text = "Grüße aus Köln\r\nПривет\r\n"

    done = _assert_cycle(
        lab.cycle(
            lambda: files.edit_text_file(
                lab.stack, lab.observer, lab.package.fileStore, NOTE, text
            )
        )
    )

    assert done.files[NOTE] == (text.encode("utf-8"), "text/plain")


def test_creating_a_text_file_and_linking_it(lab: Lab) -> None:
    element = lab.element("Note")

    def create_and_link() -> None:
        with lab.stack.group("Create"):
            name = files.create_text_file(
                lab.stack,
                lab.observer,
                lab.package.fileStore,
                "/aasx/files/readme.md",
                "# Read me",
            )
            files.link_file_element(
                lab.stack,
                lab.observer,
                lab.package.fileStore,
                element,
                name,
                adopt_content_type=True,
            )

    done = _assert_cycle(lab.cycle(create_and_link))

    assert done.files["/aasx/files/readme.md"] == (
        b"# Read me",
        "text/markdown",
    )
    assert done.paths["Note"] == "/aasx/files/readme.md"


def test_choosing_a_file_for_a_thumbnail_with_a_picker(lab: Lab) -> None:
    shell = next(iter(lab.package.shells))

    done = _assert_cycle(
        lab.cycle(
            lambda: files.link_thumbnail(
                lab.stack,
                lab.observer,
                lab.package.fileStore,
                shell.asset_information,
                DOCUMENT,
            )
        )
    )

    assert done.paths["thumbnail"] == DOCUMENT
    assert THUMBNAIL not in done.files


def test_a_file_that_nothing_refers_to_is_warned_about_and_not_saved(
    lab: Lab,
) -> None:
    files.create_text_file(
        lab.stack,
        lab.observer,
        lab.package.fileStore,
        "/aasx/files/draft.txt",
        "draft",
    )
    target = lab.tmp_path / "with_draft.aasx"
    questions: list[tuple[str, ...]] = []

    def confirm(check) -> bool:
        questions.extend(issue.details for issue in check.warnings)
        return True

    outcome = save(
        lab.package.save_source(), target, OPTIONS, write_package, confirm
    )

    assert outcome.status is SaveStatus.SAVED
    assert questions == [("/aasx/files/draft.txt",)]
    assert "/aasx/files/draft.txt" not in _state(target).files


def test_linking_the_file_before_saving_keeps_it(lab: Lab) -> None:
    name = files.create_text_file(
        lab.stack,
        lab.observer,
        lab.package.fileStore,
        "/aasx/files/draft.txt",
        "draft",
    )
    files.link_file_element(
        lab.stack,
        lab.observer,
        lab.package.fileStore,
        lab.element("Note"),
        name,
    )

    state = lab.save()

    assert state.files[name] == (b"draft", "text/plain")


def test_a_dangling_path_blocks_the_save_until_it_is_repaired(lab: Lab) -> None:
    files.remove_file(
        lab.stack,
        lab.observer,
        lab.package.objStore,
        lab.package.fileStore,
        DOCUMENT,
        files.ReferenceChoice.LEAVE,
    )
    target = lab.tmp_path / "dangling.aasx"
    refused = save(
        lab.package.save_source(),
        target,
        OPTIONS,
        write_package,
        lambda c: True,
    )
    dangling = files.find_dangling(lab.package.objStore, lab.package.fileStore)

    for reference in dangling:
        for command in files.link_commands(lab.observer, reference, NOTE):
            lab.stack.push(command)
    repaired = save(
        lab.package.save_source(),
        target,
        OPTIONS,
        write_package,
        lambda c: True,
    )

    assert refused.status is SaveStatus.REFUSED
    assert sorted(ref.location for ref in dangling) == [
        "Document",
        "Group.Appendix",
    ]
    assert repaired.status is SaveStatus.SAVED
    assert _state(target).paths["Document"] == NOTE
