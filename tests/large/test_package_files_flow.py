"""The supplementary files in the running main window, on real AASX files.

A package is opened in the main window. Files are listed, renamed, removed,
and repaired through the panel, the package tree and the save dialogs, as a user
would do it. Dialogs that ask something are replaced by fixed answers, and the
packages are saved and read again to see what a user would send.
"""

from pathlib import Path
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

DOC = "/aasx/files/doc.pdf"
NOTE = "/aasx/files/note.txt"
THUMB = "/aasx/files/thumb.png"
SPARE = "/aasx/files/spare.txt"


def _write_package(path: Path, with_spare: bool = False) -> Path:
    submodel = make_submodel(
        elements=[
            make_file_element("Document", DOC, "application/pdf"),
            make_file_element("Note", NOTE, "text/plain"),
        ]
    )
    shell = make_shell(
        submodels=[submodel],
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(THUMB, "image/png")
        ),
    )
    files = {
        DOC: (b"%PDF doc", "application/pdf"),
        NOTE: (b"note", "text/plain"),
        THUMB: (b"png", "image/png"),
    }
    if with_spare:
        files[SPARE] = (b"spare", "text/plain")
    return write_aasx(path, make_store(shell, submodel), files=files)


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, monkeypatch):
    """The main window with one package and fixed answers for its dialogs."""
    from aas_editor.editorApp import EditorApp
    from aas_editor.ui import file_dialogs
    from aas_editor.ui.actions import ViewKind
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.file_actions import register_file_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions
    from aas_editor.ui.save_warnings import IssuesDialog

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    register_file_actions()
    register_move_actions()
    register_paste_actions()
    # pytest-qt closes the window after the test, while the package still has
    # changes. Closing would ask whether to save, and wait for ever.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
    )
    # Selecting a stored file opens a preview tab with QtWebEngine, which
    # crashes the test process when it exits. The tabs are not under test.
    monkeypatch.setattr(
        EditorApp, "onSelectedPackItemChanged", lambda self, item: None
    )
    source = _write_package(tmp_path / "source.aasx")
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    answers = SimpleNamespace(
        text=None,
        picked=None,
        chosen=None,
        references=file_dialogs.ReferenceAnswer.LEAVE,
        warnings=[],
        refused=[],
    )
    monkeypatch.setattr(
        file_dialogs,
        "ask_text",
        lambda parent, title, label, text="": (
            text if answers.text is None else answers.text
        ),
    )
    monkeypatch.setattr(
        file_dialogs, "pick_file_to_add", lambda parent: answers.picked
    )
    monkeypatch.setattr(
        file_dialogs,
        "choose_stored_file",
        lambda infos, current=None, title="", parent=None: answers.chosen,
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

    def show_issues(dialog) -> int:
        answers.refused.append(
            (
                dialog.windowTitle(),
                [
                    dialog.issues_list.item(row).text()
                    for row in range(dialog.issues_list.count())
                ],
                dialog.extra_button is not None,
            )
        )
        if dialog.extra_button is not None:
            dialog.extra_button.click()
        return 0

    monkeypatch.setattr(IssuesDialog, "exec", show_issues)

    editor = SimpleNamespace(
        window=window,
        view=window.mainTreeView,
        panel=window.filesDock.panel,
        source=source,
        answers=answers,
        tmp_path=tmp_path,
    )
    (editor.package,) = window.packTreeModel.openedPacks()
    editor.stack = editor.package.commandStack
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()
    for spec in default_registry().specs_for(ViewKind.ANY):
        if spec.action_id not in before:
            default_registry().unregister(spec.action_id)


def _index(view, *names: str) -> QModelIndex:
    proxy = view.model()
    index = proxy.index(0, 0)
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(Qt.ItemDataRole.DisplayRole) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def _select(view, index: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(index, QItemSelectionModel.SelectionFlag.NoUpdate)


def _file_rows(view) -> list[str]:
    proxy = view.model()
    folder = _index(view, "fileStore")
    return sorted(
        proxy.index(row, 0, folder).data(Qt.ItemDataRole.DisplayRole)
        for row in range(proxy.rowCount(folder))
    )


def _elements(package) -> dict[str, model.File]:
    (submodel,) = list(package.submodels)
    return {
        element.id_short: element
        for element in submodel.submodel_element
        if isinstance(element, model.File)
    }


def _reload(path: Path):
    from aas_editor.package import Package

    return Package(path)


def test_the_panel_lists_the_files_and_follows_a_rename_and_its_undo(
    editor, qtbot
) -> None:
    editor.window.filesDock.toggleViewAction().trigger()
    _select(editor.view, _index(editor.view, "fileStore", NOTE))
    qtbot.waitUntil(lambda: editor.panel.table.rowCount() == 3)
    listed = sorted(
        editor.panel.table.item(row, 0).text()
        for row in range(editor.panel.table.rowCount())
    )
    editor.panel.table.selectRow(listed.index(NOTE))
    editor.answers.text = "/aasx/central"

    editor.panel.move_button.click()
    qtbot.waitUntil(lambda: "/aasx/central/note.txt" in _file_rows(editor.view))
    moved = (_elements(editor.package)["Note"].value, _file_rows(editor.view))
    editor.view.onUndo()
    qtbot.waitUntil(lambda: NOTE in _file_rows(editor.view))

    assert editor.window.filesDock.isVisible()
    assert listed == sorted([DOC, NOTE, THUMB])
    assert moved[0] == "/aasx/central/note.txt"
    assert NOTE not in moved[1]
    assert _elements(editor.package)["Note"].value == NOTE
    assert _file_rows(editor.view) == sorted([DOC, NOTE, THUMB])


def test_a_rename_in_the_context_menu_is_saved_with_its_references(
    editor, qtbot
) -> None:
    editor.answers.text = "/aasx/files/manual.pdf"
    _select(editor.view, _index(editor.view, "fileStore", DOC))
    editor.view.updateActions(_index(editor.view, "fileStore", DOC))

    editor.view.registeredActions.find("files.rename").trigger()
    saved = editor.view.savePack(
        editor.package, (editor.tmp_path / "out.aasx").as_posix()
    )
    reloaded = _reload(editor.tmp_path / "out.aasx")

    assert saved
    assert "/aasx/files/manual.pdf" in reloaded.fileStore
    assert DOC not in reloaded.fileStore
    assert _elements(reloaded)["Document"].value == "/aasx/files/manual.pdf"
    (shell,) = reloaded.shells
    assert shell.asset_information.default_thumbnail.path == THUMB


def test_deleting_a_stored_file_in_the_tree_clears_the_paths_in_one_step(
    editor, qtbot
) -> None:
    editor.answers.references = editor.answers.references.CLEAR
    _select(editor.view, _index(editor.view, "fileStore", DOC))

    editor.view.onDelClear()
    after_delete = (
        _file_rows(editor.view),
        _elements(editor.package)["Document"].value,
    )
    editor.view.onUndo()

    assert after_delete == ([NOTE, THUMB], None)
    assert _file_rows(editor.view) == sorted([DOC, NOTE, THUMB])
    assert _elements(editor.package)["Document"].value == DOC
    assert editor.answers.warnings == []


def test_a_dangling_path_is_repaired_from_the_refused_save(
    editor, qtbot, monkeypatch
) -> None:
    from aas_editor.ui import file_dialogs

    editor.answers.references = editor.answers.references.LEAVE
    _select(editor.view, _index(editor.view, "fileStore", DOC))
    editor.view.onDelClear()
    target = editor.tmp_path / "repaired.aasx"
    editor.answers.chosen = NOTE

    def repair(dialog) -> int:
        dialog.table.selectRow(0)
        dialog.choose_button.click()
        return 0

    monkeypatch.setattr(file_dialogs.DanglingDialog, "exec", repair)
    refused = editor.view.savePack(editor.package, target.as_posix())
    saved = editor.view.savePack(editor.package, target.as_posix())
    reloaded = _reload(target)

    assert refused is False
    assert editor.answers.refused[0][0] == "Package cannot be saved"
    assert editor.answers.refused[0][2]
    assert saved
    assert _elements(reloaded)["Document"].value == NOTE
    assert sorted(reloaded.fileStore) == sorted([NOTE, THUMB])


def test_the_save_warns_about_a_file_that_nothing_refers_to(
    editor, qtbot
) -> None:
    from aas_editor.application import supplementary_files as files
    from aas_editor.application.changes import observer_for

    files.create_text_file(
        editor.stack,
        observer_for(editor.package),
        editor.package.fileStore,
        SPARE,
        "spare",
    )

    saved = editor.view.savePack(
        editor.package, (editor.tmp_path / "spare.aasx").as_posix()
    )

    title, texts, has_extra = editor.answers.refused[0]
    assert saved is False
    assert title == "Save package"
    assert f"    {SPARE}" in texts
    assert has_extra


def test_read_mode_disables_the_buttons_of_the_panel(editor, qtbot) -> None:
    editor.window.filesDock.toggleViewAction().trigger()
    _select(editor.view, _index(editor.view, "fileStore", NOTE))
    qtbot.waitUntil(lambda: editor.panel.table.rowCount() == 3)
    editor.panel.table.selectRow(0)
    editor.window.readModeAct.trigger()
    try:
        disabled = not editor.panel.rename_button.isEnabled()
    finally:
        editor.window.editModeAct.trigger()

    assert disabled


def test_pasting_an_element_into_another_package_copies_its_file(
    editor, qtbot
) -> None:
    other_source = editor.tmp_path / "other.aasx"
    other_submodel = make_submodel("urn:uuid:other", "Other")
    write_aasx(
        other_source,
        make_store(
            make_shell(
                "urn:uuid:other-shell", "Other", submodels=[other_submodel]
            ),
            other_submodel,
        ),
    )
    other = editor.window.openAASFile(other_source.as_posix())
    editor.view.expandAll()
    submodel_name = next(iter(editor.package.submodels)).id_short
    _select(
        editor.view, _index(editor.view, "submodels", submodel_name, "Document")
    )

    editor.view.onCopy()
    proxy = editor.view.model()
    target_row = next(
        row
        for row in range(proxy.rowCount())
        if proxy.index(row, 0).data(Qt.ItemDataRole.DisplayRole) == "other.aasx"
    )
    submodels_index = None
    package_index = proxy.index(target_row, 0)
    for row in range(proxy.rowCount(package_index)):
        child = proxy.index(row, 0, package_index)
        if child.data(Qt.ItemDataRole.DisplayRole) == "submodels":
            submodels_index = proxy.index(0, 0, child)
    assert submodels_index is not None
    _select(editor.view, submodels_index)
    editor.view.updateActions(submodels_index)
    editor.view.registeredActions.find("structure.paste_into").trigger()
    target = editor.tmp_path / "other_saved.aasx"
    saved = editor.view.savePack(other, target.as_posix())
    reloaded = _reload(target)

    assert saved
    (other_loaded,) = list(reloaded.submodels)
    pasted = [
        element
        for element in other_loaded.submodel_element
        if isinstance(element, model.File)
    ]
    assert [element.value for element in pasted] == [DOC]
    assert list(reloaded.fileStore) == [DOC]
