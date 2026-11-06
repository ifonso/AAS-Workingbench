"""What `read_package` reports about the objects the SDK left out.

Failsafe mode skips what it cannot construct and logs a record for each. The
reader captures those records for the length of one read and turns them into
`PackageParts.load_report`. These tests check what a user would be told, that
a strict read says nothing, and that the capture leaves the logger as it was.
"""

import json
import logging
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.xml import write_aas_xml_file
import pytest
from tests.factories import DEFAULT_ASSET_ID
from tests.factories import make_concept_description
from tests.factories import make_entity
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx
from tests.medium.failsafe_causes import TEMPLATES_DIR
from tests.package_factories import FIRST_PART
from tests.package_factories import SECOND_PART
from tests.package_factories import SHARED_ID
from tests.package_factories import write_package_with_same_id_in_two_parts

from aas_editor.domain.load_report import Outcome
from aas_editor.domain.load_report import Scope
from aas_editor.infrastructure.package_io import read_package

LOSES_A_SUBMODEL = (
    TEMPLATES_DIR
    / "Hierarchical Structures enabling Bills of Material"
    / "Extension based on IEC 81346"
    / "1"
    / "0"
    / "IDTA 02011-1_Template_BoM_ExtensionbasedonIEC81346.aasx"
)


def _xml_with_equal_property_names(path: Path) -> Path:
    submodel = make_submodel(
        elements=[make_property("Alpha"), make_property("Beta")]
    )
    write_aas_xml_file(path.as_posix(), make_store(submodel))
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            "<aas:idShort>Beta</aas:idShort>",
            "<aas:idShort>Alpha</aas:idShort>",
        ),
        encoding="utf-8",
    )
    return path


