"""Runs the rules over the objects of a package."""

from collections.abc import Iterable
import logging

from basyx.aas import model

from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.findings import ValidationReport
from aas_editor.domain.validation.rule import Rule
from aas_editor.domain.validation.rules import ALL_RULES

RULE_FAILED = "EDT-RULE-FAILED"

_logger = logging.getLogger(__name__)


def validate(
    objects: Iterable[model.Identifiable],
    stored_files: Iterable[str] | None = None,
    rules: Iterable[Rule] = ALL_RULES,
    tolerant: bool = False,
) -> ValidationReport:
    """Checks the objects of a package against the rules.

    The cost is linear in the size of the package: the objects are walked
    once for all rules, and each rule goes over the views it needs.

    Args:
        objects: The shells, submodels and concept descriptions of the
            package, such as its object store.
        stored_files: The names of the supplementary files in the package, as
            `source.files` lists them. None skips the rules about files, for a
            caller that does not know them.
        rules: The rules to run. All rules by default.
        tolerant: What to do with a rule that raises, which is a defect in the
            rule. False lets the exception through, so that tests find it.
            True logs it and reports a warning with the rule `EDT-RULE-FAILED`
            instead, keeping what the rule found before it failed. The save
            gate and the dock use this, so that a defect in one rule never
            stops the user from saving or from seeing the other findings.

    Returns:
        The findings, errors first. The order within a severity is the order
        of the rules, then the order of the package.
    """
    context = ValidationContext(objects, stored_files)
    findings: list[Finding] = []
    for rule in rules:
        if tolerant:
            findings.extend(_check_tolerantly(rule, context))
        else:
            findings.extend(rule.check(context))
    return ValidationReport.of(findings)


def _check_tolerantly(rule: Rule, context: ValidationContext) -> list[Finding]:
    found: list[Finding] = []
    try:
        found.extend(rule.check(context))
    except Exception as error:  # noqa: BLE001 - any defect of a rule
        _logger.exception("Rule %s failed", rule.rule_id)
        found.append(
            Finding(
                RULE_FAILED,
                Severity.WARNING,
                f"The rule {rule.rule_id} ({rule.title}) could not run: "
                f"{type(error).__name__}: {error}. Its findings are missing",
                rule,
            )
        )
    return found
