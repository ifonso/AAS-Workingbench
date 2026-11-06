"""The validation dock lists the findings of the current package.

The dock reads the report of a service that runs the rules, debounced, after
the package changed. These tests drive the dock and the package tree view the
way the main window connects them, without the main window.
"""

import io

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.domain.validation import Severity
from aas_editor.ui.validation_service import service_for

DISPLAY = Qt.ItemDataRole.DisplayRole


def _dangling(name: str, target: str) -> model.ReferenceElement:
    return model.ReferenceElement(
        name,
        value=model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, target),), model.Submodel
        ),
    )


@pytest.fixture
def make_dock(qapp: object, qtbot: QtBot):
    from aas_editor.ui.validation_dock import ValidationDock

    def make() -> ValidationDock:
        dock = ValidationDock()
        qtbot.addWidget(dock)
        return dock

    return make


@pytest.fixture
def package_with_findings(views):
    """A package with one error and two warnings, in a package tree view."""

    class Shown:
        shown = views()
        error = make_property("X", "1")
        first = _dangling("First", "urn:gone-1")
        second = _dangling("Second", "urn:gone-2")
        submodel = make_submodel(elements=[error, first, second])
        package = shown.open_package(submodel)

    return Shown


def _cell(dock, row: int, column: int) -> str:
    return dock.filter.index(row, column).data(DISPLAY)


# ---------------------------------------------------------------------------
# What the dock lists
# ---------------------------------------------------------------------------


