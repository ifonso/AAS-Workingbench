"""Bulk editing in the running editor, on a real package.

Every step goes through the main window and its actions, as a user would do
it: a pattern rename, qualifiers from a preset, an extension from the
clipboard and its removal, and a move across two collections. The tree, the
objects, and the saved file must agree after each step, and undoing everything
must give back the package as it was read.
"""

from collections.abc import Iterator
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"
REQUIREMENT = "Expression semantic | Requirement"


@pytest.fixture
def editor(
    qapp: object,
    qtbot,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[SimpleNamespace]:
    """The main window with a copy of the package, and the bulk actions."""
    from aas_editor.editorApp import EditorApp
    from aas_editor.ui import bulk_dialogs
    from aas_editor.ui import preset_actions
    from aas_editor.ui.bulk_dialogs import ChangeAttributeDialog
    from aas_editor.ui.bulk_dialogs import RemoveExtensionsDialog
    from aas_editor.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.preset_actions import register_preset_actions
    from aas_editor.ui.preset_dialogs import PresetDialog

    register_move_actions()
    register_bulk_edit_actions()
    register_preset_actions()
    monkeypatch.setattr(
        preset_actions, "user_presets_dir", lambda: tmp_path / "presets"
    )
    problems: list[str] = []
    monkeypatch.setattr(
        bulk_dialogs,
        "show_problem",
        lambda title, message, parent=None: problems.append(message),
    )
    # Closing a window with changes would ask whether to save, and wait for
    # ever. Selecting an item opens a preview tab with QtWebEngine, which
    # crashes the test process when it exits. The tabs are not under test.
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *args, **kwargs: QMessageBox.StandardButton.No),
    )
    monkeypatch.setattr(
        EditorApp, "onSelectedPackItemChanged", lambda self, item: None
    )
    source = tmp_path / PACKAGE.name
    shutil.copy(PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    editor = SimpleNamespace()
    editor.window = window
    editor.view = window.mainTreeView
    (editor.package,) = window.packTreeModel.openedPacks()
    editor.stack = editor.package.commandStack
    editor.dir = tmp_path
    editor.problems = problems
    editor.dialogs = (
        ChangeAttributeDialog,
        RemoveExtensionsDialog,
        PresetDialog,
    )
    editor.monkeypatch = monkeypatch
    yield editor
    editor.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _find(view, parent: QModelIndex, name: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    for row in range(proxy.rowCount(parent)):
        child = proxy.index(row, 0, parent)
        if child.data(NAME_ROLE) == name:
            return child
    raise LookupError(name)


def _path(view, *names: str) -> QModelIndex:
    index = view.model().index(0, 0)
    for name in names:
        index = _find(view, index, name)
    return index


def _rows(view, *names: str) -> list[str]:
    from aas_editor.settings.app_settings import NAME_ROLE

    proxy = view.model()
    parent = _path(view, *names)
    return [
        proxy.index(row, 0, parent).data(NAME_ROLE)
        for row in range(proxy.rowCount(parent))
    ]


def _select(view, *indexes: QModelIndex) -> None:
    selection = view.selectionModel()
    selection.clear()
    for index in indexes:
        selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    selection.setCurrentIndex(
        indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
    )


def _act(view, action_id: str) -> bool:
    action = view.registeredActions.find(action_id)
    enabled = action.isEnabled()
    action.trigger()
    return enabled


def _reloaded(editor, name: str) -> model.Submodel:
    from aas_editor.package import Package

    path = editor.dir / name
    editor.package.write(path)
    return next(
        s for s in Package(path).objStore if isinstance(s, model.Submodel)
    )


def test_bulk_edits_agree_in_tree_objects_and_file_and_undo_to_the_start(
    editor,
) -> None:
    view, package, stack = editor.view, editor.package, editor.stack
    change_dialog, remove_dialog, preset_dialog = editor.dialogs
    patch = editor.monkeypatch.setattr
    original = snapshot(package.objStore)
    (submodel,) = [s for s in package.objStore if isinstance(s, model.Submodel)]
    holder_name = "ContactInformation"
    base = ("submodels", submodel.id_short, holder_name)
    holder = submodel.get_referable(holder_name)
    names = [e.id_short for e in holder.value]
    assert {"Phone", "Fax", "CityTown", "Company"} <= set(names)

    # 1. Rename two collections with a pattern. The tree, the objects, and the
    # saved file all show the new names, and the references stay valid.
    _select(
        view,
        _find(view, _path(view, *base), "Phone"),
        _find(view, _path(view, *base), "Fax"),
    )
    patch(
        change_dialog,
        "exec",
        lambda d: (
            d.set_pattern("{old}_{number|pad(2)}"),
            QDialog.DialogCode.Accepted,
        )[-1],
    )
    enabled_change = _act(view, "bulk.change_attribute")
    renamed = [e.id_short for e in holder.value]
    tree_names = _rows(view, *base)
    saved_names = [
        e.id_short
        for e in _reloaded(editor, "renamed.aasx")
        .get_referable(holder_name)
        .value
    ]

    # 2. Qualifiers from a preset on two text elements.
    parent = _path(view, *base)
    _select(
        view, _find(view, parent, "CityTown"), _find(view, parent, "Company")
    )
    patch(
        preset_dialog,
        "exec",
        lambda d: (d.choose(REQUIREMENT), QDialog.DialogCode.Accepted)[-1],
    )
    enabled_preset = _act(view, "preset.add_qualifier")
    preset_types = [
        [q.type for q in holder.get_referable(n).qualifier]
        for n in ("CityTown", "Company")
    ]

    # 3. An extension from the clipboard, on the same two, then its removal.
    def extension_names(name: str) -> list[str]:
        return [e.name for e in holder.get_referable(name).extension]

    extensions_before = [extension_names(n) for n in ("CityTown", "Company")]
    QApplication.clipboard().setText(
        json.dumps({"name": "BulkNote", "valueType": "xs:string", "value": "x"})
    )
    _act(view, "clipboard.add_extension")
    with_extension = [
        [e.name for e in holder.get_referable(n).extension]
        for n in ("CityTown", "Company")
    ]
    saved_extension = [
        e.name
        for e in _reloaded(editor, "extension.aasx")
        .get_referable(holder_name)
        .get_referable("CityTown")
        .extension
    ]
    patch(
        remove_dialog,
        "exec",
        lambda d: (d.choose("BulkNote (2)"), QDialog.DialogCode.Accepted)[-1],
    )
    _act(view, "bulk.remove_extensions")
    without_extension = [extension_names(n) for n in ("CityTown", "Company")]

    # 4. Move the first child of each renamed collection to the end of its own.
    first_children = {
        n: [e.id_short for e in holder.get_referable(n).value]
        for n in ("Phone_01", "Fax_02")
    }
    _select(
        view,
        _find(
            view, _path(view, *base, "Phone_01"), first_children["Phone_01"][0]
        ),
        _find(view, _path(view, *base, "Fax_02"), first_children["Fax_02"][0]),
    )
    enabled_move = _act(view, "structure.move_end")
    moved = {
        n: [e.id_short for e in holder.get_referable(n).value]
        for n in first_children
    }
    moved_tree = {n: _rows(view, *base, n) for n in first_children}
    final = snapshot(package.objStore)
    final_reloaded = snapshot(_reloaded_store(editor, "final.aasx"))

    # Everything back to the state that was read, then forward again.
    steps = 0
    while stack.can_undo:
        view.onUndo()
        steps += 1
    at_start = snapshot(package.objStore)
    changed_at_start = package.changed
    while stack.can_redo:
        view.onRedo()
    at_end = snapshot(package.objStore)

    assert enabled_change
    assert renamed[names.index("Phone")] == "Phone_01"
    assert renamed[names.index("Fax")] == "Fax_02"
    assert tree_names == renamed == saved_names
    assert enabled_preset
    assert [types[-1] for types in preset_types] == ["ExpressionSemantic"] * 2
    assert with_extension == [
        [*names, "BulkNote"] for names in extensions_before
    ]
    assert saved_extension == with_extension[0]
    assert without_extension == extensions_before
    assert enabled_move
    for name, children in first_children.items():
        assert moved[name] == [*children[1:], children[0]]
        assert moved_tree[name] == moved[name]
    assert final == final_reloaded
    assert steps == 5
    assert at_start == original
    assert not changed_at_start
    assert at_end == final
    assert editor.problems == []


def _reloaded_store(editor, name: str):
    from aas_editor.package import Package

    path = editor.dir / name
    editor.package.write(path)
    return Package(path).objStore
