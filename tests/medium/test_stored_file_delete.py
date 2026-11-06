"""Deleting a stored file in the package tree.

Deleting a row of the file store used to fail with "Unknown parent object
type", because the model knew how to delete members of sets and lists only.
"""

import io

from basyx.aas import model
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_submodel

PART = "/aasx/files/note.txt"
FILES = {PART: (b"hello", "text/plain")}


def test_deleting_a_stored_file_row_removes_the_file_and_undo_brings_it_back(
    model_support,
) -> None:
    from aas_editor.settings.app_settings import CLEAR_ROW_ROLE
    from aas_editor.settings.app_settings import NOT_GIVEN

    table = model_support.pack_table(make_shell(), files=FILES)
    model_support.watch(table)
    package = model_support.package_of(table)
    file_store = model_support.find_path(table, "", "fileStore")
    file_row = model_support.find(table, PART, file_store)

    table.setData(file_row, NOT_GIVEN, CLEAR_ROW_ROLE)
    after_delete = list(package.fileStore)
    rows_after_delete = model_support.names(table, file_store)
    package.commandStack.undo()
    content = io.BytesIO()
    package.fileStore.write_file(PART, content)

    assert after_delete == []
    assert rows_after_delete == []
    assert list(package.fileStore) == [PART]
    assert content.getvalue() == b"hello"
    assert package.fileStore.get_content_type(PART) == "text/plain"
    assert model_support.names(table, file_store) == [PART]
    assert model_support.violations() == []


def _open_referenced(views, monkeypatch, answer_name: str):
    from aas_editor.ui import file_dialogs

    shown = views()
    submodel = make_submodel(
        elements=[make_file_element("Note", PART, "text/plain")]
    )
    package = shown.open_package(
        make_shell(submodels=[submodel]), submodel, files=FILES
    )
    shown.view.expandAll()
    monkeypatch.setattr(
        file_dialogs,
        "ask_remove_references",
        lambda references, parent=None: file_dialogs.ReferenceAnswer[
            answer_name
        ],
    )
    shown.select(shown.index("fileStore", PART))
    element = next(iter(submodel.submodel_element))
    assert isinstance(element, model.File)
    return shown, package, element


def test_deleting_a_stored_file_in_the_view_leaves_the_references_when_asked(
    views, monkeypatch
) -> None:
    shown, package, element = _open_referenced(views, monkeypatch, "LEAVE")

    shown.view.onDelClear()
    after_delete = (list(package.fileStore), element.value)
    package.commandStack.undo()

    assert after_delete == ([], PART)
    assert list(package.fileStore) == [PART]
    assert element.value == PART


def test_deleting_a_stored_file_in_the_view_clears_the_references_in_one_step(
    views, monkeypatch
) -> None:
    shown, package, element = _open_referenced(views, monkeypatch, "CLEAR")

    shown.view.onDelClear()
    cleared = (list(package.fileStore), element.value)
    package.commandStack.undo()

    assert cleared == ([], None)
    assert list(package.fileStore) == [PART]
    assert element.value == PART


def test_cancelling_the_question_deletes_nothing(views, monkeypatch) -> None:
    shown, package, element = _open_referenced(views, monkeypatch, "CANCEL")

    shown.view.onDelClear()

    assert list(package.fileStore) == [PART]
    assert element.value == PART
    assert not package.commandStack.can_undo
