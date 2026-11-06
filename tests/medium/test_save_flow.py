"""The save flow in the package tree view, and its dialogs.

The view asks the application layer whether a save may go on, shows a dialog
for blockers and warnings, and writes only when the whole package can be
written. Modal dialogs are replaced by functions that record what they show.
"""

from collections.abc import Callable
from collections.abc import Iterator
from pathlib import Path

from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from aas_editor.domain.validation import Finding

from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx
from tests.package_factories import DOCUMENT_BYTES
from tests.package_factories import DOCUMENT_PART
from tests.package_factories import MISSING_PART
from tests.package_factories import write_package_with_missing_file


class Dialogs:
    """What the modal dialogs showed, and what they answer."""

    def __init__(self) -> None:
        self.shown: list[tuple[str, list[str]]] = []
        self.accept = False


@pytest.fixture
def view_support(qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    from aas_editor.models import PackTreeViewItem
    from aas_editor.models import PacksTable
    from aas_editor.package import Package
    from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE
    from aas_editor.settings.app_settings import DEFAULT_COLUMNS_IN_PACKS_TABLE
    from aas_editor.settings.app_settings import OPENED_PACKS_ROLE
    from aas_editor.treeviews.treeview_pack import PackTreeView
    from aas_editor.ui.save_warnings import IssuesDialog
    from aas_editor.widgets.messsageBoxes import ErrorMessageBox

    # Reading the submodel templates from disk is slow and irrelevant here.
    monkeypatch.setattr(PackTreeView, "scanFolderForExistFiles", lambda s: None)
    # The settings file of the user must not change what a save writes.
    monkeypatch.setattr(Package, "writeJsonInAasx", False)
    monkeypatch.setattr(Package, "writePrettyJson", True)
    monkeypatch.setattr(Package, "sortKeysInJson", True)
    dialogs = Dialogs()
    errors: list[str] = []
    windows: list[QWidget] = []

    def fake_dialog_exec(dialog: IssuesDialog) -> int:
        texts = [
            dialog.issues_list.item(row).text()
            for row in range(dialog.issues_list.count())
        ]
        dialogs.shown.append((dialog.windowTitle(), texts))
        if dialogs.accept:
            dialog.accept()
        return 0

    monkeypatch.setattr(IssuesDialog, "exec", fake_dialog_exec)
    monkeypatch.setattr(
        ErrorMessageBox, "exec", lambda box: errors.append(box.text()) or 0
    )

    class Support:
        shown_dialogs = dialogs
        shown_errors = errors

        @staticmethod
        def open_package(package):
            columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE)
            columns.extend(EXTENDED_COLUMNS_IN_PACK_TABLE)
            table = PacksTable(columns, PackTreeViewItem(None, None))
            table.addItem(package)
            window = QWidget()
            qtbot.addWidget(window)
            windows.append(window)  # keeps the window and its view alive
            view = PackTreeView(window)
            view.setModelWithProxy(table)
            return view

        @staticmethod
        def opened_packs(view):
            return view.model().data(QModelIndex(), OPENED_PACKS_ROLE)

        @staticmethod
        def select_package(view, package) -> None:
            (item,) = view.model().match(
                QModelIndex(),
                view_support_roles.OBJECT_ROLE,
                package,
                hits=1,
            )
            view.setCurrentIndex(item)

    from aas_editor.settings import app_settings as view_support_roles

    return Support


def _saved_names(folder: Path) -> list[str]:
    return sorted(entry.name for entry in folder.iterdir())


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


