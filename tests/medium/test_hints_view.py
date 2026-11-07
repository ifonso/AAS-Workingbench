"""The hints of the current object, and the Hints view of the Validation panel.

The status bar says how many hints the current object has. The Hints view of
the panel has the hints of the whole package, by kind, and turns a kind off
(ADR 0031). These tests drive the controller with the package tree view, the way
the main window connects them.
"""

from collections import Counter
from pathlib import Path
import shutil

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QMessageBox
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.application.hints import hint_kinds
from aas_workingbench.application.hints import hints_mode
from aas_workingbench.application.validation import is_hint
from aas_workingbench.application.validation import validate_package
from aas_workingbench.domain.validation.rules import hints as hint_rules
from aas_workingbench.settings.app_settings import OBJECT_ROLE

TECHNICAL_DATA = (
    Path(__file__).parents[2]
    / "src"
    / "aas_workingbench"
    / "submodel_templates"
    / "Technical_Data"
    / "1"
    / "2"
    / "1"
    / "IDTA_02003-1-2-1_Template_TechnicalData.aasx"
)


def _make_window(qtbot: QtBot, views):
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
            return shown.open_package(make_submodel(elements=elements))

        @staticmethod
        def open_described(*elements: model.SubmodelElement) -> object:
            """Opens a package in which nothing lacks a name or a description."""
            submodel = _described(make_submodel(elements=elements))
            return shown.open_package(submodel)

        @staticmethod
        def select(*names: str) -> None:
            shown.select(shown.index(*names))

        @staticmethod
        def select_element(element: model.SubmodelElement) -> None:
            shown.select(shown.index("submodels", "Submodel", element.id_short))

        @staticmethod
        def current_object() -> object:
            return shown.view.currentIndex().data(OBJECT_ROLE)

    return Window


@pytest.fixture
def window(qtbot: QtBot, views):
    return _make_window(qtbot, views)


def _described(referable):
    referable.display_name = model.MultiLanguageNameType({"en": "N", "de": "N"})
    referable.description = model.MultiLanguageTextType({"en": "D", "de": "D"})
    return referable


def _group_rows(window) -> dict[str, str]:
    tree = window.dock.hints_view.tree
    return {
        tree.topLevelItem(row).text(0): tree.topLevelItem(row).text(1)
        for row in range(tree.topLevelItemCount())
    }


# ---------------------------------------------------------------------------
# The status bar follows the current object
# ---------------------------------------------------------------------------


def test_the_status_bar_counts_the_hints_of_the_selected_element(
    window,
) -> None:
    plain = make_property("Plain")
    deprecated = make_property("Old")
    deprecated.category = "PARAMETER"
    window.open(plain, deprecated)

    window.select_element(plain)
    plain_text = window.status.hints_button.text()
    window.select_element(deprecated)
    old_text = window.status.hints_button.text()

    assert (plain_text, old_text) == ("2 hints here", "3 hints here")


def test_the_status_bar_says_one_hint_in_the_singular(window) -> None:
    element = _described(make_property("Pump"))
    element.category = "PARAMETER"
    window.open(element)

    window.select_element(element)

    assert window.status.hints_button.text() == "1 hint here"


def test_the_status_bar_says_nothing_for_an_object_without_hints(
    window,
) -> None:
    element = _described(make_property("Pump"))
    window.open(element)

    window.select_element(element)

    assert window.status.hints_button.isHidden()
    assert window.status.hints_here == 0


def test_the_status_bar_follows_the_selection_back_to_an_object_with_hints(
    window,
) -> None:
    clean = _described(make_property("Clean"))
    plain = make_property("Plain")
    window.open(clean, plain)
    window.select_element(plain)
    assert not window.status.hints_button.isHidden()

    window.select_element(clean)
    assert window.status.hints_button.isHidden()
    window.select_element(plain)

    assert window.status.hints_button.text() == "2 hints here"


def test_the_status_bar_counts_the_hints_of_the_submodel_for_the_submodel(
    window,
) -> None:
    window.open(make_property("Plain"))

    window.select("submodels", "Submodel")

    assert window.status.hints_button.text() == "2 hints here"


