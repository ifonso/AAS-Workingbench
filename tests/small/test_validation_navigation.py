"""Counting findings for the status bar, and going through them with F8."""

from basyx.aas import model
import pytest
from tests.factories import make_property

from aas_workingbench.application.validation import FindingCounts
from aas_workingbench.application.validation import count_findings
from aas_workingbench.application.validation import count_text
from aas_workingbench.application.validation import finding_key
from aas_workingbench.application.validation import step_finding
from aas_workingbench.application.validation import stepping_findings
from aas_workingbench.domain.validation import Finding
from aas_workingbench.domain.validation import Severity
from aas_workingbench.domain.validation import ValidationReport
from aas_workingbench.domain.validation.rules.hints import KEY_WHITESPACE


def _finding(severity: Severity, name: str = "A") -> Finding:
    element = make_property(name)
    return Finding(f"RULE-{name}", severity, f"about {name}", element, element)


def _report(*severities: Severity) -> ValidationReport:
    return ValidationReport.of(
        _finding(severity, chr(ord("A") + number))
        for number, severity in enumerate(severities)
    )


def test_findings_are_counted_by_severity() -> None:
    report = _report(
        Severity.INFO,
        Severity.ERROR,
        Severity.WARNING,
        Severity.INFO,
        Severity.INFO,
    )

    assert count_findings(report) == FindingCounts(
        errors=1, warnings=1, hints=3
    )


def test_a_hint_rule_that_gives_a_warning_is_still_a_hint() -> None:
    element = make_property("Pump")
    advice = Finding(KEY_WHITESPACE, Severity.WARNING, "m", element, element)
    rule = _finding(Severity.WARNING, "B")

    counts = count_findings(ValidationReport.of([advice, rule]))

    assert counts == FindingCounts(errors=0, warnings=1, hints=1)


def test_f8_skips_a_hint_rule_that_gives_a_warning() -> None:
    element = make_property("Pump")
    advice = Finding(KEY_WHITESPACE, Severity.WARNING, "m", element, element)

    assert stepping_findings(ValidationReport.of([advice])) == ()


def test_a_clean_report_counts_nothing() -> None:
    assert count_findings(ValidationReport()) == FindingCounts()


def test_the_findings_are_the_errors_and_warnings_but_not_the_hints() -> None:
    counts = count_findings(
        _report(Severity.ERROR, Severity.ERROR, Severity.INFO, Severity.WARNING)
    )

    assert counts.findings == 3


@pytest.mark.parametrize(
    ("count", "text"),
    [(0, "0 errors"), (1, "1 error"), (2, "2 errors")],
)
def test_a_count_takes_the_plural_of_its_noun(count: int, text: str) -> None:
    assert count_text(count, "error") == text


def test_f8_goes_through_errors_then_warnings_and_skips_hints() -> None:
    report = _report(Severity.INFO, Severity.WARNING, Severity.ERROR)

    severities = [f.severity for f in stepping_findings(report)]

    assert severities == [Severity.ERROR, Severity.WARNING]


def test_the_first_step_forward_is_the_first_finding() -> None:
    findings = stepping_findings(_report(Severity.ERROR, Severity.WARNING))

    assert step_finding(findings, None, forward=True) == 0


def test_the_first_step_back_is_the_last_finding() -> None:
    findings = stepping_findings(_report(Severity.ERROR, Severity.WARNING))

    assert step_finding(findings, None, forward=False) == 1


def test_a_step_forward_goes_to_the_finding_after_the_one_at() -> None:
    findings = stepping_findings(
        _report(Severity.ERROR, Severity.ERROR, Severity.WARNING)
    )

    assert step_finding(findings, finding_key(findings[0]), forward=True) == 1


def test_a_step_forward_from_the_last_finding_wraps_to_the_first() -> None:
    findings = stepping_findings(_report(Severity.ERROR, Severity.WARNING))

    assert step_finding(findings, finding_key(findings[1]), forward=True) == 0


def test_a_step_back_from_the_first_finding_wraps_to_the_last() -> None:
    findings = stepping_findings(_report(Severity.ERROR, Severity.WARNING))

    assert step_finding(findings, finding_key(findings[0]), forward=False) == 1


def test_a_finding_that_was_fixed_starts_again_at_the_first() -> None:
    findings = stepping_findings(_report(Severity.ERROR, Severity.WARNING))
    gone = finding_key(_finding(Severity.ERROR, "Fixed"))

    assert step_finding(findings, gone, forward=True) == 0


def test_there_is_no_step_without_findings() -> None:
    assert step_finding((), None, forward=True) is None


def test_the_same_finding_in_a_new_run_is_known_by_its_key() -> None:
    element: model.Referable = make_property("Same")
    first = Finding("R", Severity.ERROR, "m", element, element)
    again = Finding("R", Severity.ERROR, "m", element, element)
    other = _finding(Severity.WARNING, "Other")

    assert step_finding([again, other], finding_key(first), forward=True) == 1