def test_dock_lists_severity_rule_location_and_message(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()

    dock.set_package(package_with_findings.package)

    assert dock.filter.rowCount() == 3
    assert [_cell(dock, 0, column) for column in range(3)] == [
        "Error",
        "AASd-002",
        "Property 'X' of Submodel 'Submodel'",
    ]
    assert "at least two characters" in _cell(dock, 0, 3)
    assert {_cell(dock, row, 0) for row in (1, 2)} == {"Warning"}


def test_dock_lists_errors_before_warnings(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()

    dock.set_package(package_with_findings.package)

    assert [f.severity for f in dock.visible_findings()] == [
        Severity.ERROR,
        Severity.WARNING,
        Severity.WARNING,
    ]


def test_dock_says_no_findings_when_the_package_is_valid(
    make_dock, views
) -> None:
    dock = make_dock()
    package = views().open_package(make_submodel())

    dock.set_package(package)

    assert dock.counts_label.text() == "No findings"
    assert dock.filter.rowCount() == 0


def test_dock_says_no_package_open_when_it_has_no_package(make_dock) -> None:
    dock = make_dock()

    assert dock.counts_label.text() == "No package open"


def test_dock_counts_each_severity(make_dock, package_with_findings) -> None:
    dock = make_dock()

    dock.set_package(package_with_findings.package)

    assert dock.counts_label.text() == "1 errors, 2 warnings"
    assert dock.severity_boxes[Severity.ERROR].text() == "Error (1)"
    assert dock.severity_boxes[Severity.WARNING].text() == "Warning (2)"


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


def test_severity_filter_hides_the_warnings(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)

    dock.severity_boxes[Severity.WARNING].setChecked(False)

    assert [f.rule_id for f in dock.visible_findings()] == ["AASd-002"]
    assert dock.counts_label.text() == "1 errors, 2 warnings. Showing 1 of 3"


def test_severity_filter_shows_the_warnings_again(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)
    dock.severity_boxes[Severity.WARNING].setChecked(False)

    dock.severity_boxes[Severity.WARNING].setChecked(True)

    assert len(dock.visible_findings()) == 3


def test_rule_filter_shows_one_rule(make_dock, package_with_findings) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)

    dock.rule_box.setCurrentIndex(
        dock.rule_box.findData("EDT-DANGLING-REFERENCE")
    )

    assert {f.rule_id for f in dock.visible_findings()} == {
        "EDT-DANGLING-REFERENCE"
    }
    assert len(dock.visible_findings()) == 2


def test_rule_filter_lists_the_rules_with_their_counts(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()

    dock.set_package(package_with_findings.package)

    assert [
        dock.rule_box.itemText(i) for i in range(dock.rule_box.count())
    ] == [
        "All rules",
        "AASd-002 (1)",
        "EDT-DANGLING-REFERENCE (2)",
    ]


def test_both_filters_work_together(make_dock, package_with_findings) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)
    dock.rule_box.setCurrentIndex(
        dock.rule_box.findData("EDT-DANGLING-REFERENCE")
    )

    dock.severity_boxes[Severity.WARNING].setChecked(False)

    assert dock.visible_findings() == []


def test_rule_filter_stays_when_the_report_is_made_again(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)
    dock.rule_box.setCurrentIndex(
        dock.rule_box.findData("EDT-DANGLING-REFERENCE")
    )

    dock.refresh()

    assert dock.rule_box.currentData() == "EDT-DANGLING-REFERENCE"
    assert len(dock.visible_findings()) == 2


# ---------------------------------------------------------------------------
# Refresh after edits and undo, debounced
# ---------------------------------------------------------------------------


def _rename(package, element, id_short: str) -> None:
    package.commandStack.push(
        SetAttribute(observer_for(package), element, "id_short", id_short)
    )


def test_dock_shows_a_new_error_after_an_edit(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    shown = package_with_findings
    other = make_property("Fine")
    shown.submodel.submodel_element.add(other)
    dock = make_dock()
    dock.set_package(shown.package)
    assert len(dock.report.of_rule("AASd-002")) == 1

    _rename(shown.package, other, "Y")

    qtbot.waitUntil(
        lambda: len(dock.report.of_rule("AASd-002")) == 2, timeout=2000
    )


def test_dock_drops_the_error_after_an_undo(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    shown = package_with_findings
    dock = make_dock()
    dock.set_package(shown.package)
    _rename(shown.package, shown.error, "Fixed")
    qtbot.waitUntil(lambda: not dock.report.of_rule("AASd-002"), timeout=2000)

    shown.package.commandStack.undo()

    qtbot.waitUntil(
        lambda: len(dock.report.of_rule("AASd-002")) == 1, timeout=2000
    )


def test_dock_does_not_run_the_rules_while_the_user_types(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    shown = package_with_findings
    dock = make_dock()
    dock.set_package(shown.package)
    runs: list[int] = []
    service_for(shown.package).report_changed.connect(lambda: runs.append(1))

    # Twenty steps in a burst, such as a paste or a bulk delete.
    for number in range(20):
        _rename(shown.package, shown.first, f"Name{number:02}")

    assert runs == []
    qtbot.waitUntil(lambda: runs == [1], timeout=2000)
    qtbot.wait(400)
    assert runs == [1]


def test_hidden_dock_does_not_run_the_rules(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    shown = package_with_findings
    dock = make_dock()
    dock.set_package(shown.package)
    dock.set_active(False)
    runs: list[int] = []
    service_for(shown.package).report_changed.connect(lambda: runs.append(1))

    _rename(shown.package, shown.error, "Fixed")
    qtbot.wait(400)

    assert runs == []
    assert len(dock.report.of_rule("AASd-002")) == 1


def test_dock_catches_up_when_it_shows_again(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    shown = package_with_findings
    dock = make_dock()
    dock.set_package(shown.package)
    dock.set_active(False)
    _rename(shown.package, shown.error, "Fixed")

    dock.set_active(True)

    assert dock.report.of_rule("AASd-002") == ()


# ---------------------------------------------------------------------------
# Opening a finding
# ---------------------------------------------------------------------------


def test_double_click_gives_the_finding_of_the_row(
    make_dock, package_with_findings, qtbot: QtBot
) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)
    opened = []
    dock.finding_activated.connect(opened.append)

    dock.findings_table.doubleClicked.emit(dock.filter.index(0, 2))

    assert [f.rule_id for f in opened] == ["AASd-002"]
    assert opened[0].anchor is package_with_findings.error


def test_double_click_gives_the_finding_of_the_filtered_row(
    make_dock, package_with_findings
) -> None:
    dock = make_dock()
    dock.set_package(package_with_findings.package)
    dock.severity_boxes[Severity.ERROR].setChecked(False)
    opened = []
    dock.finding_activated.connect(opened.append)

    dock.findings_table.doubleClicked.emit(dock.filter.index(1, 0))

    assert opened[0].rule_id == "EDT-DANGLING-REFERENCE"


@pytest.fixture
def window(qtbot: QtBot, views):
    """A window with the package tree, and the dock connected to it."""
    from aas_editor.ui.validation_window import install_validation

    shown = views()
    main = QMainWindow()
    qtbot.addWidget(main)
    main.mainTreeView = shown.view  # type: ignore[attr-defined]
    main.packTreeModel = shown.table  # type: ignore[attr-defined]
    controller = install_validation(main)
    controller.dock.set_active(True)

    class Window:
        controller_ = controller
        dock = controller.dock
        views_ = shown

    return Window


def test_double_click_selects_the_element_in_the_package_tree(
    window,
) -> None:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    error = make_property("X", "1")
    package = window.views_.open_package(make_submodel(elements=[error]))
    window.views_.select(window.views_.index(package=0))
    assert window.dock.package is package
    window.views_.view.collapseAll()

    window.dock.activate_row(0)

    current = window.views_.view.currentIndex()
    assert current.data(OBJECT_ROLE) is error


def test_double_click_on_a_package_finding_selects_the_package(
    window,
) -> None:
    from aas_editor.settings.app_settings import PACKAGE_ROLE

    submodel = make_submodel(elements=[make_file_element("Manual", "/a/b.pdf")])
    package = window.views_.open_package(submodel)
    package.fileStore.add_file(
        "/a/unused.pdf", io.BytesIO(b"x"), "application/pdf"
    )
    window.views_.select(window.views_.index("submodels", "Submodel"))
    window.dock.refresh()
    package_findings = [
        f for f in window.dock.report.findings if f.anchor is None
    ]
    assert [f.rule_id for f in package_findings] == ["EDT-UNREFERENCED-FILE"]

    window.controller_.go_to(package_findings[0])

    current = window.views_.view.currentIndex()
    assert current.parent() == QModelIndex()
    assert current.data(PACKAGE_ROLE) is package


# ---------------------------------------------------------------------------
# One package at a time
# ---------------------------------------------------------------------------


def test_dock_follows_the_package_of_the_current_row(window) -> None:
    first = window.views_.open_package(
        make_submodel("urn:a", "First", [make_property("X", "1")])
    )
    second = window.views_.open_package(make_submodel("urn:b", "Second"))

    window.views_.select(window.views_.index(package=0))
    shown_first = window.dock.package
    window.views_.select(window.views_.index(package=1))
    shown_second = window.dock.package

    assert shown_first is first
    assert shown_second is second
    assert window.dock.visible_findings() == []


def test_dock_clears_when_its_package_is_closed(window) -> None:
    package = window.views_.open_package(
        make_submodel(elements=[make_property("X", "1")])
    )
    window.views_.select(window.views_.index(package=0))
    assert window.dock.filter.rowCount() == 1

    window.views_.view.closeFile(window.views_.index(package=0))

    assert window.dock.package is None
    assert window.dock.filter.rowCount() == 0
    assert window.dock.counts_label.text() == "No package open"
    del package


def test_dock_shows_the_remaining_package_when_one_is_closed(window) -> None:
    window.views_.open_package(
        make_submodel("urn:a", "First", [make_property("X", "1")])
    )
    second = window.views_.open_package(
        make_submodel("urn:b", "Second", [make_property("Y", "1")])
    )
    window.views_.select(window.views_.index(package=0))

    window.views_.view.closeFile(window.views_.index(package=0))

    assert window.dock.package is second
    assert len(window.dock.visible_findings()) == 1
