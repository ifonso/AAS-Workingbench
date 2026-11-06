"""The actions that load and save the bytes of a Blob."""

from collections.abc import Iterator
from pathlib import Path

from basyx.aas import model
from PyQt6.QtWidgets import QFileDialog
import pytest
from tests.factories import make_blob
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

BLOB_PATH = ("submodels", "Submodel", "Blob")


@pytest.fixture
def registered(qapp: object) -> Iterator[None]:
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.blob_actions import LOAD_ACTION_ID
    from aas_editor.ui.blob_actions import register_blob_actions
    from aas_editor.ui.blob_actions import SAVE_ACTION_ID

    register_blob_actions()
    yield
    default_registry().unregister(LOAD_ACTION_ID)
    default_registry().unregister(SAVE_ACTION_ID)


def _pick(monkeypatch: pytest.MonkeyPatch, method: str, path: Path) -> None:
    monkeypatch.setattr(
        QFileDialog,
        method,
        staticmethod(lambda *args, **kwargs: (str(path), "")),
    )


def test_registering_twice_adds_each_action_once(registered: None) -> None:
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.actions import ViewKind
    from aas_editor.ui.blob_actions import register_blob_actions

    register_blob_actions()

    ids = [
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    ]
    assert ids.count("blob.load_content") == 1
    assert ids.count("blob.save_content") == 1


def test_the_actions_are_enabled_for_a_blob_only(
    views, registered: None
) -> None:
    shown = views()
    shown.open_package(make_submodel(elements=[make_blob(), make_property()]))

    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))
    on_blob = [
        shown.view.registeredActions.find(action_id).isEnabled()
        for action_id in ("blob.load_content", "blob.save_content")
    ]
    shown.select(shown.index("submodels", "Submodel", "Property"))
    shown.view.updateActions(shown.index("submodels", "Submodel", "Property"))
    on_property = [
        shown.view.registeredActions.find(action_id).isEnabled()
        for action_id in ("blob.load_content", "blob.save_content")
    ]

    assert on_blob == [True, True]
    assert on_property == [False, False]


def test_loading_a_file_sets_the_bytes_in_one_undoable_step(
    views, registered: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blob = model.Blob("Blob", content_type=None, value=b"old")
    shown = views()
    package = shown.open_package(make_submodel(elements=[blob]))
    before = snapshot(package.objStore)
    picture = tmp_path / "picture.png"
    picture.write_bytes(bytes(range(256)))
    _pick(monkeypatch, "getOpenFileName", picture)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    shown.view.registeredActions.find("blob.load_content").trigger()
    loaded = (blob.value, blob.content_type)
    package.commandStack.undo()

    assert loaded == (bytes(range(256)), "image/png")
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_loading_keeps_the_media_type_the_blob_has(
    views, registered: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blob = make_blob(content_type="application/octet-stream")
    shown = views()
    shown.open_package(make_submodel(elements=[blob]))
    picture = tmp_path / "picture.png"
    picture.write_bytes(b"png")
    _pick(monkeypatch, "getOpenFileName", picture)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    shown.view.registeredActions.find("blob.load_content").trigger()

    assert blob.content_type == "application/octet-stream"


def test_saving_writes_the_exact_bytes(
    views, registered: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blob = make_blob(value=bytes(range(256)), content_type="image/png")
    shown = views()
    package = shown.open_package(make_submodel(elements=[blob]))
    target = tmp_path / "out.png"
    _pick(monkeypatch, "getSaveFileName", target)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    shown.view.registeredActions.find("blob.save_content").trigger()

    assert target.read_bytes() == bytes(range(256))
    assert not package.commandStack.can_undo


def test_saving_works_in_read_mode_and_loading_does_not(
    views, registered: None
) -> None:
    from aas_editor.application.editing import edit_mode

    shown = views()
    shown.open_package(make_submodel(elements=[make_blob()]))
    edit_mode().set_editing(False)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    save = shown.view.registeredActions.find("blob.save_content")
    load = shown.view.registeredActions.find("blob.load_content")

    assert save.isEnabled()
    assert not load.isEnabled()
