"""The load report against the 132 bundled templates.

A template that only opens in failsafe mode must say what was left out, and
one that opens strictly must say nothing. The report is checked against a
count that does not use the log: the `idShort` entries in the XML of the file
against those of the objects that were read. For each template the entries that
are missing are exactly those in the subtrees that the report names. A report
that said less would hide a loss, and one that said more would invent one.
"""

from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from tests.medium.failsafe_causes import relative_name
from tests.medium.failsafe_causes import strict_cause
from tests.medium.failsafe_causes import templates
from tests.medium.load_report_measure import measure
from tests.medium.load_report_measure import Measure

from aas_editor.domain.load_report import LoadReport
from aas_editor.domain.load_report import Scope
from aas_editor.infrastructure.package_io import read_package

NAMES = [relative_name(path) for path in templates()]
FAILSAFE_COUNT = 49


@dataclass(frozen=True)
class Opened:
    """A template opened the way the editor opens it."""

    needs_failsafe: bool
    partial: bool
    report: LoadReport
    measured: Measure


@cache
def _open(path: Path) -> Opened:
    needs_failsafe = strict_cause(path) is not None
    parts = read_package(path, failsafe=needs_failsafe)
    return Opened(
        needs_failsafe,
        parts.partial,
        parts.load_report,
        measure(path, parts.objects, parts.load_report),
    )


def _failsafe_templates() -> list[Opened]:
    return [o for o in map(_open, templates()) if o.needs_failsafe]


@pytest.mark.parametrize("path", templates(), ids=NAMES)
def test_a_template_reports_what_was_left_out_only_when_it_needed_failsafe(
    path: Path,
) -> None:
    opened = _open(path)

    assert bool(opened.report) is opened.needs_failsafe
    assert opened.partial is opened.needs_failsafe


@pytest.mark.parametrize("path", templates(), ids=NAMES)
def test_the_missing_id_shorts_are_those_the_report_names(path: Path) -> None:
    opened = _open(path)

    assert opened.measured.unplaced == []
    assert opened.measured.shortfall == opened.measured.explained


def test_forty_nine_templates_need_failsafe_and_all_of_them_report() -> None:
    needing = _failsafe_templates()

    assert len(needing) == FAILSAFE_COUNT
    assert all(opened.report.left_out for opened in needing)


def test_no_record_of_the_corpus_is_unclassified_or_a_remark() -> None:
    reports = [opened.report for opened in _failsafe_templates()]

    assert sum(len(report.unknown) for report in reports) == 0
    assert sum(len(report.kept) for report in reports) == 0


def test_what_the_corpus_loses_by_scope() -> None:
    reports = [opened.report for opened in _failsafe_templates()]

    found = Counter[Scope]()
    for report in reports:
        for scope in Scope:
            found[scope] += report.count(scope)

    assert {scope: count for scope, count in found.items() if count} == {
        Scope.OBJECT: 91,
        Scope.ELEMENT: 26,
        Scope.DETAIL: 83,
    }


def test_the_objects_the_corpus_loses_are_mostly_concept_descriptions() -> None:
    kinds = Counter(
        issue.subject
        for opened in _failsafe_templates()
        for issue in opened.report.left_out_objects
    )

    assert kinds == {
        "concept description": 87,
        "submodel": 3,
        "asset administration shell": 1,
    }


def test_forty_five_templates_load_fewer_id_shorts_than_their_file_has() -> (
    None
):
    shorter = [o for o in _failsafe_templates() if o.measured.shortfall > 0]

    assert len(shorter) == 45
    # The others lose only details, which are texts, references, and
    # qualifiers and have no idShort, or a shell that has none.
    unchanged = [o for o in _failsafe_templates() if o.measured.shortfall == 0]
    only_details = [
        o
        for o in unchanged
        if not o.report.count(Scope.OBJECT)
        and not o.report.count(Scope.ELEMENT)
    ]
    assert len(only_details) == 3
    assert len(unchanged) == 4
