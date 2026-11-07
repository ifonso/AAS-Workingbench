"""Turning the log records of the SDK into a report of what was left out.

The messages are copied from what the pinned SDK logs while it reads the
bundled templates and the JSON files made for these tests.
"""

import pytest

from aas_workingbench.domain.load_report import LoadReport
from aas_workingbench.domain.load_report import Outcome
from aas_workingbench.domain.load_report import RawRecord
from aas_workingbench.domain.load_report import Scope
from aas_workingbench.domain.load_report import Severity
from aas_workingbench.domain.load_report import build_report
from aas_workingbench.domain.load_report import duplicate_in_other_part
from aas_workingbench.domain.load_report import parse_record

PART = "/aasx/data/data.aas.xml"

SUBMODEL_LOST = (
    "AASConstraintViolation: A semantic_id must be defined before adding a "
    "supplemental_semantic_id! (Constraint AASd-118)\n"
    " -> Failed to construct ns0:submodel on line 33 using "
    "construct_submodel!"
)
NESTED = (
    "KeyError: ns0:text on line 6357 has no text!\n"
    " -> Failed to construct ns0:preferredName on line 6354 using "
    "construct_preferred_name_type_iec61360!\n"
    " -> Failed to construct ns0:dataSpecificationIec61360 on line 6353 "
    "using construct_data_specification_content!\n"
    " -> Failed to construct ns0:embeddedDataSpecification on line 6342 "
    "using construct_embedded_data_specification!"
)
DUPLICATE = (
    "ConceptDescription[https://admin-shell.io/idta/ExecutedProcesses/1/0] "
    "has a duplicate identifier already parsed in the document! skipping it..."
)


def error(message: str, part: str = PART) -> RawRecord:
    return RawRecord(Severity.ERROR, "basyx.test", message, part)


def warning(message: str) -> RawRecord:
    return RawRecord(Severity.WARNING, "basyx.test", message)


def test_a_submodel_that_could_not_be_built_is_an_object_that_was_left_out() -> (
    None
):
    issue = parse_record(error(SUBMODEL_LOST))

    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.OBJECT
    assert issue.subject == "submodel"
    assert issue.location == "line 33"
    assert issue.part == PART
    assert "AASd-118" in issue.reason
    assert issue.text == SUBMODEL_LOST


def test_a_nested_failure_is_one_issue_about_the_outermost_construct() -> None:
    report = build_report([error(NESTED)])

    (issue,) = report.issues
    assert issue.subject == "embedded data specification"
    assert issue.location == "line 6342"
    assert issue.scope is Scope.DETAIL
    assert issue.reason == "ns0:text on line 6357 has no text!"
    # Every line of the SDK is still there.
    assert "construct_preferred_name_type_iec61360" in issue.text


def test_an_element_is_told_from_an_object_and_a_detail() -> None:
    entity = (
        "AASConstraintViolation: A self-managed entity has to have a "
        "globalAssetId or a specificAssetId (Constraint AASd-014)\n"
        " -> Failed to construct ns0:entity on line 67 using "
        "construct_submodel_element!"
    )
    reference = (
        "ValueError: A reference must have at least one key!\n"
        " -> Failed to construct {https://admin-shell.io/aas/3/1}semanticId "
        "on line 9 using construct_reference!"
    )

    entity_issue = parse_record(error(entity))
    reference_issue = parse_record(error(reference))

    assert (entity_issue.scope, entity_issue.subject) == (
        Scope.ELEMENT,
        "entity",
    )
    assert (reference_issue.scope, reference_issue.subject) == (
        Scope.DETAIL,
        'reference "semantic id"',
    )


def test_a_second_object_with_the_same_id_names_the_id() -> None:
    issue = parse_record(error(DUPLICATE, part=""))

    assert issue.scope is Scope.OBJECT
    assert issue.subject == "concept description"
    assert (
        issue.location == "id https://admin-shell.io/idta/ExecutedProcesses/1/0"
    )
    assert "first one was kept" in issue.reason


def test_a_record_that_no_pattern_knows_is_kept_in_full() -> None:
    message = "Opening and ending tag mismatch: a line 1 and b, line 1\nmore"

    issue = parse_record(error(message))

    assert issue.outcome is Outcome.UNKNOWN
    assert issue.text == message
    assert "Opening and ending tag mismatch" in issue.describe()
    assert "more" in issue.describe()


def test_a_warning_about_a_key_type_is_kept_content_not_a_loss() -> None:
    issue = parse_record(
        warning(
            "type SUBMODEL of last key of reference to Submodel / x does not "
            "match reference type ConceptDescription"
        )
    )

    assert issue.outcome is Outcome.KEPT


def test_an_unclassified_warning_is_not_counted_as_a_loss() -> None:
    issue = parse_record(warning("Something new that nobody expected"))

    assert issue.outcome is Outcome.UNKNOWN


