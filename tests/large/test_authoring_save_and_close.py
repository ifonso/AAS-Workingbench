"""Save as, and close with changes: what a person is asked and what is kept.

A package is built from nothing, saved under another name with Save As, changed
again, and closed. Closing asks what to do with the changes: cancel keeps the
package open, discard drops the changes, and save writes them. After each
answer the file on disk and the window must agree.
"""

from pathlib import Path

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.authoring import Author
from tests.authoring_builders import make_shell
from tests.authoring_builders import make_submodel
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

BOX = ("submodels", "Box")
BOX_ID = "urn:example:sm:box"
ASK = "Do you want to save your changes"


def _add_property(author: Author, name: str) -> None:
    def fill(form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("value", "3")

    answer = author.add_element(BOX, model.Property, name, fill)
    author.assert_accepted(answer)


def _stored(path: Path) -> str:
    from aas_editor.package import Package

    return snapshot(Package(path).objStore)


@pytest.fixture
def saved_as(author: Author, tmp_path: Path) -> Author:
    """A package that was made as `first.aasx` and saved as `second.aasx`."""
    author.start_new_package(tmp_path / "first.aasx")
    make_shell(author)
    make_submodel(author, "Box", BOX_ID, model.ModellingKind.INSTANCE)
    _add_property(author, "One")
    author.pick_save_path(tmp_path / "second.aasx")
    author.select_path()
    assert author.view.saveAsAct.isEnabled()
    author.view.saveAsAct.trigger()
    return author


def test_save_as_writes_the_new_file_and_the_package_follows_it(
    saved_as: Author, tmp_path: Path
) -> None:
    author = saved_as

    assert not author.window.isWindowModified(), author.errors
    assert author.package.file == tmp_path / "second.aasx"
    assert _stored(tmp_path / "second.aasx") == snapshot(
        author.package.objStore
    )
    # The first file is the empty package that New made, and stays so.
    assert _stored(tmp_path / "first.aasx") == snapshot(
        model.DictIdentifiableStore()
    )
    assert str(author.package.name) == "second.aasx"


def test_closing_with_changes_asks_and_each_answer_keeps_file_and_window_in_step(
    saved_as: Author, tmp_path: Path
) -> None:
    author = saved_as
    second = tmp_path / "second.aasx"
    on_disk = _stored(second)
    _add_property(author, "Two")
    changed = snapshot(author.package.objStore)
    assert changed != on_disk
    assert author.window.isWindowModified()

    # Cancel: the package stays open and changed.
    author.replies.append((ASK, "Cancel"))
    author.select_path()
    author.view.closeAct.trigger()
    assert author.window.packTreeModel.rowCount() == 1
    assert author.window.isWindowModified()
    assert _stored(second) == on_disk

    # Discard: the package closes and the file keeps the old content.
    author.replies[:] = [(ASK, "Discard")]
    author.view.closeAct.trigger()
    assert author.window.packTreeModel.rowCount() == 0
    assert _stored(second) == on_disk

    # Open it again, change it again, and save while closing.
    author.pick_open_path(second)
    author.view.openPackAct.trigger()
    assert snapshot(author.package.objStore) == on_disk
    _add_property(author, "Three")
    saved = snapshot(author.package.objStore)
    author.replies[:] = [(ASK, "SaveClose")]
    author.select_path()
    author.view.closeAct.trigger()
    assert author.window.packTreeModel.rowCount() == 0
    assert _stored(second) == saved
    assert "Three" in saved
