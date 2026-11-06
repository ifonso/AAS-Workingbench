"""The controller, the panel, and the actions of the package files.

The dialogs that ask the user are replaced by functions with fixed answers, so
the tests drive the same code as a click does and check the package afterwards.
"""

from collections.abc import Iterator
import io
from pathlib import Path
from types import SimpleNamespace

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QTableWidgetSelectionRange
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.serialization import snapshot

DOC = "/aasx/files/doc.pdf"
NOTE = "/aasx/files/note.txt"
UNUSED = "/aasx/files/unused.bin"
THUMB = "/aasx/files/thumb.png"
FILES = {
    DOC: (b"%PDF doc", "application/pdf"),
    NOTE: (b"note", "text/plain"),
    UNUSED: (b"\xff\xfe", "application/octet-stream"),
    THUMB: (b"png", "image/png"),
}


@pytest.fixture
def world(views, monkeypatch: pytest.MonkeyPatch, qapp: object):
    """A package with files, and the answers that the dialogs give."""
    from aas_editor.ui import file_dialogs

    document = make_file_element("Document", DOC, "application/pdf")
    note = make_file_element("Note", NOTE, "text/plain")
    submodel = make_submodel(elements=[document, note])
    shell = make_shell(
        submodels=[submodel],
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(THUMB, "image/png")
        ),
    )
    shown = views()
    package = shown.open_package(shell, submodel, files=FILES)
    answers = SimpleNamespace(
        text=None,
        picked=None,
        chosen=None,
        edited=None,
        references=file_dialogs.ReferenceAnswer.CLEAR,
        save_path=None,
        warnings=[],
        information=[],
        asked=[],
    )

    def ask_text(parent, title, label, text=""):
        answers.asked.append((title, label, text))
        return text if answers.text is None else answers.text

    monkeypatch.setattr(file_dialogs, "ask_text", ask_text)
    monkeypatch.setattr(
        file_dialogs, "pick_file_to_add", lambda parent: answers.picked
    )
    monkeypatch.setattr(
        file_dialogs,
        "pick_path_to_save",
        lambda parent, name: answers.save_path,
    )
    monkeypatch.setattr(
        file_dialogs,
        "choose_stored_file",
        lambda infos, current=None, title="", parent=None: answers.chosen,
    )
    monkeypatch.setattr(
        file_dialogs,
        "edit_text",
        lambda name, text, parent=None: answers.edited,
    )
    monkeypatch.setattr(
        file_dialogs,
        "ask_remove_references",
        lambda references, parent=None: answers.references,
    )
    monkeypatch.setattr(
        file_dialogs,
        "show_warning",
        lambda parent, text: answers.warnings.append(text),
    )
    monkeypatch.setattr(
        file_dialogs,
        "show_information",
        lambda parent, text: answers.information.append(text),
    )
    return SimpleNamespace(
        shown=shown,
        package=package,
        submodel=submodel,
        shell=shell,
        document=document,
        note=note,
        answers=answers,
        before=snapshot(package.objStore),
    )


@pytest.fixture
def controller(world):
    from aas_editor.ui.file_controller import FileController

    return FileController(world.package, None)


def _content(package, name: str) -> bytes:
    out = io.BytesIO()
    package.fileStore.write_file(name, out)
    return out.getvalue()


@pytest.fixture
def read_mode() -> Iterator[None]:
    from aas_editor.application.editing import edit_mode

    edit_mode().set_editing(False)
    yield
    edit_mode().set_editing(True)


# -- add -------------------------------------------------------------------


