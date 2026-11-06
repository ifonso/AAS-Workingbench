"""Validates a package for the dock and for the save gate (decision D5).

The rules are in `aas_editor.domain.validation`. This module gives them what
the application has: a package that offers its objects and files, and the
words of a save check. It does not decide when to validate, and it does not
show anything.

The mapping to a save check follows D5. A finding that leaves no Save anyway
(`blocks_save`) becomes a blocker. Any other error becomes a warning, which the
user may confirm. Warnings and hints of the rules stay in the report and never
stop a save. The save flow of `application.save` already refuses a File with no
stored file and a File under an annotation, with the same functions that the
rules use, so a caller that merges both lists the blockers once.

Example:
    Asking before a save::

        report = validate_package(source)
        check = save_check_for(report)
        if check.blockers:
            refuse(check.blockers)
        elif check.warnings and not confirm(check.warnings):
            cancel()
"""

from typing import Protocol

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.application.save import MAX_LISTED
from aas_editor.application.save import SaveCheck
from aas_editor.application.save import SaveIssue
from aas_editor.domain.validation import ALL_RULES
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import ValidationReport
from aas_editor.domain.validation import validate


class ValidationSource(Protocol):
    """What validation needs to know about a package.

    `application.save.SaveSource` and the legacy `Package.save_source()`
    result offer this too.
    """

    @property
    def objects(
        self,
    ) -> model.AbstractObjectStore[model.Identifier, model.Identifiable]:
        """The shells, submodels, and concept descriptions."""
        ...

    @property
    def files(self) -> AbstractSupplementaryFileContainer:
        """The supplementary files stored in the package."""
        ...


def validate_package(source: ValidationSource) -> ValidationReport:
    """Checks a package against all rules.

    Args:
        source: The package.

    Returns:
        The findings, errors first. The cost is linear in the size of the
        package, about 45 ms for the largest bundled template.
    """
    return validate(source.objects, stored_files=source.files)


def save_check_for(report: ValidationReport) -> SaveCheck:
    """Turns the findings of a validation into the issues of a save (D5).

    Args:
        report: The result of `validate_package`.

    Returns:
        The blockers (findings with `blocks_save`) and, as warnings, the other
        errors, which the user may confirm. Each rule is one issue, with the
        location and message of its findings as details. Warnings and hints
        of the report are not part of the check.
    """
    titles = {rule.rule_id: rule.title for rule in ALL_RULES}
    blockers = _issues(report.blocking, titles)
    confirmable = tuple(f for f in report.errors if not f.blocks_save)
    return SaveCheck(blockers, _issues(confirmable, titles))


def _issues(
    findings: tuple[Finding, ...], titles: dict[str, str]
) -> tuple[SaveIssue, ...]:
    groups: dict[str, list[Finding]] = {}
    for finding in findings:
        groups.setdefault(finding.rule_id, []).append(finding)
    return tuple(
        SaveIssue(
            f"{group[0].rule_id}: {titles.get(rule_id, rule_id)} "
            f"({len(group)} found)",
            _details(group),
        )
        for rule_id, group in groups.items()
    )


def _details(group: list[Finding]) -> tuple[str, ...]:
    listed = [f"{f.location}: {f.message}" for f in group[:MAX_LISTED]]
    if len(group) > MAX_LISTED:
        listed.append(f"... and {len(group) - MAX_LISTED} more")
    return tuple(listed)
