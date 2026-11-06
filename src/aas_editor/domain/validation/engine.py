"""Runs the rules over the objects of a package."""

from collections.abc import Iterable

from basyx.aas import model

from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import ValidationReport
from aas_editor.domain.validation.rule import Rule
from aas_editor.domain.validation.rules import ALL_RULES


def validate(
    objects: Iterable[model.Identifiable],
    stored_files: Iterable[str] | None = None,
    rules: Iterable[Rule] = ALL_RULES,
) -> ValidationReport:
    """Checks the objects of a package against the rules.

    The cost is linear in the size of the package: the objects are walked
    once for all rules, and each rule goes over the views it needs. A rule
    that raises is a defect in the rule, and the exception is not caught.

    Args:
        objects: The shells, submodels and concept descriptions of the
            package, such as its object store.
        stored_files: The names of the supplementary files in the package, as
            `source.files` lists them. None skips the rules about files, for a
            caller that does not know them.
        rules: The rules to run. All rules by default.

    Returns:
        The findings, errors first. The order within a severity is the order
        of the rules, then the order of the package.
    """
    context = ValidationContext(objects, stored_files)
    return ValidationReport.of(
        finding for rule in rules for finding in rule.check(context)
    )
