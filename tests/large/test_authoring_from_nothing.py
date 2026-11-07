"""A person builds a package from nothing in the running editor.

The window starts with no package. Everything goes through what a person
touches: the New button of the start panel, the Create AAS and Create
Submodel dialogs, the Add dialog of every element type, and the actions of
the context menu. The package is then validated, saved as AASX, closed, and
opened again, and its content must be the one that the editor showed.
"""

from pathlib import Path
from xml.etree import ElementTree
import zipfile

from basyx.aas import model
import pytest
from tests.authoring import Author
from tests.authoring_builders import SUBMODEL
from tests.authoring_builders import build_everything
from tests.authoring_builders import make_concept
from tests.authoring_builders import make_shell
from tests.authoring_builders import make_submodels
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


def _findings(author: Author) -> list[tuple[str, str, str]]:
    """Runs the validation of the dock, and lists what it found."""
    dock = author.window.validationController.dock
    dock.show()
    dock.refresh()
    return [
        (finding.severity.value, finding.rule_id, finding.message)
        for finding in dock.report.findings
        if finding.severity.value != "info"
    ]


# Elements that the SDK keeps in a set, so their order is not part of the file.
_UNORDERED = ("submodels", "specificAssetIds", "valueReferencePairs")


def _aas_xml(path: Path) -> bytes:
    """Reads the AAS of an AASX file, with the sets in a fixed order."""
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("aasx/data.xml"))
    for parent in root.iter():
        if parent.tag.rpartition("}")[2] in _UNORDERED:
            children = sorted(parent, key=ElementTree.tostring)
            for child in list(parent):
                parent.remove(child)
            parent.extend(children)
    return ElementTree.tostring(root)


def test_the_start_panel_makes_an_empty_package(
    author: Author, tmp_path: Path
) -> None:
    assert author.window.emptyState.isVisible()
    assert author.window.packTreeModel.rowCount() == 0

    author.start_new_package(tmp_path / "pump.aasx")

    assert not author.window.emptyState.isVisible()
    assert (tmp_path / "pump.aasx").exists()
    assert author.package.file == tmp_path / "pump.aasx"
    assert list(author.package.objStore) == []
    assert not author.stack.can_undo
    assert not author.window.isWindowModified()


def test_a_concept_description_with_a_value_list_is_made_in_the_editor(
    author: Author, tmp_path: Path
) -> None:
    author.start_new_package(tmp_path / "pump.aasx")

    concept = make_concept(author)

    (record,) = concept.embedded_data_specifications
    content = record.data_specification_content
    assert content.preferred_name["de"] == "Geschwindigkeit"  # type: ignore[attr-defined]
    assert {pair.value for pair in content.value_list} == {"slow", "fast"}  # type: ignore[attr-defined]


def test_a_shell_and_three_submodels_are_made_and_linked(
    author: Author, tmp_path: Path
) -> None:
    author.start_new_package(tmp_path / "pump.aasx")

    shell = make_shell(author)
    make_submodels(author)

    asset = shell.asset_information
    assert asset.asset_kind is model.AssetKind.INSTANCE
    assert asset.global_asset_id == "urn:example:asset:pump-1"
    assert asset.asset_type == "urn:example:type:pump"
    assert {(s.name, s.value) for s in asset.specific_asset_id} == {
        ("serialNumber", "SN-100"),
        ("batch", "B7"),
    }
    assert sorted(r.key[0].value for r in shell.submodel) == [
        "urn:example:sm:everything",
        "urn:example:sm:nameplate",
        "urn:example:sm:nameplate-template",
    ]
    kinds = {
        s.id_short: s.kind
        for s in author.package.objStore
        if isinstance(s, model.Submodel)
    }
    assert kinds == {
        "Nameplate": model.ModellingKind.INSTANCE,
        "NameplateTemplate": model.ModellingKind.TEMPLATE,
        "Everything": model.ModellingKind.INSTANCE,
    }


