"""The example package `example/robot_arm_pick_and_place.aasx`.

The package is a file in the repository that `example/build_robot_arm.py`
writes. These tests open it as the editor does, check it against the rules of
the metamodel and against the structure of the IDTA templates that it follows,
and check that the file is what the script makes, so that the two cannot drift
apart.
"""

from collections import defaultdict
from collections.abc import Iterator
import importlib
from pathlib import Path
import sys
from types import ModuleType
import zipfile

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
import json
from PyQt6.QtGui import QImage
import pytest
from tests.serialization import snapshot

from aas_editor.application.save import SaveOptions
from aas_editor.domain.references import is_model_reference
from aas_editor.domain.references import iter_slots
from aas_editor.domain.validation import validate
from aas_editor.domain.walking import descendants
from aas_editor.domain.walking import walk_elements
from aas_editor.infrastructure.package_io import PackageParts
from aas_editor.infrastructure.package_io import read_package
from aas_editor.infrastructure.package_io import write_package

REPOSITORY = Path(__file__).resolve().parents[2]
EXAMPLE = REPOSITORY / "example"
PACKAGE = EXAMPLE / "robot_arm_pick_and_place.aasx"
NAMESPACE = "https://example.com/ids"

ALL_ELEMENT_TYPES = {
    model.Property,
    model.MultiLanguageProperty,
    model.Range,
    model.Blob,
    model.File,
    model.ReferenceElement,
    model.RelationshipElement,
    model.AnnotatedRelationshipElement,
    model.Capability,
    model.Operation,
    model.BasicEventElement,
    model.Entity,
    model.SubmodelElementCollection,
    model.SubmodelElementList,
}

EXPECTED_FILES = {
    "/aasx/files/pp6_arm.png": "image/png",
    "/aasx/files/pp6_work_envelope.png": "image/png",
    "/aasx/files/pp6_thumbnail.png": "image/png",
    "/aasx/files/pp6_logo.png": "image/png",
    "/aasx/files/pp6_marking.png": "image/png",
    "/aasx/files/pp6_datasheet.pdf": "application/pdf",
    "/aasx/files/pp6_quickstart_en.pdf": "application/pdf",
    "/aasx/files/pp6_quickstart_de.pdf": "application/pdf",
}

# The submodels that follow a bundled template, by the key of the template.
TEMPLATE_SUBMODELS = {
    "nameplate": "Nameplate",
    "contact": "ContactInformations",
    "technical": "TechnicalData",
    "handover": "HandoverDocumentation",
    "structure": "HierarchicalStructures",
    "carbon": "CarbonFootprint",
    "software": "SoftwareNameplate",
    "series": "TimeSeries",
}

# References that point outside the package on purpose, and where.
EXTERNAL_ON_PURPOSE = {
    # The manufacturer, as the subject of the specific asset ids and the creator
    # of the submodels.
    f"{NAMESPACE}/company/workingbench-example-robotics",
    # The IEC 61360 template of every concept description.
    "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/1",
    # The scanner of the station, a neighbor that has no shell here.
    f"{NAMESPACE}/asset/safety-scanner/SS-0007",
    # The value of the state of a finished time series segment, from the
    # specification of the template.
    "https://admin-shell.io/idta/TimeSeries/Segment/State/Completed/1/1",
}


@pytest.fixture(scope="module")
def builder() -> Iterator[ModuleType]:
    """Imports the script that builds the example."""
    sys.path.insert(0, str(EXAMPLE))
    try:
        yield importlib.import_module("build_robot_arm")
    finally:
        sys.path.remove(str(EXAMPLE))


@pytest.fixture(scope="module")
def templates(builder: ModuleType) -> ModuleType:
    """The module of the script that reads the bundled templates."""
    return sys.modules["arm_templates"]


@pytest.fixture(scope="module")
def parts() -> PackageParts:
    """Opens the example strictly, as the editor does first."""
    return read_package(PACKAGE, failsafe=False)


