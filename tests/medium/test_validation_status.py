"""Validation at a glance: counts in the status bar, F8, and links to findings.

The counts keep the report up to date while the Validation panel is hidden
(ADR 0029). These tests drive the controller with the package tree view, the way
the main window connects them, without the main window.
"""

import logging
import time

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMainWindow
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.edits import SetAttribute
from aas_workingbench.application.hints import hints_mode
from aas_workingbench.domain.validation import Severity
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui import validation_service
from aas_workingbench.ui.validation_service import ValidationService
from aas_workingbench.ui.validation_service import service_for


def _dangling(name: str, target: str) -> model.ReferenceElement:
    return model.ReferenceElement(
        name,
        value=model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, target),), model.Submodel
        ),
    )


@pytest.fixture
def window(qtbot: QtBot, views):
    """A window with the package tree and the validation controller."""
    from aas_workingbench.ui.validation_window import install_validation

    shown = views()
    main = QMainWindow()
    qtbot.addWidget(main)
    main.mainTreeView = shown.view  # type: ignore[attr-defined]
    main.packTreeModel = shown.table  # type: ignore[attr-defined]
    controller = install_validation(main)

    class Window:
        main_ = main
        controller_ = controller
        dock = controller.dock
        status = controller.status
        views_ = shown

        @staticmethod
        def open(*elements: model.SubmodelElement) -> object:
            package = shown.open_package(make_submodel(elements=elements))
            shown.select(
                shown.index(package=len(shown.table.openedPacks()) - 1)
            )
            return package

        @staticmethod
        def current_object() -> object:
            return shown.view.currentIndex().data(OBJECT_ROLE)

        @staticmethod
        def select_element(element: model.SubmodelElement) -> None:
            shown.select(shown.index("submodels", "Submodel", element.id_short))

    return Window


def _rename(package: object, element: model.Referable, name: str) -> None:
    package.commandStack.push(  # type: ignore[attr-defined]
        SetAttribute(observer_for(package), element, "id_short", name)
    )


# ---------------------------------------------------------------------------
# The counts
# ---------------------------------------------------------------------------


def test_the_counts_are_there_while_the_panel_is_hidden(window) -> None:
    error = make_property("X", "1")
    window.open(
        error, _dangling("First", "urn:a"), _dangling("Second", "urn:b")
    )

    assert not window.dock.isVisible()
    assert window.status.findings_button.text() == "1 error, 2 warnings"


def test_the_counts_follow_an_edit_while_the_panel_is_hidden(
    window, qtbot: QtBot
) -> None:
    error = make_property("X", "1")
    package = window.open(error)
    assert window.status.findings_button.text() == "1 error, 0 warnings"

    _rename(package, error, "Fixed")

    qtbot.waitUntil(
        lambda: window.status.findings_button.text() == "0 errors, 0 warnings",
        timeout=2000,
    )


def test_one_error_is_not_plural(window) -> None:
    window.open(make_property("X", "1"))

    assert window.status.findings_button.text().startswith("1 error,")