def test_every_element_type_is_added_through_its_dialog(
    author: Author, tmp_path: Path
) -> None:
    concept = build_everything(author, tmp_path)

    everything = author.package.objStore.get_item("urn:example:sm:everything")
    kinds = {e.id_short: type(e) for e in everything.submodel_element}
    assert kinds == {
        "Voltage": model.Property,
        "Label": model.MultiLanguageProperty,
        "Limits": model.Range,
        "Certificate": model.Blob,
        "Datasheet": model.File,
        "Ref": model.ReferenceElement,
        "Rel": model.RelationshipElement,
        "Annotated": model.AnnotatedRelationshipElement,
        "Machine": model.Entity,
        "Start": model.Operation,
        "CanStart": model.Capability,
        "Alarm": model.BasicEventElement,
        "Group": model.SubmodelElementCollection,
    }
    voltage = everything.get_referable("Voltage")
    assert voltage.value == 230
    assert dict(voltage.display_name) == {"en": "Voltage", "de": "Spannung"}
    assert dict(voltage.description)["de"] == "Die Versorgungsspannung"
    assert voltage.semantic_id.key[0].value == concept.id
    assert [(q.type, q.value) for q in voltage.qualifier] == [
        ("Cardinality", "One")
    ]
    assert [e.name for e in voltage.extension] == ["origin"]
    assert [
        k.value for r in voltage.supplemental_semantic_id for k in r.key
    ] == ["urn:example:supplemental"]
    group = everything.get_referable("Group")
    assert [e.id_short for e in group.value][:2] == ["Speed", "Inner"]
    readings = group.get_referable("Readings")
    assert [p.value for p in readings.value] == [11, 12]
    rows = group.get_referable("Rows")
    assert [type(e) for e in rows.value] == [model.SubmodelElementCollection]
    assert rows.value_type_list_element is None
    assert [
        type(e) for e in everything.get_referable("Annotated").annotation
    ] == [model.Property]
    assert [
        e.id_short for e in everything.get_referable("Start").input_variable
    ] == ["Speed"]


def test_a_package_that_a_person_made_correctly_has_no_errors_or_warnings(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)

    findings = _findings(author)

    assert findings == []
    assert author.window.validationController.status.counts.errors == 0
    assert author.window.validationController.status.counts.warnings == 0


def test_undo_goes_back_to_empty_and_redo_gives_the_same_file(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    built = snapshot(author.package.objStore)
    before = tmp_path / "before.aasx"
    author.package.write(before)

    undone = author.undo_all()

    assert undone > 20
    assert list(author.package.objStore) == []
    assert snapshot(author.package.objStore) == snapshot(
        model.DictIdentifiableStore()
    )
    for node in ("shells", "submodels", "concept_descriptions"):
        assert author.names(node) == []
    assert not author.stack.can_undo

    redone = author.redo_all()

    assert redone == undone
    assert snapshot(author.package.objStore) == built
    after = tmp_path / "after.aasx"
    author.package.write(after)
    assert _aas_xml(after) == _aas_xml(before)


def test_the_package_is_saved_as_aasx_closed_and_opened_with_the_same_content(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    built = snapshot(author.package.objStore)
    assert author.window.isWindowModified()
    author.select_path()

    assert author.view.saveAct.isEnabled()
    author.view.saveAct.trigger()

    path = tmp_path / "pump.aasx"
    assert not author.window.isWindowModified(), author.errors
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    assert "[Content_Types].xml" in names
    assert any(name.endswith("aasx-origin") for name in names)
    with zipfile.ZipFile(path) as archive:
        raw = archive.read("aasx/data.xml")
    assert raw.count(b"<aas:id>urn:example:sm:") == 3

    author.view.closeAct.trigger()
    assert author.window.packTreeModel.rowCount() == 0
    assert author.window.emptyState.isVisible()

    author.pick_open_path(path)
    author.view.openPackAct.trigger()

    assert author.window.packTreeModel.rowCount() == 1
    assert snapshot(author.package.objStore) == built
    assert _findings(author) == []
    assert not author.window.isWindowModified()
    assert SUBMODEL[-1] in author.names("submodels")