def _json_with_defects(path: Path) -> Path:
    property_ = {
        "modelType": "Property",
        "idShort": "P",
        "valueType": "xs:string",
        "value": "v",
    }
    data = {
        "submodels": [
            {"modelType": "Submodel", "id": "urn:x:ok", "idShort": "Good"},
            {
                "modelType": "Submodel",
                "id": "urn:x:bad",
                "idShort": "Bad",
                "submodelElements": [property_, property_],
            },
        ]
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _sdk_logger_state() -> tuple[list[logging.Handler], int]:
    logger = logging.getLogger("basyx")
    return list(logger.handlers), logger.level


def test_a_strict_read_of_a_clean_package_has_an_empty_report(
    tmp_path: Path,
) -> None:
    path = write_aasx(tmp_path / "clean.aasx", make_store(make_shell()))

    parts = read_package(path, failsafe=False)

    assert not parts.load_report
    assert parts.partial is False


def test_a_failsafe_read_of_a_clean_package_has_an_empty_report(
    tmp_path: Path,
) -> None:
    path = write_aasx(tmp_path / "clean.aasx", make_store(make_shell()))

    parts = read_package(path, failsafe=True)

    assert not parts.load_report
    assert parts.partial is True


def test_two_elements_with_one_id_short_cost_the_whole_submodel(
    tmp_path: Path,
) -> None:
    path = _xml_with_equal_property_names(tmp_path / "defect.xml")

    parts = read_package(path, failsafe=True)

    # The SDK adds the elements while it builds the submodel, so the
    # constraint fails the submodel, and not only the second property. The
    # report says what is gone: the submodel.
    (issue,) = parts.load_report.issues
    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.OBJECT
    assert issue.subject == "submodel"
    assert issue.location.startswith("line ")
    assert "AASd-022" in issue.reason
    assert len(parts.objects) == 0


def test_an_element_that_fails_alone_is_one_element_and_its_siblings_stay(
    tmp_path: Path,
) -> None:
    entity = make_entity("Part")
    submodel = make_submodel(elements=[make_property("Alpha"), entity])
    path = tmp_path / "entity.xml"
    write_aas_xml_file(path.as_posix(), make_store(submodel))
    text = path.read_text(encoding="utf-8")
    # A self-managed entity needs an asset id (AASd-014).
    path.write_text(
        text.replace(
            f"<aas:globalAssetId>{DEFAULT_ASSET_ID}</aas:globalAssetId>", ""
        ),
        encoding="utf-8",
    )

    parts = read_package(path, failsafe=True)

    (issue,) = parts.load_report.issues
    assert (issue.scope, issue.subject) == (Scope.ELEMENT, "entity")
    assert "AASd-014" in issue.reason
    (loaded,) = parts.objects
    assert isinstance(loaded, model.Submodel)
    assert [e.id_short for e in loaded.submodel_element] == ["Alpha"]


def test_a_failsafe_read_of_json_gives_one_issue_for_each_object(
    tmp_path: Path,
) -> None:
    path = _json_with_defects(tmp_path / "defect.json")

    parts = read_package(path, failsafe=True)

    (issue,) = parts.load_report.issues
    assert issue.scope is Scope.OBJECT
    assert issue.subject == "submodel"
    assert issue.location == "id urn:x:bad"
    assert "AASd-022" in issue.reason
    assert [o.id for o in parts.objects] == ["urn:x:ok"]


def test_a_failsafe_read_of_an_aasx_names_the_part_and_the_object(
    tmp_path: Path,
) -> None:
    parts = read_package(LOSES_A_SUBMODEL, failsafe=True)

    submodels = [
        i for i in parts.load_report.left_out_objects if i.subject == "submodel"
    ]
    (lost,) = submodels
    assert lost.location == "line 33"
    assert lost.part.endswith(".aas.xml")
    assert "AASd-118" in lost.reason


def test_a_duplicate_concept_description_is_reported_with_its_id(
    tmp_path: Path,
) -> None:
    path = tmp_path / "duplicate.xml"
    write_aas_xml_file(path.as_posix(), make_store(make_concept_description()))
    text = path.read_text(encoding="utf-8")
    start = text.index("<aas:conceptDescription>")
    end = text.index("</aas:conceptDescription>") + len(
        "</aas:conceptDescription>"
    )
    block = text[start:end]
    path.write_text(text[:end] + block + text[end:], encoding="utf-8")

    parts = read_package(path, failsafe=True)

    (issue,) = parts.load_report.issues
    assert issue.scope is Scope.OBJECT
    assert issue.subject == "concept description"
    assert issue.location.startswith("id urn:uuid:")
    assert len(parts.objects) == 1


def test_an_object_in_a_second_part_with_a_known_id_is_reported_in_strict_mode(
    tmp_path: Path,
) -> None:
    path = write_package_with_same_id_in_two_parts(tmp_path / "two.aasx")

    parts = read_package(path, failsafe=False)

    (issue,) = parts.load_report.issues
    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.OBJECT
    assert issue.location == f"id {SHARED_ID}"
    assert issue.part == SECOND_PART
    assert FIRST_PART in issue.reason
    # The first one is kept, and the report is why the package is partial.
    kept = parts.objects.get(SHARED_ID)
    assert isinstance(kept, model.Submodel)
    assert kept.id_short == "First"
    assert parts.partial is True


def test_an_object_in_a_second_part_is_reported_once_in_failsafe_mode(
    tmp_path: Path,
) -> None:
    path = write_package_with_same_id_in_two_parts(tmp_path / "two.aasx")

    parts = read_package(path, failsafe=True)

    assert len(parts.load_report.issues) == 1


def test_the_sdk_logger_is_left_as_it_was_after_a_read() -> None:
    handlers, level = _sdk_logger_state()

    read_package(LOSES_A_SUBMODEL, failsafe=True)

    assert _sdk_logger_state() == (handlers, level)


def test_the_sdk_logger_is_left_as_it_was_when_the_read_raises(
    tmp_path: Path,
) -> None:
    handlers, level = _sdk_logger_state()
    broken = tmp_path / "broken.json"
    broken.write_text("{ not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Expecting"):
        read_package(broken, failsafe=True)
    with pytest.raises(OSError, match="missing"):
        read_package(tmp_path / "missing.aasx", failsafe=True)

    assert _sdk_logger_state() == (handlers, level)


def test_records_are_captured_when_the_sdk_logger_is_set_above_warning(
    tmp_path: Path,
) -> None:
    logger = logging.getLogger("basyx")
    old = logger.level
    logger.setLevel(logging.CRITICAL)
    try:
        parts = read_package(
            _xml_with_equal_property_names(tmp_path / "defect.xml"),
            failsafe=True,
        )
        level_after = logger.level
    finally:
        logger.setLevel(old)

    assert len(parts.load_report.issues) == 1
    assert level_after == logging.CRITICAL


def test_the_capture_leaves_other_handlers_of_the_logger_working(
    tmp_path: Path,
) -> None:
    class Collect(logging.Handler):
        def __init__(self) -> None:
            super().__init__()
            self.messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:
            self.messages.append(record.getMessage())

    collector = Collect()
    logger = logging.getLogger("basyx")
    logger.addHandler(collector)
    try:
        read_package(
            _xml_with_equal_property_names(tmp_path / "defect.xml"),
            failsafe=True,
        )
    finally:
        logger.removeHandler(collector)

    assert any("AASd-022" in message for message in collector.messages)