def test_hints_are_counted_apart_from_the_findings(window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    window.open(element)
    window.select_element(element)

    counts = window.status.counts

    assert (counts.errors, counts.warnings) == (0, 0)
    assert window.status.hints_button.text() == "3 hints here"
    assert "hint" not in window.status.findings_button.text()


def test_the_status_bar_has_no_count_for_the_whole_package(window) -> None:
    window.open(make_property("Pump"))

    # The submodel and the property each lack a display name and a description,
    # but the package row is current, so there is nothing to say "here".
    assert window.status.hints_button.isHidden()
    assert "hints" not in window.status.findings_button.text()
    assert window.dock.hints_view.shown_count == 4


def test_the_counts_say_which_kind_a_hint_is(window) -> None:
    window.open(make_property("Pump"))

    findings_tip = window.status.findings_button.toolTip()
    hints_tip = window.status.hints_button.toolTip()

    assert "Validation panel" in findings_tip
    assert "not rules" in hints_tip and "whole package" in hints_tip


def test_hints_are_left_out_while_hints_mode_is_off(window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    window.open(element)
    window.select_element(element)
    assert not window.status.hints_button.isHidden()

    hints_mode().set_on(False)

    assert window.status.hints_button.isHidden()
    assert window.status.hints_here == 0


def test_hints_come_back_with_hints_mode(window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    window.open(element)
    window.select_element(element)
    hints_mode().set_on(False)

    hints_mode().set_on(True)

    assert not window.status.hints_button.isHidden()
    assert window.status.hints_here == 3


def test_hints_mode_does_not_fail_in_a_window_that_was_deleted(
    views, caplog: pytest.LogCaptureFixture
) -> None:
    from PyQt6 import sip

    from aas_workingbench.ui.validation_window import install_validation

    shown = views()
    main = QMainWindow()
    main.mainTreeView = shown.view  # type: ignore[attr-defined]
    main.packTreeModel = shown.table  # type: ignore[attr-defined]
    controller = install_validation(main)
    # The Python objects outlive the window, as the objects of a test do.
    sip.delete(main)
    assert sip.isdeleted(controller.hints_action)

    with caplog.at_level(logging.ERROR):
        hints_mode().set_on(False)
        hints_mode().set_on(True)

    assert "Listener failed" not in caplog.text


def test_the_counts_are_hidden_without_a_package(window) -> None:
    window.open(make_property("X", "1"))
    assert not window.status.isHidden()

    window.views_.view.closeFile(window.views_.index(package=0))

    assert window.status.isHidden()


def test_the_counts_follow_the_package_of_the_current_row(window) -> None:
    window.open(make_property("X", "1"))
    window.open(_dangling("Only", "urn:a"))
    window.views_.select(window.views_.index(package=0))
    first = window.status.findings_button.text()
    window.views_.select(window.views_.index(package=1))
    second = window.status.findings_button.text()

    assert (first, second) == ("1 error, 0 warnings", "0 errors, 1 warning")


def test_the_state_of_the_counts_is_the_worst_finding(window) -> None:
    window.open(make_property("X", "1"))
    error = window.status.findings_button.property("state")
    window.open(_dangling("Only", "urn:a"))
    warning = window.status.findings_button.property("state")
    window.open(make_property("Fine", "x" * 3))
    clean = window.status.findings_button.property("state")

    assert (error, warning, clean) == ("error", "warning", "ok")


def test_a_click_on_the_counts_shows_the_panel(window, qtbot: QtBot) -> None:
    window.open(make_property("X", "1"))
    window.main_.show()
    assert not window.dock.isVisible()

    QTest.mouseClick(window.status.findings_button, Qt.MouseButton.LeftButton)

    assert window.dock.isVisible()


def test_the_list_of_findings_says_where_the_hints_are(window) -> None:
    window.open(make_property("Pump"))

    note = window.dock.note_label.text()

    assert "not rules" in note
    assert "not in this list" in note
    assert "Hints view" in note


# ---------------------------------------------------------------------------
# The cost of running while the panel is hidden
# ---------------------------------------------------------------------------


class _Slow:
    """A package whose rules take a set time, to see how the wait follows."""

    def save_source(self) -> object:
        return object()


@pytest.mark.parametrize(
    ("seconds", "wait_at_least"), [(0.0, 250), (0.12, 600)]
)
def test_the_wait_after_a_change_grows_with_the_cost_of_a_run(
    qapp: object,
    monkeypatch: pytest.MonkeyPatch,
    seconds: float,
    wait_at_least: int,
) -> None:
    from aas_workingbench.domain.validation import ValidationReport

    def slow(source: object, with_hints: bool = False) -> ValidationReport:
        time.sleep(seconds)
        return ValidationReport()

    monkeypatch.setattr(validation_service, "validate_package", slow)
    package = _Slow()
    service = ValidationService(package)
    service.listen(object())

    assert service.wait_ms >= wait_at_least
    assert service._timer.interval() == service.wait_ms


def test_a_cheap_run_keeps_the_usual_wait(window, qtbot: QtBot) -> None:
    window.open(make_property("X", "1"))

    service = service_for(window.dock.package)

    assert service.wait_ms == validation_service.DEBOUNCE_MS


# ---------------------------------------------------------------------------
# F8 and Shift+F8
# ---------------------------------------------------------------------------


def _two_problems(
    window,
) -> tuple[object, model.Property, model.ReferenceElement]:
    error = make_property("X", "1")
    warning = _dangling("Dangling", "urn:gone")
    package = window.open(error, warning)
    return package, error, warning


def test_f8_goes_to_the_first_error(window) -> None:
    _, error, _ = _two_problems(window)

    finding = window.controller_.step(forward=True)

    assert finding is not None and finding.severity is Severity.ERROR
    assert window.current_object() is error


def test_f8_again_goes_to_the_warning(window) -> None:
    _, _, warning = _two_problems(window)
    window.controller_.step(forward=True)

    window.controller_.step(forward=True)

    assert window.current_object() is warning


def test_f8_wraps_around_to_the_first_finding(window) -> None:
    _, error, _ = _two_problems(window)
    for _ in range(3):
        window.controller_.step(forward=True)

    assert window.current_object() is error


def test_shift_f8_goes_back_from_the_start_to_the_last_finding(window) -> None:
    _, _, warning = _two_problems(window)

    window.controller_.step(forward=False)

    assert window.current_object() is warning


def test_shift_f8_goes_back_one_finding(window) -> None:
    _, error, _ = _two_problems(window)
    window.controller_.step(forward=True)
    window.controller_.step(forward=True)

    window.controller_.step(forward=False)

    assert window.current_object() is error


def test_f8_says_which_finding_it_went_to(window) -> None:
    _two_problems(window)

    window.controller_.step(forward=True)

    message = window.main_.statusBar().currentMessage()
    assert message.startswith("Error 1 of 2: AASd-002")


def test_f8_says_so_when_there_is_nothing_to_go_to(window) -> None:
    window.open(make_property("Fine", "text"))

    finding = window.controller_.step(forward=True)

    assert finding is None
    assert window.main_.statusBar().currentMessage() == "No errors or warnings"


def test_f8_selects_the_finding_in_the_panel_when_it_is_open(window) -> None:
    _two_problems(window)
    window.main_.show()
    window.dock.show()

    finding = window.controller_.step(forward=True)

    selected = window.dock.findings_table.selectionModel().selectedRows()
    assert [
        window.dock.filter.index(i.row(), 0).data(Qt.ItemDataRole.UserRole)
        for i in selected
    ] == [finding]


def test_f8_does_not_go_to_a_hint(window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    window.open(element)

    finding = window.controller_.step(forward=True)

    assert finding is None


def test_f8_and_shift_f8_are_the_keys_of_the_actions(window) -> None:
    from PyQt6.QtGui import QKeySequence

    assert window.controller_.next_finding_action.shortcut() == QKeySequence(
        "F8"
    )
    assert window.controller_.previous_finding_action.shortcut() == (
        QKeySequence("Shift+F8")
    )


def test_f8_is_not_bound_to_another_action(window) -> None:
    from PyQt6.QtGui import QAction
    from PyQt6.QtGui import QKeySequence

    owners = [
        action
        for action in window.main_.findChildren(QAction)
        if QKeySequence("F8") in action.shortcuts()
    ]

    assert owners == [window.controller_.next_finding_action]


# ---------------------------------------------------------------------------
# The panel opens at a finding
# ---------------------------------------------------------------------------


def test_reveal_selects_the_finding_in_the_table(window) -> None:
    _two_problems(window)
    finding = window.dock.report.errors[0]

    assert window.dock.reveal(finding)

    row = window.dock.findings_table.currentIndex().row()
    assert window.dock.visible_findings()[row] is finding


def test_reveal_clears_a_filter_that_hides_the_finding(window) -> None:
    _two_problems(window)
    window.dock.severity_boxes[Severity.ERROR].setChecked(False)
    finding = window.dock.report.errors[0]
    assert finding not in window.dock.visible_findings()

    window.dock.reveal(finding)

    assert finding in window.dock.visible_findings()
    assert window.dock.severity_boxes[Severity.ERROR].isChecked()


def test_reveal_knows_a_finding_again_after_a_new_run(window) -> None:
    package, error, _ = _two_problems(window)
    old = window.dock.report.errors[0]
    window.dock.refresh()
    assert window.dock.report.errors[0] is not old

    assert window.dock.reveal(old)


def test_reveal_refuses_a_finding_that_is_not_in_the_report(window) -> None:
    from aas_workingbench.domain.validation import Finding

    _two_problems(window)
    other = make_property("Elsewhere")

    assert not window.dock.reveal(Finding("R", Severity.ERROR, "m", other))


# ---------------------------------------------------------------------------
# The bar of a tab links to the panel
# ---------------------------------------------------------------------------


@pytest.fixture
def bar(qapp: object, qtbot: QtBot):
    from aas_workingbench.ui.hints_bar import HintsBar

    widget = HintsBar()
    qtbot.addWidget(widget)
    return widget


def test_a_bar_with_an_error_links_to_it(bar, window) -> None:
    error = make_property("X", "1")
    package = window.open(error)

    bar.set_target(package, error)

    assert bar.linked is not None and bar.linked.rule_id == "AASd-002"


def test_a_click_on_the_bar_opens_the_finding_in_the_panel(
    bar, window, qtbot: QtBot
) -> None:
    from aas_workingbench.ui.hints_bar import finding_links

    error = make_property("X", "1")
    package = window.open(error)
    bar.set_target(package, error)
    window.main_.show()
    opened: list[object] = []
    finding_links().opened.connect(lambda p, f: opened.append(f))

    QTest.mouseClick(bar, Qt.MouseButton.LeftButton)

    assert opened == [bar.linked]
    assert window.dock.isVisible()
    row = window.dock.findings_table.currentIndex().row()
    assert window.dock.visible_findings()[row] is window.dock.report.errors[0]


def test_a_click_on_the_text_of_the_bar_opens_the_finding_too(
    bar, window
) -> None:
    error = make_property("X", "1")
    package = window.open(error)
    bar.set_target(package, error)
    window.main_.show()
    bar.show()

    QTest.mouseClick(bar.label, Qt.MouseButton.LeftButton)

    assert window.dock.isVisible()


def test_a_bar_that_has_only_hints_links_nowhere(bar, window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    package = window.open(element)

    bar.set_target(package, element)

    assert bar.lines != []
    assert bar.linked is None
    assert bar.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_a_click_on_a_bar_with_only_hints_opens_nothing(bar, window) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    package = window.open(element)
    bar.set_target(package, element)
    window.main_.show()
    bar.show()

    QTest.mouseClick(bar, Qt.MouseButton.LeftButton)

    assert not window.dock.isVisible()


def test_the_tooltip_of_the_bar_says_what_a_hint_is(bar, window) -> None:
    error = make_property("X", "1")
    package = window.open(error)

    bar.set_target(package, error)

    tip = bar.toolTip()
    assert "Hints are advice, not rules" in tip
    assert "Click to open it in the Validation panel." in tip


def test_the_tooltip_of_a_hints_only_bar_has_no_click_to_open(
    bar, window
) -> None:
    element = make_property("Pump")
    element.category = "PARAMETER"
    package = window.open(element)

    bar.set_target(package, element)

    assert "Click to open" not in bar.toolTip()


def test_the_line_for_the_rest_does_not_send_users_to_the_panel() -> None:
    from aas_workingbench.domain.validation import Finding
    from aas_workingbench.ui.hints_bar import hint_lines

    element = make_property("Pump")
    findings = tuple(
        Finding(f"R-{n}", Severity.WARNING, "m", element, element)
        for n in range(8)
    )

    last = hint_lines(findings)[-1]

    assert last == "... and 3 more. Hover to read them"


# ---------------------------------------------------------------------------
# The panel in a narrow strip
# ---------------------------------------------------------------------------


def test_every_header_of_the_panel_fits_in_a_narrow_dock(
    window, qtbot: QtBot
) -> None:
    from aas_workingbench.ui.validation_dock import COLUMNS

    _two_problems(window)
    window.dock.setFloating(True)
    window.dock.resize(480, 300)
    window.dock.show()
    qtbot.waitExposed(window.dock)
    header = window.dock.findings_table.horizontalHeader()
    metrics = header.fontMetrics()

    widths = [header.sectionSize(i) for i in range(len(COLUMNS))]
    needed = [metrics.horizontalAdvance(name) for name in COLUMNS]

    assert all(have >= want for have, want in zip(widths, needed, strict=True))


def test_the_bar_calls_a_hint_a_hint_even_when_its_rule_gives_a_warning(
    bar, window
) -> None:
    element = make_property("Pump")
    element.semantic_id = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:a b"),)
    )
    package = window.open(element)

    bar.set_target(package, element)

    whitespace = [
        line for line in bar.lines if "EDT-HINT-KEY-WHITESPACE" in line
    ]
    assert len(whitespace) == 1 and whitespace[0].startswith("Hint:")
    assert not any(line.startswith("Warning:") for line in bar.lines)
    assert bar.linked is None


def test_a_hint_rule_warning_is_not_counted_with_the_panel_warnings(
    window,
) -> None:
    element = make_property("Pump")
    element.semantic_id = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:a b"),)
    )
    window.open(element)
    window.select_element(element)
    whitespace = [
        f
        for f in window.dock.hint_report.findings
        if f.rule_id == "EDT-HINT-KEY-WHITESPACE"
    ]

    counts = window.status.counts

    assert counts.findings == len(window.dock.report.findings) == 0
    assert len(whitespace) == 1
    assert window.status.hints_here >= 1
