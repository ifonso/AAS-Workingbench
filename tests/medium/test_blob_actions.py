"""The actions that load and save the bytes of a Blob."""

from collections.abc import Iterator
from pathlib import Path

from basyx.aas import model
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.factories import make_blob
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

BLOB_PATH = ("submodels", "Submodel", "Blob")


@pytest.fixture
def registered(qapp: object) -> Iterator[None]:
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.blob_actions import FROM_BASE64_ACTION_ID
    from aas_workingbench.ui.blob_actions import LOAD_ACTION_ID
    from aas_workingbench.ui.blob_actions import register_blob_actions
    from aas_workingbench.ui.blob_actions import SAVE_ACTION_ID
    from aas_workingbench.ui.blob_actions import TO_BASE64_ACTION_ID

    register_blob_actions()
    yield
    for action_id in (
        LOAD_ACTION_ID,
        SAVE_ACTION_ID,
        FROM_BASE64_ACTION_ID,
        TO_BASE64_ACTION_ID,
    ):
        default_registry().unregister(action_id)


def _pick(monkeypatch: pytest.MonkeyPatch, method: str, path: Path) -> None:
    monkeypatch.setattr(
        QFileDialog,
        method,
        staticmethod(lambda *args, **kwargs: (str(path), "")),
    )


def test_registering_twice_adds_each_action_once(registered: None) -> None:
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.blob_actions import register_blob_actions

    register_blob_actions()

    ids = [
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    ]
    assert ids.count("blob.load_content") == 1
    assert ids.count("blob.save_content") == 1
    assert ids.count("blob.from_base64") == 1
    assert ids.count("blob.to_base64") == 1


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
    from aas_workingbench.application.editing import edit_mode

    shown = views()
    shown.open_package(make_submodel(elements=[make_blob()]))
    edit_mode().set_editing(False)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    save = shown.view.registeredActions.find("blob.save_content")
    load = shown.view.registeredActions.find("blob.load_content")

    assert save.isEnabled()
    assert not load.isEnabled()


def _convert(shown, action_id: str) -> None:
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))
    shown.view.registeredActions.find(action_id).trigger()


def test_base64_text_becomes_the_bytes_in_one_undoable_step(
    views, registered: None
) -> None:
    blob = make_blob(value=b"SGVsbG8=", content_type="text/plain")
    shown = views()
    package = shown.open_package(make_submodel(elements=[blob]))
    before = snapshot(package.objStore)

    _convert(shown, "blob.from_base64")
    converted = blob.value
    package.commandStack.undo()

    assert converted == b"Hello"
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_bytes_become_base64_text_in_one_undoable_step(
    views, registered: None
) -> None:
    blob = make_blob(value=b"\x00\x01\x02\xff")
    shown = views()
    package = shown.open_package(make_submodel(elements=[blob]))
    before = snapshot(package.objStore)

    _convert(shown, "blob.to_base64")
    converted = blob.value
    package.commandStack.undo()

    assert converted == b"AAEC/w=="
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_the_conversion_there_and_back_gives_the_bytes_again(
    views, registered: None
) -> None:
    blob = make_blob(value=bytes(range(256)))
    shown = views()
    shown.open_package(make_submodel(elements=[blob]))

    _convert(shown, "blob.to_base64")
    _convert(shown, "blob.from_base64")

    assert blob.value == bytes(range(256))


def test_text_that_is_no_base64_is_refused_with_a_reason(
    views, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    blob = make_blob(value=b"not base64!", content_type="text/plain")
    shown = views()
    package = shown.open_package(make_submodel(elements=[blob]))
    before = snapshot(package.objStore)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda parent, title, text: messages.append(text)),
    )

    _convert(shown, "blob.from_base64")

    assert blob.value == b"not base64!"
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo
    assert len(messages) == 1
    assert messages[0].startswith("The content was not changed.")
    assert "'!' at character 11 is not in the Base64 alphabet" in messages[0]


def test_the_conversions_are_off_in_read_mode(views, registered: None) -> None:
    from aas_workingbench.application.editing import edit_mode

    shown = views()
    shown.open_package(make_submodel(elements=[make_blob(value=b"SGVsbG8=")]))
    edit_mode().set_editing(False)
    shown.select(shown.index(*BLOB_PATH))
    shown.view.updateActions(shown.index(*BLOB_PATH))

    actions = [
        shown.view.registeredActions.find(action_id)
        for action_id in ("blob.from_base64", "blob.to_base64")
    ]

    assert [action.isEnabled() for action in actions] == [False, False]