def test_the_status_bar_counts_an_edit_of_the_current_object(
    window, qtbot: QtBot
) -> None:
    element = make_property("Plain")
    package = window.open(element)
    window.select_element(element)
    assert window.status.hints_button.text() == "2 hints here"

    from aas_workingbench.application.changes import observer_for
    from aas_workingbench.application.edits import SetAttribute

    package.commandStack.push(  # type: ignore[attr-defined]
        SetAttribute(observer_for(package), element, "category", "PARAMETER")
    )

    qtbot.waitUntil(
        lambda: window.status.hints_button.text() == "3 hints here",
        timeout=2000,
    )


def test_a_click_on_the_hints_opens_the_hints_view(
    window, qtbot: QtBot
) -> None:
    element = make_property("Plain")
    window.open(element)
    window.select_element(element)
    window.main_.show()
    assert not window.dock.isVisible()

    QTest.mouseClick(window.status.hints_button, Qt.MouseButton.LeftButton)

    from aas_workingbench.ui.validation_dock import HINTS_VIEW

    assert window.dock.isVisible()
    assert window.dock.current_view == HINTS_VIEW


def test_a_click_on_the_errors_opens_the_list_of_findings(
    window, qtbot: QtBot
) -> None:
    window.open(make_property("X", "1"))
    window.dock.show_hints()
    window.main_.show()

    QTest.mouseClick(window.status.findings_button, Qt.MouseButton.LeftButton)

    from aas_workingbench.ui.validation_dock import FINDINGS_VIEW

    assert window.dock.current_view == FINDINGS_VIEW


def test_the_status_bar_button_has_the_look_of_the_errors_button(
    window,
) -> None:
    from PyQt6.QtWidgets import QToolButton

    assert isinstance(window.status.hints_button, QToolButton)
    assert window.status.findings_button.autoRaise()
    assert window.status.hints_button.autoRaise()
    assert (
        window.status.hints_button.cursor().shape()
        == window.status.findings_button.cursor().shape()
    )


# ---------------------------------------------------------------------------
# The Hints view
# ---------------------------------------------------------------------------


def test_the_hints_view_groups_the_hints_of_a_package_by_kind(window) -> None:
    first = make_property("First")
    second = make_property("Second")
    second.category = "PARAMETER"
    window.open(first, second)

    window.dock.show_hints()

    assert _group_rows(window) == {
        "Missing description": "3",
        "Missing display name": "3",
        "Deprecated category": "1",
    }
    assert window.dock.hints_view.summary_label.text() == "7 hints in 3 kinds"
    assert window.dock.view_bar.tabText(1) == "Hints (7)"


def test_a_group_opens_to_the_elements_that_have_the_hint(window) -> None:
    first = make_property("First")
    second = _described(make_property("Second"))
    second.category = "PARAMETER"
    window.open(first, second)
    window.dock.show_hints()
    view = window.dock.hints_view

    category = view.group_item(hint_rules.CATEGORY_DEPRECATED)
    assert category is not None
    category.setExpanded(True)

    assert category.childCount() == 1
    assert "Second" in category.child(0).text(0)


def test_a_double_click_on_an_element_goes_to_it(window, qtbot: QtBot) -> None:
    first = _described(make_property("First"))
    second = _described(make_property("Second"))
    second.category = "PARAMETER"
    window.open(first, second)
    window.select_element(first)
    window.main_.show()
    window.dock.show_hints()
    qtbot.waitExposed(window.dock)
    view = window.dock.hints_view
    category = view.group_item(hint_rules.CATEGORY_DEPRECATED)
    assert category is not None
    category.setExpanded(True)
    child = category.child(0)
    rect = view.tree.visualItemRect(child)

    # A click presses the row, and the second press of the double click opens.
    QTest.mouseClick(
        view.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
    )
    QTest.mouseDClick(
        view.tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center()
    )

    assert window.current_object() is second


def test_a_double_click_on_a_kind_does_not_go_anywhere(window) -> None:
    first = make_property("First")
    window.open(first)
    window.select_element(first)
    window.dock.show_hints()
    view = window.dock.hints_view
    group = view.group_item(hint_rules.DESCRIPTION_MISSING)
    assert group is not None
    activated: list[object] = []
    window.dock.finding_activated.connect(activated.append)

    view.activate(group)

    assert activated == []
    assert window.current_object() is first


