"""The start of the window, before a package is open."""

from pathlib import Path
from collections.abc import Iterator

from PyQt6.QtCore import QMimeData
from PyQt6.QtCore import QPointF
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QDropEvent
from PyQt6.QtWidgets import QLabel
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.ui.empty_state import EmptyState


class Start:
    """An empty state with the actions that the window gives it."""

    def __init__(self, qtbot: QtBot) -> None:
        self.opened: list[str] = []
        self.open_runs = 0
        self.open_action = QAction("Open", statusTip="Open an AAS file")
        self.open_action.triggered.connect(self._count_open)
        self.new_actions = [QAction("New as json"), QAction("New as aasx")]
        self.recent = [QAction("") for _ in range(3)]
        for action in self.recent:
            action.setVisible(False)
        self.recent_runs: list[int] = []
        for place, action in enumerate(self.recent):
            action.triggered.connect(
                lambda _=False, at=place: self.recent_runs.append(at)
            )
        self.widget = EmptyState(
            self.open_action,
            self.new_actions,
            self.recent,
            self.opened.append,
        )
        qtbot.addWidget(self.widget)
        self.widget.resize(600, 500)
        self.widget.show()

    def _count_open(self) -> None:
        self.open_runs += 1

    def recent_texts(self) -> list[str]:
        return [
            button.text()
            for button in self.widget.recent_buttons
            if button.isVisibleTo(self.widget)
        ]


@pytest.fixture
def start(qapp: object, qtbot: QtBot) -> Iterator[Start]:
    yield Start(qtbot)


def test_open_runs_the_open_action(start: Start) -> None:
    start.widget.open_button.click()

    assert start.open_runs == 1


def test_open_is_the_main_action(start: Start) -> None:
    assert start.widget.open_button.property("primary") is True


def test_new_offers_each_kind_of_file(start: Start) -> None:
    menu = start.widget.new_button.menu()

    assert menu is not None
    assert [action.text() for action in menu.actions()] == [
        "New as json",
        "New as aasx",
    ]


def test_no_recent_file_leaves_no_list(start: Start) -> None:
    assert start.recent_texts() == []
    title = start.widget.findChild(QLabel, "emptyRecentTitle")
    assert title is not None
    assert not title.isVisibleTo(start.widget)


def test_the_recent_files_follow_their_actions(start: Start) -> None:
    start.recent[0].setText("..one.aasx")
    start.recent[0].setVisible(True)
    start.recent[1].setText("..two & more.aasx")
    start.recent[1].setVisible(True)

    assert start.recent_texts() == ["..one.aasx", "..two && more.aasx"]


def test_a_recent_file_opens_by_its_action(start: Start) -> None:
    start.recent[1].setText("..two.aasx")
    start.recent[1].setVisible(True)

    start.widget.recent_buttons[1].click()

    assert start.recent_runs == [1]


def test_a_recent_file_that_is_gone_leaves_the_list(start: Start) -> None:
    start.recent[0].setText("..one.aasx")
    start.recent[0].setVisible(True)
    start.recent[0].setVisible(False)

    assert start.recent_texts() == []


def test_a_dropped_file_is_opened(start: Start, tmp_path: Path) -> None:
    # Paths of this system, as a drop gives them, so that the test holds on
    # Windows and on Linux alike.
    one = (tmp_path / "one.aasx").as_posix()
    two = (tmp_path / "two.json").as_posix()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(one), QUrl.fromLocalFile(two)])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    start.widget.dropEvent(event)

    assert [path.replace("\\", "/") for path in start.opened] == [one, two]


def test_the_start_accepts_drops(start: Start) -> None:
    assert start.widget.acceptDrops()
