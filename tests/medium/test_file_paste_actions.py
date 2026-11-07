"""Paste above, below and into brings the files of the copies along."""

from pathlib import Path

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QApplication
from tests.factories import make_file_element
from tests.factories import make_submodel

from aas_workingbench.application import supplementary_files as files
from aas_workingbench.application.file_transfer import copy_source

DOC = "/aasx/files/doc.pdf"
SOURCE_FILES = {DOC: (b"%PDF source", "application/pdf")}


@pytest.fixture
def lab(views, monkeypatch: pytest.MonkeyPatch):
    """A package with a File element and its file, and an empty target."""
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions

    register_move_actions()
    register_paste_actions()
    QApplication.clipboard().clear()

    class Lab:
        def __init__(self, target_files=None) -> None:
            self.shown = views()
            self.view = self.shown.view
            self.view.treeClipboard.clear()
            self.element = make_file_element("Doc", DOC, "application/pdf")
            submodel = make_submodel(elements=[self.element])
            self.source = self.shown.open_package(submodel, files=SOURCE_FILES)
            self.target_submodel = make_submodel(
                "urn:uuid:target",
                "Target",
                elements=[make_file_element("Existing", DOC)]
                if target_files
                else [],
            )
            self.target = self.shown.open_package(
                self.target_submodel, files=target_files
            )
            self.view.expandAll()

        def paste_into_target(self) -> None:
            self.shown.select(
                self.shown.index("submodels", "Submodel", "Doc", package=0)
            )
            self.view.onCopy()
            self.shown.select(
                self.shown.index("submodels", "Target", package=1)
            )
            action = self.view.registeredActions.find("structure.paste_into")
            assert action.isEnabled()
            action.trigger()

        def pasted(self) -> model.File:
            element = (
                self.target_submodel.submodel_element.get_object_by_attribute(
                    "id_short", "Doc"
                )
            )
            assert isinstance(element, model.File)
            return element

    return Lab


def test_paste_into_another_package_copies_the_file(lab) -> None:
    lab = lab()

    lab.paste_into_target()

    assert lab.pasted().value == DOC
    assert files.read_file(lab.target.fileStore, DOC) == b"%PDF source"
    assert lab.target.fileStore.get_content_type(DOC) == "application/pdf"
    assert files.read_file(lab.source.fileStore, DOC) == b"%PDF source"


def test_one_undo_takes_the_element_and_its_file_out(lab) -> None:
    lab = lab()
    lab.paste_into_target()

    lab.target.commandStack.undo()

    assert list(lab.target.fileStore) == []
    assert len(lab.target_submodel.submodel_element) == 0
    lab.target.commandStack.redo()
    assert files.read_file(lab.target.fileStore, DOC) == b"%PDF source"
    assert lab.pasted().value == DOC


def test_a_different_file_of_the_same_name_is_kept_and_the_copy_is_numbered(
    lab,
) -> None:
    lab = lab({DOC: (b"%PDF target", "application/pdf")})

    lab.paste_into_target()

    assert files.read_file(lab.target.fileStore, DOC) == b"%PDF target"
    assert lab.pasted().value == "/aasx/files/doc_0001.pdf"
    assert (
        files.read_file(lab.target.fileStore, "/aasx/files/doc_0001.pdf")
        == b"%PDF source"
    )
    lab.target.commandStack.undo()
    assert list(lab.target.fileStore) == [DOC]


def test_the_pasted_package_saves_and_reads_back_with_both_files(
    lab, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package

    lab = lab({DOC: (b"%PDF target", "application/pdf")})
    lab.paste_into_target()

    lab.target.write(tmp_path / "target.aasx")
    reloaded = Package(tmp_path / "target.aasx")

    assert sorted(reloaded.fileStore) == [DOC, "/aasx/files/doc_0001.pdf"]
    assert files.find_dangling(reloaded.objStore, reloaded.fileStore) == []


def test_a_paste_inside_one_package_adds_no_file(lab) -> None:
    lab = lab()
    lab.shown.select(lab.shown.index("submodels", "Submodel", "Doc", package=0))
    lab.view.onCopy()
    lab.shown.select(lab.shown.index("submodels", "Submodel", package=0))

    lab.view.registeredActions.find("structure.paste_into").trigger()

    assert list(lab.source.fileStore) == [DOC]
    assert files.read_file(lab.source.fileStore, DOC) == b"%PDF source"


def test_the_buffer_hands_its_package_to_the_copy_source(lab) -> None:
    lab = lab()
    clipboard = lab.view.treeClipboard

    clipboard.source = lab.source
    known = copy_source.store
    clipboard.clear()

    assert known is lab.source.fileStore
    assert copy_source.store is None