def test_the_hints_view_of_a_package_without_hints_says_so(window) -> None:
    window.open_described(_described(make_property("Pump")))

    window.dock.show_hints()

    assert window.dock.hints_view.tree.topLevelItemCount() == 0
    assert window.dock.hints_view.summary_label.text() == "No hints"


def test_the_hints_view_without_a_package_says_so(window) -> None:
    assert window.dock.hints_view.summary_label.text() == "No package open"


def test_the_hints_view_has_the_hints_that_the_list_of_findings_leaves_out(
    window,
) -> None:
    window.open(make_property("X", "1"))
    window.dock.show_hints()

    findings = window.dock.report.findings
    hints = window.dock.hint_report

    assert all(not is_hint(f) for f in findings)
    assert any(is_hint(f) for f in hints.findings)
    assert [f for f in hints.findings if not is_hint(f)] == list(findings)


def test_the_list_of_errors_and_warnings_is_as_before(window) -> None:
    window.open(
        make_property("X", "1"),
        model.ReferenceElement(
            "Dangling",
            value=model.ModelReference(
                (model.Key(model.KeyTypes.SUBMODEL, "urn:a"),), model.Submodel
            ),
        ),
    )
    window.dock.show_findings()

    assert window.dock.counts_label.text() == "1 error, 1 warning"
    assert all(not is_hint(f) for f in window.dock.visible_findings())


def test_the_hints_view_is_up_to_date_after_an_edit(
    window, qtbot: QtBot
) -> None:
    element = make_property("Plain")
    package = window.open(element)
    window.dock.show_hints()
    assert _group_rows(window)["Missing description"] == "2"

    from aas_workingbench.application.changes import observer_for
    from aas_workingbench.application.edits import SetAttribute

    package.commandStack.push(  # type: ignore[attr-defined]
        SetAttribute(
            observer_for(package),
            element,
            "description",
            model.MultiLanguageTextType({"en": "D", "de": "D"}),
        )
    )

    qtbot.waitUntil(
        lambda: _group_rows(window).get("Missing description") == "1",
        timeout=2000,
    )


def test_the_grouped_counts_match_what_validate_package_reports_for_a_template(
    window, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.ui.load_report_dialog import LoadReportDialog

    # The template opens in failsafe mode: the user agrees, and the report of
    # what was left out is not shown.
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Yes
    )
    monkeypatch.setattr(LoadReportDialog, "exec", lambda dialog: 0)
    source = tmp_path / TECHNICAL_DATA.name
    shutil.copy(TECHNICAL_DATA, source)
    package = window.views_.view.openPack(source.as_posix())
    assert package is not None
    window.views_.select(window.views_.index(package=0))
    window.dock.show_hints()

    report = validate_package(package.save_source(), with_hints=True)
    expected = Counter(f.rule_id for f in report.findings if is_hint(f))
    shown = {g.rule_id: g.count for g in window.dock.hints_view.groups}

    assert shown == dict(expected)
    # The numbers that docs/software/validation.md gives for this template.
    assert shown == {
        hint_rules.DISPLAY_NAME_MISSING: 43,
        hint_rules.DESCRIPTION_ONE_LANGUAGE: 41,
        hint_rules.CATEGORY_DEPRECATED: 11,
        hint_rules.DESCRIPTION_MISSING: 1,
    }
    assert len(shown) > 1
    assert sum(shown.values()) == window.dock.hints_view.shown_count
    # Each row reads as the name of its kind and its count.
    rows = _group_rows(window)
    assert rows["Missing description"] == str(
        expected[hint_rules.DESCRIPTION_MISSING]
    )
    assert rows["Missing display name"] == str(
        expected[hint_rules.DISPLAY_NAME_MISSING]
    )
    assert (
        window.dock.view_bar.tabText(1) == f"Hints ({sum(expected.values())})"
    )


# ---------------------------------------------------------------------------
# A kind that is turned off
# ---------------------------------------------------------------------------


def _untick(window, rule_id: str) -> None:
    item = window.dock.hints_view.group_item(rule_id)
    assert item is not None
    item.setCheckState(0, Qt.CheckState.Unchecked)


