"""The About dialog, and the contacts and credits that it reads."""

import re

import pytest
from PyQt6.QtWidgets import QMainWindow
from pytestqt.qtbot import QtBot


@pytest.fixture
def about_text(qapp: object, qtbot: QtBot) -> str:
    from aas_editor.widgets.messsageBoxes import AboutMessageBox

    parent = QMainWindow()
    qtbot.addWidget(parent)
    box = AboutMessageBox(parent)
    qtbot.addWidget(box)
    return box.text()


def _plain(rich: str) -> str:
    return re.sub(r"<[^>]+>", " ", rich)


def test_the_name_shown_to_users_is_aas_workingbench(
    qapp: object, about_text: str
) -> None:
    from aas_editor.settings.app_settings import APPLICATION_NAME
    from aas_editor.settings.app_settings import WINDOW_TITLE

    assert APPLICATION_NAME == "AAS Workingbench"
    assert WINDOW_TITLE.startswith("AAS Workingbench ")
    assert about_text.startswith("AAS Workingbench<br>")


def test_the_dialog_gives_the_contacts_of_this_project(
    about_text: str,
) -> None:
    assert "Contact: contato@ifonso.com.br<br>" in about_text
    assert "<a href='https://github.com/ifonso/AAS-Workingbench'>" in about_text
    assert "iat.rwth-aachen.de" not in about_text
    assert "garmaev@" not in about_text


def test_the_dialog_credits_the_project_that_this_one_is_based_on(
    about_text: str,
) -> None:
    assert (
        "Based on <a href='https://github.com/rwth-iat/aas_manager'>"
        "AAS Manager</a> by Igor Garmaev and RWTH Aachen IAT"
    ) in about_text
    contributors = _plain(about_text)
    assert "Igor Garmaev (original author)" in contributors
    assert "ifonso (maintainer)" in contributors


def test_the_report_links_lead_to_this_repository(qapp: object) -> None:
    from aas_editor.settings.app_settings import APPLICATION_LINK
    from aas_editor.settings.app_settings import CONTACT
    from aas_editor.settings.app_settings import REPORT_ERROR_LINK

    assert APPLICATION_LINK == "https://github.com/ifonso/AAS-Workingbench"
    assert REPORT_ERROR_LINK == (
        "https://github.com/ifonso/AAS-Workingbench/issues"
    )
    assert CONTACT == "contato@ifonso.com.br"


def test_the_stored_settings_of_users_keep_their_old_name(
    qapp: object,
) -> None:
    from aas_editor.settings.app_settings import IAT
    from aas_editor.settings.app_settings import SETTINGS_APPLICATION_NAME

    assert (IAT, SETTINGS_APPLICATION_NAME) == ("IAT", "AAS Manager")
