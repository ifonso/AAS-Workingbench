"""A test does not write the settings or the recent files of the user.

A large test once wrote its temporary paths into the recent files of the
person who ran it, and the start panel listed them afterwards.
"""

from pathlib import Path

from PyQt6.QtCore import QSettings
from pytestqt.qtbot import QtBot


def test_the_recent_files_of_a_test_are_not_kept_where_the_user_keeps_theirs(
    qapp: object,
) -> None:
    from aas_workingbench.settings.app_settings import recent_settings

    store = recent_settings()

    assert store.format() == QSettings.Format.IniFormat
    assert Path(store.fileName()).name == "recent.ini"


def test_the_settings_of_a_test_are_not_the_settings_file_of_the_program(
    qapp: object,
) -> None:
    from aas_workingbench.settings import app_settings

    assert Path(app_settings.SETTINGS.fileName()) != app_settings.SETTINGS_FILE


def test_a_recent_file_is_written_to_the_store_of_the_test(
    qapp: object, qtbot: QtBot
) -> None:
    from PyQt6.QtWidgets import QWidget

    from aas_workingbench.settings.app_settings import recent_settings
    from aas_workingbench.treeviews.treeview_pack import PackTreeView

    window = QWidget()
    qtbot.addWidget(window)
    view = PackTreeView(window)

    view.updateRecentFiles("C:/somewhere/package.aasx")

    assert recent_settings().value("recentFiles") == [
        "C:/somewhere/package.aasx"
    ]


def test_each_test_starts_with_no_recent_file(qapp: object) -> None:
    from aas_workingbench.settings.app_settings import recent_settings

    assert recent_settings().value("recentFiles") is None