def test_a_kind_that_is_off_is_left_out_of_the_hints_here(window) -> None:
    element = make_property("Plain")
    window.open(element)
    window.select_element(element)
    window.dock.show_hints()

    _untick(window, hint_rules.DESCRIPTION_MISSING)

    assert window.status.hints_button.text() == "1 hint here"


def test_every_kind_off_leaves_nothing_here(window) -> None:
    element = make_property("Plain")
    window.open(element)
    window.select_element(element)
    window.dock.show_hints()

    _untick(window, hint_rules.DESCRIPTION_MISSING)
    _untick(window, hint_rules.DISPLAY_NAME_MISSING)

    assert window.status.hints_button.isHidden()


def test_a_kind_that_is_off_is_left_out_of_the_bar_above_a_tab(
    window, qtbot: QtBot
) -> None:
    from aas_workingbench.ui.hints_bar import HintsBar

    bar = HintsBar()
    qtbot.addWidget(bar)
    element = make_property("Plain")
    package = window.open(element)
    bar.set_target(package, element)
    assert bar.lines == [
        "2 hints about displayName, description. Hover to read them"
    ]

    hint_kinds().set_off(hint_rules.DESCRIPTION_MISSING, True)

    (line,) = bar.lines
    assert line.startswith("Hint: ")
    assert line.endswith("(EDT-HINT-DISPLAY-NAME-MISSING)")
    hint_kinds().set_off(hint_rules.DESCRIPTION_MISSING, False)
    assert len(bar.lines) == 1 and "2 hints about" in bar.lines[0]


def test_a_kind_that_is_off_stays_in_the_view_so_that_it_can_come_back(
    window,
) -> None:
    window.open(make_property("Plain"))
    window.dock.show_hints()

    _untick(window, hint_rules.DESCRIPTION_MISSING)
    item = window.dock.hints_view.group_item(hint_rules.DESCRIPTION_MISSING)

    assert item is not None
    assert item.checkState(0) == Qt.CheckState.Unchecked
    assert window.dock.hints_view.summary_label.text() == (
        "2 hints in 1 kind. 2 hints turned off"
    )
    item.setCheckState(0, Qt.CheckState.Checked)
    assert not hint_kinds().off
    assert window.dock.hints_view.summary_label.text() == "4 hints in 2 kinds"


def test_the_tab_counts_only_the_kinds_that_are_on(window) -> None:
    window.open(make_property("Plain"))
    window.dock.show_hints()
    assert window.dock.view_bar.tabText(1) == "Hints (4)"

    _untick(window, hint_rules.DESCRIPTION_MISSING)

    assert window.dock.view_bar.tabText(1) == "Hints (2)"


def test_a_button_turns_every_kind_on_again(window) -> None:
    window.open(make_property("Plain"))
    window.dock.show_hints()
    view = window.dock.hints_view
    assert view.turn_on_button.isHidden()
    _untick(window, hint_rules.DESCRIPTION_MISSING)
    _untick(window, hint_rules.DISPLAY_NAME_MISSING)
    assert not view.turn_on_button.isHidden()

    view.turn_on_button.click()

    assert hint_kinds().off == frozenset()
    assert view.turn_on_button.isHidden()
    assert view.summary_label.text() == "4 hints in 2 kinds"


def test_a_kind_that_is_off_stays_off_across_a_restart(
    qtbot: QtBot, views
) -> None:
    from aas_workingbench.settings import app_settings

    first = _make_window(qtbot, views)
    first.open(make_property("Plain"))
    first.dock.show_hints()
    _untick(first, hint_rules.DESCRIPTION_MISSING)
    assert app_settings.SETTINGS.value("disabledHintKinds") == (
        hint_rules.DESCRIPTION_MISSING
    )

    # A new session starts with no kind off, and reads the settings.
    hint_kinds().load(())
    second = _make_window(qtbot, views)
    element = make_property("Again")
    second.open(element)
    second.select_element(element)

    assert hint_kinds().off == frozenset({hint_rules.DESCRIPTION_MISSING})
    assert second.status.hints_button.text() == "1 hint here"
    second.dock.show_hints()
    item = second.dock.hints_view.group_item(hint_rules.DESCRIPTION_MISSING)
    assert item is not None
    assert item.checkState(0) == Qt.CheckState.Unchecked


