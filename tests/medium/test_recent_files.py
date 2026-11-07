"""The actions of the recent files open one file, once, however often they refresh."""

from typing import Any

from PyQt6.QtWidgets import QMenu
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot


@pytest.fixture
def view(qapp: object, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> Any:
    """A package tree view whose `openPack` records the files it is asked for."""
    from aas_workingbench.treeviews import treeview_pack

    window = QWidget()
    qtbot.addWidget(window)
    tree = treeview_pack.PackTreeView(window)
    menu = QMenu(window)
    tree.recentFilesSeparator = menu.addSeparator()
    opened: list[str] = []

    def open_pack(file: str) -> None:
        opened.append(file)

    monkeypatch.setattr(tree, "openPack", open_pack)
    tree.opened = opened  # type: ignore[attr-defined]
    # qtbot holds its widgets weakly, so the window lives as long as the view.
    tree.holder = window  # type: ignore[attr-defined]
    return tree


def _remember(*files: str) -> None:
    from aas_workingbench.settings.app_settings import recent_settings

    recent_settings().setValue("recentFiles", list(files))


def test_a_recent_file_opens_once_after_the_list_was_refreshed_often(
    view: Any,
) -> None:
    _remember("C:/one.aasx")

    for _ in range(3):
        view.updateRecentFileActs()
    view.recentFileActs[0].trigger()

    assert view.opened == ["C:/one.aasx"]


def test_a_recent_action_opens_the_file_it_shows_now_and_not_an_earlier_one(
    view: Any,
) -> None:
    _remember("C:/old.aasx")
    view.updateRecentFileActs()
    _remember("C:/new.aasx", "C:/old.aasx")
    view.updateRecentFileActs()

    view.recentFileActs[0].trigger()
    view.recentFileActs[1].trigger()

    assert view.opened == ["C:/new.aasx", "C:/old.aasx"]


def test_the_actions_of_missing_files_are_hidden(view: Any) -> None:
    _remember("C:/one.aasx")

    view.updateRecentFileActs()

    shown = [act.isVisible() for act in view.recentFileActs]
    assert shown[0] is True
    assert not any(shown[1:])
