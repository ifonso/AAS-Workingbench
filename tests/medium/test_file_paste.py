"""Copying objects to another open package brings their files along."""

import copy
import io

from basyx.aas import model
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_editor.application import supplementary_files as files
from aas_editor.application.file_transfer import copy_source

DOC = "/aasx/files/doc.pdf"


def _two_packages(views, target_files):
    shown = views()
    element = make_file_element("Doc", DOC, "application/pdf")
    submodel = make_submodel(elements=[element])
    source = shown.open_package(
        make_shell(submodels=[submodel]),
        submodel,
        files={DOC: (b"%PDF source", "application/pdf")},
    )
    other = make_submodel(
        "urn:uuid:other",
        "Other",
        elements=[make_file_element("Existing", DOC)] if target_files else [],
    )
    target = shown.open_package(
        make_shell("urn:uuid:other-shell", "OtherShell", submodels=[other]),
        other,
        files=target_files,
    )
    shown.view.expandAll()
    return shown, source, target, submodel


def _source_index(shown, package: int):
    """The index of the Submodels node, in the model behind the view."""
    return shown.view.model().mapToSource(
        shown.index("submodels", package=package)
    )


def _paste_submodel(shown, source, submodel) -> model.Submodel:
    pasted = copy.deepcopy(submodel)
    pasted.id = "urn:uuid:pasted"
    copy_source.remember(source)
    shown.table.addItem(pasted, _source_index(shown, package=1))
    return pasted


def _pasted_element(submodel: model.Submodel) -> model.File:
    element = next(iter(submodel.submodel_element))
    assert isinstance(element, model.File)
    return element


def test_pasting_a_submodel_into_another_package_copies_its_file(views) -> None:
    shown, source, target, submodel = _two_packages(views, None)

    pasted = _paste_submodel(shown, source, submodel)

    assert files.read_file(target.fileStore, DOC) == b"%PDF source"
    assert target.fileStore.get_content_type(DOC) == "application/pdf"
    assert _pasted_element(pasted).value == DOC
    assert files.find_dangling(target.objStore, target.fileStore) == []


def test_undo_takes_the_submodel_and_its_file_out_in_one_step(views) -> None:
    shown, source, target, submodel = _two_packages(views, None)
    _paste_submodel(shown, source, submodel)

    target.commandStack.undo()

    assert list(target.fileStore) == []
    assert "urn:uuid:pasted" not in [obj.id for obj in target.submodels]
    target.commandStack.redo()
    assert files.read_file(target.fileStore, DOC) == b"%PDF source"


def test_a_different_file_with_the_same_name_in_the_target_is_kept(
    views,
) -> None:
    shown, source, target, submodel = _two_packages(
        views, {DOC: (b"%PDF target", "application/pdf")}
    )

    pasted = _paste_submodel(shown, source, submodel)

    assert files.read_file(target.fileStore, DOC) == b"%PDF target"
    renamed = _pasted_element(pasted).value
    assert renamed == "/aasx/files/doc_0001.pdf"
    assert files.read_file(target.fileStore, renamed) == b"%PDF source"
    target.commandStack.undo()
    assert files.read_file(target.fileStore, DOC) == b"%PDF target"
    assert _pasted_element(pasted).value == DOC


def test_pasting_without_a_known_source_adds_no_file(views) -> None:
    shown, _source, target, submodel = _two_packages(views, None)
    pasted = copy.deepcopy(submodel)
    pasted.id = "urn:uuid:pasted"
    copy_source.forget()

    shown.table.addItem(pasted, _source_index(shown, package=1))

    assert list(target.fileStore) == []
    assert _pasted_element(pasted).value == DOC


def test_copying_in_the_tree_remembers_the_files_of_that_package(
    views,
) -> None:
    shown, source, _, _ = _two_packages(views, None)
    shown.select(shown.index("submodels", "Submodel", package=0))

    shown.view.onCopy()

    assert copy_source.store is source.fileStore


def test_a_copy_inside_the_same_package_does_not_touch_its_files(views) -> None:
    shown, source, _, submodel = _two_packages(views, None)
    copy_source.remember(source)
    pasted = copy.deepcopy(submodel)
    pasted.id = "urn:uuid:again"

    shown.table.addItem(pasted, _source_index(shown, package=0))

    assert list(source.fileStore) == [DOC]
    assert files.read_file(source.fileStore, DOC) == b"%PDF source"


def test_the_pasted_file_is_written_by_a_save_and_read_again(
    views, tmp_path
) -> None:
    from aas_editor.package import Package

    shown, source, target, submodel = _two_packages(
        views, {DOC: (b"%PDF target", "application/pdf")}
    )
    pasted = _paste_submodel(shown, source, submodel)
    renamed = _pasted_element(pasted).value

    target.write(tmp_path / "target.aasx")
    reloaded = Package(tmp_path / "target.aasx")

    assert files.read_file(reloaded.fileStore, DOC) == b"%PDF target"
    assert files.read_file(reloaded.fileStore, renamed) == b"%PDF source"
    assert files.find_dangling(reloaded.objStore, reloaded.fileStore) == []


def test_a_content_that_is_identical_is_reused_and_survives_undo(views) -> None:
    shown, source, target, submodel = _two_packages(
        views, {DOC: (b"%PDF source", "application/pdf")}
    )
    _paste_submodel(shown, source, submodel)

    target.commandStack.undo()

    assert list(target.fileStore) == [DOC]
    out = io.BytesIO()
    target.fileStore.write_file(DOC, out)
    assert out.getvalue() == b"%PDF source"
