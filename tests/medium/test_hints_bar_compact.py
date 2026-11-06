"""The hints bar is compact: several hints share one line, errors stay whole."""

from basyx.aas import model

from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Severity
from aas_editor.ui.hints_bar import hint_details
from aas_editor.ui.hints_bar import hint_lines


def _finding(rule_id: str, severity: Severity) -> Finding:
    return Finding(rule_id, severity, f"Message of {rule_id}.", object())


def test_two_hints_share_one_line_that_names_their_rules() -> None:
    findings = (
        _finding("EDT-HINT-DISPLAY-NAME-MISSING", Severity.INFO),
        _finding("EDT-HINT-DESCRIPTION-MISSING", Severity.INFO),
    )

    lines = hint_lines(findings)

    assert len(lines) == 1
    assert lines[0].startswith("2 hints about EDT-HINT-DISPLAY-NAME-MISSING, ")
    assert "EDT-HINT-DESCRIPTION-MISSING" in lines[0]


def test_one_hint_keeps_its_whole_sentence() -> None:
    findings = (_finding("EDT-HINT-CATEGORY", Severity.INFO),)

    assert hint_lines(findings) == [
        "Hint: Message of EDT-HINT-CATEGORY. (EDT-HINT-CATEGORY)"
    ]


def test_errors_and_warnings_stay_whole_next_to_the_shared_line() -> None:
    findings = (
        _finding("AASd-002", Severity.ERROR),
        _finding("EDT-WARN", Severity.WARNING),
        _finding("EDT-HINT-A", Severity.INFO),
        _finding("EDT-HINT-B", Severity.INFO),
        _finding("EDT-HINT-C", Severity.INFO),
    )

    lines = hint_lines(findings)

    assert lines[0] == "Error: Message of AASd-002. (AASd-002)"
    assert lines[1] == "Warning: Message of EDT-WARN. (EDT-WARN)"
    assert lines[2].startswith(
        "3 hints about EDT-HINT-A, EDT-HINT-B, EDT-HINT-C"
    )
    assert len(lines) == 3


def test_the_tooltip_has_every_finding_in_full() -> None:
    findings = (
        _finding("EDT-HINT-A", Severity.INFO),
        _finding("EDT-HINT-B", Severity.INFO),
    )

    details = hint_details(findings).splitlines()

    assert details == [
        "Hint: Message of EDT-HINT-A. (EDT-HINT-A)",
        "Hint: Message of EDT-HINT-B. (EDT-HINT-B)",
    ]


def test_the_shared_line_names_the_attributes_as_the_metamodel_does() -> None:
    subject = model.Property("Pump", model.datatypes.String)
    findings = (
        Finding(
            "EDT-HINT-A", Severity.INFO, "a", subject, subject, "display_name"
        ),
        Finding(
            "EDT-HINT-B", Severity.INFO, "b", subject, subject, "description"
        ),
    )

    (line,) = hint_lines(findings)

    assert "displayName, description" in line
    assert "EDT-HINT" not in line
