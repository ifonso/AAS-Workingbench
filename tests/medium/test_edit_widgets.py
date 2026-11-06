"""Input widgets for values."""

import pytest
from pytestqt.qtbot import QtBot


@pytest.fixture
def bytes_edit(qapp: object, qtbot: QtBot):
    from aas_editor.widgets.editWidgets import BytesEdit

    widget = BytesEdit()
    qtbot.addWidget(widget)
    return widget


def test_bytes_edit_returns_bytes_when_text_is_a_bytes_literal(
    bytes_edit,
) -> None:
    bytes_edit.setPlainText("b'ab\\x00c'")

    assert bytes_edit.getObj2add() == b"ab\x00c"


def test_bytes_edit_returns_none_when_text_is_empty(bytes_edit) -> None:
    bytes_edit.setPlainText("")

    assert bytes_edit.getObj2add() is None


def test_bytes_edit_refuses_text_that_is_not_a_literal(bytes_edit) -> None:
    # An expression that starts with b' and ends with ' would have been run
    # by the former implementation.
    bytes_edit.setPlainText("b'a' + b'b'")

    with pytest.raises(ValueError, match="b'text'"):
        bytes_edit.getObj2add()


def test_bytes_edit_refuses_code_that_would_run_a_command(bytes_edit) -> None:
    bytes_edit.setPlainText("b'' if __import__('os').getcwd() else b'x'")

    with pytest.raises(ValueError, match="b'text'"):
        bytes_edit.getObj2add()


def test_bytes_edit_refuses_text_when_literal_is_not_bytes(bytes_edit) -> None:
    bytes_edit.setPlainText("'text'")

    with pytest.raises(ValueError, match="b'text'"):
        bytes_edit.getObj2add()
