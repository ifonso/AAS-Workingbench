"""Validation rules over BaSyx objects (ADR 0005).

The SDK enforces only part of the constraints of metamodel V3.1, and mostly
when an object is made or added. This package finds the rest, on the objects
as they are after edits, pastes and lenient reading. It has no Qt and does not
change anything.

Example:
    Checking a package and listing what stops a save::

        report = validate(package.objStore, stored_files=package.fileStore)
        for finding in report.errors:
            print(finding.rule_id, finding.location, finding.message)

`coverage.COVERAGE` says, for each constraint of the specification, whether
the SDK enforces it, a rule here does, or neither.
"""

from aas_workingbench.domain.validation.engine import RULE_FAILED
from aas_workingbench.domain.validation.engine import validate
from aas_workingbench.domain.validation.findings import Finding
from aas_workingbench.domain.validation.findings import Severity
from aas_workingbench.domain.validation.findings import ValidationReport
from aas_workingbench.domain.validation.rule import Rule
from aas_workingbench.domain.validation.rules import ALL_RULES
from aas_workingbench.domain.validation.rules import HINT_RULES

__all__ = [
    "ALL_RULES",
    "HINT_RULES",
    "RULE_FAILED",
    "Finding",
    "Rule",
    "Severity",
    "ValidationReport",
    "validate",
]
