"""The editors for values and for the bytes of a Blob."""

from pathlib import Path

from basyx.aas.model import datatypes
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFileDialog
import pytest
from pytestqt.qtbot import QtBot

from aas_workingbench.domain.blob_content import MAX_SHOWN_BYTES
from aas_workingbench.domain.value_types import InvalidValueError
from aas_workingbench.ui.value_editor import BinaryEdit
from aas_workingbench.ui.value_editor import ValueEdit
from aas_workingbench.ui.value_editor import ValueEditDialog
from aas_workingbench.ui.value_editor import ValueTypeBox


@pytest.fixture
def value_edit(qapp: object, qtbot: QtBot) -> ValueEdit:
    widget = ValueEdit(datatypes.Int)
    qtbot.addWidget(widget)
    widget.show()
    return widget


@pytest.fixture
def binary_edit(qapp: object, qtbot: QtBot) -> BinaryEdit:
    widget = BinaryEdit()
    qtbot.addWidget(widget)
    widget.show()
    return widget


class TestValueTypeBox:
    def test_lists_every_xsd_type_by_its_name(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox()
        qtbot.addWidget(box)

        names = [box.itemText(row) for row in range(box.count())]

        assert len(names) == 31
        assert names[:2] == ["xs:anyURI", "xs:base64Binary"]
        assert "xs:unsignedByte" in names

    def test_starts_with_the_given_type(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox(datatypes.Date)
        qtbot.addWidget(box)

        assert box.value_type() is datatypes.Date
        assert box.currentText() == "xs:date"

    def test_shows_xs_string_when_no_type_is_given_and_none_is_not_allowed(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox(None)
        qtbot.addWidget(box)

        assert box.value_type() is datatypes.String

    def test_offers_no_type_when_the_attribute_is_optional(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox(None, allow_none=True)
        qtbot.addWidget(box)

        assert box.value_type() is None
        assert box.count() == 32

    def test_tells_when_the_user_chooses_another_type(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox(datatypes.String)
        qtbot.addWidget(box)

        with qtbot.waitSignal(box.value_type_changed) as blocker:
            box.setCurrentIndex(box.findData(datatypes.Int))

        assert blocker.args == [datatypes.Int]

    def test_is_silent_when_the_program_sets_the_type(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        box = ValueTypeBox(datatypes.String)
        qtbot.addWidget(box)

        with qtbot.assertNotEmitted(box.value_type_changed):
            box.set_value_type(datatypes.Long)

        assert box.value_type() is datatypes.Long


class TestValueEdit:
    def test_gives_a_value_of_the_type(self, value_edit: ValueEdit) -> None:
        value_edit.set_text("12")

        value = value_edit.value()

        assert value == 12
        assert isinstance(value, datatypes.Int)
        assert value_edit.problem() is None

    def test_says_what_is_wrong_while_the_user_types(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_text("abc")

        assert value_edit.problem() == (
            "'abc' is not a valid xs:int: it must be a whole number "
            "such as 12 or -3"
        )
        assert value_edit.problem_label.isVisible()
        assert value_edit.problem_label.text() == value_edit.problem()

    def test_refuses_to_give_a_value_when_the_text_is_wrong(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_text("abc")

        with pytest.raises(InvalidValueError, match="xs:int"):
            value_edit.value()

    def test_hides_the_problem_when_the_text_is_fixed(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_text("abc")
        value_edit.set_text("1")

        assert not value_edit.problem_label.isVisible()

    def test_checks_the_text_again_when_the_type_changes(
        self, value_edit: ValueEdit, qtbot: QtBot
    ) -> None:
        value_edit.set_text("300")
        with qtbot.waitSignal(value_edit.changed):
            value_edit.set_value_type(datatypes.Byte)

        assert "out of the range of xs:byte" in (value_edit.problem() or "")
        assert not value_edit.problem_label.isHidden()

    def test_gives_none_when_the_text_of_a_number_is_empty(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_text("")

        assert value_edit.value() is None
        assert value_edit.problem() is None

    def test_gives_an_empty_string_when_the_text_of_a_string_is_empty(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_value_type(datatypes.String)
        value_edit.set_text("")

        assert value_edit.value() == ""

    def test_shows_a_value_in_its_lexical_form(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_value_type(datatypes.Date)

        value_edit.set_value(datatypes.Date(2024, 5, 31))

        assert value_edit.text() == "2024-05-31"

    def test_shows_nothing_for_a_missing_value(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_text("5")

        value_edit.set_value(None)

        assert value_edit.text() == ""

    def test_tells_the_form_of_the_value_in_the_placeholder(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_value_type(datatypes.DateTime)

        assert value_edit.line.placeholderText() == (
            "xs:dateTime: 2024-05-31T13:45:00Z"
        )

    def test_takes_a_number_beyond_32_bits_when_the_type_is_xs_long(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_value_type(datatypes.Long)
        value_edit.set_text("9223372036854775807")

        assert value_edit.value() == 9223372036854775807

    def test_offers_true_and_false_when_the_type_is_xs_boolean(
        self, value_edit: ValueEdit
    ) -> None:
        value_edit.set_value_type(datatypes.Boolean)

        completer = value_edit.line.completer()

        assert completer is not None
        model = completer.model()
        assert model is not None
        assert model.rowCount() == 2


class TestBinaryEdit:
    def test_shows_text_content_as_text(self, binary_edit: BinaryEdit) -> None:
        binary_edit.set_data(b"hello\nworld")

        assert binary_edit.mode() == "text"
        assert binary_edit.editor.toPlainText() == "hello\nworld"
        assert binary_edit.size_label.text() == "11 bytes, text"

    def test_shows_content_that_is_no_text_as_hex(
        self, binary_edit: BinaryEdit
    ) -> None:
        binary_edit.set_data(b"\x89PNG\r\n\x1a\n\x00")

        assert binary_edit.mode() == "hex"
        assert binary_edit.editor.toPlainText() == "89 50 4e 47 0d 0a 1a 0a 00"
        assert binary_edit.size_label.text() == "9 bytes, binary"

    def test_gives_back_the_same_bytes_when_the_user_changes_nothing(
        self, binary_edit: BinaryEdit
    ) -> None:
        original = b"line one\r\nline two\r\n"
        binary_edit.set_data(original)

        assert binary_edit.data() == original

    def test_gives_back_binary_bytes_exactly_when_the_user_changes_nothing(
        self, binary_edit: BinaryEdit
    ) -> None:
        original = bytes(range(256))
        binary_edit.set_data(original)

        assert binary_edit.data() == original

    def test_keeps_windows_line_breaks_when_the_user_edits_the_text(
        self, binary_edit: BinaryEdit
    ) -> None:
        binary_edit.set_data(b"one\r\ntwo\r\n")

        binary_edit.editor.setPlainText("one\ntwo\nthree\n")

        assert binary_edit.data() == b"one\r\ntwo\r\nthree\r\n"

    def test_encodes_typed_text_as_utf8(self, binary_edit: BinaryEdit) -> None:
        binary_edit.set_data(None)

        binary_edit.editor.setPlainText("Größe €")

        assert binary_edit.data() == "Größe €".encode()

    def test_reads_typed_hex_as_bytes(self, binary_edit: BinaryEdit) -> None:
        binary_edit.set_data(b"\x00\x01")

        binary_edit.editor.setPlainText("de ad be ef")

        assert binary_edit.data() == b"\xde\xad\xbe\xef"
        assert binary_edit.problem() is None

    def test_says_what_is_wrong_with_hex_that_is_no_bytes(
        self, binary_edit: BinaryEdit
    ) -> None:
        binary_edit.set_data(b"\x00\x01")

        binary_edit.editor.setPlainText("de a")

        assert "digit left over" in (binary_edit.problem() or "")
        assert not binary_edit.problem_label.isHidden()
        with pytest.raises(InvalidValueError):
            binary_edit.data()

    def test_switches_text_to_hex_and_back_without_changing_bytes(
        self, binary_edit: BinaryEdit
    ) -> None:
        binary_edit.set_data(b"Hi \xc3\xa4")

        binary_edit.view_box.setCurrentIndex(
            binary_edit.view_box.findData("hex")
        )
        binary_edit.view_box.activated.emit(1)
        in_hex = binary_edit.editor.toPlainText()
        binary_edit.view_box.setCurrentIndex(
            binary_edit.view_box.findData("text")
        )
        binary_edit.view_box.activated.emit(0)

        assert in_hex == "48 69 20 c3 a4"
        assert binary_edit.mode() == "text"
        assert binary_edit.editor.toPlainText() == "Hi ä"
        assert binary_edit.data() == b"Hi \xc3\xa4"

    def test_refuses_to_show_binary_content_as_text(
        self, binary_edit: BinaryEdit
    ) -> None:
        binary_edit.set_data(b"\xff\xfe\x00")

        binary_edit.view_box.setCurrentIndex(
            binary_edit.view_box.findData("text")
        )
        binary_edit.view_box.activated.emit(0)

        assert binary_edit.mode() == "hex"
        assert binary_edit.view_box.currentData() == "hex"
        assert "can only be shown as hex" in binary_edit.problem_label.text()
        assert binary_edit.data() == b"\xff\xfe\x00"

    def test_loads_a_file_and_suggests_its_media_type(
        self,
        binary_edit: BinaryEdit,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        qtbot: QtBot,
    ) -> None:
        picture = tmp_path / "picture.png"
        picture.write_bytes(b"\x89PNG\x00\x01")
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *args, **kwargs: (str(picture), "")),
        )

        with qtbot.waitSignal(binary_edit.content_type_suggested) as blocker:
            binary_edit.load_button.click()

        assert binary_edit.data() == b"\x89PNG\x00\x01"
        assert binary_edit.mode() == "hex"
        assert blocker.args == ["image/png"]

    def test_loads_nothing_when_the_file_dialog_is_cancelled(
        self, binary_edit: BinaryEdit, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        binary_edit.set_data(b"keep")
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *args, **kwargs: ("", "")),
        )

        binary_edit.load_button.click()

        assert binary_edit.data() == b"keep"

    def test_says_so_when_the_file_cannot_be_read(
        self,
        binary_edit: BinaryEdit,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *args, **kwargs: (str(tmp_path / "gone"), "")),
        )
        binary_edit.set_data(b"keep")

        binary_edit.load_button.click()

        assert "could not be read" in binary_edit.problem_label.text()
        assert binary_edit.data() == b"keep"

    def test_saves_the_exact_bytes_to_a_file(
        self,
        binary_edit: BinaryEdit,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "out.bin"
        asked: list[str] = []

        def choose(*args: object, **kwargs: object) -> tuple[str, str]:
            asked.append(str(args[2]))
            return str(target), ""

        monkeypatch.setattr(
            QFileDialog, "getSaveFileName", staticmethod(choose)
        )
        binary_edit.set_content_type("image/png")
        binary_edit.set_data(bytes(range(256)))

        binary_edit.save_button.click()

        assert target.read_bytes() == bytes(range(256))
        assert asked == ["content.png"]

    def test_saves_the_edited_text_to_a_file(
        self,
        binary_edit: BinaryEdit,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        target = tmp_path / "out.txt"
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *args, **kwargs: (str(target), "")),
        )
        binary_edit.editor.setPlainText("ä")

        binary_edit.save_button.click()

        assert target.read_bytes() == b"\xc3\xa4"

    def test_has_nothing_to_save_without_content(
        self, binary_edit: BinaryEdit, tmp_path: Path
    ) -> None:
        binary_edit.save_button.click()

        assert binary_edit.problem_label.text() == "There is no content to save"

    def test_clears_the_content(self, binary_edit: BinaryEdit) -> None:
        binary_edit.set_data(b"abc")

        binary_edit.clear_button.click()

        assert binary_edit.data() is None
        assert binary_edit.editor.toPlainText() == ""

    def test_does_not_show_content_that_is_too_large_but_keeps_it(
        self, binary_edit: BinaryEdit
    ) -> None:
        large = b"a" * (MAX_SHOWN_BYTES + 1)

        binary_edit.set_data(large)

        assert not binary_edit.is_content_shown()
        assert binary_edit.editor.toPlainText() == ""
        assert binary_edit.editor.isReadOnly()
        assert (
            binary_edit.size_label.text() == f"{len(large)} bytes (not shown)"
        )
        assert binary_edit.data() == large

    def test_tells_when_the_content_changes(
        self, binary_edit: BinaryEdit, qtbot: QtBot
    ) -> None:
        with qtbot.waitSignal(binary_edit.changed):
            binary_edit.editor.setPlainText("x")


class TestValueEditDialog:
    def test_returns_the_typed_value(self, qapp: object, qtbot: QtBot) -> None:
        dialog = ValueEditDialog(
            title="Edit value",
            objVal=datatypes.Int(3),
            value_type=datatypes.Int,
        )
        qtbot.addWidget(dialog)
        assert dialog.value_edit is not None

        dialog.value_edit.set_text("12")

        assert dialog.getObj2add() == 12
        assert dialog.windowTitle() == "Edit value"

    def test_shows_the_current_value(self, qapp: object, qtbot: QtBot) -> None:
        dialog = ValueEditDialog(
            objVal=datatypes.Date(2024, 5, 31), value_type=datatypes.Date
        )
        qtbot.addWidget(dialog)
        assert dialog.value_edit is not None

        assert dialog.value_edit.text() == "2024-05-31"

    def test_cannot_be_accepted_while_the_value_is_wrong(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        dialog = ValueEditDialog(value_type=datatypes.Int)
        qtbot.addWidget(dialog)
        assert dialog.value_edit is not None
        ok = dialog.buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert ok is not None

        dialog.value_edit.set_text("abc")
        broken = ok.isEnabled()
        dialog.value_edit.set_text("5")

        assert not broken
        assert ok.isEnabled()

    def test_clears_the_value(self, qapp: object, qtbot: QtBot) -> None:
        dialog = ValueEditDialog(
            objVal=datatypes.Int(3), value_type=datatypes.Int
        )
        qtbot.addWidget(dialog)

        assert dialog.clear_button is not None
        dialog.clear_button.click()

        assert dialog.getObj2add() is None

    def test_edits_the_bytes_of_a_blob(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        dialog = ValueEditDialog(
            objVal=b"\x00\x01", binary=True, content_type="image/png"
        )
        qtbot.addWidget(dialog)
        assert dialog.binary_edit is not None

        dialog.binary_edit.editor.setPlainText("ff 00")

        assert dialog.getObj2add() == b"\xff\x00"

    def test_ignores_the_arguments_of_the_generated_dialogs(
        self, qapp: object, qtbot: QtBot
    ) -> None:
        dialog = ValueEditDialog(
            parent=None,
            title="t",
            objTypeHint=int,
            rmDefParams=False,
            objVal=None,
            value_type=datatypes.Int,
        )
        qtbot.addWidget(dialog)

        assert dialog.getObj2add() is None
