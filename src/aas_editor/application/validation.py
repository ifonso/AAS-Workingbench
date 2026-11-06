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
rules use, so `SaveGate` lists those blockers once, from `check_save`, which
also knows the target format.

Example:
    Asking before a save::

        gate = SaveGate()
        outcome = save(source, target, options, writer, ask, gate.check)
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.application.save import MAX_LISTED
from aas_editor.application.save import SaveCheck
from aas_editor.application.save import SaveIssue
from aas_editor.application.save import SaveOptions
from aas_editor.application.save import SaveSource
from aas_editor.application.save import check_save
from aas_editor.domain.validation import ALL_RULES
from aas_editor.domain.validation import HINT_RULES
from aas_editor.domain.validation import RULE_FAILED
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Rule
from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import ValidationReport
from aas_editor.domain.validation import validate
from aas_editor.domain.validation.rules.files import FILE_IN_ANNOTATION
from aas_editor.domain.validation.rules.files import MISSING_FILE

# The blockers that `check_save` makes too, knowing the target format. The
# rules report them for the dock, and the save gate leaves them out.
SAVE_CHECK_RULES = frozenset({MISSING_FILE, FILE_IN_ANNOTATION})

_HINT_IDS = frozenset(rule.rule_id for rule in HINT_RULES)

FindingKey = tuple[str, str, str]


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


def validate_package(
    source: ValidationSource,
    with_hints: bool = False,
    tolerant: bool = True,
) -> ValidationReport:
    """Checks a package against all rules.

    Args:
        source: The package.
        with_hints: Also run the hint rules of hints mode. Their findings are
            in the report, and `package_findings` takes them out again.
        tolerant: A rule that raises becomes a warning of the rule
            `EDT-RULE-FAILED` and is logged, instead of an exception. The
            dock and the save gate need this, because a defect in one rule
            must not stop the user from looking at the others or from saving.

    Returns:
        The findings, errors first. The cost is linear in the size of the
        package, about 45 ms for the largest bundled template.
    """
    rules = (*ALL_RULES, *HINT_RULES) if with_hints else ALL_RULES
    return validate(
        source.objects,
        stored_files=source.files,
        rules=rules,
        tolerant=tolerant,
    )


def is_hint(finding: Finding) -> bool:
    """Tells whether a finding comes from a hint rule and not a package rule."""
    return finding.rule_id in _HINT_IDS


def package_findings(report: ValidationReport) -> ValidationReport:
    """Takes the hints out of a report, which leaves the package check."""
    return ValidationReport(tuple(f for f in report.findings if not is_hint(f)))


def hints_for(report: ValidationReport, target: object) -> tuple[Finding, ...]:
    """Selects the findings to show with an object in hints mode.

    Args:
        report: A report made with hints.
        target: The shell, submodel, description or element that is shown.

    Returns:
        The findings whose anchor is the object, most severe first. A rule
        that raised belongs to the package and not to an object, and it is
        listed for every object, so that a defect of a hint is seen where
        the hints are (F-EDT-01 AC14).
    """
    return tuple(
        f
        for f in report.findings
        if f.anchor is target or f.rule_id == RULE_FAILED
    )


@dataclass(frozen=True)
class FindingCounts:
    """How many findings a report has, by what the user can do about them.

    Errors and warnings are findings of the rules of the specification, and
    the Validation panel lists them. Hints come from the hint rules, or have
    the severity of a notice. They are advice, show next to their object, and
    the panel does not list them, whatever severity a hint rule gives them.

    Attributes:
        errors: The errors of the rules.
        warnings: The warnings of the rules.
        hints: Every other finding of the report.
    """

    errors: int = 0
    warnings: int = 0
    hints: int = 0

    @property
    def findings(self) -> int:
        """The errors and warnings together, which the panel lists."""
        return self.errors + self.warnings


def is_listed(finding: Finding) -> bool:
    """Tells whether the Validation panel lists a finding.

    Args:
        finding: A finding of a report that was made with hints.

    Returns:
        True for an error or a warning of the rules, and False for a hint.
    """
    return not is_hint(finding) and finding.severity is not Severity.INFO