def _submodels(parts: PackageParts) -> dict[str, model.Submodel]:
    return {
        obj.id_short: obj
        for obj in parts.objects
        if isinstance(obj, model.Submodel)
    }


def _concepts(parts: PackageParts) -> dict[str, model.ConceptDescription]:
    return {
        obj.id: obj
        for obj in parts.objects
        if isinstance(obj, model.ConceptDescription)
    }


def _elements(parts: PackageParts) -> Iterator[model.SubmodelElement]:
    for submodel in _submodels(parts).values():
        yield from descendants(submodel)


def _value(submodel: model.Submodel, *path: str) -> object:
    current: object = submodel
    for step in path:
        current = current.get_referable(step)  # type: ignore[attr-defined]
    return current.value  # type: ignore[attr-defined]


def test_it_opens_strictly_with_no_load_report(parts: PackageParts) -> None:
    assert not parts.partial
    assert parts.load_report.issues == ()
    assert parts.missing_files == ()


def test_it_is_small(parts: PackageParts) -> None:
    assert PACKAGE.stat().st_size < 1_000_000


def test_it_has_one_shell_and_the_planned_submodels(
    parts: PackageParts,
) -> None:
    shells = [
        o
        for o in parts.objects
        if isinstance(o, model.AssetAdministrationShell)
    ]
    (shell,) = shells

    assert shell.asset_information.global_asset_id is not None
    assert shell.asset_information.asset_kind is model.AssetKind.INSTANCE
    assert len(shell.asset_information.specific_asset_id) == 3
    assert shell.asset_information.default_thumbnail is not None
    assert {s.id_short for s in _submodels(parts).values()} == {
        "Nameplate",
        "ContactInformations",
        "TechnicalData",
        "HandoverDocumentation",
        "HierarchicalStructures",
        "Capabilities",
        "CycleBehavior",
        "PickAndPlaceJob",
        "PickAndPlaceStation",
        "OperationalData",
        "TimeSeries",
        "SoftwareNameplate",
        "CarbonFootprint",
        "Documentation",
    }
    assert {r.key[0].value for r in shell.submodel} == {
        s.id for s in _submodels(parts).values()
    }


def test_all_fourteen_element_types_are_present(parts: PackageParts) -> None:
    found = {type(element) for element in _elements(parts)}

    assert found == ALL_ELEMENT_TYPES


def test_walking_the_elements_finds_the_same_types_as_descendants(
    parts: PackageParts,
) -> None:
    # Guards the walk of the test against the walk of the SDK.
    walked = {
        type(element)
        for submodel in _submodels(parts).values()
        for element in walk_elements(submodel)
    }

    assert walked <= ALL_ELEMENT_TYPES


def test_validation_reports_no_errors_and_no_warnings(
    parts: PackageParts,
) -> None:
    report = validate(parts.objects, stored_files=parts.files)

    assert report.errors == ()
    assert report.warnings == ()


def test_ids_are_under_the_namespace_of_the_example(
    parts: PackageParts,
) -> None:
    own = [
        o for o in parts.objects if not _is_imported_template_concept(o, parts)
    ]

    assert own
    assert all(o.id.startswith(f"{NAMESPACE}/") for o in own)


def _is_imported_template_concept(
    obj: model.Identifiable, parts: PackageParts
) -> bool:
    return isinstance(obj, model.ConceptDescription) and not obj.id.startswith(
        NAMESPACE
    )


def _template_semantics(templates: ModuleType) -> set[str]:
    """The values of every reference that the bundled templates store."""
    values: set[str] = set()
    for key in templates.TEMPLATE_FILES:
        template = templates.Template(key)
        for obj in (template.submodel, *template.objects):
            for slot in iter_slots(obj):
                for ref in (slot.reference,):
                    values.update("".join(k.value.split()) for k in ref.key)
            if isinstance(obj, model.ConceptDescription):
                values.add(obj.id)
    return values


