"""The operations on the supplementary files and what refers to them (D15)."""

import io
from types import SimpleNamespace

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pytest
from tests.factories import make_annotated_relationship
from tests.factories import make_asset_information
from tests.factories import make_collection
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_workingbench.application import supplementary_files as files
from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.commands import ReadOnlyError
from aas_workingbench.application.supplementary_files import FileNameTakenError
from aas_workingbench.application.supplementary_files import NotTextError
from aas_workingbench.application.supplementary_files import ReferenceChoice
from aas_workingbench.domain.part_names import InvalidPartNameError

DOC = "/aasx/files/doc.pdf"
NOTE = "/aasx/files/note.txt"


def _bytes(store: DictSupplementaryFileContainer, name: str) -> bytes:
    return files.read_file(store, name)


@pytest.fixture
def world() -> SimpleNamespace:
    """A package with a document, a note, a thumbnail and three references."""
    world = SimpleNamespace()
    world.annotation_file = make_file_element(
        "Annotated", DOC, "application/pdf"
    )
    world.document = make_file_element("Document", DOC, "application/pdf")
    world.note = make_file_element("Note", NOTE, "text/plain")
    world.relationship = make_annotated_relationship(
        annotations=[world.annotation_file]
    )
    world.group = make_collection("Group", [world.relationship])
    world.submodel = make_submodel(
        elements=[world.document, world.note, world.group]
    )
    world.thumbnail = model.Resource(DOC, "application/pdf")
    world.shell = make_shell(
        submodels=[world.submodel],
        asset_information=make_asset_information(
            default_thumbnail=world.thumbnail
        ),
    )
    world.objects = make_store(world.shell, world.submodel)
    world.store = DictSupplementaryFileContainer()
    world.store.add_file(DOC, io.BytesIO(b"%PDF doc"), "application/pdf")
    world.store.add_file(NOTE, io.BytesIO(b"note"), "text/plain")
    world.stack = CommandStack()
    world.observer = ModelChangeObserver()
    world.changes = []
    world.observer.subscribe(world.changes.append)
    world.before = snapshot(world.objects)
    world.paths = lambda: [
        world.document.value,
        world.annotation_file.value,
        world.thumbnail.path,
    ]
    return world


# -- reading ---------------------------------------------------------------


def test_file_infos_tell_each_file_what_refers_to_it(world) -> None:
    unused = "/aasx/files/unused.bin"
    world.store.add_file(unused, io.BytesIO(b"123"), "application/octet-stream")

    infos = files.file_infos(world.objects, world.store)

    by_name = {info.name: info for info in infos}
    assert [info.name for info in infos] == sorted([DOC, NOTE, unused])
    assert len(by_name[DOC].references) == 3
    assert by_name[NOTE].is_referenced
    assert not by_name[unused].is_referenced
    assert by_name[unused].size == 3
    assert by_name[unused].content_type == "application/octet-stream"


def test_dangling_references_include_annotations_and_the_thumbnail(
    world,
) -> None:
    world.store.delete_file(DOC)

    dangling = files.find_dangling(world.objects, world.store)

    assert sorted(ref.location for ref in dangling) == sorted(
        ["Document", "Group.Relationship.Annotated", "Default thumbnail"]
    )


def test_a_url_is_not_dangling(world) -> None:
    world.document.value = "https://example.com/doc.pdf"
    world.store.delete_file(DOC)

    dangling = files.find_dangling(world.objects, world.store)

    assert "Document" not in [ref.location for ref in dangling]


# -- add -------------------------------------------------------------------


def test_adding_a_file_is_undone_and_redone(world) -> None:
    name = files.add_file(
        world.stack,
        world.observer,
        world.store,
        "/aasx/files/new.txt",
        b"new",
        "text/plain",
    )
    present = "/aasx/files/new.txt" in world.store
    world.stack.undo()
    gone = "/aasx/files/new.txt" not in world.store
    world.stack.redo()

    assert name == "/aasx/files/new.txt"
    assert present
    assert gone
    assert _bytes(world.store, name) == b"new"
    assert world.store.get_content_type(name) == "text/plain"


def test_adding_a_different_file_under_a_taken_name_never_overwrites(
    world,
) -> None:
    name = files.add_file(
        world.stack, world.observer, world.store, NOTE, b"other", "text/plain"
    )

    assert name == "/aasx/files/note_0001.txt"
    assert _bytes(world.store, NOTE) == b"note"
    assert _bytes(world.store, name) == b"other"