def test_save_is_refused_and_original_is_kept_when_file_has_no_part(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    before = source.read_bytes()
    package = Package(source)
    view = view_support.open_package(package)

    saved = view.savePack(package)

    assert saved is False
    assert source.read_bytes() == before
    assert _saved_names(tmp_path) == ["dangling.aasx"]
    assert view_support.shown_dialogs.shown == [
        (
            "Package cannot be saved",
            [
                "A File points to a file that is not in the package, so the "
                "package cannot be written. Remove the path, or add the file.",
                f"    Datasheet ({MISSING_PART})",
            ],
        )
    ]


def test_save_as_json_is_allowed_when_file_has_no_part(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(source)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = True

    saved = view.savePack(package, (tmp_path / "copy.json").as_posix())

    assert saved is True
    assert package.file == tmp_path / "copy.json"
    assert [title for title, _ in view_support.shown_dialogs.shown] == [
        "Save package"
    ]


def test_save_as_keeps_file_when_user_refuses_to_lose_files(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(source)
    original_file = package.file
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = False

    saved = view.savePack(package, (tmp_path / "copy.json").as_posix())

    assert saved is False
    assert package.file == original_file
    assert _saved_names(tmp_path) == ["dangling.aasx"]


def test_save_is_refused_when_partial_package_overwrites_its_source(
    view_support, tmp_path: Path, aasx_file: Path
) -> None:
    from aas_editor.package import Package

    source = tmp_path / "source.aasx"
    source.write_bytes(aasx_file.read_bytes())
    package = Package(source, failsafe=True)
    view = view_support.open_package(package)

    saved = view.savePack(package)

    assert saved is False
    assert source.read_bytes() == aasx_file.read_bytes()
    assert view_support.shown_dialogs.shown[0][0] == "Package cannot be saved"


def test_save_as_keeps_going_when_partial_package_is_saved_elsewhere(
    view_support, tmp_path: Path, aasx_file: Path
) -> None:
    from aas_editor.package import Package

    source = tmp_path / "source.aasx"
    source.write_bytes(aasx_file.read_bytes())
    package = Package(source, failsafe=True)
    view = view_support.open_package(package)

    first = view.savePack(package, (tmp_path / "copy.aasx").as_posix())
    # The copy is not the source, so the next save may replace it.
    second = view.savePack(package)
    # The source stays protected after the copy was saved.
    third = view.savePack(package, source.as_posix())

    assert (first, second, third) == (True, True, False)


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def _package_with_unreferenced_file(tmp_path: Path):
    from aas_editor.package import Package

    submodel = make_submodel(
        elements=[make_file_element("Document", DOCUMENT_PART)]
    )
    source = write_aasx(
        tmp_path / "files.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
        files={DOCUMENT_PART: (DOCUMENT_BYTES, "application/pdf")},
    )
    package = Package(source)
    submodel_in_package = next(iter(package.submodels))
    submodel_in_package.submodel_element.remove(
        submodel_in_package.get_referable("Document")
    )
    return package


def test_save_asks_before_it_drops_files_that_nothing_refers_to(
    view_support, tmp_path: Path
) -> None:
    package = _package_with_unreferenced_file(tmp_path)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = False

    saved = view.savePack(package)

    assert saved is False
    assert view_support.shown_dialogs.shown == [
        (
            "Save package",
            [
                "These files are in the package, but no File element or "
                "thumbnail refers to them. They are not saved.",
                f"    {DOCUMENT_PART}",
            ],
        )
    ]


def test_save_drops_files_when_user_confirms(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    package = _package_with_unreferenced_file(tmp_path)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = True

    saved = view.savePack(package)

    assert saved is True
    assert list(Package(tmp_path / "files.aasx").fileStore) == []


# ---------------------------------------------------------------------------
# Default save path and the explicit link action (D8)
# ---------------------------------------------------------------------------


def test_save_writes_to_own_file_when_no_file_is_given(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    submodel = make_submodel()
    source = write_aasx(
        tmp_path / "plain.aasx", make_store(make_shell(), submodel)
    )
    package = Package(source)
    package.changed = True
    view = view_support.open_package(package)

    saved = view.savePack(package)

    reloaded = Package(source)
    assert saved is True
    assert package.changed is False
    assert [len(shell.submodel) for shell in reloaded.shells] == [0]
    assert view_support.shown_dialogs.shown == []


def test_link_action_adds_references_when_user_asks_for_it(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_aasx(
        tmp_path / "plain.aasx", make_store(make_shell(), make_submodel())
    )
    package = Package(source)
    view = view_support.open_package(package)
    view_support.select_package(view, package)

    added = view.linkAllSubmodelsToFirstAas()

    assert added == 1
    assert package.changed is True
    assert [len(shell.submodel) for shell in package.shells] == [1]


def test_link_action_adds_nothing_when_references_exist(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    submodel = make_submodel()
    source = write_aasx(
        tmp_path / "linked.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
    )
    package = Package(source)
    view = view_support.open_package(package)
    view_support.select_package(view, package)

    added = view.linkAllSubmodelsToFirstAas()

    assert added == 0
    assert package.changed is False


# ---------------------------------------------------------------------------
# Closing and saving all
# ---------------------------------------------------------------------------


def test_close_keeps_package_open_when_save_is_refused(
    view_support, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(source)
    package.changed = True
    view = view_support.open_package(package)
    view_support.select_package(view, package)
    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Save
    )

    view.closeFileWithDialog()

    assert view_support.opened_packs(view) == {package}


def test_save_all_skips_package_when_it_has_no_changes(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(source)
    view = view_support.open_package(package)

    view.saveAll()

    assert view_support.shown_dialogs.shown == []


# ---------------------------------------------------------------------------
# Opening
# ---------------------------------------------------------------------------


def test_open_shows_missing_files_when_part_is_missing(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    view = view_support.open_package(Package())

    pack = view.openPack(source.as_posix())

    assert pack is not None
    assert view_support.shown_dialogs.shown == [
        (
            "Files missing in package",
            ["1 missing", f"    {MISSING_PART}"],
        )
    ]


def test_open_shows_no_dialog_when_package_is_complete(
    view_support, tmp_path: Path, aasx_file: Path
) -> None:
    from aas_editor.package import Package

    view = view_support.open_package(Package())

    pack = view.openPack(aasx_file.as_posix())

    assert pack is not None
    assert view_support.shown_dialogs.shown == []


# ---------------------------------------------------------------------------
# The dialog
# ---------------------------------------------------------------------------


def test_dialog_offers_save_anyway_and_cancel_when_it_asks_for_confirmation(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_editor.application.save import SaveIssue
    from aas_editor.ui.save_warnings import IssuesDialog

    dialog = IssuesDialog(
        "Save package",
        "Summary",
        [SaveIssue("Something is dropped.", ("a.pdf",))],
        accept_text="Save anyway",
    )
    qtbot.addWidget(dialog)

    texts = [button.text() for button in dialog.buttons.buttons()]
    default_texts = [
        button.text()
        for button in dialog.buttons.buttons()
        if button.isDefault()
    ]
    assert texts == ["Save anyway", "Cancel"]
    assert default_texts == ["Cancel"]
    assert dialog.summary_label.text() == "Summary"


def test_dialog_has_only_ok_when_it_informs(qapp: object, qtbot: QtBot) -> None:
    from aas_editor.application.save import SaveIssue
    from aas_editor.ui.save_warnings import IssuesDialog

    dialog = IssuesDialog("Title", "Summary", [SaveIssue("Problem.")])
    qtbot.addWidget(dialog)

    assert [button.text() for button in dialog.buttons.buttons()] == ["OK"]


def _answer(
    monkeypatch: pytest.MonkeyPatch, answer: Callable[[QDialog], None]
) -> None:
    from aas_editor.ui.save_warnings import IssuesDialog

    monkeypatch.setattr(IssuesDialog, "exec", answer)


def test_confirm_save_is_true_when_user_accepts(
    qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.application.save import SaveCheck
    from aas_editor.application.save import SaveIssue
    from aas_editor.ui.save_warnings import confirm_save

    _answer(monkeypatch, lambda dialog: dialog.accept())

    confirmed = confirm_save(SaveCheck(warnings=(SaveIssue("Dropped."),)))

    assert confirmed is True


def test_confirm_save_is_false_when_user_cancels(
    qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.application.save import SaveCheck
    from aas_editor.application.save import SaveIssue
    from aas_editor.ui.save_warnings import confirm_save

    _answer(monkeypatch, lambda dialog: dialog.reject())

    confirmed = confirm_save(SaveCheck(warnings=(SaveIssue("Dropped."),)))

    assert confirmed is False


# ---------------------------------------------------------------------------
# The errors of the validation rules (D5)
# ---------------------------------------------------------------------------


def _package_with_one_letter_id_short(tmp_path: Path):
    from aas_editor.package import Package

    submodel = make_submodel(elements=[make_property("X", "1")])
    source = write_aasx(
        tmp_path / "rules.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
    )
    return Package(source)


def test_save_asks_with_the_rules_that_the_package_breaks(
    view_support, tmp_path: Path
) -> None:
    package = _package_with_one_letter_id_short(tmp_path)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = False

    saved = view.savePack(package)

    assert saved is False
    ((title, texts),) = view_support.shown_dialogs.shown
    assert title == "Save package"
    assert texts[0] == "AASd-002: idShort matches the pattern (1 found)"
    assert texts[1].startswith("    Property 'X' of Submodel 'Submodel'")


def test_save_writes_the_package_when_the_user_confirms_the_errors(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    package = _package_with_one_letter_id_short(tmp_path)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = True

    saved = view.savePack(package)

    assert saved is True
    submodel = next(iter(Package(tmp_path / "rules.aasx").submodels))
    assert submodel.get_referable("X").value == "1"


def test_save_asks_about_the_same_errors_only_once(
    view_support, tmp_path: Path
) -> None:
    package = _package_with_one_letter_id_short(tmp_path)
    view = view_support.open_package(package)
    view_support.shown_dialogs.accept = True

    first = view.savePack(package)
    second = view.savePack(package)

    assert (first, second) == (True, True)
    assert len(view_support.shown_dialogs.shown) == 1


def test_save_does_not_ask_when_the_package_only_has_warnings(
    view_support, tmp_path: Path
) -> None:
    import basyx.aas.model as model

    from aas_editor.package import Package

    dangling = model.ReferenceElement(
        "Link",
        value=model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),), model.Submodel
        ),
    )
    submodel = make_submodel(elements=[dangling])
    source = write_aasx(
        tmp_path / "warn.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
    )
    package = Package(source)
    view = view_support.open_package(package)

    saved = view.savePack(package)

    assert saved is True
    assert view_support.shown_dialogs.shown == []


def test_save_still_works_when_a_rule_raises(
    view_support, tmp_path: Path
) -> None:
    from aas_editor.application.validation import SaveGate
    from aas_editor.domain.validation import Rule

    def broken(context: object) -> Iterator[Finding]:
        raise RuntimeError("defect in the rule")
        yield

    package = _package_with_one_letter_id_short(tmp_path)
    package.saveGate = SaveGate(
        rules=(Rule("TEST-BROKEN", "Broken", "test", broken),)
    )
    view = view_support.open_package(package)

    saved = view.savePack(package)

    assert saved is True
    assert view_support.shown_dialogs.shown == []
