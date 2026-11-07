"""Save acts on one package and Save All on every one, and the keys differ."""

from pathlib import Path
from typing import Any

from PyQt6.QtGui import QKeySequence
import pytest
from tests.factories import make_property
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture
def two_packages(views: Any, tmp_path: Path) -> Any:
    """Two open packages, both changed, each with a file of its own."""
    shown = views()
    first = shown.open_package(make_submodel(elements=[make_property("Alpha")]))
    second = shown.open_package(make_submodel(elements=[make_property("Beta")]))
    first.file = tmp_path / "first.json"
    second.file = tmp_path / "second.json"
    first.changed = True
    second.changed = True
    shown.first, shown.second = first, second
    shown.targets = (first.file, second.file)
    shown.updated = []
    shown.view.unsavedPackagesChanged.connect(shown.updated.append)
    return shown


def test_save_is_ctrl_s_and_save_all_is_ctrl_shift_s(views: Any) -> None:
    view = views().view

    assert view.saveAct.shortcut() == QKeySequence("Ctrl+S")
    assert view.saveAllAct.shortcut() == QKeySequence("Ctrl+Shift+S")


def test_no_registered_action_uses_the_keys_of_save(views: Any) -> None:
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.location_actions import register_location_actions
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions

    # The application registers these before its first view.
    register_move_actions()
    register_paste_actions()
    register_location_actions()
    taken = {
        spec.shortcut
        for spec in default_registry().specs_for(ViewKind.ANY)
        if spec.shortcut is not None
    }
    shown = views()
    taken |= {
        shortcut
        for action in shown.view.registeredActions.actions
        for shortcut in action.shortcuts()
    }

    save_keys = (
        QKeySequence("Ctrl+S"),
        QKeySequence("Ctrl+Shift+S"),
        QKeySequence(QKeySequence.StandardKey.SaveAs),
    )

    assert not any(key in taken for key in save_keys if not key.isEmpty())


def test_save_saves_the_package_of_the_selected_row_only(
    two_packages: Any,
) -> None:
    two_packages.view.setCurrentIndex(
        two_packages.index("submodels", package=1)
    )

    two_packages.view.saveAct.trigger()

    first, second = two_packages.targets
    assert (first.exists(), second.exists()) == (False, True)
    assert (two_packages.first.changed, two_packages.second.changed) == (
        True,
        False,
    )


def test_save_names_the_package_that_it_saves(two_packages: Any) -> None:
    two_packages.view.setCurrentIndex(
        two_packages.index("submodels", package=1)
    )

    text = two_packages.view.saveAct.text()
    tip = two_packages.view.saveAct.toolTip()

    assert text == "Save second.json"
    assert "Ctrl+S" in tip


def test_save_without_a_selected_row_saves_the_only_open_package(
    views: Any, tmp_path: Path
) -> None:
    from PyQt6.QtCore import QModelIndex

    shown = views()
    package = shown.open_package(make_submodel())
    package.file = tmp_path / "only.json"
    package.changed = True
    shown.view.setCurrentIndex(QModelIndex())

    enabled = shown.view.saveAct.isEnabled()
    shown.view.saveAct.trigger()

    assert enabled and package.file.exists() and not package.changed


def test_save_all_saves_every_changed_package(two_packages: Any) -> None:
    two_packages.view.saveAllAct.trigger()

    assert all(target.exists() for target in two_packages.targets)
    assert not (two_packages.first.changed or two_packages.second.changed)


def test_save_all_says_how_many_packages_it_saves(two_packages: Any) -> None:
    two_packages.view.updateWindowModified()

    tip = two_packages.view.saveAllAct.toolTip()

    assert "2 packages" in tip and "Ctrl+Shift+S" in tip


def test_the_view_reports_the_number_of_unsaved_packages(
    two_packages: Any,
) -> None:
    two_packages.view.updateWindowModified()
    two_packages.view.setCurrentIndex(
        two_packages.index("submodels", package=1)
    )
    two_packages.view.saveAct.trigger()

    assert (two_packages.updated[0], two_packages.updated[-1]) == (2, 1)


def test_closing_a_package_with_changes_lowers_the_number(
    two_packages: Any,
) -> None:
    two_packages.view.updateWindowModified()

    two_packages.view.closeFile(two_packages.view.model().index(1, 0))

    assert two_packages.updated[-1] == 1


def test_a_package_that_opens_with_changes_is_counted(views: Any) -> None:
    from aas_workingbench.package import Package

    shown = views()
    updated: list[int] = []
    shown.view.unsavedPackagesChanged.connect(updated.append)
    package = Package()
    package.changed = True

    shown.table.addItem(package)

    assert updated[-1] == 1


@pytest.fixture
def tab_of_second(two_packages: Any, qtbot: Any) -> Any:
    """A tab that shows an element of the second package, in the window.

    The row of the tree stays in the first package, as it does when the
    selection does not follow the tabs ("autoscroll from source" is off).
    """
    from PyQt6.QtWidgets import QApplication

    from aas_workingbench.widgets.tab import TabWidget

    shown = two_packages
    shown.view.setCurrentIndex(shown.index("submodels", package=0))
    shown.tabs = TabWidget(shown.window, unclosable=True)
    shown.tabs.openItemInNewTab(
        shown.index("submodels", "Submodel", "Beta", package=1)
    )
    shown.tab = shown.tabs.currentWidget()
    shown.window.show()
    shown.window.activateWindow()
    qtbot.waitActive(shown.window)

    def focus(widget: Any) -> None:
        widget.setFocus()
        qtbot.waitUntil(lambda: QApplication.focusWidget() is widget)

    shown.focus = focus
    return shown


def test_save_with_the_focus_in_a_tab_saves_the_package_of_the_tab(
    tab_of_second: Any,
) -> None:
    tab_of_second.focus(tab_of_second.tab.attrsTreeView)

    tab_of_second.view.saveAct.trigger()

    first, second = tab_of_second.targets
    assert (first.exists(), second.exists()) == (False, True)
    assert (tab_of_second.first.changed, tab_of_second.second.changed) == (
        True,
        False,
    )


def test_save_with_the_focus_in_the_tree_saves_the_package_of_the_row(
    tab_of_second: Any,
) -> None:
    tab_of_second.focus(tab_of_second.view)

    tab_of_second.view.saveAct.trigger()

    first, second = tab_of_second.targets
    assert (first.exists(), second.exists()) == (True, False)


def test_save_names_the_package_of_the_tab_when_the_focus_moves_there(
    tab_of_second: Any,
) -> None:
    tab_of_second.focus(tab_of_second.view)
    before = tab_of_second.view.saveAct.text()

    tab_of_second.focus(tab_of_second.tab.attrsTreeView)
    after = tab_of_second.view.saveAct.text()

    assert (before, after) == ("Save first.json", "Save second.json")


def test_closing_a_package_saves_that_package_when_the_focus_is_in_a_tab(
    tab_of_second: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox, "exec", lambda box: QMessageBox.StandardButton.Save
    )
    tab_of_second.focus(tab_of_second.tab.attrsTreeView)

    tab_of_second.view.closeFileWithDialog()

    first, second = tab_of_second.targets
    assert (first.exists(), second.exists()) == (True, False)