def test_a_name_that_differs_only_in_case_is_numbered(world) -> None:
    name = files.add_file(
        world.stack,
        world.observer,
        world.store,
        "/AASX/files/NOTE.txt",
        b"other",
        "text/plain",
    )

    assert name == "/AASX/files/NOTE_0001.txt"
    assert _bytes(world.store, NOTE) == b"note"


def test_adding_the_same_file_again_adds_nothing_and_undo_keeps_the_original(
    world,
) -> None:
    name = files.add_file(
        world.stack, world.observer, world.store, NOTE, b"note", "text/plain"
    )
    world.stack.undo()

    assert name == NOTE
    assert NOTE in world.store
    assert _bytes(world.store, NOTE) == b"note"


def test_a_name_that_is_not_a_part_name_is_refused(world) -> None:
    with pytest.raises(InvalidPartNameError):
        files.add_file(
            world.stack,
            world.observer,
            world.store,
            "/../evil.txt",
            b"x",
            "text/plain",
        )
    assert not world.stack.can_undo
    assert sorted(world.store) == [DOC, NOTE]


def test_read_mode_refuses_adding(world) -> None:
    stack = CommandStack(is_editing=lambda: False)

    with pytest.raises(ReadOnlyError):
        files.add_file(
            stack, world.observer, world.store, "/a.txt", b"x", "text/plain"
        )
    assert sorted(world.store) == [DOC, NOTE]


# -- rename and move -------------------------------------------------------


def test_renaming_updates_files_annotations_and_the_thumbnail_in_one_step(
    world,
) -> None:
    new = "/aasx/files/renamed.pdf"

    updated = files.rename_file(
        world.stack, world.observer, world.objects, world.store, DOC, new
    )

    assert updated == 3
    assert world.paths() == [new, new, new]
    assert sorted(world.store) == [NOTE, new]
    assert _bytes(world.store, new) == b"%PDF doc"
    assert world.store.get_content_type(new) == "application/pdf"
    assert files.find_dangling(world.objects, world.store) == []
    renamed = snapshot(world.objects)

    world.stack.undo()

    assert world.paths() == [DOC, DOC, DOC]
    assert sorted(world.store) == [DOC, NOTE]
    assert snapshot(world.objects) == world.before
    assert not world.stack.can_undo

    world.stack.redo()

    assert snapshot(world.objects) == renamed
    assert sorted(world.store) == [NOTE, new]


def test_renaming_onto_another_file_is_refused_and_changes_nothing(
    world,
) -> None:
    with pytest.raises(FileNameTakenError):
        files.rename_file(
            world.stack, world.observer, world.objects, world.store, DOC, NOTE
        )

    assert sorted(world.store) == [DOC, NOTE]
    assert snapshot(world.objects) == world.before
    assert not world.stack.can_undo


def test_renaming_onto_a_name_that_is_the_same_part_is_refused(world) -> None:
    with pytest.raises(FileNameTakenError):
        files.rename_file(
            world.stack,
            world.observer,
            world.objects,
            world.store,
            DOC,
            "/AASX/files/NOTE.TXT",
        )
    assert snapshot(world.objects) == world.before


def test_renaming_onto_an_identical_file_does_not_merge_them(world) -> None:
    world.store.add_file(
        "/aasx/files/copy.txt", io.BytesIO(b"note"), "text/plain"
    )

    with pytest.raises(FileNameTakenError):
        files.rename_file(
            world.stack,
            world.observer,
            world.objects,
            world.store,
            "/aasx/files/copy.txt",
            NOTE,
        )

    assert "/aasx/files/copy.txt" in world.store


def test_renaming_only_the_case_is_allowed(world) -> None:
    files.rename_file(
        world.stack,
        world.observer,
        world.objects,
        world.store,
        NOTE,
        "/aasx/files/Note.txt",
    )

    assert world.note.value == "/aasx/files/Note.txt"
    assert "/aasx/files/Note.txt" in world.store


def test_renaming_to_a_hostile_name_is_refused(world) -> None:
    with pytest.raises(InvalidPartNameError):
        files.rename_file(
            world.stack,
            world.observer,
            world.objects,
            world.store,
            NOTE,
            "/aasx/../../evil.txt",
        )
    assert snapshot(world.objects) == world.before


