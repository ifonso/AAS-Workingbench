"""The global switch for hints (F-EDT-06), and the kinds of hints.

In hints mode the editor shows advice next to the object that it is about, and
under the fields of the dialogs that make one. The advice comes from the
validation rules and the hint rules, and it never blocks anything: a value that
a hint complains about stays in the model and can be saved. The mode is on at
first, as in Package Explorer.

A hint belongs to a kind, which is the rule that found it. Almost every element
has a few of them (no display name, no description), and a template leaves them
out on purpose, so a person can turn a kind off. `HintKinds` says which kinds
are off. The Validation panel groups the hints of a package by kind
(`group_hints`), and the status bar and the bar above a tab count only the
kinds that are on.
"""

from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from aas_workingbench.application.listeners import Listeners
from aas_workingbench.application.listeners import Subscription
from aas_workingbench.application.validation import count_text
from aas_workingbench.application.validation import is_listed
from aas_workingbench.domain.validation import HINT_RULES
from aas_workingbench.domain.validation import Finding
from aas_workingbench.domain.validation import ValidationReport
from aas_workingbench.domain.validation.rules import hints as hint_rules

HINT_KIND_NAMES: Final = {
    hint_rules.KEY_WHITESPACE: "Whitespace in a semantic id key",
    hint_rules.CATEGORY_DEPRECATED: "Deprecated category",
    hint_rules.COPY_NAME: "Name made by a copy",
    hint_rules.ASSET_ID_EMPTY: "Missing global asset id",
    hint_rules.ASSET_ID_DUPLICATE: "Duplicate global asset id",
    hint_rules.NO_DATA_SPECIFICATION: "No data specification",
    hint_rules.ENTITY_GLOBAL_ID: "Entity without global asset id",
    hint_rules.DISPLAY_NAME_MISSING: "Missing display name",
    hint_rules.DISPLAY_NAME_ONE_LANGUAGE: "Display name in one language",
    hint_rules.DESCRIPTION_MISSING: "Missing description",
    hint_rules.DESCRIPTION_ONE_LANGUAGE: "Description in one language",
}
"""What the user reads for each hint rule, in a few words. A test keeps it in
step with `HINT_RULES`."""


def hint_kind_name(rule_id: str) -> str:
    """Gives the words for a kind of hint, or the rule id for an unknown one."""
    return HINT_KIND_NAMES.get(rule_id, rule_id)


def hint_kind_tip(rule_id: str) -> str:
    """Says what a kind of hint looks for, in the words of its rule."""
    for rule in HINT_RULES:
        if rule.rule_id == rule_id:
            return f"{rule.title}. {rule.source}"
    return rule_id


class HintsMode:
    """Tells whether hints are shown, and who wants to know."""

    def __init__(self) -> None:
        self._on = True
        self._listeners: Listeners[[bool]] = Listeners()

    @property
    def is_on(self) -> bool:
        """True if hints are shown."""
        return self._on

    def set_on(self, on: bool) -> None:
        """Switches hints on or off, and tells the subscribers if it changed.

        Args:
            on: True to show hints.
        """
        if on == self._on:
            return
        self._on = on
        self._listeners.notify(on)

    def subscribe(self, listener: Callable[[bool], None]) -> Subscription:
        """Registers a callback for every change of the mode.

        Args:
            listener: Called with the new value of `is_on`. A bound method is
                held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)


_hints_mode = HintsMode()


def hints_mode() -> HintsMode:
    """Returns the one switch of the application."""
    return _hints_mode


class HintKinds:
    """Tells which kinds of hints are turned off, and who wants to know.

    A kind is the id of a hint rule. The set is the user's, so it is not in the
    package: the same kinds stay off for every package, and across sessions
    when the window keeps them in the settings.
    """

    def __init__(self, off: Iterable[str] = ()) -> None:
        self._off = frozenset(off)
        self._listeners: Listeners[[]] = Listeners()

    @property
    def off(self) -> frozenset[str]:
        """The ids of the kinds that are turned off."""
        return self._off

    def is_off(self, rule_id: str) -> bool:
        """Tells whether the hints of a kind are left out."""
        return rule_id in self._off

    def set_off(self, rule_id: str, off: bool) -> None:
        """Turns a kind off or on, and tells the subscribers if it changed.

        Args:
            rule_id: The id of the hint rule.
            off: True to leave the kind out.
        """
        self.load(self._off | {rule_id} if off else self._off - {rule_id})

    def load(self, off: Iterable[str]) -> None:
        """Replaces the set, and tells the subscribers if it changed.

        Args:
            off: The ids of the kinds that are off.
        """
        wanted = frozenset(off)
        if wanted != self._off:
            self._off = wanted
            self._listeners.notify()

    def subscribe(self, listener: Callable[[], None]) -> Subscription:
        """Registers a callback for every change of the set.

        Args:
            listener: Called with no argument. A bound method is held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)


_hint_kinds = HintKinds()


def hint_kinds() -> HintKinds:
    """Returns the one set of the application."""
    return _hint_kinds


def hints_shown(
    findings: Iterable[Finding], kinds: HintKinds | None = None
) -> tuple[Finding, ...]:
    """Takes out the hints of the kinds that are off.

    Args:
        findings: The findings about one object, as `hints_for` gives them.
        kinds: The kinds that are off. The set of the application by default.

    Returns:
        The errors and warnings, and the hints of the kinds that are on.
    """
    off = (_hint_kinds if kinds is None else kinds).off
    return tuple(f for f in findings if is_listed(f) or f.rule_id not in off)


def hint_count_here(
    findings: Iterable[Finding], kinds: HintKinds | None = None
) -> int:
    """Counts the hints among the findings about one object.

    Args:
        findings: The findings about one object, as `hints_for` gives them.
        kinds: The kinds that are off. The set of the application by default.

    Returns:
        The hints of the kinds that are on. Errors and warnings are not hints.
    """
    return sum(1 for f in hints_shown(findings, kinds) if not is_listed(f))


def hints_here_text(count: int) -> str:
    """Words the count of hints about the current object."""
    return f"{count_text(count, 'hint')} here"


@dataclass(frozen=True)
class HintGroup:
    """The hints of one kind in a package.

    Attributes:
        rule_id: The hint rule that found them.
        findings: The hints, in the order of the package.
    """

    rule_id: str
    findings: tuple[Finding, ...]

    @property
    def name(self) -> str:
        """What the user reads for the kind."""
        return hint_kind_name(self.rule_id)

    @property
    def count(self) -> int:
        """How many hints of the kind the package has."""
        return len(self.findings)


def group_hints(report: ValidationReport) -> tuple[HintGroup, ...]:
    """Groups the hints of a report by kind.

    Args:
        report: A report made with hints.

    Returns:
        One group for each kind that has a hint, the largest first and then by
        name. Errors and warnings of the rules are not in a group. A kind that
        is turned off is still a group, so that it can be turned on again.
    """
    by_rule: dict[str, list[Finding]] = {}
    for finding in report.findings:
        if not is_listed(finding):
            by_rule.setdefault(finding.rule_id, []).append(finding)
    groups = (HintGroup(rule, tuple(found)) for rule, found in by_rule.items())
    return tuple(sorted(groups, key=lambda g: (-g.count, g.name)))