def test_every_model_reference_resolves_and_every_external_one_is_known(
    parts: PackageParts, templates: ModuleType
) -> None:
    concepts = set(_concepts(parts))
    known_semantics = _template_semantics(templates)
    value_ids = {
        pair.value_id.key[0].value
        for concept in _concepts(parts).values()
        for record in concept.embedded_data_specifications
        for pair in (record.data_specification_content.value_list or ())  # type: ignore[union-attr]
        if pair.value_id is not None
    }
    problems: list[str] = []
    for obj in parts.objects:
        for slot in iter_slots(obj):
            reference = slot.reference
            where = f"{slot.location} -> {reference.key[-1].value}"
            if is_model_reference(reference):
                try:
                    reference.resolve(parts.objects)  # type: ignore[attr-defined]
                except (KeyError, ValueError, TypeError, AttributeError):
                    problems.append(f"does not resolve: {where}")
                continue
            value = reference.key[-1].value
            if slot.attribute in (
                "semantic_id",
                "supplemental_semantic_id",
                "semantic_id_list_element",
            ):
                if value not in concepts and value not in known_semantics:
                    problems.append(f"unknown semantic id: {where}")
            elif slot.attribute == "is_case_of":
                # A description of a template that is a case of an entry of a
                # dictionary that the package does not hold.
                continue
            elif slot.attribute == "value_id":
                if (
                    value not in value_ids
                    and value not in EXTERNAL_ON_PURPOSE
                    and value not in known_semantics
                ):
                    problems.append(f"unknown value id: {where}")
            elif value not in EXTERNAL_ON_PURPOSE and value not in value_ids:
                problems.append(f"external on no purpose: {where}")

    assert problems == []


def test_every_element_has_a_semantic_id_that_means_something(
    parts: PackageParts, templates: ModuleType
) -> None:
    concepts = set(_concepts(parts))
    known = _template_semantics(templates)
    missing = [
        element.id_short
        for element in _elements(parts)
        if element.semantic_id is None
    ]
    unknown = [
        element.id_short
        for element in _elements(parts)
        if element.semantic_id is not None
        and element.semantic_id.key[-1].value not in concepts
        and "".join(element.semantic_id.key[-1].value.split()) not in known
    ]

    assert missing == []
    assert unknown == []


def test_every_concept_of_the_example_is_used(parts: PackageParts) -> None:
    used: set[str] = set()
    for obj in parts.objects:
        for slot in iter_slots(obj):
            if slot.attribute != "data_specification":
                used.update(k.value for k in slot.reference.key)
    unused = [
        concept_id
        for concept_id in _concepts(parts)
        if concept_id.startswith(NAMESPACE) and concept_id not in used
    ]

    assert unused == []


def test_every_concept_has_an_iec_record_in_three_languages(
    parts: PackageParts,
) -> None:
    weak: list[str] = []
    for concept_id, concept in _concepts(parts).items():
        if not concept_id.startswith(NAMESPACE):
            continue
        (record,) = concept.embedded_data_specifications
        content = record.data_specification_content
        assert isinstance(content, model.DataSpecificationIEC61360)
        for texts in (content.preferred_name, content.definition):
            if texts is None or set(texts) != {"en", "de", "pt"}:
                weak.append(concept_id)
        measure = content.data_type in (
            model.DataTypeIEC61360.REAL_MEASURE,
            model.DataTypeIEC61360.INTEGER_MEASURE,
        )
        if measure and not content.unit:
            weak.append(f"{concept_id} has no unit")

    assert weak == []