def test_renaming_a_missing_file_changes_nothing(world) -> None:
    with pytest.raises(KeyError):
        files.rename_file(
            world.stack,
            world.observer,
            world.objects,
            world.store,
            "/aasx/files/none.txt",
            "/aasx/files/other.txt",
        )
    assert not world.stack.can_undo


def test_moving_a_file_changes_its_folder_and_its_references(world) -> None:
    updated = files.move_file(
        world.stack,
        world.observer,
        world.objects,
        world.store,
        NOTE,
        "central\\docs",
    )

    assert updated == 1
    assert world.note.value == "/central/docs/note.txt"
    assert "/central/docs/note.txt" in world.store
    world.stack.undo()
    assert world.note.value == NOTE
    assert NOTE in world.store


def test_moving_into_a_folder_with_a_file_of_that_name_is_refused(
    world,
) -> None:
    world.store.add_file("/other/note.txt", io.BytesIO(b"x"), "text/plain")

    with pytest.raises(FileNameTakenError):
        files.move_file(
            world.stack,
            world.observer,
            world.objects,
            world.store,
            NOTE,
            "/other",
        )


def test_the_read_gate_refuses_a_rename_and_nothing_changes(world) -> None:
    stack = CommandStack(is_editing=lambda: False)

    with pytest.raises(ReadOnlyError):
        files.rename_file(
            stack, world.observer, world.objects, world.store, NOTE, "/n.txt"
        )

    assert snapshot(world.objects) == world.before
    assert NOTE in world.store


# -- remove ----------------------------------------------------------------


def test_removing_and_clearing_the_references_is_one_step(world) -> None:
    cleared = files.remove_file(
        world.stack,
        world.observer,
        world.objects,
        world.store,
        DOC,
        ReferenceChoice.CLEAR,
    )

    assert cleared == 3
    assert DOC not in world.store
    assert world.document.value is None
    assert world.annotation_file.value is None
    assert world.shell.asset_information.default_thumbnail is None
    assert files.find_dangling(world.objects, world.store) == []

    world.stack.undo()

    assert snapshot(world.objects) == world.before
    assert _bytes(world.store, DOC) == b"%PDF doc"
    assert world.store.get_content_type(DOC) == "application/pdf"
    assert world.shell.asset_information.default_thumbnail is world.thumbnail


def test_removing_and_leaving_the_references_leaves_them_dangling(
    world,
) -> None:
    files.remove_file(
        world.stack,
        world.observer,
        world.objects,
        world.store,
        DOC,
        ReferenceChoice.LEAVE,
    )

    assert world.paths() == [DOC, DOC, DOC]
    assert len(files.find_dangling(world.objects, world.store)) == 3
    world.stack.undo()
    assert files.find_dangling(world.objects, world.store) == []


def test_removing_a_file_that_shares_its_bytes_keeps_the_other_file(
    world,
) -> None:
    world.store.add_file(
        "/aasx/files/copy.txt", io.BytesIO(b"note"), "text/plain"
    )

    files.remove_file(
        world.stack, world.observer, world.objects, world.store, NOTE
    )
    world.stack.undo()

    assert _bytes(world.store, "/aasx/files/copy.txt") == b"note"
    assert _bytes(world.store, NOTE) == b"note"


# -- text files ------------------------------------------------------------


def test_creating_a_text_file_is_a_step_with_a_text_media_type(world) -> None:
    name = files.create_text_file(
        world.stack,
        world.observer,
        world.store,
        "/aasx/files/readme.md",
        "# Hi",
    )

    assert _bytes(world.store, name) == b"# Hi"
    assert world.store.get_content_type(name) == "text/markdown"
    world.stack.undo()
    assert name not in world.store


def test_a_text_file_with_an_unknown_extension_is_plain_text(world) -> None:
    name = files.create_text_file(
        world.stack, world.observer, world.store, "/aasx/files/log.zzz"
    )
    assert world.store.get_content_type(name) == "text/plain"
    assert _bytes(world.store, name) == b""


def test_creating_a_text_file_with_a_taken_name_changes_nothing(world) -> None:
    with pytest.raises(FileNameTakenError):
        files.create_text_file(
            world.stack, world.observer, world.store, NOTE.upper()
        )
    assert not world.stack.can_undo