def count_findings(report: ValidationReport) -> FindingCounts:
    """Counts the errors, warnings, and hints of a report.

    Args:
        report: A report, made with or without hints.

    Returns:
        The counts. The warnings are those of the rules, so they match the
        panel, and a hint that a hint rule gives the severity of a warning is
        a hint.
    """
    listed = tuple(f for f in report.findings if is_listed(f))
    errors = sum(1 for f in listed if f.severity is Severity.ERROR)
    warnings = len(listed) - errors
    return FindingCounts(errors, warnings, len(report.findings) - len(listed))


def count_text(count: int, noun: str) -> str:
    """Words a count with its noun, such as `1 error` and `2 errors`."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def stepping_findings(report: ValidationReport) -> tuple[Finding, ...]:
    """Selects the findings that F8 goes through: errors, then warnings."""
    return tuple(f for f in report.findings if is_listed(f))


def step_finding(
    findings: Sequence[Finding], after: FindingKey | None, forward: bool
) -> int | None:
    """Finds which finding F8 or Shift+F8 goes to.

    Args:
        findings: The findings to go through, in order.
        after: The key of the finding that the user was at, or None. A run
            makes new objects, so the finding is known by its key.
        forward: True for the next finding, False for the previous one.

    Returns:
        The index in `findings`, wrapping at both ends. When the user was at
        no finding, or the finding is gone, the first one going forward and
        the last one going back. None if there is no finding.
    """
    if not findings:
        return None
    position = next(
        (i for i, f in enumerate(findings) if finding_key(f) == after), None
    )
    if position is None:
        return 0 if forward else len(findings) - 1
    return (position + (1 if forward else -1)) % len(findings)


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


def finding_key(finding: Finding) -> FindingKey:
    """Names a finding by what the user sees, to know it again after edits."""
    return (finding.rule_id, finding.location, finding.message)


class SaveGate:
    """The checks of a save: lost content and the errors of the rules (D5).

    A package that breaks a rule is asked about once. After the user chose
    Save anyway, the same errors do not ask again on the next save, because
    six bundled templates have 120 one-letter idShorts, and a user who saves
    often would confirm the same list over and over. An error that is new, or
    that changed, asks again. Content that a save drops (D7) is asked about on
    every save, because it depends on the target.

    Use one gate for each package.
    """

    def __init__(self, rules: Iterable[Rule] = ALL_RULES) -> None:
        """Makes a gate that has not been told about any error yet.

        Args:
            rules: The rules to check on a save. All rules by default.
        """
        self._rules = tuple(rules)
        self._acknowledged: set[FindingKey] = set()
        self._asked: tuple[Finding, ...] = ()

    def check(
        self, source: SaveSource, target: Path, options: SaveOptions
    ) -> SaveCheck:
        """Finds what stops a save, and what the user has to confirm.

        The blockers are those of `check_save`, plus those of a blocking rule
        that `check_save` does not know. The warnings are what the save drops,
        followed by the errors of the rules that the user has not confirmed.

        Args:
            source: The content to save.
            target: The file to save to.
            options: The settings that change the output.

        Returns:
            The merged check.

        Raises:
            TypeError: If the extension of the target is not supported.
        """
        saving = check_save(source, target, options)
        report = validate(
            source.objects,
            stored_files=source.files,
            rules=self._rules,
            tolerant=True,
        )
        findings = tuple(
            f
            for f in report.findings
            if f.rule_id not in SAVE_CHECK_RULES
            and finding_key(f) not in self._acknowledged
        )
        rules = save_check_for(ValidationReport(findings))
        self._asked = tuple(
            f
            for f in findings
            if f.severity is Severity.ERROR and not f.blocks_save
        )
        return SaveCheck(
            saving.blockers + rules.blockers,
            saving.warnings + rules.warnings,
        )

    def confirm(
        self, check: SaveCheck, ask: Callable[[SaveCheck], bool]
    ) -> bool:
        """Asks the user, and remembers the errors when the answer is yes.

        Args:
            check: The result of `check`.
            ask: Shows the check, and returns True to save anyway.

        Returns:
            The answer.
        """
        confirmed = ask(check)
        if confirmed:
            self._acknowledged.update(finding_key(f) for f in self._asked)
        return confirmed


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