def test_turning_a_kind_on_again_is_saved_too(qtbot: QtBot, views) -> None:
    from aas_workingbench.settings import app_settings

    window = _make_window(qtbot, views)
    window.open(make_property("Plain"))
    window.dock.show_hints()
    _untick(window, hint_rules.DESCRIPTION_MISSING)

    window.dock.hints_view.turn_on_button.click()

    assert not app_settings.SETTINGS.value("disabledHintKinds")
    hint_kinds().load(())
    _make_window(qtbot, views)
    assert hint_kinds().off == frozenset()


def test_turning_a_kind_off_does_not_change_the_package(window) -> None:
    package = window.open(make_property("Plain"))
    window.dock.show_hints()

    _untick(window, hint_rules.DESCRIPTION_MISSING)

    assert package.changed is False  # type: ignore[attr-defined]


def test_the_hints_view_says_when_hints_mode_is_off(window) -> None:
    window.open(make_property("Plain"))
    window.dock.show_hints()
    view = window.dock.hints_view
    assert view.mode_label.isHidden()

    hints_mode().set_on(False)

    assert not view.mode_label.isHidden()
    assert view.tree.topLevelItemCount() == 2
    hints_mode().set_on(True)
    assert view.mode_label.isHidden()


# ---------------------------------------------------------------------------
# F8 and the note
# ---------------------------------------------------------------------------


def test_f8_goes_through_errors_and_warnings_and_not_hints(window) -> None:
    window.open(make_property("X", "1"), make_property("Plain"))
    window.dock.show_hints()
    assert any(is_hint(f) for f in window.dock.hint_report.findings)

    first = window.controller_.step(forward=True)
    second = window.controller_.step(forward=True)

    # One error and nothing else to stop at: the walk wraps to the same error.
    assert first is not None and first.rule_id == "AASd-002"
    assert second is not None and second.rule_id == "AASd-002"


def test_the_note_of_the_list_of_findings_sends_to_the_hints_view(
    window,
) -> None:
    note = window.dock.note_label.text()

    assert "Hints view" in note
    assert "not listed here" not in note


# ---------------------------------------------------------------------------
# Colors come from the theme
# ---------------------------------------------------------------------------


def test_the_hints_button_is_styled_as_the_errors_button_by_the_sheet(
    tmp_path: Path,
) -> None:
    from aas_workingbench.domain.design_tokens import DARK
    from aas_workingbench.domain.design_tokens import LIGHT
    from aas_workingbench.ui.theme.stylesheet import build_stylesheet

    for tokens in (LIGHT, DARK):
        sheet = build_stylesheet(tokens, image_dir=tmp_path)

        assert (
            "QToolButton#validationStatusFindings,\n"
            "QToolButton#validationStatusHints {\n    padding: 0 6px;"
        ) in sheet.replace("\r\n", "\n")


def test_a_kind_that_is_off_is_drawn_in_the_quiet_color_of_each_theme(
    window, qapp: object
) -> None:
    from aas_workingbench.domain.design_tokens import DARK
    from aas_workingbench.domain.design_tokens import LIGHT
    from aas_workingbench.ui.theme import theme_manager

    window.open(make_property("Plain"))
    window.dock.show_hints()
    _untick(window, hint_rules.DESCRIPTION_MISSING)
    item = window.dock.hints_view.group_item(hint_rules.DESCRIPTION_MISSING)
    assert item is not None

    try:
        theme_manager().apply("light")
        light = item.foreground(0).color()
        theme_manager().apply("dark")
        dark = item.foreground(0).color()
    finally:
        theme_manager().apply("light")

    assert light == QColor(LIGHT.fg_muted)
    assert dark == QColor(DARK.fg_muted)


def test_the_new_views_name_no_color_of_their_own() -> None:
    import re

    import aas_workingbench.ui.hints_view as view
    import aas_workingbench.ui.validation_status as status

    for module in (view, status):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{6}\b|QColor\(\"", source)
        assert "setStyleSheet" not in source