def test_editing_a_text_file_keeps_non_ascii_text_and_line_breaks(
    world,
) -> None:
    text = "Grüße\r\nПривет 日本\r\n"

    changed = files.edit_text_file(
        world.stack, world.observer, world.store, NOTE, text
    )

    assert changed
    assert files.read_text(world.store, NOTE) == text
    assert _bytes(world.store, NOTE) == text.encode("utf-8")
    assert world.store.get_content_type(NOTE) == "text/plain"
    world.stack.undo()
    assert _bytes(world.store, NOTE) == b"note"
    world.stack.redo()
    assert files.read_text(world.store, NOTE) == text


def test_editing_with_the_same_text_pushes_no_step(world) -> None:
    assert not files.edit_text_file(
        world.stack, world.observer, world.store, NOTE, "note"
    )
    assert not world.stack.can_undo


def test_a_binary_file_is_not_read_as_text(world) -> None:
    world.store.add_file(
        "/b.bin", io.BytesIO(b"\xff\xfe\x00"), "application/octet-stream"
    )

    with pytest.raises(NotTextError):
        files.read_text(world.store, "/b.bin")


# -- linking and repair ----------------------------------------------------


def test_linking_a_file_element_keeps_its_media_type_unless_asked(
    world,
) -> None:
    element = make_file_element("New", None, "text/html")
    world.submodel.submodel_element.add(element)

    files.link_file_element(
        world.stack, world.observer, world.store, element, DOC
    )
    kept = (element.value, element.content_type)
    world.stack.undo()
    files.link_file_element(
        world.stack,
        world.observer,
        world.store,
        element,
        DOC,
        adopt_content_type=True,
    )

    assert kept == (DOC, "text/html")
    assert (element.value, element.content_type) == (DOC, "application/pdf")
    world.stack.undo()
    assert (element.value, element.content_type) == (None, "text/html")


def test_linking_to_a_file_that_is_not_stored_is_refused(world) -> None:
    with pytest.raises(files.FileOperationError):
        files.link_file_element(
            world.stack, world.observer, world.store, world.note, "/none.txt"
        )
    assert world.note.value == NOTE


def test_the_thumbnail_is_set_and_created_when_the_shell_has_none(
    world,
) -> None:
    asset = world.shell.asset_information
    asset.default_thumbnail = None

    files.link_thumbnail(world.stack, world.observer, world.store, asset, NOTE)
    assert asset.default_thumbnail is not None
    assert asset.default_thumbnail.path == NOTE
    assert asset.default_thumbnail.content_type == "text/plain"
    files.link_thumbnail(world.stack, world.observer, world.store, asset, DOC)
    assert asset.default_thumbnail.path == DOC
    world.stack.undo()
    assert asset.default_thumbnail.path == NOTE
    world.stack.undo()
    assert asset.default_thumbnail is None


def test_adding_and_linking_is_one_step_and_adopts_the_media_type(
    world,
) -> None:
    element = make_file_element("New", None, "text/plain")
    world.submodel.submodel_element.add(element)

    name = files.add_and_link(
        world.stack,
        world.observer,
        world.store,
        element,
        "/aasx/files/report_final.pdf",
        b"%PDF",
        "application/pdf",
    )
    linked = (element.value, element.content_type)
    world.stack.undo()

    assert name == "/aasx/files/report_final.pdf"
    assert linked == (name, "application/pdf")
    assert name not in world.store
    assert (element.value, element.content_type) == (None, "text/plain")


def test_a_dangling_reference_is_repaired_by_linking_it_to_a_stored_file(
    world,
) -> None:
    world.store.delete_file(DOC)
    reference = next(
        ref
        for ref in files.find_dangling(world.objects, world.store)
        if ref.location == "Default thumbnail"
    )

    for command in files.link_commands(world.observer, reference, NOTE):
        world.stack.push(command)

    assert world.thumbnail.path == NOTE
    assert [
        ref.location for ref in files.find_dangling(world.objects, world.store)
    ] == [
        "Document",
        "Group.Relationship.Annotated",
    ]


def test_every_command_reports_to_the_observer_and_nothing_else(world) -> None:
    files.rename_file(
        world.stack, world.observer, world.objects, world.store, NOTE, "/n.txt"
    )

    assert world.changes
    assert any(change.target is world.store for change in world.changes)