def test_a_coded_property_has_a_value_in_the_value_list_of_its_concept(
    parts: PackageParts,
) -> None:
    concepts = _concepts(parts)
    checked = 0
    for element in _elements(parts):
        if not isinstance(element, model.Property) or element.value_id is None:
            continue
        concept = concepts.get(element.semantic_id.key[-1].value)  # type: ignore[union-attr]
        if concept is None:
            continue
        (record,) = concept.embedded_data_specifications
        pairs = {
            p.value: p.value_id.key[0].value  # type: ignore[union-attr]
            for p in (record.data_specification_content.value_list or ())  # type: ignore[union-attr]
        }
        if not pairs:
            # A description of a template that names no list; the value id is
            # then the value of its enumeration in the specification.
            continue
        assert pairs[element.value] == element.value_id.key[0].value
        checked += 1

    assert checked > 10


def test_the_mode_has_a_value_list_in_its_concept(parts: PackageParts) -> None:
    concept = _concepts(parts)[f"{NAMESPACE}/concept/OperatingMode"]
    (record,) = concept.embedded_data_specifications
    values = {p.value for p in record.data_specification_content.value_list}  # type: ignore[union-attr]

    assert values == {"AUTOMATIC", "MANUAL_REDUCED", "MANUAL_HIGH"}


def test_the_supplementary_files_are_stored(parts: PackageParts) -> None:
    stored = {name: parts.files.get_content_type(name) for name in parts.files}

    assert stored == EXPECTED_FILES


def test_the_files_are_real_files_that_nothing_but_the_example_made(
    parts: PackageParts,
) -> None:
    for name, content_type in EXPECTED_FILES.items():
        content = _read(parts, name)
        if content_type == "image/png":
            assert content.startswith(b"\x89PNG\r\n\x1a\n"), name
        else:
            assert content.startswith(b"%PDF-1.4"), name
            assert content.rstrip().endswith(b"%%EOF"), name
    assert len(_read(parts, "/aasx/files/pp6_arm.png")) > 5_000


def _read(parts: PackageParts, name: str) -> bytes:
    import io

    buffer = io.BytesIO()
    parts.files.write_file(name, buffer)
    return buffer.getvalue()


def test_the_datasheet_says_that_it_is_fictional(parts: PackageParts) -> None:
    import io

    from pypdf import PdfReader

    text = PdfReader(io.BytesIO(_read(parts, "/aasx/files/pp6_datasheet.pdf")))
    page = text.pages[0].extract_text()

    assert "Workingbench Example Arm PP-6" in page
    assert "FICTIONAL EXAMPLE" in page
    assert "900 mm" in page


def test_every_file_element_points_at_a_stored_file(
    parts: PackageParts,
) -> None:
    files = [e for e in _elements(parts) if isinstance(e, model.File)]
    paths = {f.value for f in files}

    assert len(files) >= 10
    assert paths <= set(parts.files)
    assert all(
        f.content_type == parts.files.get_content_type(f.value) for f in files
    )


def test_the_thumbnails_are_the_same_picture(parts: PackageParts) -> None:
    (shell,) = [
        o
        for o in parts.objects
        if isinstance(o, model.AssetAdministrationShell)
    ]
    default = shell.asset_information.default_thumbnail

    assert parts.thumbnail is not None
    assert default is not None
    assert parts.thumbnail.data == _read(parts, default.path)


def test_the_blob_holds_json(parts: PackageParts) -> None:
    blob = _submodels(parts)["Documentation"].get_referable("JointCalibration")

    assert isinstance(blob, model.Blob)
    assert blob.content_type == "application/json"
    assert json.loads(blob.value)["unit"] == "deg"  # type: ignore[arg-type]


def test_the_texts_come_in_english_german_and_portuguese(
    parts: PackageParts,
) -> None:
    documentation = _submodels(parts)["Documentation"]

    for name in ("ProductOverview", "ExampleDisclaimer", "SafetyNotice"):
        element = documentation.get_referable(name)
        assert isinstance(element, model.MultiLanguageProperty)
        assert set(element.value or ()) == {"en", "de", "pt"}


