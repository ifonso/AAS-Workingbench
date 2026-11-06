"""What a validation finds: findings, their severity, and the report.

A finding names the rule that fired, the object that breaks it, a sentence for
the user, and whether the SDK can still write the package. The report is the
list of findings of one run, with the counts that a dock or a save dialog
needs.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import enum

from basyx.aas import model

from aas_editor.domain.references import describe_object


class Severity(enum.Enum):
    """How serious a finding is.

    The order of the members is the order of the sort: errors first.
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        """Position in the sort order, with errors at 0."""
        return list(Severity).index(self)


@dataclass(frozen=True, eq=False)
class Finding:
    """One violation of a rule.

    Attributes:
        rule_id: The constraint, such as `AASd-020`, or an editor rule such as
            `EDT-DUPLICATE-ID`.
        severity: An error breaks a "shall" of the specification, or makes the
            package unreadable or unwritable. A warning is legal but probably
            wrong. Info is a hint.
        message: A sentence for the user. It names the attribute and the
            value, not the object, because the location says that.
        subject: The object that breaks the rule. It can be a part of an
            element, such as a `Qualifier` or a `SpecificAssetId`, or a file
            name for a file that nothing refers to.
        anchor: The shell, submodel, concept description or element to go to
            when the user opens the finding, or None if the finding belongs to
            the package as a whole.
        attribute: The attribute of the subject that holds the problem, if
            there is one.
        blocks_save: True if the SDK cannot write the package as an AASX file
            while the finding exists, so that D5 offers no Save anyway.
    """

    rule_id: str
    severity: Severity
    message: str
    subject: object
    anchor: model.Referable | None = None
    attribute: str | None = None
    blocks_save: bool = False

    @property
    def location(self) -> str:
        """Where the finding is, as a short text such as `Property 'Pump'`."""
        if self.anchor is None:
            return "Package"
        return describe_object(self.anchor)


@dataclass(frozen=True)
class ValidationReport:
    """The findings of one validation run, sorted by severity.

    Attributes:
        findings: Every finding, errors first, then in the order of the
            package.
    """

    findings: tuple[Finding, ...] = ()

    @classmethod
    def of(cls, findings: Iterable[Finding]) -> "ValidationReport":
        """Makes a report, sorting by severity and keeping the document order.

        Args:
            findings: The findings in document order.

        Returns:
            The sorted report.
        """
        return cls(tuple(sorted(findings, key=lambda f: f.severity.rank)))

    @property
    def errors(self) -> tuple[Finding, ...]:
        """The findings with severity error."""
        return self.with_severity(Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        """The findings with severity warning."""
        return self.with_severity(Severity.WARNING)

    @property
    def blocking(self) -> tuple[Finding, ...]:
        """The findings that leave no Save anyway (D5)."""
        return tuple(f for f in self.findings if f.blocks_save)

    @property
    def is_clean(self) -> bool:
        """True if there is no finding at all."""
        return not self.findings

    def with_severity(self, severity: Severity) -> tuple[Finding, ...]:
        """Selects the findings of one severity."""
        return tuple(f for f in self.findings if f.severity is severity)

    def of_rule(self, rule_id: str) -> tuple[Finding, ...]:
        """Selects the findings of one rule."""
        return tuple(f for f in self.findings if f.rule_id == rule_id)

    def counts_by_rule(self) -> dict[str, int]:
        """Counts the findings of each rule, most frequent first."""
        return dict(Counter(f.rule_id for f in self.findings).most_common())
