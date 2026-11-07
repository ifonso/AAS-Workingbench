"""Strings and texts with line breaks can be typed, not only shown."""

from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.factories import make_multi_language_property
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID
from tests.medium.forms import answering
from tests.serialization import snapshot

TWO_LINES = "first line\nsecond line"


@pytest.fixture
def edit(qapp: object) -> Any:
    from aas_workingbench.ui.value_editor import ValueEdit

    def make(value_type: Any = datatypes.String) -> ValueEdit:
        return ValueEdit(value_type)

    return make


def test_a_string_is_entered_in_a_box_of_several_lines(edit: Any) -> None:
    field = edit(datatypes.String)

    field.set_text(TWO_LINES)

    assert field.is_multiline()
    assert field.value() == TWO_LINES
    assert field.problem() is None


@pytest.mark.parametrize(
    "value_type",
    [
        datatypes.NormalizedString,
        datatypes.Int,
        datatypes.Date,
        datatypes.AnyURI,
    ],
)
def test_every_other_type_stays_a_line(edit: Any, value_type: Any) -> None:
    field = edit(value_type)

    assert not field.is_multiline()


def test_a_normalized_string_refuses_a_line_break_with_the_reason(
    edit: Any,
) -> None:
    field = edit(datatypes.NormalizedString)

    field.set_text(TWO_LINES)

    assert "must not contain line breaks" in (field.problem() or "")


def test_windows_line_breaks_come_back_as_they_were(edit: Any) -> None:
    field = edit(datatypes.String)

    field.set_text("one\r\ntwo\r\n")

    assert field.value() == "one\r\ntwo\r\n"


def test_an_edit_keeps_the_line_break_the_text_had(edit: Any) -> None:
    field = edit(datatypes.String)
    field.set_text("one\r\ntwo")

    field.area.appendPlainText("three")

    assert field.value() == "one\r\ntwo\r\nthree"


def test_a_lone_carriage_return_survives_when_nothing_is_edited(
    edit: Any,
) -> None:
    field = edit(datatypes.String)

    field.set_text("one\rtwo")

    assert field.value() == "one\rtwo"


def test_an_empty_string_is_a_value_and_an_empty_number_is_none(
    edit: Any,
) -> None:
    text = edit(datatypes.String)
    number = edit(datatypes.Int)

    assert (text.value(), number.value()) == ("", None)


def test_the_text_goes_along_when_the_type_changes(edit: Any) -> None:
    field = edit(datatypes.Int)
    field.set_text("12")

    field.set_value_type(datatypes.String)
    as_string = (field.is_multiline(), field.text())
    field.set_value_type(datatypes.Int)

    assert as_string == (True, "12")
    assert (field.is_multiline(), field.value()) == (False, 12)


def test_the_edit_dialog_of_a_property_takes_several_lines(
    lab_class: Any,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "old"))
    attrs = lab.attrs()

    def fill(dialog: Any) -> None:
        dialog.value_edit.set_text(TWO_LINES)

    lab.edit_in_dialog(attrs, "value", fill, dialog_class=lab.value_dialog)
    changed = snapshot(lab.package.objStore)
    lab.stack.undo()

    assert lab.save_and_reload() == snapshot(lab.package.objStore)
    lab.stack.redo()
    assert lab.element().value == TWO_LINES
    assert lab.save_and_reload() == changed


def test_a_new_property_is_made_with_several_lines(lab_class: Any) -> None:
    lab = lab_class()

    def fill(form: Any) -> None:
        form.choose_type(model.Property)
        form.type_text("id_short", ELEMENT_ID)
        form.choose("value_type", datatypes.String)
        form.type_text("value", TWO_LINES)

    lab.add(fill)

    assert lab.element().value == TWO_LINES
    assert lab.save_and_reload() == snapshot(lab.package.objStore)


def test_a_text_with_a_line_break_in_a_cell_is_not_changed_by_looking_at_it(
    lab_class: Any,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, TWO_LINES))
    attrs = lab.attrs()
    before = snapshot(lab.package.objStore)

    unchanged = lab.set(attrs, "value", TWO_LINES)

    assert unchanged
    assert not lab.stack.can_undo
    assert snapshot(lab.package.objStore) == before


def test_a_new_multi_language_property_takes_a_text_of_several_lines(
    lab_class: Any,
) -> None:
    lab = lab_class()

    def fill(form: Any) -> None:
        form.choose_type(model.MultiLanguageProperty)
        form.type_text("id_short", ELEMENT_ID)
        form.add_language("value", "en", TWO_LINES)

    lab.add(fill)

    assert dict(lab.element().value) == {"en": TWO_LINES}
    assert lab.save_and_reload() == snapshot(lab.package.objStore)


def test_the_text_of_a_language_is_a_box_and_its_language_a_line(
    lab_class: Any,
) -> None:
    from aas_workingbench.ui.value_editor import MultiLineTextEdit
    from PyQt6.QtWidgets import QLineEdit

    lab = lab_class()
    entries: list[Any] = []

    def fill(form: Any) -> None:
        form.choose_type(model.MultiLanguageProperty)
        form.type_text("id_short", ELEMENT_ID)
        form.add_language("value", "en", "text")
        entries.append(form.widget("value").inputWidgets[-1])

    lab.add(fill)

    entry = entries[0]
    assert isinstance(entry.paramWidgets["value"].widget, MultiLineTextEdit)
    assert isinstance(entry.paramWidgets["key"].widget, QLineEdit)


def test_an_existing_multi_language_text_keeps_its_line_breaks_in_the_dialog(
    lab_class: Any,
) -> None:
    lab = lab_class(
        make_multi_language_property(
            ELEMENT_ID, {"en": "a\r\nb", "de": TWO_LINES}
        )
    )
    attrs = lab.attrs()
    before = snapshot(lab.package.objStore)

    def fill(dialog: Any) -> None:
        pass  # accepted as it is

    lab.edit_in_dialog(attrs, "value", fill)

    assert snapshot(lab.package.objStore) == before
    assert dict(lab.element().value) == {"en": "a\r\nb", "de": TWO_LINES}


def test_one_language_entry_is_edited_in_a_box_of_several_lines(
    monkeypatch: pytest.MonkeyPatch, lab_class: Any
) -> None:
    from aas_workingbench.dialogs import EditObjDialog
    from aas_workingbench.ui.value_editor import MultiLineTextEdit

    lab = lab_class(make_multi_language_property(ELEMENT_ID, {"en": "old"}))
    attrs = lab.attrs()
    row = lab.row(attrs, "value", "DictItem 0")
    attrs.setCurrentIndex(row)
    boxes: list[Any] = []

    def fill(dialog: Any) -> None:
        entry = dialog.inputWidget
        boxes.append(entry.paramWidgets["value"].widget)
        boxes[0].setText(TWO_LINES)

    with answering(monkeypatch, EditObjDialog, fill, lab.shown.shown_errors):
        attrs.onEditCreate(None, row)

    assert isinstance(boxes[0], MultiLineTextEdit)
    assert dict(lab.element().value) == {"en": TWO_LINES}
