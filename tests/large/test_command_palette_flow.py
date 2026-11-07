"""The command palette in the real main window."""

from pathlib import Path
import shutil
from types import SimpleNamespace

from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtGui import QShortcut
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
import pytest
from tests.conftest import TEST_DATA_DIR

from aas_workingbench.application.command_palette import EntryKind
from aas_workingbench.application.command_palette import RecentCommands
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui.actions import ViewKind
from aas_workingbench.ui.actions import default_registry

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02002-1-0_Template_ContactInformation.aasx"


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path):
    """The main window with one package."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui.location_actions import register_location_actions
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions

    # The application registers its actions before its first window.
    register_move_actions()
    register_paste_actions()
    register_location_actions()
    source = tmp_path / PACKAGE
    shutil.copy(TEST_DATA_DIR / PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitActive(window)
    # The commands used last stay in memory, and not in the settings of the user.
    recent = RecentCommands()
    window.commandPalette.recent = recent
    window.commandPalette.palette._recent = recent

    editor = SimpleNamespace()
    editor.window = window
    editor.view = window.mainTreeView
    editor.controller = window.commandPalette
    editor.palette = window.commandPalette.palette
    (editor.package,) = window.packTreeModel.openedPacks()
    yield editor
    window._recoveryTimer.stop()
    window.close()


def test_ctrl_k_opens_the_palette_from_the_tree(editor, qtbot) -> None:
    editor.view.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is editor.view)

    QTest.keySequence(editor.view, QKeySequence("Ctrl+K"))

    assert editor.palette.isVisible()
    qtbot.waitUntil(editor.palette.input.hasFocus, timeout=2000)


def test_ctrl_k_has_one_owner_in_the_window(editor) -> None:
    wanted = QKeySequence("Ctrl+K")
    owners: list[object] = [
        a
        for a in editor.window.findChildren(QAction)
        if wanted in a.shortcuts()
    ]
    owners += [
        s for s in editor.window.findChildren(QShortcut) if s.key() == wanted
    ]

    assert owners == [editor.controller.action]


def test_the_palette_is_in_the_navigate_menu(editor) -> None:
    assert editor.controller.action in editor.window.menuNavigate.actions()


def test_every_registered_action_has_an_entry_in_the_real_window(
    editor,
) -> None:
    keys = {entry.key for entry in editor.controller.commands()}
    registered = {
        spec.action_id
        for spec in default_registry().specs_for(ViewKind.PACKAGES)
    }

    assert registered
    assert registered <= keys


def test_the_commands_of_the_menus_and_the_tree_are_listed(editor) -> None:
    titles = {entry.title for entry in editor.controller.commands()}

    assert {
        "Save All",
        "Copy",
        "Paste",
        "Delete/clear",
        "Next finding",
    } <= titles


def test_picking_an_element_selects_it_in_the_tree(editor) -> None:
    from basyx.aas import model

    submodel = next(
        o for o in editor.package.objStore if isinstance(o, model.Submodel)
    )
    target = next(iter(submodel.submodel_element))
    editor.view.collapseAll()
    editor.controller.open()
    editor.palette.input.setText(target.id_short)
    entry = next(
        e
        for e in editor.palette.shown_entries
        if e.kind is EntryKind.ELEMENT and e.payload[1] is target  # type: ignore[index]
    )

    assert editor.controller.run(entry)

    assert editor.view.currentIndex().data(OBJECT_ROLE) is target


def test_a_command_of_the_palette_runs_in_the_window(editor, qtbot) -> None:
    editor.controller.open()
    editor.palette.input.setText("Next finding")

    assert editor.palette.current_entry is not None
    assert editor.palette.current_entry.title == "Next finding"
    editor.palette.choose_current()
    qtbot.waitUntil(lambda: editor.controller.recent.keys() != (), timeout=2000)

    assert editor.controller.recent.keys()[0] == "menu:Navigate > Next finding"
