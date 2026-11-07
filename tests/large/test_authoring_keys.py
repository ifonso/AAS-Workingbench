"""A person authors with the keyboard: add, copy, paste, delete, undo, redo, save.

Real key events go to the package tree, which has the focus. The dialogs and
the question before a delete are answered as in the other authoring tests.
"""

from pathlib import Path

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
import pytest
from tests.authoring import Author
from tests.authoring_builders import make_shell
from tests.authoring_builders import make_submodel
from tests.medium.forms import Form
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

BOX = ("submodels", "Box")
BOX_ID = "urn:example:sm:box"
CTRL = Qt.KeyboardModifier.ControlModifier


def _press(
    author: Author, key: Qt.Key, modifier=Qt.KeyboardModifier.NoModifier
):
    author.view.setFocus()
    QApplication.processEvents()
    QTest.keyClick(author.view, key, modifier)
    QApplication.processEvents()


def _names(author: Author) -> list[str]:
    box = author.package.objStore.get_item(BOX_ID)
    return [e.id_short for e in box.submodel_element]


def test_keys_add_copy_paste_delete_undo_redo_and_save_a_package(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.dialogs import EditObjDialog

    author.start_new_package(tmp_path / "box.aasx")
    make_shell(author)
    make_submodel(author, "Box", BOX_ID, model.ModellingKind.INSTANCE)
    author.stack.mark_saved()

    def fill(dialog) -> None:
        form = Form(dialog)
        form.choose_type(model.Property)
        form.type_text("id_short", "Pressed")
        form.choose("value_type", datatypes.Int)
        form.type_text("value", "4")

    # Ctrl+N adds below the selected submodel.
    author.select_path(*BOX)
    with author.answering(EditObjDialog, fill) as answer:
        _press(author, Qt.Key.Key_N, CTRL)
    author.assert_accepted(answer)
    assert _names(author) == ["Pressed"]

    # Ctrl+C on the element, Ctrl+V with the submodel selected: a copy.
    author.select_path(*BOX, "Pressed")
    _press(author, Qt.Key.Key_C, CTRL)
    author.select_path(*BOX)
    # The paste opens the form of the element to check it, and OK accepts it.
    with author.answering(EditObjDialog, lambda dialog: None) as answer:
        _press(author, Qt.Key.Key_V, CTRL)
    author.assert_accepted(answer)
    assert len(_names(author)) == 2
    assert _names(author)[0] == "Pressed"
    copy = _names(author)[1]
    assert copy.startswith("Pressed")

    # Delete asks first, and one undo brings the element back.
    author.select_path(*BOX, copy)
    author.replies.append(("Delete", "Delete"))
    _press(author, Qt.Key.Key_Delete)
    assert _names(author) == ["Pressed"]
    after_delete = snapshot(author.package.objStore)
    _press(author, Qt.Key.Key_Z, CTRL)
    assert _names(author) == ["Pressed", copy]
    _press(author, Qt.Key.Key_Y, CTRL)
    assert _names(author) == ["Pressed"]
    assert snapshot(author.package.objStore) == after_delete

    # Ctrl+S writes the file, and the window is not marked as changed.
    author.select_path()
    _press(author, Qt.Key.Key_S, CTRL)
    assert not author.window.isWindowModified(), author.errors
    from aas_workingbench.package import Package

    reread = Package(tmp_path / "box.aasx")
    assert snapshot(reread.objStore) == after_delete
