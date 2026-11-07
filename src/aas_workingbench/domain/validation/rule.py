"""The shape of a rule, and the helper that rules use to report."""

from collections.abc import Callable
from collections.abc import Iterator
from dataclasses import dataclass

from aas_workingbench.domain.validation.context import ValidationContext
from aas_workingbench.domain.validation.findings import Finding

RuleCheck = Callable[[ValidationContext], Iterator[Finding]]


@dataclass(frozen=True)
class Rule:
    """One check over the objects of a package.

    Attributes:
        rule_id: `AASd-nnn` for a constraint of the specification, or
            `EDT-...` for a rule of the editor.
        title: What the rule checks, in a few words.
        source: Where the rule comes from: the constraint with its part of the
            specification, or the reason for an editor rule.
        check: Yields a finding for each violation. It must walk the package
            at most once, so that a run stays linear.
    """

    rule_id: str
    title: str
    source: str
    check: RuleCheck