def test_the_numbers_of_the_arm_agree(parts: PackageParts) -> None:
    technical = _submodels(parts)["TechnicalData"]
    areas = list(technical.get_referable("TechnicalPropertyAreas").value)  # type: ignore[attr-defined]
    performance = areas[0]
    axes = list(areas[1].get_referable("Axes").value)
    operational = _submodels(parts)["OperationalData"]
    joints = list(operational.get_referable("JointStates").value)  # type: ignore[attr-defined]
    structure = _submodels(parts)["HierarchicalStructures"]
    masses = [
        e.value
        for e in descendants(structure)
        if isinstance(e, model.Property) and e.id_short == "PartMass"
    ]
    arm_mass = performance.get_referable("ArmMass").value

    assert performance.get_referable("NumberOfAxes").value == 6
    assert len(axes) == len(joints) == 6
    # The mass of the arm is the sum of its parts, without the gripper (0.97
    # kg with the option) and the controller.
    assert sum(masses) - 0.55 - 0.06 - 0.06 - 0.18 - 12.0 == pytest.approx(
        arm_mass
    )
    # The last temperature of the history is what the operational data shows.
    series = _submodels(parts)["TimeSeries"]
    last = list(
        series.get_referable("Segments")  # type: ignore[attr-defined]
        .get_referable("InternalSegment")
        .get_referable("Records")
        .value
    )[-1]
    for index, joint in enumerate(joints, start=1):
        assert last.get_referable(f"Joint{index}Temperature").value == (
            joint.get_referable("JointTemperature").value
        )


def test_the_job_visits_poses_that_the_arm_can_reach(
    parts: PackageParts,
) -> None:
    job = _submodels(parts)["PickAndPlaceJob"]
    reach = 900.0
    for item in job.get_referable("Poses").value:  # type: ignore[attr-defined]
        pose = item.get_referable("Pose")
        x, y, z = (
            pose.get_referable(k).value for k in ("PoseX", "PoseY", "PoseZ")
        )
        assert (x**2 + y**2 + z**2) ** 0.5 <= reach + 200  # the tool is long


def test_a_state_machine_has_no_transition_out_of_nowhere(
    parts: PackageParts,
) -> None:
    behavior = _submodels(parts)["CycleBehavior"]
    states = list(behavior.get_referable("CycleStates").value)  # type: ignore[attr-defined]
    for transition in behavior.get_referable("StateTransitions").value:  # type: ignore[attr-defined]
        for end in ("From", "To"):
            target = transition.get_referable(end).value.resolve(parts.objects)
            assert target in states


# ---- The templates


def _key(element: model.Referable) -> str | None:
    semantic = getattr(element, "semantic_id", None)
    if semantic is None:
        return None
    return "".join(semantic.key[-1].value.split())


def _cardinality(element: model.SubmodelElement) -> str | None:
    for qualifier in element.qualifier:
        if qualifier.type.rsplit("/", 1)[-1] in ("Cardinality", "Multiplicity"):
            return qualifier.value
    return None


def _children(element: model.Referable) -> list[model.SubmodelElement]:
    if isinstance(
        element, (model.SubmodelElementCollection, model.SubmodelElementList)
    ):
        return list(element.value)
    if isinstance(element, model.Submodel):
        return list(element.submodel_element)
    if isinstance(element, model.Entity):
        return list(element.statement)
    return []