def test_a_warning_that_drops_a_child_is_a_loss() -> None:
    issue = parse_record(
        warning(
            "ns0:value on line 9 has more than one submodel element, using "
            "the first one..."
        )
    )

    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.DETAIL


def test_the_two_json_records_of_one_loss_are_one_issue() -> None:
    cause = (
        "Error while trying to convert JSON object into Submodel: The "
        "id_short must contain only letters, digits underscore and hyphen "
        "(Constraint AASd-002) >>> {'id': 'urn:x:bad', 'idShort': 'Bad "
        "idShort!', 'modelType': 'Submodel'}"
    )
    followup = (
        "Expected a Submodel in list 'submodels', but found {'modelType': "
        "'Submodel', 'id': 'urn:x:bad', 'idShort': 'Bad idShort!'}. "
        "Skipping it..."
    )

    report = build_report([error(cause, ""), error(followup, "")])

    (issue,) = report.issues
    assert issue.scope is Scope.OBJECT
    assert issue.location == "id urn:x:bad"
    assert "AASd-002" in issue.reason
    # Both records are kept in the text.
    assert cause in issue.text
    assert followup in issue.text


def test_json_records_of_different_objects_are_not_merged() -> None:
    first = (
        "Error while trying to convert JSON object into Property: 'valueType'"
        " >>> {'idShort': 'NoType', 'modelType': 'Property'}"
    )
    second = (
        "Expected a SubmodelElement in Submodel[urn:x:s2], but found "
        "{'modelType': 'Property', 'idShort': 'Other'}"
    )

    report = build_report([error(first, ""), error(second, "")])

    assert len(report.issues) == 2


def test_a_json_detail_without_a_followup_stays_a_detail() -> None:
    message = (
        "Error while trying to convert JSON object into "
        "MultiLanguageTextType: 'text' >>> {'language': 'en'}"
    )

    (issue,) = build_report([error(message, "")]).issues

    assert issue.scope is Scope.DETAIL
    assert issue.subject == "multi language text type"


def test_an_object_in_an_earlier_part_is_described_with_both_parts() -> None:
    issue = duplicate_in_other_part(
        "Submodel", "urn:x:sm1", "/aasx/second.xml", "/aasx/first.xml"
    )

    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.OBJECT
    assert issue.location == "id urn:x:sm1"
    assert issue.part == "/aasx/second.xml"
    assert "/aasx/first.xml" in issue.reason


def test_the_summary_counts_by_scope_and_names_the_kinds_of_objects() -> None:
    report = build_report(
        [
            error(SUBMODEL_LOST),
            error(DUPLICATE, ""),
            error(DUPLICATE.replace("ExecutedProcesses", "Other"), ""),
            error(NESTED),
        ]
    )

    summary = report.summary()

    assert summary == (
        "Left out: 3 objects (2 concept descriptions, 1 submodel) and 1 detail."
    )


def test_the_summary_says_when_messages_could_not_be_classified() -> None:
    report = build_report([error("what is this"), error(SUBMODEL_LOST)])

    assert "1 message of the SDK could not be classified" in report.summary()


def test_the_text_to_copy_has_every_issue_and_every_line_of_the_sdk() -> None:
    report = build_report([error(SUBMODEL_LOST), error(NESTED)])

    text = report.text()

    assert text.startswith(report.summary())
    assert "1. Left out submodel (line 33, /aasx/data/data.aas.xml)" in text
    assert "2. Left out embedded data specification" in text
    for record in (SUBMODEL_LOST, NESTED):
        for line in record.splitlines():
            assert f"SDK: {line}" in text


def test_the_biggest_losses_come_first_and_the_unknown_last() -> None:
    report = build_report(
        [
            error(NESTED),
            error("what is this"),
            error(SUBMODEL_LOST),
            error(DUPLICATE, ""),
        ]
    )

    ordered = [issue.scope for issue in report.by_weight()]

    assert ordered == [
        Scope.OBJECT,
        Scope.OBJECT,
        Scope.DETAIL,
        Scope.OTHER,
    ]
    assert report.by_weight()[-1].outcome is Outcome.UNKNOWN
    assert report.text().splitlines()[2].startswith("1. Left out submodel")


def test_an_empty_report_is_false_and_says_nothing() -> None:
    report = LoadReport()

    assert not report
    assert report.summary() == ""
    assert report.text() == ""


@pytest.mark.parametrize(
    "records",
    [
        [error(SUBMODEL_LOST), error(NESTED), error(DUPLICATE, "")],
        [warning("Something new")],
    ],
)
def test_a_report_survives_being_written_as_data(
    records: list[RawRecord],
) -> None:
    report = build_report(records)

    assert LoadReport.from_data(report.to_data()) == report
