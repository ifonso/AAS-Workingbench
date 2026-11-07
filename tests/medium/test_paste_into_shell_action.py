"""Paste into an AAS: Submodels and references to them (F-EDT-08 AC11, AC12).

The paste goes through the tree view and its registered action, as a user does.
One paste is one undo step, and what it makes survives a save and a reload.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QApplication
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_workingbench.application.editing import edit_mode

INTO = "structure.paste_into"


@pytest.fixture
def pasting(views, monkeypatch: pytest.MonkeyPatch):
    """Two packages, and ways to copy and paste in the package tree."""
    from aas_workingbench.ui import paste_dialogs
    from aas_workingbench.ui.paste_actions import register_paste_actions

    register_paste_actions()
    problems: list[str] = []
    monkeypatch.setattr(
        paste_dialogs,
        "show_problem",
        lambda message, parent=None: problems.append(message),
    )
    monkeypatch.setattr(
        paste_dialogs, "ask_copy_concepts", lambda plan, parent=None: False
    )
    QApplication.clipboard().clear()

    class Pasting:
        def __init__(self) -> None:
            self.problems = problems
            self.shown = views()
            self.view = self.shown.view
            self.view.treeClipboard.clear()
            self.shell = make_shell(id_="urn:shell:a", id_short="Shell")
            self.first = make_submodel(id_="urn:sm:1", id_short="First")
            self.first.submodel_element.add(make_property("P"))
            self.second = make_submodel(id_="urn:sm:2", id_short="Second")
            self.package = self.shown.open_package(
                self.shell, self.first, self.second
            )
            self.stack = self.package.commandStack

        def select(self, *path: str, package: int = 0) -> None:
            self.shown.select(self.shown.index(*path, package=package))

        def put_reference_in_buffer(self, reference: Any, source: Any) -> None:
            self.view.treeClipboard.clear()
            self.view.treeClipboard.append(reference, objRepr=str(reference))
            self.view.treeClipboard.source = source

        def paste_into_shell(self) -> bool:
            self.select("shells", "Shell")
            action = self.view.registeredActions.find(INTO)
            enabled = action.isEnabled()
            if enabled:
                action.trigger()
            return enabled

        def saved(self, directory: Path) -> Any:
            from aas_workingbench.package import Package

            path = directory / "pasted.aasx"
            self.package.write(path)
            return Package(path).objStore

    return Pasting


def _linked_ids(shell: model.AssetAdministrationShell) -> list[str]:
    return sorted(reference.key[0].value for reference in shell.submodel)


def test_a_copied_submodel_is_added_with_a_new_id_and_a_reference(
    pasting, tmp_path: Path
) -> None:
    lab = pasting()
    before = snapshot(lab.package.objStore)
    lab.select("submodels", "First")
    lab.view.onCopy()

    enabled = lab.paste_into_shell()

    (reference,) = lab.shell.submodel
    copy = reference.resolve(lab.package.objStore)
    assert enabled
    assert copy is not lab.first
    assert copy.id != lab.first.id
    assert [e.id_short for e in copy.submodel_element] == ["P"]
    assert lab.first.id in {o.id for o in lab.package.objStore}
    reloaded = lab.saved(tmp_path)
    (saved_shell,) = [
        o for o in reloaded if isinstance(o, model.AssetAdministrationShell)
    ]
    (saved_reference,) = saved_shell.submodel
    assert saved_reference.resolve(reloaded).id == copy.id
    lab.stack.undo()
    assert snapshot(lab.package.objStore) == before
    assert not lab.stack.can_undo


def test_a_pasted_reference_is_added_and_the_submodel_stays_shared(
    pasting,
) -> None:
    lab = pasting()
    lab.put_reference_in_buffer(make_reference_to(lab.second), lab.package)

    lab.paste_into_shell()

    assert _linked_ids(lab.shell) == ["urn:sm:2"]
    assert len(list(lab.package.objStore)) == 3


def test_pasting_the_same_reference_again_is_skipped_and_said(pasting) -> None:
    lab = pasting()
    reference = make_reference_to(lab.second)
    lab.put_reference_in_buffer(reference, lab.package)
    lab.paste_into_shell()
    steps = lab.stack.undo_description

    lab.paste_into_shell()

    assert _linked_ids(lab.shell) == ["urn:sm:2"]
    assert lab.stack.undo_description == steps
    (message,) = lab.problems
    assert "already" in message


def test_a_reference_from_another_package_brings_its_submodel(
    pasting, tmp_path: Path
) -> None:
    lab = pasting()
    foreign = make_submodel(id_="urn:sm:foreign", id_short="Foreign")
    foreign.submodel_element.add(make_property("Q"))
    other = lab.shown.open_package(make_shell(id_="urn:shell:b"), foreign)
    lab.put_reference_in_buffer(make_reference_to(foreign), other)

    lab.paste_into_shell()

    added = lab.package.objStore.get_item("urn:sm:foreign")
    assert added is not foreign
    assert [e.id_short for e in added.submodel_element] == ["Q"]
    assert _linked_ids(lab.shell) == ["urn:sm:foreign"]
    reloaded = lab.saved(tmp_path)
    assert reloaded.get_item("urn:sm:foreign") is not None
    lab.stack.undo()
    assert "urn:sm:foreign" not in {o.id for o in lab.package.objStore}
    assert len(lab.shell.submodel) == 0


def test_a_reference_to_nothing_is_pasted_and_reported_as_dangling(
    pasting,
) -> None:
    lab = pasting()
    gone = model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, "urn:sm:gone"),), model.Submodel
    )
    lab.put_reference_in_buffer(gone, lab.package)

    lab.paste_into_shell()

    assert _linked_ids(lab.shell) == ["urn:sm:gone"]
    (message,) = lab.problems
    assert "not in this package" in message


def test_a_cut_submodel_keeps_its_id_when_pasted_into_a_shell(pasting) -> None:
    lab = pasting()
    lab.select("submodels", "First")
    lab.view.onCut()

    lab.paste_into_shell()

    assert _linked_ids(lab.shell) == ["urn:sm:1"]
    assert lab.package.objStore.get_item("urn:sm:1") is not None


def test_an_element_in_the_buffer_is_refused_with_a_reason(pasting) -> None:
    lab = pasting()
    lab.select("submodels", "First", "P")
    lab.view.onCopy()

    lab.paste_into_shell()

    assert len(lab.shell.submodel) == 0
    (message,) = lab.problems
    assert "Submodels" in message


def test_the_action_is_off_in_read_mode(pasting) -> None:
    lab = pasting()
    lab.put_reference_in_buffer(make_reference_to(lab.second), lab.package)
    edit_mode().set_editing(False)
    try:
        enabled = lab.paste_into_shell()
    finally:
        edit_mode().set_editing(True)

    assert not enabled
    assert len(lab.shell.submodel) == 0


def test_submodel_json_typed_into_the_box_is_added_to_the_shell(
    pasting, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.domain.clipboard_json import dump_objects
    from aas_workingbench.ui import paste_dialogs

    lab = pasting()
    typed = make_submodel(id_="urn:sm:typed", id_short="Typed")
    monkeypatch.setattr(
        paste_dialogs,
        "ask_paste_text",
        lambda places, parent=None: (dump_objects([typed]), "into"),
    )
    lab.select("shells", "Shell")

    lab.view.registeredActions.find("structure.paste_text").trigger()

    (added,) = list(lab.shell.submodel)
    assert added.key[0].value != "urn:sm:typed"
    assert lab.package.objStore.get_item(added.key[0].value).id_short == "Typed"
    lab.stack.undo()
    assert len(lab.shell.submodel) == 0
