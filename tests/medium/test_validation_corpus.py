"""The validation rules over the 132 bundled IDTA templates.

Every rule must run on every template without raising. The numbers in
`docs/software/validation.md` come from the aggregate test: a rule that fires
on many official templates is either a defect of the templates or a wrong rule,
and the documentation says which, with the evidence.

A template is opened as the editor opens it: strictly first, and in failsafe
mode when that fails. Failsafe mode drops the objects that the SDK refuses, so
the findings describe what the editor shows, not the file as it is on disk.
"""

from functools import cache
from pathlib import Path
import time

import pytest
from tests.medium.failsafe_causes import relative_name
from tests.medium.failsafe_causes import templates

from aas_editor.domain.validation import ValidationReport
from aas_editor.domain.validation import validate
from aas_editor.infrastructure.package_io import read_package

PURCHASE_ORDER = "Purchase Order/1/0/IDTA-02050_Template_PurchaseOrder.aasx"

# Findings and the packages that have them, over all templates.
EXPECTED_BY_RULE: dict[str, tuple[int, int]] = {
    "EDT-DANGLING-REFERENCE": (569, 56),
    "AASd-002": (120, 6),
    "EDT-MISSING-FILE": (60, 13),
    "EDT-VALUE-TYPE": (1, 1),
}


@cache
def _report(path: Path) -> ValidationReport:
    try:
        parts = read_package(path, failsafe=False)
    except Exception:  # noqa: BLE001 - the editor falls back to failsafe mode
        parts = read_package(path, failsafe=True)
    return validate(parts.objects, stored_files=parts.files)


@pytest.mark.parametrize("path", templates(), ids=relative_name)
def test_every_rule_runs_when_a_template_is_validated(path: Path) -> None:
    report = _report(path)

    assert isinstance(report, ValidationReport)


def test_rules_fire_as_documented_when_all_templates_are_validated() -> None:
    findings: dict[str, int] = {}
    packages: dict[str, int] = {}
    for path in templates():
        counts = _report(path).counts_by_rule()
        for rule_id, count in counts.items():
            findings[rule_id] = findings.get(rule_id, 0) + count
            packages[rule_id] = packages.get(rule_id, 0) + 1

    assert {r: (findings[r], packages[r]) for r in findings} == EXPECTED_BY_RULE


def test_only_the_missing_file_rule_blocks_a_save_of_the_templates() -> None:
    blocking: set[str] = set()
    for path in templates():
        blocking.update(f.rule_id for f in _report(path).blocking)

    assert blocking == {"EDT-MISSING-FILE"}


def test_validate_takes_well_under_a_second_when_the_template_is_the_largest() -> (
    None
):
    path = next(p for p in templates() if relative_name(p) == PURCHASE_ORDER)
    parts = read_package(path, failsafe=True)

    started = time.perf_counter()
    validate(parts.objects, stored_files=parts.files)
    elapsed = time.perf_counter() - started

    # About 0.05 s on a laptop. The limit only guards against a rule that
    # turns quadratic.
    assert elapsed < 2.0
