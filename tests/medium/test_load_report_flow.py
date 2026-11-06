"""What the user sees of a load report: on open, on request, and on a save.

Modal dialogs are replaced by functions that record what they show.
"""

from collections.abc import Iterator
from pathlib import Path

from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.load_report_measure import LOSES_A_SUBMODEL
from tests.package_factories import write_package_with_same_id_in_two_parts

from aas_editor.application.save import check_save
from aas_editor.application.save import SaveOptions
from aas_editor.domain.load_report import build_report
from aas_editor.domain.load_report import LoadReport
from aas_editor.domain.load_report import RawRecord
from aas_editor.domain.load_report import Severity


def _report(count_details: int = 2) -> LoadReport:
    records = [
        RawRecord(
            Severity.ERROR,
            "basyx.test",
            "KeyError: ns0:text on line 5 has no text!\n"
            f" -> Failed to construct ns0:value on line {line} using "
            "construct_multi_language_text_type!",
            "/aasx/data.xml",
        )
        for line in range(10, 10 + count_details)
    ]
    records.append(
        RawRecord(
            Severity.ERROR,
            "basyx.test",
            "AASConstraintViolation: A semantic_id must be defined before "
            "adding a supplemental_semantic_id! (Constraint AASd-118)\n"
            " -> Failed to construct ns0:submodel on line 33 using "
            "construct_submodel!",
            "/aasx/data.xml",
        )
    )
    return build_report(records)


@pytest.fixture
def shown_reports(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[str, list[str]]]:
    """Records the summary and the rows of each load report dialog."""
    from aas_editor.ui.load_report_dialog import LoadReportDialog

    shown: list[tuple[str, list[str]]] = []

    def record(dialog: LoadReportDialog) -> int:
        rows = [
            dialog.issues_list.item(row).text()
            for row in range(dialog.issues_list.count())
        ]
        shown.append((dialog.summary_label.text(), rows))
        return 0

    monkeypatch.setattr(LoadReportDialog, "exec", record)
    return shown


# -- the dialog ---------------------------------------------------------------


