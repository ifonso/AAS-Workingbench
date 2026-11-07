"""The kinds of hints: names, the set that is off, and the groups of a report."""

from basyx.aas import model
from tests.factories import make_property

from aas_editor.application.hints import HINT_KIND_NAMES
from aas_editor.application.hints import HintKinds
from aas_editor.application.hints import group_hints
from aas_editor.application.hints import hint_count_here
from aas_editor.application.hints import hint_kind_name
from aas_editor.application.hints import hint_kind_tip
from aas_editor.application.hints import hints_here_text
from aas_editor.application.hints import hints_shown
from aas_editor.domain.validation import HINT_RULES
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import ValidationReport
from aas_editor.domain.validation.rules import hints as hint_rules


def _finding(
    rule_id: str, severity: Severity, element: model.Referable
) -> Finding:
    return Finding(rule_id, severity, "m", element, element)


def test_every_hint_rule_has_a_name_in_words() -> None:
    ids = {rule.rule_id for rule in HINT_RULES}

    assert set(HINT_KIND_NAMES) == ids
    assert all(not name.startswith("EDT-") for name in HINT_KIND_NAMES.values())


def test_the_names_of_the_kinds_differ() -> None:
    assert len(set(HINT_KIND_NAMES.values())) == len(HINT_KIND_NAMES)


def test_the_names_of_the_commonest_kinds_are_the_ones_users_read() -> None:
    assert hint_kind_name(hint_rules.DESCRIPTION_MISSING) == (
        "Missing description"
    )
    assert hint_kind_name(hint_rules.DISPLAY_NAME_MISSING) == (
        "Missing display name"
    )
    assert hint_kind_name(hint_rules.DESCRIPTION_ONE_LANGUAGE) == (
        "Description in one language"
    )


def test_a_kind_that_is_not_known_is_named_by_its_rule() -> None:
    assert hint_kind_name("EDT-HINT-FUTURE") == "EDT-HINT-FUTURE"
    assert hint_kind_tip("EDT-HINT-FUTURE") == "EDT-HINT-FUTURE"


def test_the_tip_of_a_kind_says_what_its_rule_looks_for() -> None:
    tip = hint_kind_tip(hint_rules.DESCRIPTION_MISSING)

    assert tip.startswith("A Referable has a description.")


def test_every_kind_is_on_at_first() -> None:
    kinds = HintKinds()

    assert kinds.off == frozenset()
    assert not kinds.is_off(hint_rules.DESCRIPTION_MISSING)


def test_a_kind_is_turned_off_and_on_and_the_subscribers_are_told() -> None:
    kinds = HintKinds()
    told: list[frozenset[str]] = []
    subscription = kinds.subscribe(lambda: told.append(kinds.off))

    kinds.set_off(hint_rules.DESCRIPTION_MISSING, True)
    kinds.set_off(hint_rules.DESCRIPTION_MISSING, True)
    kinds.set_off(hint_rules.DESCRIPTION_MISSING, False)

    assert told == [frozenset({hint_rules.DESCRIPTION_MISSING}), frozenset()]
    subscription.cancel()
    kinds.set_off(hint_rules.COPY_NAME, True)
    assert len(told) == 2


def test_loading_replaces_the_set() -> None:
    kinds = HintKinds({hint_rules.COPY_NAME})

    kinds.load([hint_rules.DESCRIPTION_MISSING])

    assert kinds.off == frozenset({hint_rules.DESCRIPTION_MISSING})


def test_a_kind_that_is_off_is_left_out_of_the_hints_of_an_object() -> None:
    element = make_property("Pump")
    findings = (
        _finding("AASd-002", Severity.ERROR, element),
        _finding(hint_rules.DESCRIPTION_MISSING, Severity.INFO, element),
        _finding(hint_rules.DISPLAY_NAME_MISSING, Severity.INFO, element),
    )
    kinds = HintKinds({hint_rules.DESCRIPTION_MISSING})

    shown = hints_shown(findings, kinds)

    assert [f.rule_id for f in shown] == [
        "AASd-002",
        hint_rules.DISPLAY_NAME_MISSING,
    ]
    assert hint_count_here(findings, kinds) == 1
    assert hint_count_here(findings, HintKinds()) == 2


def test_a_hint_rule_that_gives_a_warning_is_still_a_hint() -> None:
    element = make_property("Pump")
    warning = _finding(hint_rules.COPY_NAME, Severity.WARNING, element)

    assert hint_count_here((warning,), HintKinds()) == 1
    assert hint_count_here((warning,), HintKinds({hint_rules.COPY_NAME})) == 0


def test_the_count_here_is_worded_for_one_and_for_many() -> None:
    assert hints_here_text(1) == "1 hint here"
    assert hints_here_text(3) == "3 hints here"


def test_hints_are_grouped_by_kind_largest_first_without_the_findings() -> None:
    first, second = make_property("A"), make_property("B")
    report = ValidationReport.of(
        [
            _finding(hint_rules.DESCRIPTION_MISSING, Severity.INFO, first),
            _finding(hint_rules.DESCRIPTION_MISSING, Severity.INFO, second),
            _finding(hint_rules.COPY_NAME, Severity.WARNING, first),
            _finding("AASd-002", Severity.ERROR, first),
            _finding("EDT-DANGLING-REFERENCE", Severity.WARNING, second),
        ]
    )

    groups = group_hints(report)

    assert [(g.name, g.count) for g in groups] == [
        ("Missing description", 2),
        ("Name made by a copy", 1),
    ]
    assert [f.anchor for f in groups[0].findings] == [first, second]


def test_kinds_with_the_same_count_are_ordered_by_name() -> None:
    element = make_property("A")
    report = ValidationReport.of(
        [
            _finding(hint_rules.DISPLAY_NAME_MISSING, Severity.INFO, element),
            _finding(hint_rules.DESCRIPTION_MISSING, Severity.INFO, element),
        ]
    )

    assert [g.name for g in group_hints(report)] == [
        "Missing description",
        "Missing display name",
    ]


def test_a_report_without_hints_has_no_group() -> None:
    assert group_hints(ValidationReport()) == ()
