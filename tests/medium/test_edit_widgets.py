"""Input widgets for values, as the generated dialogs use them."""

from basyx.aas.model import base
from basyx.aas.model import datatypes
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.domain.value_types import InvalidValueError


@pytest.fixture
def bytes_edit(qapp: object, qtbot: QtBot):
    from aas_workingbench.widgets.editWidgets import BytesEdit

    widget = BytesEdit()
    qtbot.addWidget(widget)
    return widget


def test_bytes_edit_returns_the_text_as_utf8_bytes(bytes_edit) -> None:
    bytes_edit.editor.setPlainText("Größe")

    assert bytes_edit.getObj2add() == "Größe".encode()


def test_bytes_edit_returns_none_when_the_content_is_empty(bytes_edit) -> None:
    bytes_edit.editor.setPlainText("")

    assert bytes_edit.getObj2add() is None


def test_bytes_edit_gives_back_the_bytes_that_were_set(bytes_edit) -> None:
    bytes_edit.setVal(b"\x00\xff\x10binary")

    assert bytes_edit.getObj2add() == b"\x00\xff\x10binary"
    assert bytes_edit.mode() == "hex"


def test_bytes_edit_takes_text_that_looks_like_code_as_plain_text(
    bytes_edit,
) -> None:
    # The former implementation ran text that starts with b' and ends with '.
    bytes_edit.editor.setPlainText("b'' if __import__('os').getcwd() else b'x'")

    assert bytes_edit.getObj2add() == (
        b"b'' if __import__('os').getcwd() else b'x'"
    )


def test_bytes_edit_does_not_ask_for_a_python_literal(bytes_edit) -> None:
    bytes_edit.editor.setPlainText("b'ab'")

    assert bytes_edit.getObj2add() == b"b'ab'"


def test_bytes_edit_refuses_hex_that_is_no_bytes(bytes_edit) -> None:
    bytes_edit.setVal(b"\x00\x01")
    bytes_edit.editor.setPlainText("zz")

    with pytest.raises(InvalidValueError, match="not a hexadecimal digit"):
        bytes_edit.getObj2add()


def test_the_dialog_for_bytes_uses_the_binary_editor(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_workingbench.widgets.editWidgets import BytesEdit
    from aas_workingbench.widgets.editWidgets import SpecialInputWidget

    widget = SpecialInputWidget(bytes, objVal=b"hello")
    qtbot.addWidget(widget)

    assert isinstance(widget.widget, BytesEdit)
    assert widget.getObj2add() == b"hello"
    pre_object = widget.getPreObj()
    assert pre_object is not None
    assert pre_object.init() == b"hello"


def test_the_widget_for_a_value_type_lists_the_xsd_types(
    qapp: object, qtbot: QtBot
) -> None:
    from aas_workingbench.widgets.editWidgets import ValueTypeInputWidget
    from aas_workingbench.widgets.widgetUtil import InputWidgetUtil

    widget = InputWidgetUtil.getInputWidget(
        base.DataTypeDefXsd, objVal=datatypes.Int
    )
    qtbot.addWidget(widget)

    assert isinstance(widget, ValueTypeInputWidget)
    assert widget.getObj2add() is datatypes.Int
