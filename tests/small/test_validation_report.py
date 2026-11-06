"""The report, the engine, and the table of constraint coverage."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_valid_environment
from tests.validation_factories import store_with

from aas_editor.domain.validation import ALL_RULES
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Rule
from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import ValidationReport
from aas_editor.domain.validation import validate
from aas_editor.domain.validation.coverage import COVERAGE
from aas_editor.domain.validation.coverage import EDITOR_RULE_REASONS
from aas_editor.domain.validation.coverage import ConstraintCoverage
from aas_editor.domain.validation.coverage import Enforcement
from aas_editor.domain.validation.coverage import known_rule_ids
from aas_editor.domain.validation.coverage import rules_for


def _finding(rule_id: str, severity: Severity, blocks: bool = False) -> Finding:
    return Finding(rule_id, severity, "message", "subject", None, None, blocks)


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def test_report_lists_errors_first_when_findings_have_mixed_severities() -> (
    None
):
    info = _finding("A", Severity.INFO)
    warning = _finding("B", Severity.WARNING)
    error = _finding("C", Severity.ERROR)

    report = ValidationReport.of([info, warning, error])

    assert report.findings == (error, warning, info)


def test_report_keeps_the_document_order_when_severities_are_equal() -> None:
    first = _finding("A", Severity.ERROR)
    second = _finding("B", Severity.ERROR)

    report = ValidationReport.of([first, second])

    assert report.findings == (first, second)


def test_report_selects_by_severity_rule_and_blocking() -> None:
    blocking = _finding("EDT-MISSING-FILE", Severity.ERROR, True)
    error = _finding("AASd-002", Severity.ERROR)
    warning = _finding("EDT-DANGLING-REFERENCE", Severity.WARNING)

    report = ValidationReport.of([warning, error, blocking])

    assert report.errors == (error, blocking)
    assert report.warnings == (warning,)
    assert report.blocking == (blocking,)
    assert report.of_rule("AASd-002") == (error,)
    assert not report.is_clean


def test_report_counts_findings_of_each_rule_when_a_rule_fires_twice() -> None:
    report = ValidationReport.of(
        [
            _finding("AASd-002", Severity.ERROR),
            _finding("EDT-DANGLING-REFERENCE", Severity.WARNING),
            _finding("AASd-002", Severity.ERROR),
        ]
    )

    assert report.counts_by_rule() == {
        "AASd-002": 2,
        "EDT-DANGLING-REFERENCE": 1,
    }


def test_report_is_clean_when_it_has_no_findings() -> None:
    assert ValidationReport().is_clean


def test_finding_location_names_the_package_when_it_has_no_anchor() -> None:
    assert _finding("A", Severity.INFO).location == "Package"


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


def test_validate_finds_nothing_when_the_environment_is_valid() -> None:
    report = validate(make_valid_environment(), stored_files=[])

    assert report.is_clean


def test_validate_runs_only_the_given_rules_when_a_subset_is_passed() -> None:
    store = store_with(make_property("X", "1"), make_file_element("Manual"))
    only_id_short = tuple(r for r in ALL_RULES if r.rule_id == "AASd-002")

    report = validate(store, stored_files=[], rules=only_id_short)

    assert report.counts_by_rule() == {"AASd-002": 1}


def test_validate_combines_the_findings_of_all_rules() -> None:
    prop = model.Property(
        "X",
        model.datatypes.String,
        supplemental_semantic_id=[make_external_reference("urn:extra")],
    )
    store = store_with(prop, make_file_element("Manual"))

    report = validate(store, stored_files=[])

    assert report.counts_by_rule() == {
        "AASd-002": 1,
        "AASd-118": 1,
        "EDT-MISSING-FILE": 1,
    }


def test_validate_finds_a_shell_that_references_a_missing_submodel() -> None:
    shell = make_shell()
    shell.submodel.add(
        model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),), model.Submodel
        )
    )

    report = validate(make_store(shell))

    assert report.counts_by_rule() == {"EDT-DANGLING-REFERENCE": 1}


# ---------------------------------------------------------------------------
# The coverage table
# ---------------------------------------------------------------------------


def test_every_rule_has_a_unique_id() -> None:
    ids = [rule.rule_id for rule in ALL_RULES]

    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("rule", ALL_RULES, ids=lambda rule: rule.rule_id)
def test_every_rule_names_its_source_and_title(rule: Rule) -> None:
    assert rule.title
    assert rule.source


def test_every_constraint_rule_is_in_the_coverage_table() -> None:
    constraint_rules = {
        rule.rule_id for rule in ALL_RULES if rule.rule_id.startswith("AASd-")
    }
    listed = {
        rule_id
        for entry in COVERAGE
        if entry.enforcement in (Enforcement.RULE, Enforcement.PARTIAL)
        for rule_id in entry.rule_ids
        if rule_id.startswith("AASd-")
    }

    assert constraint_rules == listed


def test_every_rule_in_the_coverage_table_exists() -> None:
    listed = {rule_id for entry in COVERAGE for rule_id in entry.rule_ids}

    assert listed <= known_rule_ids()


def test_every_editor_rule_has_a_reason() -> None:
    editor_rules = {
        rule.rule_id for rule in ALL_RULES if rule.rule_id.startswith("EDT-")
    }

    assert editor_rules == set(EDITOR_RULE_REASONS)


@pytest.mark.parametrize("entry", COVERAGE, ids=lambda entry: entry.constraint)
def test_a_constraint_has_rules_exactly_when_the_editor_checks_it(
    entry: ConstraintCoverage,
) -> None:
    checked = entry.enforcement in (Enforcement.RULE, Enforcement.PARTIAL)

    assert bool(entry.rule_ids) is checked


def test_coverage_lists_each_constraint_once() -> None:
    names = [entry.constraint for entry in COVERAGE]

    assert len(names) == len(set(names))


def test_rules_for_returns_the_rules_of_a_constraint() -> None:
    assert rules_for("AASd-020") == ("AASd-020", "EDT-VALUE-TYPE")
    assert rules_for("AASd-014") == ()
    assert rules_for("AASd-999") == ()


def test_coverage_marks_the_constraints_that_v31_does_not_have() -> None:
    not_in_v31 = {
        entry.constraint
        for entry in COVERAGE
        if entry.enforcement is Enforcement.NOT_V31
    }

    assert not_in_v31 == {"AASd-013", "AASd-137", "AASd-138"}
