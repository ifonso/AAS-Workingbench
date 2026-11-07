"""Two packages open at once: copy between them, close, Save All, recent files.

The pump package has a stored file. The requester package has 34 concept
descriptions. Both are opened through the File menu. A submodel with its file
and a concept description are copied across, one package is closed with
unsaved changes, and the answers of the person decide what is written.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.usage_open_window import DOCUMENT
from tests.usage_open_window import close_window
from tests.usage_open_window import column_of
from tests.usage_open_window import every_action  # noqa: F401
from tests.usage_open_window import open_window
from tests.usage_open_window import row_named
from tests.usage_open_window import screen  # noqa: F401
from tests.usage_open_window import write_pump_package

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

REQUESTER = ("submodels", "CapabilityDescription")
THREAD_SYSTEM = (
    *REQUESTER,
    "CapabilitySet",
    "ScrewingRequestedContainer",
    "ScrewingFastenerRequirementSet",
    "ThreadSystemContainer",
    "ThreadSystem",
)


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, screen, every_action):  # noqa: F811
    """The main window with the pump package first and the requester second."""
    pump = write_pump_package(tmp_path / "pump.aasx")
    requester = tmp_path / "Requester_screwing.aasx"
    shutil.copy(TEST_DATA_DIR / "Requester_screwing.aasx", requester)
    shown = open_window(qtbot)
    for path in (pump, requester):
        screen.open_paths.append(path.as_posix())
        shown.view.openPackAct.trigger()
    shown.view.expandAll()
    shown.screen = screen
    shown.tmp_path = tmp_path
    shown.pump_file = pump
    shown.requester_file = requester
    shown.pump, shown.requester = _in_order(shown)
    yield shown
    close_window(shown)


def _in_order(editor: SimpleNamespace) -> tuple[object, object]:
    by_name = {pack.name: pack for pack in editor.model.openedPacks()}
    return by_name["pump.aasx"], by_name["Requester_screwing.aasx"]


def _row(editor: SimpleNamespace, package: int, *names: str):
    return row_named(editor.view, *names, package=package)


def _select(editor: SimpleNamespace, index) -> None:
    editor.view.setCurrentIndex(index)
    editor.view.updateActions(index)


def _edit_value(editor: SimpleNamespace, package: int) -> None:
    view = editor.view
    cell = _row(editor, package, *THREAD_SYSTEM).siblingAtColumn(
        column_of(view, "value")
    )
    assert view.model().setData(cell, "other", Qt.ItemDataRole.EditRole)
    view.setCurrentIndex(_row(editor, package, *THREAD_SYSTEM))


def test_both_packages_show_in_the_tree_and_in_the_recent_files(
    editor,
) -> None:
    names = [
        editor.view.model().index(row, 0).data()
        for row in range(editor.view.model().rowCount())
    ]
    visible = [act for act in editor.view.recentFileActs if act.isVisible()]

    assert names == ["pump.aasx", "Requester_screwing.aasx"]
    assert [act.data() for act in visible] == [
        editor.requester_file.absolute().as_posix(),
        editor.pump_file.absolute().as_posix(),
    ]


def test_a_submodel_with_its_file_is_copied_to_the_other_package(
    editor,
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _select(editor, _row(editor, 0, "submodels", "Submodel"))
    editor.view.onCopy()
    _select(editor, _row(editor, 1, "submodels"))
    editor.view.registeredActions.find("structure.paste_into").trigger()
    target = editor.tmp_path / "requester_with_pump.aasx"
    editor.screen.save_paths.append(target.as_posix())
    _select(editor, _row(editor, 1))
    editor.view.saveAsAct.trigger()

    saved = read_package(target)

    assert sorted(
        s.id_short for s in saved.objects if isinstance(s, model.Submodel)
    ) == ["CapabilityDescription", "Submodel"]
    assert list(saved.files) == [DOCUMENT]
    assert (
        len(
            [
                c
                for c in saved.objects
                if isinstance(c, model.ConceptDescription)
            ]
        )
        == 34
    )


def test_a_concept_description_is_copied_to_the_other_package(editor) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _select(editor, _row(editor, 1, "concept_descriptions", "Screwing"))
    editor.view.onCopy()
    _select(editor, _row(editor, 0, "concept_descriptions"))
    editor.view.registeredActions.find("structure.paste_into").trigger()
    editor.screen.save_paths.append(editor.pump_file.as_posix())
    _select(editor, _row(editor, 0))
    editor.view.saveAct.trigger()

    saved = read_package(editor.pump_file)

    assert sorted(
        c.id_short
        for c in saved.objects
        if isinstance(c, model.ConceptDescription)
    ) == ["Concept", "Screwing"]


def test_closing_a_package_with_changes_asks_and_discard_leaves_the_file(
    editor,
) -> None:
    before = editor.requester_file.read_bytes()
    _edit_value(editor, 1)
    editor.screen.box_answer = QMessageBox.StandardButton.Discard

    editor.view.closeAct.trigger()

    assert [p.name for p in editor.model.openedPacks()] == ["pump.aasx"]
    assert editor.requester_file.read_bytes() == before
    assert editor.screen.last().title.startswith("Close ")


def test_closing_a_package_with_changes_and_cancel_keeps_it_open(
    editor,
) -> None:
    _edit_value(editor, 1)
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel

    editor.view.closeAct.trigger()

    assert sorted(p.name for p in editor.model.openedPacks()) == [
        "Requester_screwing.aasx",
        "pump.aasx",
    ]
    assert editor.requester.changed


def test_closing_with_save_writes_the_change_and_closes(editor) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _edit_value(editor, 1)
    editor.screen.box_answer = QMessageBox.StandardButton.Save

    editor.view.closeAct.trigger()

    assert [p.name for p in editor.model.openedPacks()] == ["pump.aasx"]
    saved = read_package(editor.requester_file)
    (submodel,) = [o for o in saved.objects if isinstance(o, model.Submodel)]
    assert (
        submodel.get_referable(
            [
                "CapabilitySet",
                "ScrewingRequestedContainer",
                "ScrewingFastenerRequirementSet",
                "ThreadSystemContainer",
                "ThreadSystem",
            ]
        ).value
        == "other"
    )


def test_save_all_writes_every_package_with_changes_and_only_those(
    editor,
) -> None:
    _edit_value(editor, 1)
    cell = _row(editor, 0, "submodels", "Submodel", "Name").siblingAtColumn(
        column_of(editor.view, "value")
    )
    assert editor.view.model().setData(cell, "motor", Qt.ItemDataRole.EditRole)
    untouched = editor.pump_file.stat().st_mtime_ns
    assert editor.pump.changed
    assert editor.requester.changed

    editor.view.saveAllAct.trigger()

    assert not editor.pump.changed
    assert not editor.requester.changed
    assert editor.pump_file.stat().st_mtime_ns != untouched
    assert editor.window._unsavedStatusLabel.text() == "All changes saved"


def test_a_package_that_is_closed_can_be_opened_from_the_recent_files(
    editor,
) -> None:
    editor.view.setCurrentIndex(_row(editor, 0))
    editor.view.closeAct.trigger()
    assert [p.name for p in editor.model.openedPacks()] == [
        "Requester_screwing.aasx"
    ]
    recent = [
        act
        for act in editor.view.recentFileActs
        if act.data() == editor.pump_file.absolute().as_posix()
    ]

    recent[0].trigger()

    assert sorted(p.name for p in editor.model.openedPacks()) == [
        "Requester_screwing.aasx",
        "pump.aasx",
    ]


def test_a_recent_file_that_is_gone_says_so_and_leaves_the_list(
    editor,
) -> None:
    editor.view.setCurrentIndex(_row(editor, 0))
    editor.view.closeAct.trigger()
    editor.pump_file.unlink()
    recent = [
        act
        for act in editor.view.recentFileActs
        if act.data() == editor.pump_file.absolute().as_posix()
    ]

    recent[0].trigger()

    assert "no longer exists" in editor.screen.last().text or (
        "does not exist" in editor.screen.last().text
    )
    editor.view.updateRecentFileActs()
    assert editor.pump_file.absolute().as_posix() not in [
        act.data() for act in editor.view.recentFileActs if act.isVisible()
    ]


def test_save_all_saves_the_others_when_one_package_cannot_be_saved(
    editor,
) -> None:
    from aas_editor.infrastructure.package_io import read_package

    template = editor.tmp_path / "AIDeployment.aasx"
    shutil.copy(
        next(
            (
                Path(__file__).parents[2]
                / "src"
                / "aas_editor"
                / "submodel_templates"
            ).rglob("IDTA 02059-1-0-1_Template_AIDeployment.aasx")
        ),
        template,
    )
    editor.screen.open_paths.append(template.as_posix())
    editor.view.openPackAct.trigger()
    partial = next(
        p for p in editor.model.openedPacks() if p.name == "AIDeployment.aasx"
    )
    partial.changed = True
    _edit_value(editor, 1)
    editor.screen.forget()

    editor.view.saveAllAct.trigger()

    assert not editor.requester.changed
    assert partial.changed
    assert "Package cannot be saved" in editor.screen.titles()
    (submodel,) = [
        o
        for o in read_package(editor.requester_file).objects
        if isinstance(o, model.Submodel)
    ]
    assert submodel.get_referable(list(THREAD_SYSTEM[2:])).value == "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_close_all_with_save_writes_both_and_closes_both(editor) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _edit_value(editor, 1)
    cell = _row(editor, 0, "submodels", "Submodel", "Name").siblingAtColumn(
        column_of(editor.view, "value")
    )
    assert editor.view.model().setData(cell, "motor", Qt.ItemDataRole.EditRole)
    editor.screen.box_answer = QMessageBox.StandardButton.Save

    editor.view.closeAllAct.trigger()

    assert not editor.model.openedPacks()
    assert editor.window.emptyState.isVisible()
    assert editor.screen.last().title == "Close all AAS files"
    pump = read_package(editor.pump_file)
    (pump_submodel,) = [
        o for o in pump.objects if isinstance(o, model.Submodel)
    ]
    assert pump_submodel.get_referable("Name").value == "motor"  # pyright: ignore[reportAttributeAccessIssue]
    requester = read_package(editor.requester_file)
    (submodel,) = [
        o for o in requester.objects if isinstance(o, model.Submodel)
    ]
    assert submodel.get_referable(list(THREAD_SYSTEM[2:])).value == "other"  # pyright: ignore[reportAttributeAccessIssue]


def test_close_all_with_cancel_keeps_both_open_and_with_discard_closes_both(
    editor,
) -> None:
    _edit_value(editor, 1)
    before = editor.requester_file.read_bytes()
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel

    editor.view.closeAllAct.trigger()

    assert len(editor.model.openedPacks()) == 2
    editor.screen.box_answer = QMessageBox.StandardButton.Discard

    editor.view.closeAllAct.trigger()

    assert not editor.model.openedPacks()
    assert editor.requester_file.read_bytes() == before


def test_closing_the_window_with_changes_asks_and_cancel_keeps_it_open(
    editor,
) -> None:
    _edit_value(editor, 1)
    editor.screen.box_answer = QMessageBox.StandardButton.Cancel

    closed = editor.window.close()

    assert not closed
    assert editor.window.isVisible()
    assert editor.requester.changed
    assert editor.screen.last().title == "Window Close"


def test_closing_the_window_with_yes_saves_every_package(editor) -> None:
    from aas_editor.infrastructure.package_io import read_package

    _edit_value(editor, 1)
    editor.screen.box_answer = QMessageBox.StandardButton.Yes

    closed = editor.window.close()

    assert closed
    (submodel,) = [
        o
        for o in read_package(editor.requester_file).objects
        if isinstance(o, model.Submodel)
    ]
    assert submodel.get_referable(list(THREAD_SYSTEM[2:])).value == "other"  # pyright: ignore[reportAttributeAccessIssue]