def _conform(
    template: model.Referable,
    instance: model.Referable,
    path: str,
    allowed_extra: set[str],
    problems: list[str],
) -> None:
    """Compares an element with the element of the template at its place."""
    if type(template) is not type(instance):
        problems.append(
            f"{path}: {type(instance).__name__}, not {type(template).__name__}"
        )
        return
    if (
        isinstance(template, model.Property)
        and isinstance(instance, model.Property)
        and template.value_type is not instance.value_type
    ):
        problems.append(f"{path}: value type {instance.value_type.__name__}")
    if (
        isinstance(template, model.SubmodelElementList)
        and isinstance(instance, model.SubmodelElementList)
        and (
            template.type_value_list_element
            is not instance.type_value_list_element
        )
    ):
        problems.append(
            f"{path}: list of {instance.type_value_list_element.__name__}"
        )
    by_key: dict[str | None, list[model.SubmodelElement]] = defaultdict(list)
    for child in _children(template):
        by_key[_key(child)].append(child)
    instances = _children(instance)
    matched: set[int] = set()
    for key, templates in by_key.items():
        if key is None or "SMT/General" in key or len(templates) > 1:
            continue
        found = [c for c in instances if _key(c) == key]
        matched.update(id(c) for c in found)
        cardinality = _cardinality(templates[0])
        name = templates[0].id_short or key
        if cardinality in ("One", "OneToMany") and not found:
            problems.append(
                f"{path}/{name}: required ({cardinality}) and missing"
            )
        # The items of a list are as many as the list needs, whatever the
        # template says about the one item that it shows.
        in_list = isinstance(template, model.SubmodelElementList)
        if (
            cardinality in ("One", "ZeroToOne")
            and len(found) > 1
            and not in_list
        ):
            problems.append(f"{path}/{name}: {len(found)} of a {cardinality}")
        for child in found:
            _conform(
                templates[0],
                child,
                f"{path}/{child.id_short or name}",
                allowed_extra,
                problems,
            )
    for child in instances:
        if id(child) in matched:
            continue
        key = _key(child)
        if key is None or key not in allowed_extra:
            problems.append(
                f"{path}/{child.id_short}: not in the template, and not described by the example"
            )


@pytest.mark.parametrize("key", list(TEMPLATE_SUBMODELS))
def test_a_template_submodel_follows_the_structure_of_its_template(
    key: str, parts: PackageParts, templates: ModuleType
) -> None:
    from_templates = _template_semantics(templates)
    own = {c for c in _concepts(parts) if c.startswith(NAMESPACE)}
    template = templates.Template(key)
    instance = _submodels(parts)[TEMPLATE_SUBMODELS[key]]
    problems: list[str] = []

    assert instance.semantic_id is not None
    assert instance.id_short == template.submodel.id_short
    assert instance.kind is model.ModellingKind.INSTANCE
    assert _key(instance) == _key(template.submodel)
    assert instance.administration is not None
    assert instance.administration.version == (
        template.submodel.administration.version  # type: ignore[union-attr]
        if template.submodel.administration
        and template.submodel.administration.version
        else "1"
    )
    _conform(
        template.submodel,
        instance,
        instance.id_short,
        own | from_templates,
        problems,
    )

    assert problems == []


def test_a_template_submodel_has_no_template_qualifier_and_no_placeholder(
    parts: PackageParts,
) -> None:
    problems: list[str] = []
    for key, name in TEMPLATE_SUBMODELS.items():
        for element in descendants(_submodels(parts)[name]):
            for qualifier in element.qualifier:
                if qualifier.kind is model.QualifierKind.TEMPLATE_QUALIFIER:
                    problems.append(
                        f"{name}/{element.id_short}: template qualifier"
                    )
            texts = []
            if isinstance(element, model.MultiLanguageProperty):
                texts = list((element.value or {}).values())
            elif isinstance(element, model.Property) and isinstance(
                element.value, str
            ):
                texts = [element.value]
            for text in texts:
                lowered = text.lower()
                if any(
                    mark in lowered
                    for mark in (
                        "muster ag",
                        "domain-abc",
                        "abc-123",
                        "sample",
                        "e.g.",
                        "<",
                        "tud.de",
                    )
                ):
                    problems.append(f"{name}/{element.id_short}: {text!r}")

    assert problems == []


@pytest.mark.parametrize("key", list(TEMPLATE_SUBMODELS))
def test_each_template_opens_strictly_in_the_editor(
    key: str, templates: ModuleType
) -> None:
    files = templates.TEMPLATE_FILES
    templates = templates.TEMPLATES
    path = templates / files[key]

    opened = read_package(path, failsafe=False)

    assert not opened.partial
    assert opened.load_report.issues == ()


