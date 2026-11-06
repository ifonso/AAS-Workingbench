"""Hint rules, the checks of single texts, and a failing rule in the engine."""

from collections.abc import Iterator
import logging

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_valid_environment
from tests.validation_factories import store_with

from aas_editor.domain.validation import ALL_RULES
from aas_editor.domain.validation import HINT_RULES
from aas_editor.domain.validation import RULE_FAILED
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Rule
from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import validate
from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.field_checks import copy_name_problem
from aas_editor.domain.validation.field_checks import global_asset_id_problem
from aas_editor.domain.validation.field_checks import id_short_problem
from aas_editor.domain.validation.field_checks import key_value_problem


def _hints(objects: model.SetIdentifiableStore) -> dict[str, int]:
    return validate(objects, rules=HINT_RULES).counts_by_rule()


# ---------------------------------------------------------------------------
# The hint rules are not package rules
# ---------------------------------------------------------------------------


def test_hint_rules_are_not_part_of_the_package_rules() -> None:
    package_ids = {rule.rule_id for rule in ALL_RULES}
    hint_ids = {rule.rule_id for rule in HINT_RULES}

    assert package_ids.isdisjoint(hint_ids)
    assert all(rule_id.startswith("EDT-HINT-") for rule_id in hint_ids)


def test_a_valid_environment_has_no_hint() -> None:
    assert _hints(make_valid_environment()) == {}


# ---------------------------------------------------------------------------
# Single texts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["Ab", "my_motor", "A1", "a-b_c", "x" * 128])
def test_id_short_problem_is_none_when_the_text_matches_the_pattern(
    text: str,
) -> None:
    assert id_short_problem(text) is None


@pytest.mark.parametrize(
    "text", ["A", "1abc", "my motor!", "trailing-", "", "x" * 129]
)
def test_id_short_problem_says_what_is_required_when_the_text_breaks_it(
    text: str,
) -> None:
    problem = id_short_problem(text)

    assert problem is not None
    assert "at least two characters" in problem


def test_copy_name_problem_is_found_when_the_name_has_three_dashes() -> None:
    assert copy_name_problem("Pump---3") is not None
    assert copy_name_problem("Pump--3") is None


def test_key_value_problem_is_found_when_the_value_has_whitespace() -> None:
    assert key_value_problem("urn:a b") is not None
    assert key_value_problem(" urn:a") is not None
    assert key_value_problem("urn:ab") is None


def test_global_asset_id_problem_is_found_only_when_the_text_is_blank() -> None:
    assert global_asset_id_problem("  ") is not None
    assert global_asset_id_problem("urn:x") is None
    assert global_asset_id_problem(None) is None


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------


def test_key_whitespace_is_a_warning_on_the_element_with_the_semantic_id() -> (
    None
):
    element = make_property("Pump")
    element.semantic_id = make_external_reference("urn:with space")
    store = store_with(element)

    report = validate(store, rules=HINT_RULES)

    (finding,) = report.of_rule("EDT-HINT-KEY-WHITESPACE")
    assert finding.severity is Severity.WARNING
    assert finding.anchor is element
    assert "urn:with space" in finding.message


def test_key_whitespace_looks_at_supplemental_semantic_ids_too() -> None:
    element = make_property("Pump")
    element.semantic_id = make_external_reference("urn:fine")
    element.supplemental_semantic_id.append(make_external_reference("urn:a b"))

    report = validate(store_with(element), rules=HINT_RULES)

    assert len(report.of_rule("EDT-HINT-KEY-WHITESPACE")) == 1


def test_category_is_an_info_hint_when_an_element_has_one() -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"

    report = validate(store_with(element), rules=HINT_RULES)

    (finding,) = report.of_rule("EDT-HINT-CATEGORY")
    assert finding.severity is Severity.INFO
    assert finding.anchor is element


def test_copy_name_is_a_warning_when_an_id_short_has_three_dashes() -> None:
    element = make_property("Pump---1")

    report = validate(store_with(element), rules=HINT_RULES)

    (finding,) = report.of_rule("EDT-HINT-COPY-NAME")
    assert finding.anchor is element


def test_empty_asset_id_is_a_warning_on_the_shell() -> None:
    shell = make_shell(asset_information=make_asset_information(" "))

    report = validate(make_store(shell), rules=HINT_RULES)

    (finding,) = report.of_rule("EDT-HINT-ASSET-ID-EMPTY")
    assert finding.anchor is shell
    assert finding.severity is Severity.WARNING


def test_duplicate_asset_id_is_reported_on_every_shell_that_shares_it() -> None:
    first = make_shell(
        "urn:s1", "One", asset_information=make_asset_information("urn:a")
    )
    second = make_shell(
        "urn:s2", "Two", asset_information=make_asset_information("urn:a")
    )
    third = make_shell(
        "urn:s3", "Three", asset_information=make_asset_information("urn:b")
    )

    report = validate(make_store(first, second, third), rules=HINT_RULES)

    anchors = [f.anchor for f in report.of_rule("EDT-HINT-ASSET-ID-DUPLICATE")]
    assert anchors == [first, second] or anchors == [second, first]


def test_hints_do_not_change_the_package_rules() -> None:
    element = make_property("Pump---1")
    store = store_with(element)

    assert validate(store).of_rule("EDT-HINT-COPY-NAME") == ()


# ---------------------------------------------------------------------------
# A rule that raises
# ---------------------------------------------------------------------------


def _first_then_fails(context: ValidationContext) -> Iterator[Finding]:
    yield Finding("TEST-PARTIAL", Severity.ERROR, "before the defect", "x")
    raise RuntimeError("defect in the rule")


BROKEN = Rule("TEST-BROKEN", "A broken rule", "A test", _first_then_fails)


def test_validate_lets_the_exception_through_when_a_rule_raises() -> None:
    with pytest.raises(RuntimeError, match="defect in the rule"):
        validate(make_valid_environment(), rules=(BROKEN,))


def test_tolerant_validate_reports_a_warning_when_a_rule_raises() -> None:
    report = validate(make_valid_environment(), rules=(BROKEN,), tolerant=True)

    (failed,) = report.of_rule(RULE_FAILED)
    assert failed.severity is Severity.WARNING
    assert not failed.blocks_save
    assert "TEST-BROKEN" in failed.message
    assert "defect in the rule" in failed.message


def test_tolerant_validate_keeps_what_the_rule_found_before_it_raised() -> None:
    report = validate(make_valid_environment(), rules=(BROKEN,), tolerant=True)

    assert [f.message for f in report.of_rule("TEST-PARTIAL")] == [
        "before the defect"
    ]


def test_tolerant_validate_still_runs_the_other_rules(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = store_with(make_property("X", "1"))

    with caplog.at_level(logging.ERROR):
        report = validate(store, rules=(BROKEN, *ALL_RULES), tolerant=True)

    assert len(report.of_rule("AASd-002")) == 1
    assert len(report.of_rule(RULE_FAILED)) == 1
    assert any(
        "TEST-BROKEN" in record.getMessage() for record in caplog.records
    )