def test_adding_a_file_sanitizes_the_name_and_guesses_the_media_type(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "report final.pdf"
    source.write_bytes(b"%PDF report")
    world.answers.picked = source

    name = controller.add_from_disk()

    assert name == "/aasx/files/report_final.pdf"
    assert _content(world.package, name) == b"%PDF report"
    assert world.package.fileStore.get_content_type(name) == "application/pdf"
    assert world.answers.asked[0][2] == name
    world.package.commandStack.undo()
    assert name not in world.package.fileStore


def test_an_unknown_extension_is_stored_as_binary(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "data.zzz"
    source.write_bytes(b"x")
    world.answers.picked = source

    name = controller.add_from_disk()

    assert world.package.fileStore.get_content_type(name) == (
        "application/octet-stream"
    )


def test_adding_a_different_file_under_a_taken_name_tells_the_user(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "note.txt"
    source.write_bytes(b"another note")
    world.answers.picked = source

    name = controller.add_from_disk()

    assert name == "/aasx/files/note_0001.txt"
    assert _content(world.package, NOTE) == b"note"
    assert len(world.answers.information) == 1
    assert NOTE in world.answers.information[0]


def test_a_hostile_name_typed_by_the_user_is_refused(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "a.txt"
    source.write_bytes(b"x")
    world.answers.picked = source
    world.answers.text = "/../../evil.txt"

    name = controller.add_from_disk()

    assert name is None
    assert len(world.answers.warnings) == 1
    assert (
        "'..'" in world.answers.warnings[0]
        or "valid" in (world.answers.warnings[0])
    )
    assert sorted(world.package.fileStore) == sorted(FILES)
    assert not world.package.commandStack.can_undo


def test_a_cancelled_picker_changes_nothing(world, controller) -> None:
    world.answers.picked = None

    assert controller.add_from_disk() is None
    assert not world.package.commandStack.can_undo


def test_read_mode_refuses_adding_with_a_message(
    world, controller, tmp_path: Path, read_mode: None
) -> None:
    source = tmp_path / "a.txt"
    source.write_bytes(b"x")
    world.answers.picked = source

    assert controller.add_from_disk() is None

    assert "Read mode" in world.answers.warnings[0]
    assert sorted(world.package.fileStore) == sorted(FILES)


def test_an_unreadable_source_is_reported(
    world, controller, tmp_path: Path
) -> None:
    world.answers.picked = tmp_path / "missing.txt"

    assert controller.add_from_disk() is None

    assert len(world.answers.warnings) == 1
    assert sorted(world.package.fileStore) == sorted(FILES)


# -- text files ----------------------------------------------------------------


def test_a_text_file_is_created_empty_and_edited_with_utf8(
    world, controller
) -> None:
    world.answers.text = "/aasx/files/readme.txt"
    name = controller.new_text_file()
    world.answers.edited = "Grüße — 日本"

    changed = controller.edit_text(name)

    assert name == "/aasx/files/readme.txt"
    assert changed
    assert _content(world.package, name) == "Grüße — 日本".encode()
    world.package.commandStack.undo()
    assert _content(world.package, name) == b""


def test_creating_a_text_file_with_a_taken_name_warns_and_changes_nothing(
    world, controller
) -> None:
    world.answers.text = NOTE

    assert controller.new_text_file() is None

    assert "already" in world.answers.warnings[0]
    assert not world.package.commandStack.can_undo


def test_creating_a_text_file_for_a_file_element_links_it_in_one_step(
    world, controller
) -> None:
    world.answers.text = "/aasx/files/new.txt"

    name = controller.new_text_file(world.document)

    assert world.document.value == name
    assert world.document.content_type == "text/plain"
    world.package.commandStack.undo()
    assert world.document.value == DOC
    assert world.document.content_type == "application/pdf"
    assert name not in world.package.fileStore


def test_a_binary_file_cannot_be_edited_as_text(world, controller) -> None:
    world.answers.edited = "x"

    assert not controller.edit_text(UNUSED)

    assert "not UTF-8 text" in world.answers.warnings[0]


def test_cancelling_the_editor_changes_nothing(world, controller) -> None:
    world.answers.edited = None

    assert not controller.edit_text(NOTE)
    assert not world.package.commandStack.can_undo


# -- rename, move, remove ----------------------------------------------------------


def test_renaming_tells_how_many_references_are_updated(
    world, controller
) -> None:
    world.answers.text = "/aasx/files/manual.pdf"

    new = controller.rename(DOC)

    assert new == "/aasx/files/manual.pdf"
    assert "1 reference" in world.answers.asked[0][1]
    assert world.document.value == new
    world.package.commandStack.undo()
    assert snapshot(world.package.objStore) == world.before


def test_renaming_onto_a_taken_name_warns_and_keeps_everything(
    world, controller
) -> None:
    world.answers.text = NOTE

    assert controller.rename(DOC) is None

    assert "already" in world.answers.warnings[0]
    assert snapshot(world.package.objStore) == world.before
    assert not world.package.commandStack.can_undo


def test_moving_a_file_updates_its_references(world, controller) -> None:
    world.answers.text = "central"

    new = controller.move(NOTE)

    assert new == "/central/note.txt"
    assert world.note.value == "/central/note.txt"
    assert "/central/note.txt" in world.package.fileStore


def test_removing_a_file_asks_about_its_references(world, controller) -> None:
    world.answers.references = world.answers.references.CLEAR

    assert controller.remove(DOC)

    assert DOC not in world.package.fileStore
    assert world.document.value is None


def test_cancelling_the_question_keeps_the_file(world, controller) -> None:
    world.answers.references = world.answers.references.CANCEL

    assert not controller.remove(DOC)

    assert DOC in world.package.fileStore
    assert not world.package.commandStack.can_undo


def test_removing_a_file_nothing_refers_to_asks_nothing(
    world, controller
) -> None:
    world.answers.references = world.answers.references.CANCEL

    assert controller.remove(UNUSED)

    assert UNUSED not in world.package.fileStore


def test_several_files_are_removed_as_one_step_with_one_question(
    world, controller, monkeypatch
) -> None:
    from aas_editor.ui import file_dialogs

    questions: list[int] = []

    def ask(references, parent=None):
        questions.append(len(references))
        return file_dialogs.ReferenceAnswer.CLEAR

    monkeypatch.setattr(file_dialogs, "ask_remove_references", ask)

    assert controller.remove_many([DOC, NOTE, UNUSED])

    assert sorted(world.package.fileStore) == [THUMB]
    assert world.document.value is None and world.note.value is None
    assert questions == [2]
    world.package.commandStack.undo()
    assert sorted(world.package.fileStore) == sorted(FILES)
    assert (world.document.value, world.note.value) == (DOC, NOTE)
    assert not world.package.commandStack.can_undo


def test_cancelling_the_question_for_several_files_keeps_all_of_them(
    world, controller
) -> None:
    world.answers.references = world.answers.references.CANCEL

    assert not controller.remove_many([DOC, UNUSED])

    assert sorted(world.package.fileStore) == sorted(FILES)
    assert not world.package.commandStack.can_undo


def test_leaving_the_paths_removes_only_the_files(world, controller) -> None:
    world.answers.references = world.answers.references.LEAVE

    assert controller.remove_many([DOC, NOTE])

    assert (world.document.value, world.note.value) == (DOC, NOTE)
    assert sorted(world.package.fileStore) == sorted([UNUSED, THUMB])


def test_saving_a_file_to_disk_writes_its_bytes(
    world, controller, tmp_path: Path
) -> None:
    world.answers.save_path = tmp_path / "out.pdf"

    assert controller.save_to_disk(DOC)

    assert (tmp_path / "out.pdf").read_bytes() == b"%PDF doc"


# -- links and the picker (D15) ------------------------------------------------------


def test_choosing_a_file_for_a_file_element_keeps_its_media_type(
    world, controller
) -> None:
    world.answers.chosen = NOTE

    assert controller.choose_for(world.document)

    assert world.document.value == NOTE
    assert world.document.content_type == "application/pdf"


def test_adding_a_file_for_a_file_element_sets_value_and_media_type(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "report final.pdf"
    source.write_bytes(b"%PDF report")
    world.answers.picked = source

    name = controller.add_for(world.note)

    assert name == "/aasx/files/report_final.pdf"
    assert world.note.value == name
    assert world.note.content_type == "application/pdf"
    world.package.commandStack.undo()
    assert world.note.value == NOTE
    assert world.note.content_type == "text/plain"
    assert name not in world.package.fileStore


def test_choosing_a_default_thumbnail_and_adding_one(
    world, controller, tmp_path: Path
) -> None:
    asset = world.shell.asset_information
    world.answers.chosen = DOC

    assert controller.choose_thumbnail(asset)
    assert asset.default_thumbnail.path == DOC

    source = tmp_path / "logo.png"
    source.write_bytes(b"logo")
    world.answers.picked = source
    name = controller.add_thumbnail(asset)

    assert asset.default_thumbnail.path == name == "/aasx/files/logo.png"
    world.package.commandStack.undo()
    assert asset.default_thumbnail.path == DOC
    assert "/aasx/files/logo.png" not in world.package.fileStore


def test_the_default_thumbnail_is_removed_after_a_question_and_the_file_stays(
    world, controller, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.package import Package
    from aas_editor.ui import file_dialogs

    questions: list[str] = []
    monkeypatch.setattr(
        file_dialogs,
        "confirm",
        lambda parent, text: questions.append(text) or True,
    )
    asset = world.shell.asset_information

    assert controller.remove_thumbnail(asset)

    assert asset.default_thumbnail is None
    assert THUMB in world.package.fileStore
    assert THUMB in questions[0]
    path = tmp_path / "no_thumb.aasx"
    world.package.write(path)
    assert (
        Package(path)
        .objStore.get_item(world.shell.id)
        .asset_information.default_thumbnail
        is None
    )
    world.package.commandStack.undo()
    assert asset.default_thumbnail.path == THUMB


def test_declining_the_question_keeps_the_default_thumbnail(
    world, controller, monkeypatch
) -> None:
    from aas_editor.ui import file_dialogs

    monkeypatch.setattr(file_dialogs, "confirm", lambda parent, text: False)

    assert not controller.remove_thumbnail(world.shell.asset_information)

    assert world.shell.asset_information.default_thumbnail.path == THUMB
    assert not world.package.commandStack.can_undo


def test_without_a_default_thumbnail_there_is_nothing_to_remove(
    world, controller
) -> None:
    world.shell.asset_information.default_thumbnail = None

    assert not controller.remove_thumbnail(world.shell.asset_information)

    assert world.answers.warnings == ["The AAS has no default thumbnail."]


def test_a_removed_default_thumbnail_can_be_chosen_again(
    world, controller, monkeypatch
) -> None:
    from aas_editor.ui import file_dialogs

    monkeypatch.setattr(file_dialogs, "confirm", lambda parent, text: True)
    asset = world.shell.asset_information
    controller.remove_thumbnail(asset)
    world.answers.chosen = THUMB

    assert controller.choose_thumbnail(asset)

    assert asset.default_thumbnail.path == THUMB


def test_remove_default_thumbnail_is_offered_on_a_shell_that_has_one(
    views,
) -> None:
    from aas_editor.ui.file_actions import register_file_actions

    register_file_actions()
    shown = views()
    shell = make_shell(
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(THUMB, "image/png")
        )
    )
    shown.open_package(shell, files=FILES)
    shown.select(shown.index("shells", "Shell"))
    view = shown.view
    view.updateActions(view.currentIndex())
    action = view.registeredActions.find("files.remove_thumbnail")

    offered = action.isEnabled()
    shell.asset_information.default_thumbnail = None
    view.updateActions(view.currentIndex())

    assert offered
    assert not action.isEnabled()


def test_the_package_thumbnail_is_changed_saved_and_read_back(
    world, controller, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.package import Package
    from aas_editor.ui import file_dialogs

    image = tmp_path / "cover.png"
    image.write_bytes(b"\x89PNG cover")
    monkeypatch.setattr(file_dialogs, "pick_thumbnail_image", lambda p: image)

    assert controller.change_package_thumbnail()

    thumbnail = world.package.thumbnail
    assert (thumbnail.name, thumbnail.content_type, thumbnail.data) == (
        "/thumbnail.png",
        "image/png",
        b"\x89PNG cover",
    )
    assert "/thumbnail.png" not in world.package.fileStore
    saved = tmp_path / "with_thumbnail.aasx"
    world.package.write(saved)
    reloaded = Package(saved).thumbnail
    assert reloaded is not None and reloaded.data == b"\x89PNG cover"
    assert reloaded.name == "/thumbnail.png"
    world.package.commandStack.undo()
    assert world.package.thumbnail is None


def test_a_file_that_is_no_image_is_refused_with_a_message(
    world, controller, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.ui import file_dialogs

    text = tmp_path / "notes.txt"
    text.write_bytes(b"hello")
    monkeypatch.setattr(file_dialogs, "pick_thumbnail_image", lambda p: text)

    assert not controller.change_package_thumbnail()

    assert world.package.thumbnail is None
    assert "not an image" in world.answers.warnings[0]
    assert not world.package.commandStack.can_undo


def test_cancelling_the_picker_keeps_the_package_thumbnail(
    world, controller, monkeypatch
) -> None:
    from aas_editor.ui import file_dialogs

    monkeypatch.setattr(file_dialogs, "pick_thumbnail_image", lambda p: None)

    assert not controller.change_package_thumbnail()

    assert not world.package.commandStack.can_undo


def test_a_changed_package_thumbnail_survives_a_crash(
    world, controller, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.package import Package
    from aas_editor.ui import file_dialogs

    source = tmp_path / "source.aasx"
    world.package.write(source)
    package = Package(source)
    image = tmp_path / "new.jpg"
    image.write_bytes(b"jpeg")
    monkeypatch.setattr(file_dialogs, "pick_thumbnail_image", lambda p: image)
    from aas_editor.ui.file_controller import FileController

    assert FileController(package, None).change_package_thumbnail()

    recovery = package.write_recovery(tmp_path / "recovery")
    restored = Package.restore_from_recovery(recovery, source)

    assert restored.thumbnail is not None
    assert restored.thumbnail.data == b"jpeg"
    assert restored.thumbnail_changed()


def test_an_unchanged_package_thumbnail_keeps_the_cheap_recovery(
    world, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = tmp_path / "source.aasx"
    world.package.write(source)
    package = Package(source)

    recovery = package.write_recovery(tmp_path / "recovery")

    assert recovery.suffix == ".json"
    assert not package.thumbnail_changed()


def test_the_panel_says_which_package_thumbnail_there_is(
    world, controller, panel, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.ui import file_dialogs

    before = panel.summary_label.text()
    image = tmp_path / "cover.png"
    image.write_bytes(b"png")
    monkeypatch.setattr(file_dialogs, "pick_thumbnail_image", lambda p: image)
    controller.change_package_thumbnail()
    panel.refresh()

    assert "No package thumbnail" in before
    assert "/thumbnail.png" in panel.summary_label.text()


def test_the_package_thumbnail_button_is_off_in_read_mode(world, panel) -> None:
    from aas_editor.application.editing import edit_mode

    on = panel.thumbnail_button.isEnabled()
    edit_mode().set_editing(False)
    try:
        off = not panel.thumbnail_button.isEnabled()
    finally:
        edit_mode().set_editing(True)

    assert on and off


def test_editing_the_text_file_of_a_file_element(world, controller) -> None:
    world.answers.edited = "edited"

    assert controller.edit_text_of(world.note)
    assert _content(world.package, NOTE) == b"edited"


def test_a_file_element_without_a_stored_file_cannot_be_edited(
    world, controller
) -> None:
    world.document.value = "https://example.com/a.txt"

    assert not controller.edit_text_of(world.document)
    assert len(world.answers.warnings) == 1


# -- dangling references --------------------------------------------------------


def _make_dangling(world) -> None:
    from aas_editor.application import supplementary_files as files
    from aas_editor.application.changes import observer_for

    files.remove_file(
        world.package.commandStack,
        observer_for(world.package),
        world.package.objStore,
        world.package.fileStore,
        DOC,
        files.ReferenceChoice.LEAVE,
    )


def test_the_dangling_references_are_listed_and_repaired_by_a_stored_file(
    world, controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    _make_dangling(world)
    world.answers.chosen = NOTE
    rows: list[list[str]] = []

    def exec_dialog(dialog) -> int:
        rows.append(
            [
                dialog.table.item(r, 0).text()
                for r in range(dialog.table.rowCount())
            ]
        )
        dialog.table.selectRow(0)
        dialog.choose_button.click()
        rows.append(
            [
                dialog.table.item(r, 0).text()
                for r in range(dialog.table.rowCount())
            ]
        )
        return 0

    monkeypatch.setattr(file_dialogs.DanglingDialog, "exec", exec_dialog)

    controller.repair_dangling()

    assert rows == [["Document"], []]
    assert world.document.value == NOTE
    assert controller.dangling() == []


def test_a_dangling_path_is_cleared_in_the_repair_dialog(
    world, controller, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    _make_dangling(world)

    def exec_dialog(dialog) -> int:
        dialog.table.selectRow(0)
        dialog.clear_button.click()
        return 0

    monkeypatch.setattr(file_dialogs.DanglingDialog, "exec", exec_dialog)

    controller.repair_dangling()

    assert world.document.value is None
    world.package.commandStack.undo()
    assert world.document.value == DOC


def test_a_dangling_path_is_repaired_with_a_new_file(
    world, controller, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_editor.ui import file_dialogs

    _make_dangling(world)
    source = tmp_path / "doc.pdf"
    source.write_bytes(b"%PDF replacement")
    world.answers.picked = source

    def exec_dialog(dialog) -> int:
        dialog.table.selectRow(0)
        dialog.add_button.click()
        return 0

    monkeypatch.setattr(file_dialogs.DanglingDialog, "exec", exec_dialog)

    controller.repair_dangling()

    assert world.document.value == DOC
    assert _content(world.package, DOC) == b"%PDF replacement"
    assert controller.dangling() == []
    world.package.commandStack.undo()
    assert DOC not in world.package.fileStore


# -- the panel ------------------------------------------------------------------


@pytest.fixture
def panel(world, qtbot):
    from aas_editor.ui.package_files import PackageFilesPanel

    panel = PackageFilesPanel(lambda: world.package)
    qtbot.addWidget(panel)
    panel.show()
    panel.set_package(world.package)
    return panel


def _rows(panel) -> dict[str, list[str]]:
    return {
        panel.table.item(row, 0).text(): [
            panel.table.item(row, column).text() for column in range(1, 4)
        ]
        for row in range(panel.table.rowCount())
    }


def test_the_panel_lists_each_file_with_what_refers_to_it(panel) -> None:
    rows = _rows(panel)

    assert sorted(rows) == sorted(FILES)
    assert rows[DOC] == ["application/pdf", "8 B", "Document"]
    assert rows[THUMB][2] == "Default thumbnail"
    assert rows[UNUSED][2].startswith("Not referenced")
    assert "4 file(s)" in panel.summary_label.text()


def test_the_panel_follows_changes_and_undo(world, panel, qtbot) -> None:
    from aas_editor.application import supplementary_files as files
    from aas_editor.application.changes import observer_for

    files.rename_file(
        world.package.commandStack,
        observer_for(world.package),
        world.package.objStore,
        world.package.fileStore,
        DOC,
        "/aasx/files/manual.pdf",
    )
    qtbot.waitUntil(lambda: "/aasx/files/manual.pdf" in _rows(panel))
    renamed = _rows(panel)["/aasx/files/manual.pdf"][2]
    world.package.commandStack.undo()
    qtbot.waitUntil(lambda: DOC in _rows(panel))

    assert renamed == "Document"
    assert "/aasx/files/manual.pdf" not in _rows(panel)


def test_the_panel_buttons_work_on_the_selected_file(
    world, panel, qtbot
) -> None:
    world.answers.text = "/aasx/files/renamed.txt"
    panel.table.selectRow(sorted(FILES).index(NOTE))

    panel.rename_button.click()
    qtbot.waitUntil(lambda: "/aasx/files/renamed.txt" in _rows(panel))

    assert world.note.value == "/aasx/files/renamed.txt"


def test_the_panel_removes_several_selected_files_at_once(
    world, panel, qtbot
) -> None:
    names = sorted(FILES)
    panel.table.clearSelection()
    panel.table.setRangeSelected(
        QTableWidgetSelectionRange(names.index(DOC), 0, names.index(DOC), 3),
        True,
    )
    panel.table.setRangeSelected(
        QTableWidgetSelectionRange(
            names.index(UNUSED), 0, names.index(UNUSED), 3
        ),
        True,
    )
    selected = panel.selected_names()
    single_only = [
        button.isEnabled()
        for button in (panel.rename_button, panel.edit_button)
    ]

    panel.remove_button.click()
    qtbot.waitUntil(lambda: UNUSED not in _rows(panel))

    assert sorted(selected) == sorted([DOC, UNUSED])
    assert single_only == [False, False]
    assert sorted(world.package.fileStore) == sorted([NOTE, THUMB])
    world.package.commandStack.undo()
    assert sorted(world.package.fileStore) == sorted(FILES)


def test_the_selected_files_stay_selected_when_the_list_refreshes(
    world, panel
) -> None:
    names = sorted(FILES)
    for name in (NOTE, THUMB):
        index = names.index(name)
        panel.table.setRangeSelected(
            QTableWidgetSelectionRange(index, 0, index, 3), True
        )

    panel.refresh()

    assert sorted(panel.selected_names()) == sorted([NOTE, THUMB])


def test_the_edit_button_is_for_text_files_only(world, panel) -> None:
    panel.table.selectRow(sorted(FILES).index(NOTE))
    on_text = panel.edit_button.isEnabled()
    panel.table.selectRow(sorted(FILES).index(UNUSED))

    assert on_text
    assert not panel.edit_button.isEnabled()
    assert panel.remove_button.isEnabled()


def test_the_buttons_that_change_the_package_are_off_in_read_mode(
    world, panel
) -> None:
    from aas_editor.application.editing import edit_mode

    panel.table.selectRow(0)
    edit_mode().set_editing(False)
    try:
        disabled = [
            not button.isEnabled()
            for button in (
                panel.add_button,
                panel.new_button,
                panel.edit_button,
                panel.rename_button,
                panel.move_button,
                panel.remove_button,
            )
        ]
        can_save = panel.save_button.isEnabled()
    finally:
        edit_mode().set_editing(True)

    assert disabled == [True] * 6
    assert can_save


def test_the_panel_without_a_package_says_so(qtbot) -> None:
    from aas_editor.ui.package_files import PackageFilesPanel

    panel = PackageFilesPanel(lambda: None)
    qtbot.addWidget(panel)

    assert panel.table.rowCount() == 0
    assert not panel.add_button.isEnabled()
    assert "No package" in panel.summary_label.text()


def test_the_buttons_fit_a_panel_of_the_width_of_a_dock(qtbot) -> None:
    from aas_editor.ui.package_files import PackageFilesPanel

    panel = PackageFilesPanel(lambda: None)
    qtbot.addWidget(panel)
    buttons = (
        panel.add_button,
        panel.new_button,
        panel.edit_button,
        panel.rename_button,
        panel.move_button,
        panel.remove_button,
        panel.save_button,
        panel.dangling_button,
    )

    needed = panel.minimumSizeHint().width()
    panel.resize(needed, 300)
    panel.show()
    qtbot.waitExposed(panel)
    cut_off = [b.text() for b in buttons if b.width() < b.sizeHint().width()]

    # Eight buttons in one row need about 1000 pixels, and a dock is often
    # narrower, so the buttons were cut and showed "ew text file".
    assert needed <= 700
    assert cut_off == []


def test_the_dangling_summary_is_shown(world, panel) -> None:
    _make_dangling(world)
    panel.refresh()

    assert "1 reference(s) point to a file that is not in the package" in (
        panel.summary_label.text()
    )


# -- the context menu actions ---------------------------------------------------------


@pytest.fixture
def registered(qapp: object) -> Iterator[None]:
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.file_actions import action_ids
    from aas_editor.ui.file_actions import register_file_actions

    register_file_actions()
    yield
    for action_id in action_ids():
        default_registry().unregister(action_id)


def _action(shown, action_id: str, *path: str):
    index = shown.index(*path)
    shown.select(index)
    shown.view.updateActions(index)
    return shown.view.registeredActions.find(action_id)


def _enabled(shown, action_id: str, *path: str) -> bool:
    return _action(shown, action_id, *path).isEnabled()


def test_registering_twice_adds_each_action_once(registered: None) -> None:
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.actions import ViewKind
    from aas_editor.ui.file_actions import register_file_actions

    register_file_actions()

    ids = [s.action_id for s in default_registry().specs_for(ViewKind.ANY)]
    assert len(ids) == len(set(ids))
    assert "files.rename" in ids


def test_file_actions_are_enabled_on_the_rows_of_stored_files(
    world, registered: None, views
) -> None:
    del world
    shown = views()
    shown.open_package(make_shell(), files=FILES)

    rename = _enabled(shown, "files.rename", "fileStore", NOTE)
    edit = _enabled(shown, "files.edit_text", "fileStore", NOTE)
    edit_binary = _enabled(shown, "files.edit_text", "fileStore", UNUSED)
    add_on_folder = _enabled(shown, "files.add", "fileStore")
    rename_on_folder = _enabled(shown, "files.rename", "fileStore")

    assert rename
    assert edit
    assert not edit_binary
    assert add_on_folder
    assert not rename_on_folder


def test_the_rename_action_renames_and_updates_the_references(
    views, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    note = make_file_element("Note", NOTE, "text/plain")
    shown = views()
    package = shown.open_package(make_submodel(elements=[note]), files=FILES)
    monkeypatch.setattr(
        file_dialogs, "ask_text", lambda *args, **kwargs: "/aasx/files/n.txt"
    )

    _action(shown, "files.rename", "fileStore", NOTE).trigger()

    assert note.value == "/aasx/files/n.txt"
    assert "/aasx/files/n.txt" in package.fileStore
    package.commandStack.undo()
    assert note.value == NOTE
    assert NOTE in package.fileStore


def test_the_rows_of_the_file_store_follow_a_rename_and_its_undo(
    views, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    shown = views()
    package = shown.open_package(make_shell(), files=FILES)
    monkeypatch.setattr(
        file_dialogs, "ask_text", lambda *args, **kwargs: "/aasx/files/n.txt"
    )
    _action(shown, "files.rename", "fileStore", NOTE).trigger()
    proxy = shown.view.model()

    def names() -> list[str]:
        folder = shown.index("fileStore")
        return sorted(
            proxy.index(row, 0, folder).data()
            for row in range(proxy.rowCount(folder))
        )

    renamed = names()
    package.commandStack.undo()

    assert "/aasx/files/n.txt" in renamed
    assert NOTE not in renamed
    assert NOTE in names()
    assert "/aasx/files/n.txt" not in names()


def test_file_element_actions_are_enabled_on_a_file_element_only(
    views, registered: None
) -> None:
    shown = views()
    shown.open_package(
        make_submodel(
            elements=[
                make_file_element("Doc", DOC),
                make_file_element("Note", NOTE),
            ]
        ),
        files=FILES,
    )
    path = ("submodels", "Submodel", "Doc")

    choose = _enabled(shown, "files.choose", *path)
    on_submodel = _enabled(shown, "files.choose", "submodels", "Submodel")

    assert choose
    assert not on_submodel


def test_the_choose_action_links_a_file_element(
    views, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import file_dialogs

    doc = make_file_element("Doc", DOC)
    shown = views()
    package = shown.open_package(make_submodel(elements=[doc]), files=FILES)
    monkeypatch.setattr(
        file_dialogs,
        "choose_stored_file",
        lambda infos, current=None, title="", parent=None: NOTE,
    )

    _action(shown, "files.choose", "submodels", "Submodel", "Doc").trigger()

    assert doc.value == NOTE
    package.commandStack.undo()
    assert doc.value == DOC


def test_the_thumbnail_action_is_enabled_on_the_asset_information(
    views, registered: None
) -> None:
    shown = views()
    submodel = make_submodel()
    shown.open_package(make_shell(submodels=[submodel]), submodel, files=FILES)

    on_shell = _enabled(shown, "files.choose_thumbnail", "shells", "Shell")
    on_files = _enabled(shown, "files.choose_thumbnail", "fileStore")

    assert on_shell
    assert not on_files


def test_the_actions_that_change_the_package_are_off_in_read_mode(
    views, registered: None, read_mode: None
) -> None:
    shown = views()
    shown.open_package(make_shell(), files=FILES)

    rename = _enabled(shown, "files.rename", "fileStore", NOTE)
    save_as = _enabled(shown, "files.save_as", "fileStore", NOTE)
    dangling = _enabled(shown, "files.dangling", "fileStore", NOTE)

    assert not rename
    assert save_as
    assert dangling
