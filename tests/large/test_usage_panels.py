"""The Selection panel, bulk actions, presets, the files and the tabs.

The package is a copy of the Technical Data template. Rows are selected as a
person does with Ctrl+click, a button of the panel is pressed, and the saved
file is read again to compare.
"""

from collections.abc import Iterator
import gc
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QDialog
import pytest
from tests import usage_window as uw
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

GENERAL = "GeneralInformation"


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the actions that `__main__` registers before the first view."""
    added = uw.register_all_actions()
    yield
    uw.unregister_actions(added)


@pytest.fixture
def large(
    qapp: object,
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[uw.UsageWindow]:
    """The main window on a copy of the Technical Data template."""
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui import preset_actions

    # Selecting a File opens a preview with QtWebEngine, which ends the test
    # process with an access violation after the tests passed (CHANGELOG, Known
    # limits). The tabs that these tests look at are opened by their own actions.
    monkeypatch.setattr(
        EditorApp, "onSelectedPackItemChanged", lambda self, item: None
    )
    # The presets of the user are kept next to the settings, in the code.
    monkeypatch.setattr(
        preset_actions, "user_presets_dir", lambda: tmp_path / "presets"
    )
    yield from uw.open_window(qtbot, monkeypatch, tmp_path, uw.TECHNICAL_DATA)
    uw.release_clipboard()


def _children(window: uw.UsageWindow, holder: str) -> list[QModelIndex]:
    """The rows below a collection of the submodel, in the order shown."""
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    parent = next(
        i
        for i in uw.all_rows(window.view)
        if isinstance(i.data(OBJECT_ROLE), model.SubmodelElementCollection)
        and i.data() == holder
    )
    proxy = window.view.model()
    return [proxy.index(r, 0, parent) for r in range(proxy.rowCount(parent))]


def _collection(window: uw.UsageWindow, holder: str) -> Any:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    window.view.expandAll()
    return next(
        i.data(OBJECT_ROLE)
        for i in uw.all_rows(window.view)
        if isinstance(i.data(OBJECT_ROLE), model.SubmodelElementCollection)
        and i.data() == holder
    )


def _order(window: uw.UsageWindow, holder: str) -> list[str]:
    return [e.id_short for e in _collection(window, holder).value]


def _saved(window: uw.UsageWindow, tmp_path: Path, name: str) -> Any:
    from aas_workingbench.package import Package

    window.package.write(tmp_path / name)
    return Package(tmp_path / name)


# The Selection panel


def test_several_rows_open_the_selection_panel_with_the_buttons_for_them(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    dock = large.window.selectionDock
    hidden_before = not dock.isVisible()

    uw.select(large.view, rows[0], rows[2], rows[3])

    panel = dock.panel
    assert hidden_before
    assert dock.isVisible()
    assert panel.header_label.text() == "Several elements selected"
    assert panel.detail_label.text().startswith(
        "2 Property, 1 MultiLanguageProperty"
    )
    assert GENERAL in panel.detail_label.text()
    shown = {t for t, b in panel.buttons.items() if not b.isHidden()}
    assert {"Move up", "Move to end", "Cut", "Copy", "Delete"} <= shown


def test_one_row_again_hides_the_buttons_of_the_panel(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    uw.select(large.view, rows[0], rows[1])

    uw.select(large.view, rows[1])

    panel = large.window.selectionDock.panel
    assert panel.header_label.text() != "Several elements selected"
    assert all(b.isHidden() for b in panel.buttons.values())


def test_move_to_end_on_two_rows_that_are_apart_moves_both_and_undo_restores(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    names = _order(large, GENERAL)
    original = snapshot(large.package.objStore)
    uw.select(large.view, rows[0], rows[2])

    large.window.selectionDock.panel.buttons["Move to end"].click()
    moved = _order(large, GENERAL)
    large.view.onUndo()

    assert moved == [names[1], *names[3:], names[0], names[2]]
    assert _order(large, GENERAL) == names
    assert snapshot(large.package.objStore) == original


def test_copy_of_several_rows_puts_the_json_of_them_on_the_clipboard(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    names = _order(large, GENERAL)
    uw.select(large.view, rows[0], rows[1])

    large.window.selectionDock.panel.buttons["Copy"].click()
    text = QApplication.clipboard().text()

    assert text.startswith("[")
    assert f'"idShort": "{names[0]}"' in text
    assert f'"idShort": "{names[1]}"' in text
    assert f'"idShort": "{names[2]}"' not in text


def test_delete_of_the_selection_removes_the_rows_and_undo_brings_them_back(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    names = _order(large, GENERAL)
    original = snapshot(large.package.objStore)
    uw.select(large.view, rows[0], rows[1])

    large.window.selectionDock.panel.buttons["Delete"].click()
    after = _order(large, GENERAL)
    large.view.onUndo()

    assert after == names[2:]
    assert _order(large, GENERAL) == names
    assert snapshot(large.package.objStore) == original


def test_the_panel_buttons_follow_the_read_mode(large: uw.UsageWindow) -> None:
    from aas_workingbench.application.editing import edit_mode

    rows = _children(large, GENERAL)
    uw.select(large.view, rows[0], rows[1])
    panel = large.window.selectionDock.panel

    edit_mode().set_editing(False)

    for text in ("Move to end", "Cut", "Delete"):
        assert not panel.buttons[text].isEnabled(), text
    assert panel.buttons["Copy"].isEnabled()


def test_shift_and_down_extend_the_selection_and_open_the_panel(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    large.view.setCurrentIndex(rows[0])
    large.view.setFocus()

    QTest.keyClick(
        large.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier
    )
    QTest.keyClick(
        large.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier
    )

    assert large.window.selectionDock.panel.header_label.text() == (
        "Several elements selected"
    )
    assert large.window.selectionDock.isVisible()


# Bulk changes and presets


def test_change_attribute_renames_three_rows_in_the_file_and_undo_restores(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_workingbench.ui.bulk_dialogs import ChangeAttributeDialog

    rows = _children(large, GENERAL)
    names = _order(large, GENERAL)
    original = snapshot(large.package.objStore)
    uw.select(large.view, rows[0], rows[1], rows[2])
    monkeypatch.setattr(
        ChangeAttributeDialog,
        "exec",
        lambda d: (
            d.set_pattern("{old}_{number|pad(2)}"),
            QDialog.DialogCode.Accepted,
        )[-1],
    )

    large.window.selectionDock.panel.buttons["Change attribute..."].click()
    renamed = _order(large, GENERAL)
    reopened = _saved(large, tmp_path, "renamed.aasx")
    in_file = [
        e.id_short
        for e in next(
            s for s in reopened.objStore if isinstance(s, model.Submodel)
        )
        .get_referable("GeneralInformation")
        .value
    ]
    large.view.onUndo()

    assert renamed[:3] == [f"{n}_0{i + 1}" for i, n in enumerate(names[:3])]
    assert in_file == renamed
    assert _order(large, GENERAL) == names
    assert snapshot(large.package.objStore) == original


def test_a_preset_qualifier_goes_to_each_selected_row_and_into_the_file(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_workingbench.ui.preset_dialogs import PresetDialog

    rows = _children(large, GENERAL)
    collection = _collection(large, GENERAL)
    names = _order(large, GENERAL)
    before = [len(collection.get_referable(n).qualifier) for n in names[:3]]
    uw.select(large.view, rows[0], rows[1], rows[2])
    monkeypatch.setattr(
        PresetDialog,
        "exec",
        lambda d: (
            d.choose("Expression semantic | Requirement"),
            QDialog.DialogCode.Accepted,
        )[-1],
    )

    large.view.registeredActions.find("preset.add_qualifier").trigger()
    after = [len(collection.get_referable(n).qualifier) for n in names[:3]]
    reopened = _saved(large, tmp_path, "preset.aasx")
    saved = next(
        s for s in reopened.objStore if isinstance(s, model.Submodel)
    ).get_referable(GENERAL)
    saved_types = [
        [q.type for q in saved.get_referable(n).qualifier][-1]
        for n in names[:3]
    ]

    assert after == [n + 1 for n in before]
    assert saved_types == ["ExpressionSemantic"] * 3
    assert large.boxes == []


def test_a_preset_on_a_selection_of_a_package_and_a_row_changes_nothing(
    large: uw.UsageWindow,
) -> None:
    rows = _children(large, GENERAL)
    package_row = large.view.model().index(0, 0)
    original = snapshot(large.package.objStore)
    uw.select(large.view, package_row, rows[0])
    action = large.view.registeredActions.find("preset.add_qualifier")

    action.trigger()

    assert snapshot(large.package.objStore) == original
    assert not large.package.commandStack.can_undo


# The package files panel


COVER = "/aasx/files/coverpage.png"
DECLARED_FILES = 6


def _select_cover(panel: Any) -> None:
    (row,) = [
        number
        for number in range(panel.table.rowCount())
        if panel.table.item(number, 0).text() == COVER
    ]
    panel.table.selectRow(row)


def test_the_files_panel_lists_the_stored_file_and_a_click_selects_a_row(
    large: uw.UsageWindow,
) -> None:
    large.window.filesDock.toggleViewAction().trigger()
    panel = large.window.filesDock.panel
    panel.follow_current_package()
    panel.refresh()

    _select_cover(panel)

    assert large.window.filesDock.isVisible()
    assert panel.table.rowCount() == DECLARED_FILES
    assert panel.table.item(panel.table.currentRow(), 1).text() == "image/png"
    assert panel.selected_name() == COVER
    assert panel.rename_button.isEnabled()
    assert panel.save_button.isEnabled()


def test_removing_the_file_in_the_panel_unlinks_nothing_silently_and_undo_returns_it(
    large: uw.UsageWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.ui import file_dialogs

    original = snapshot(large.package.objStore)
    asked: list[Any] = []
    monkeypatch.setattr(
        file_dialogs,
        "ask_remove_references",
        lambda references, parent=None: (
            asked.append(references) or file_dialogs.ReferenceAnswer.LEAVE
        ),
    )
    large.window.filesDock.show()
    panel = large.window.filesDock.panel
    panel.follow_current_package()
    panel.refresh()
    _select_cover(panel)

    panel.remove_button.click()
    panel.refresh()
    gone = (panel.table.rowCount(), COVER in large.package.fileStore)
    large.view.onUndo()
    panel.refresh()

    assert gone == (DECLARED_FILES - 1, False)
    assert panel.table.rowCount() == DECLARED_FILES
    assert "/aasx/files/coverpage.png" in large.package.fileStore
    assert snapshot(large.package.objStore) == original


# Tabs


def _without_files(
    window: uw.UsageWindow, rows: list[QModelIndex]
) -> list[QModelIndex]:
    """The rows that are not a File, whose tab would load a preview."""
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    return [r for r in rows if not isinstance(r.data(OBJECT_ROLE), model.File)]


def _open_in_new_tab(window: uw.UsageWindow, index: QModelIndex) -> None:
    window.view.setCurrentIndex(index)
    window.view.openInNewTabAct.trigger()
    QApplication.processEvents()


def test_many_tabs_open_close_and_keep_one(large: uw.UsageWindow) -> None:
    tabs = large.window.mainTabWidget
    rows = _without_files(large, _children(large, GENERAL))
    start = tabs.count()

    for row in rows:
        _open_in_new_tab(large, row)
    opened = tabs.count()
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    first_close = tabs.tabBar().tabButton(
        0, tabs.tabBar().ButtonPosition.RightSide
    )
    first_close.click()
    after_one = tabs.count()
    tab_bar = tabs.tabBar()
    tab_bar.menuIndexTab = 2
    tab_bar.closeOthersAct.trigger()
    only = tabs.count()

    assert opened == start + len(rows)
    assert {row.data() for row in rows} <= set(titles)
    assert after_one == opened - 1
    assert only == 1
    assert tabs.tabBar().tabsClosable() is False


def test_close_all_to_the_right_and_to_the_left_leave_the_chosen_tab(
    large: uw.UsageWindow,
) -> None:
    tabs = large.window.mainTabWidget
    rows = _without_files(large, _children(large, GENERAL))
    for row in rows:
        _open_in_new_tab(large, row)
    chosen = tabs.tabText(2)
    tab_bar = tabs.tabBar()

    tab_bar.menuIndexTab = 2
    tab_bar.closeAllRightAct.trigger()
    on_the_right = tabs.count()
    tab_bar.closeAllLeftAct.trigger()

    assert on_the_right == 3
    assert tabs.count() == 1
    assert tabs.tabText(0) == chosen


def test_a_tab_of_a_deleted_element_closes_itself(
    large: uw.UsageWindow,
) -> None:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    tabs = large.window.mainTabWidget
    rows = _without_files(large, _children(large, GENERAL))
    victim = rows[0].data(OBJECT_ROLE).id_short
    _open_in_new_tab(large, rows[0])
    with_tab = tabs.count()
    large.view.setCurrentIndex(rows[0])

    large.view.delClearAct.trigger()
    QApplication.processEvents()

    assert victim not in [tabs.tabText(i) for i in range(tabs.count())]
    assert tabs.count() == with_tab - 1
    large.view.onUndo()


def test_open_in_new_window_shows_the_row_in_a_window_of_its_own(
    large: uw.UsageWindow, qtbot: Any
) -> None:
    from aas_workingbench.widgets.tab import TabWidget

    rows = _without_files(large, _children(large, GENERAL))
    before = len(TabWidget.openedTabWidgets)
    large.view.setCurrentIndex(rows[1])

    large.view.openInNewWindowAct.trigger()
    QApplication.processEvents()
    windows = [
        w
        for w in TabWidget.openedTabWidgets
        if w is not large.window.mainTabWidget
    ]
    new = windows[-1]
    qtbot.addWidget(new)

    assert len(TabWidget.openedTabWidgets) == before + 1
    assert new.isVisible()
    assert new.currentWidget().packItem.data() == rows[1].data()
    new.close()
    new.deleteLater()
    # Python objects of the closed window are freed here, and not in the middle
    # of a paint of another view, where freeing a widget ends in a crash.
    QApplication.processEvents()
    gc.collect()