def test_the_dialog_names_the_package_and_counts_before_it_lists(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_editor.ui.load_report_dialog import LoadReportDialog

    dialog = LoadReportDialog("template.aasx", _report())
    qtbot.addWidget(dialog)

    text = dialog.summary_label.text()

    assert text.startswith("template.aasx could not be read completely.")
    assert "Left out: 1 object (1 submodel) and 2 details." in text
    assert "Save As" in text


def test_the_dialog_lists_the_biggest_losses_first(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_editor.ui.load_report_dialog import LoadReportDialog

    dialog = LoadReportDialog("template.aasx", _report())
    qtbot.addWidget(dialog)

    rows = [
        dialog.issues_list.item(row).text()
        for row in range(dialog.issues_list.count())
    ]

    assert len(rows) == 3
    assert rows[0].startswith("Left out submodel (line 33, data.xml)")
    assert rows[1].startswith("Left out ")
    assert "multi language text type" in rows[1]


def test_the_copy_button_puts_the_whole_report_on_the_clipboard(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_editor.ui.load_report_dialog import LoadReportDialog

    report = _report()
    dialog = LoadReportDialog("template.aasx", report)
    qtbot.addWidget(dialog)

    dialog.copy_button.click()

    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == report.text()
    # The text has the records of the SDK as well as the sentences.
    assert "SDK: AASConstraintViolation" in clipboard.text()


def test_the_dialog_for_an_empty_report_is_not_shown(
    qapp: object, shown_reports: list[tuple[str, list[str]]]
) -> None:
    from aas_editor.ui.load_report_dialog import show_load_report

    show_load_report("template.aasx", LoadReport())

    assert shown_reports == []


# -- on open -----------------------------------------------------------------


@pytest.fixture
def tree_view(qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    from aas_editor.models import PackTreeViewItem
    from aas_editor.models import PacksTable
    from aas_editor.package import Package
    from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_editor.settings.app_settings import DEFAULT_COLUMNS_IN_PACKS_TABLE
    from aas_editor.treeviews.treeview_pack import PackTreeView

    monkeypatch.setattr(PackTreeView, "scanFolderForExistFiles", lambda s: None)
    # The user agrees to open a package that fails strict reading.
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Yes
    )
    columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
    columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
    table = PacksTable(columns, PackTreeViewItem(None, None))
    table.addItem(Package())
    window = QWidget()
    qtbot.addWidget(window)
    view = PackTreeView(window)
    view.setModelWithProxy(table)
    return view


def test_opening_a_package_in_failsafe_mode_shows_what_was_left_out(
    tree_view, shown_reports: list[tuple[str, list[str]]]
) -> None:
    pack = tree_view.openPack(LOSES_A_SUBMODEL.as_posix())

    assert pack is not None
    assert pack.partial is True
    assert len(shown_reports) == 1
    summary, rows = shown_reports[0]
    assert "Left out: 1 object (1 submodel) and 1 element." in summary
    assert len(rows) == 2
    assert rows[0].startswith("Left out submodel (line 33")


def test_opening_a_package_strictly_shows_no_report(
    tree_view, shown_reports: list[tuple[str, list[str]]], aasx_file: Path
) -> None:
    pack = tree_view.openPack(aasx_file.as_posix())

    assert pack is not None
    assert shown_reports == []


def test_a_strict_open_that_loses_an_object_in_a_second_part_says_so(
    tree_view, shown_reports: list[tuple[str, list[str]]], tmp_path: Path
) -> None:
    source = write_package_with_same_id_in_two_parts(tmp_path / "two.aasx")

    pack = tree_view.openPack(source.as_posix())

    assert pack is not None
    assert pack.partial is True
    (summary, rows) = shown_reports[0]
    assert "Left out: 1 object (1 submodel)." in summary
    assert rows[0].startswith(
        "Left out submodel (id urn:uuid:00000000-0000-4000-8000-0000000000aa, "
        "second.xml)"
    )


# -- later, from the menu -----------------------------------------------------


@pytest.fixture
def registered(qapp: object) -> Iterator[None]:
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.load_report_actions import ACTION_ID
    from aas_editor.ui.load_report_actions import register_load_report_actions

    register_load_report_actions()
    register_load_report_actions()
    yield
    default_registry().unregister(ACTION_ID)


def test_the_action_is_enabled_for_a_package_with_a_report_only(
    views, registered: None
) -> None:
    shown = views()
    clean = shown.open_package(make_submodel(id_="urn:x:a"))
    lossy = shown.open_package(make_submodel(id_="urn:x:b"))
    lossy.loadReport = _report()

    states = []
    for position in (0, 1):
        index = shown.index(package=position)
        shown.select(index)
        shown.view.updateActions(index)
        states.append(
            shown.view.registeredActions.find("package.load_report").isEnabled()
        )

    assert (clean is not lossy) and states == [False, True]


def test_the_action_shows_the_report_of_the_package(
    views,
    registered: None,
    shown_reports: list[tuple[str, list[str]]],
) -> None:
    shown = views()
    package = shown.open_package(make_submodel(elements=[make_property()]))
    package.loadReport = _report()
    index = shown.index(package=0)
    shown.select(index)
    shown.view.updateActions(index)

    shown.view.registeredActions.find("package.load_report").trigger()

    assert len(shown_reports) == 1
    assert (
        "Left out: 1 object (1 submodel) and 2 details." in shown_reports[0][0]
    )


# -- on a save ----------------------------------------------------------------


def test_a_refused_save_offers_the_full_list_of_what_was_left_out(
    qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_editor.package import Package
    from aas_editor.ui.save_warnings import IssuesDialog
    from aas_editor.ui.save_warnings import show_save_refused

    package = Package(LOSES_A_SUBMODEL, failsafe=True)
    check = check_save(package.save_source(), LOSES_A_SUBMODEL, SaveOptions())
    monkeypatch.setattr(
        IssuesDialog, "exec", lambda dialog: dialog.extra_button.click()
    )
    opened: list[bool] = []

    show_save_refused(check, None, None, lambda: opened.append(True))

    assert opened == [True]


def test_the_refused_save_lists_what_the_package_lacks(
    qapp: object, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    package = Package(LOSES_A_SUBMODEL, failsafe=True)

    (blocker,) = check_save(
        package.save_source(), LOSES_A_SUBMODEL, SaveOptions()
    ).blockers

    assert "Left out: 1 object (1 submodel) and 1 element." in blocker.message
    assert "Use Save As" in blocker.message
    assert len(blocker.details) == 2
    assert blocker.details[0].startswith("Left out submodel (line 33")


def test_the_report_survives_a_crash_recovery(
    qapp: object, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    package = Package(LOSES_A_SUBMODEL, failsafe=True)
    package.changed = True
    recovery_dir = tmp_path / "recovery"

    recovery = package.write_recovery(recovery_dir)
    restored = Package.restore_from_recovery(recovery, LOSES_A_SUBMODEL)

    assert restored.partial is True
    assert restored.loadReport == package.loadReport
    assert restored.loadReport