def test_the_nameplate_template_is_the_one_that_is_not_in_metamodel_3_1(
    templates: ModuleType,
) -> None:
    files = templates.TEMPLATE_FILES
    templates = templates.TEMPLATES
    namespaces: dict[str, str] = {}
    for key, relative in files.items():
        with zipfile.ZipFile(templates / relative) as archive:
            name = next(
                n
                for n in archive.namelist()
                if n.endswith((".xml", ".json")) and "rels" not in n
            )
            head = archive.read(name)[:600].decode("utf-8", "replace")
        namespaces[key] = "3/1" if "aas/3/1" in head else "3/0"

    assert {k for k, v in namespaces.items() if v == "3/0"} == {"nameplate"}


# ---- Save, reopen, and rebuild


def test_it_survives_a_save_and_a_reopen(
    parts: PackageParts, tmp_path: Path
) -> None:
    target = tmp_path / "again.aasx"

    write_package(target, parts, SaveOptions())
    again = read_package(target, failsafe=False)

    assert again.load_report.issues == ()
    assert snapshot(again.objects) == snapshot(parts.objects)
    assert _stored(again) == _stored(parts)
    assert again.thumbnail == parts.thumbnail
    assert _properties(again) == _properties(parts)


def _properties(parts: PackageParts) -> dict[str, object]:
    properties = parts.core_properties
    assert properties is not None
    return {a[0]: getattr(properties, a[0]) for a in properties.ATTRIBUTES}


def _stored(parts: PackageParts) -> dict[str, tuple[str, bytes]]:
    return {
        name: (parts.files.get_content_type(name), _read(parts, name))
        for name in sorted(parts.files)
    }


def _same_picture(first: bytes, second: bytes) -> bool:
    """Tells whether two PNG files show the same image, give or take a shade.

    The pictures are drawn with antialiasing, which two machines can round
    differently by a level, so the comparison allows that and nothing more.
    """
    a = QImage.fromData(first, "PNG").convertToFormat(
        QImage.Format.Format_RGB32
    )
    b = QImage.fromData(second, "PNG").convertToFormat(
        QImage.Format.Format_RGB32
    )
    if a.size() != b.size():
        return False
    worst = 0
    for y in range(0, a.height(), 3):
        for x in range(0, a.width(), 3):
            p, q = a.pixelColor(x, y), b.pixelColor(x, y)
            worst = max(
                worst,
                abs(p.red() - q.red()),
                abs(p.green() - q.green()),
                abs(p.blue() - q.blue()),
            )
    return worst <= 3


def test_running_the_script_gives_the_package_in_the_repository(
    parts: PackageParts, builder: ModuleType, tmp_path: Path
) -> None:
    target = tmp_path / "rebuilt.aasx"

    builder.write(builder.build(), target)
    rebuilt = read_package(target, failsafe=False)

    assert rebuilt.load_report.issues == ()
    assert snapshot(rebuilt.objects) == snapshot(parts.objects)
    assert _properties(rebuilt) == _properties(parts)
    stored, rebuilt_files = _stored(parts), _stored(rebuilt)
    assert stored.keys() == rebuilt_files.keys()
    for name, (content_type, content) in stored.items():
        assert rebuilt_files[name][0] == content_type
        if content_type == "image/png":
            assert _same_picture(content, rebuilt_files[name][1]), name
        else:
            assert content == rebuilt_files[name][1], name
    assert parts.thumbnail is not None and rebuilt.thumbnail is not None
    assert parts.thumbnail.name == rebuilt.thumbnail.name
    assert _same_picture(parts.thumbnail.data, rebuilt.thumbnail.data)


def test_the_encoder_of_the_sdk_writes_every_object(
    parts: PackageParts,
) -> None:
    # A last guard: nothing in the example is out of reach of the JSON writer,
    # so a user can export it.
    for obj in parts.objects:
        assert json.dumps(obj, cls=AASToJsonEncoder)
