"""Values that follow a value type, and changing the type."""

import decimal
from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.factories import make_list
from tests.factories import make_property

from aas_editor.application.changes import Change
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.edits import SetValueType
from aas_editor.domain import typed_values
from aas_editor.domain.value_types import InvalidValueError


def _range(
    value_type: type = datatypes.Int,
    minimum: Any = None,
    maximum: Any = None,
) -> model.Range:
    return model.Range("Range", value_type=value_type, min=minimum, max=maximum)


def test_value_attrs_names_the_attributes_that_hold_values() -> None:
    qualifier = model.Qualifier("kind", datatypes.String)
    extension = model.Extension("name", datatypes.String)

    assert typed_values.value_attrs(make_property()) == ("value",)
    assert typed_values.value_attrs(_range()) == ("min", "max")
    assert typed_values.value_attrs(qualifier) == ("value",)
    assert typed_values.value_attrs(extension) == ("value",)
    assert typed_values.value_attrs(model.Capability("c")) == ()


def test_is_value_type_attr_is_true_for_value_type_of_an_owner_with_values() -> (
    None
):
    assert typed_values.is_value_type_attr(make_property(), "value_type")
    assert not typed_values.is_value_type_attr(make_property(), "value")
    assert not typed_values.is_value_type_attr(
        model.Capability("c"), "value_type"
    )


def test_prepare_edit_parses_text_for_an_int_property() -> None:
    prop = make_property(value=None, value_type=datatypes.Int)

    value = typed_values.prepare_edit(prop, "value", "12")

    assert value == 12
    assert isinstance(value, datatypes.Int)


def test_prepare_edit_refuses_text_that_is_no_int() -> None:
    prop = make_property(value=None, value_type=datatypes.Int)

    with pytest.raises(InvalidValueError, match="'abc' is not a valid xs:int"):
        typed_values.prepare_edit(prop, "value", "abc")


def test_prepare_edit_keeps_text_for_a_string_property() -> None:
    prop = make_property(value=None, value_type=datatypes.String)

    assert typed_values.prepare_edit(prop, "value", " 12 ") == " 12 "


def test_prepare_edit_gives_none_when_text_is_empty_for_a_number() -> None:
    prop = make_property(value=3, value_type=datatypes.Int)

    assert typed_values.prepare_edit(prop, "value", "") is None


def test_prepare_edit_keeps_an_empty_string_for_a_string_property() -> None:
    prop = make_property(value="x", value_type=datatypes.String)

    assert typed_values.prepare_edit(prop, "value", "") == ""


def test_prepare_edit_keeps_none_when_clearing() -> None:
    prop = make_property(value=3, value_type=datatypes.Int)

    assert typed_values.prepare_edit(prop, "value", None) is None


def test_prepare_edit_casts_a_python_number_to_the_value_type() -> None:
    prop = make_property(value=None, value_type=datatypes.Int)

    value = typed_values.prepare_edit(prop, "value", 7)

    assert isinstance(value, datatypes.Int)


def test_prepare_edit_refuses_a_python_number_beyond_the_type() -> None:
    prop = make_property(value=None, value_type=datatypes.Byte)

    with pytest.raises(InvalidValueError, match="xs:byte"):
        typed_values.prepare_edit(prop, "value", 300)


def test_prepare_edit_refuses_a_value_for_an_extension_without_type() -> None:
    extension = model.Extension("name")

    with pytest.raises(InvalidValueError, match="Choose a value type"):
        typed_values.prepare_edit(extension, "value", "x")


def test_prepare_edit_parses_the_values_of_a_qualifier() -> None:
    qualifier = model.Qualifier("q", datatypes.Boolean)

    assert typed_values.prepare_edit(qualifier, "value", "true") is True


def test_prepare_edit_parses_a_big_integer_for_xs_integer() -> None:
    prop = make_property(value=None, value_type=datatypes.Integer)

    value = typed_values.prepare_edit(prop, "value", "123456789012345678901234")

    assert value == 123456789012345678901234


def test_prepare_edit_refuses_a_minimum_above_the_maximum() -> None:
    rng = _range(minimum=0, maximum=10)

    with pytest.raises(InvalidValueError, match="minimum 11 is more than"):
        typed_values.prepare_edit(rng, "min", "11")


def test_prepare_edit_refuses_a_maximum_below_the_minimum() -> None:
    rng = _range(minimum=5, maximum=10)

    with pytest.raises(InvalidValueError, match="maximum 4"):
        typed_values.prepare_edit(rng, "max", "4")


def test_prepare_edit_accepts_a_minimum_equal_to_the_maximum() -> None:
    rng = _range(minimum=0, maximum=10)

    assert typed_values.prepare_edit(rng, "min", "10") == 10


def test_prepare_edit_accepts_a_limit_when_the_other_is_missing() -> None:
    rng = _range(minimum=None, maximum=None)

    assert typed_values.prepare_edit(rng, "min", "100") == 100


def test_check_new_object_refuses_a_range_the_wrong_way_around() -> None:
    with pytest.raises(InvalidValueError, match="more than the maximum"):
        typed_values.check_new_object(_range(minimum=5, maximum=1))


def test_check_new_object_accepts_other_objects() -> None:
    typed_values.check_new_object(make_property())


def test_type_change_values_converts_the_value_through_its_text() -> None:
    prop = make_property(value="12", value_type=datatypes.String)

    values = typed_values.type_change_values(prop, datatypes.Int)

    assert values == {"value": 12}
    assert isinstance(values["value"], datatypes.Int)


def test_type_change_values_converts_both_limits_of_a_range() -> None:
    rng = _range(datatypes.Int, 1, 9)

    values = typed_values.type_change_values(rng, datatypes.Decimal)

    assert values == {"min": decimal.Decimal(1), "max": decimal.Decimal(9)}


def test_type_change_values_has_nothing_to_convert_when_there_is_no_value() -> (
    None
):
    prop = make_property(value=None, value_type=datatypes.Int)

    assert typed_values.type_change_values(prop, datatypes.Date) == {}


def test_type_change_values_refuses_when_the_value_does_not_fit() -> None:
    prop = make_property(value="abc", value_type=datatypes.String)

    with pytest.raises(InvalidValueError) as error:
        typed_values.type_change_values(prop, datatypes.Int)

    assert str(error.value) == (
        "The value type cannot change to xs:int: the value 'abc' is not a "
        "valid xs:int: it must be a whole number such as 12 or -3. "
        "Clear or change the value first"
    )


def test_type_change_values_refuses_when_one_limit_does_not_fit() -> None:
    rng = _range(datatypes.Int, 1, 300)

    with pytest.raises(InvalidValueError, match="the max .* out of the range"):
        typed_values.type_change_values(rng, datatypes.Byte)


def test_type_change_values_refuses_for_a_property_in_a_list_of_one_type() -> (
    None
):
    prop = make_property("p", 1, datatypes.Int)
    make_list(
        "Numbers", [prop], model.Property, value_type_list_element=datatypes.Int
    )

    with pytest.raises(InvalidValueError, match="AASd-109"):
        typed_values.type_change_values(prop, datatypes.Long)


def test_type_change_values_allows_the_type_the_list_needs() -> None:
    prop = make_property("p", 1, datatypes.Int)
    make_list(
        "Numbers", [prop], model.Property, value_type_list_element=datatypes.Int
    )

    assert typed_values.type_change_values(prop, datatypes.Int) == {"value": 1}


def test_type_change_values_refuses_to_remove_the_type_of_an_extension_value() -> (
    None
):
    extension = model.Extension("name", datatypes.String, "text")

    with pytest.raises(InvalidValueError, match="Clear the value first"):
        typed_values.type_change_values(extension, None)


def test_type_change_values_removes_the_type_of_an_extension_without_value() -> (
    None
):
    extension = model.Extension("name", datatypes.String)

    assert typed_values.type_change_values(extension, None) == {}


class TestSetValueType:
    """The command that changes the type and the values in one step."""

    def test_changes_type_and_value_and_undo_gives_both_back(self) -> None:
        prop = make_property(value="12", value_type=datatypes.String)
        stack = CommandStack()

        stack.push(SetValueType(ModelChangeObserver(), prop, datatypes.Int))
        after_push = (prop.value_type, prop.value)
        stack.undo()
        after_undo = (prop.value_type, prop.value)
        stack.redo()

        assert after_push == (datatypes.Int, 12)
        assert after_undo == (datatypes.String, "12")
        assert (prop.value_type, prop.value) == (datatypes.Int, 12)
        assert isinstance(prop.value, datatypes.Int)

    def test_converts_the_limits_of_a_range_together(self) -> None:
        rng = _range(datatypes.Int, 1, 9)
        stack = CommandStack()

        stack.push(SetValueType(ModelChangeObserver(), rng, datatypes.Double))
        stack.undo()

        assert (rng.value_type, rng.min, rng.max) == (datatypes.Int, 1, 9)
        assert isinstance(rng.min, datatypes.Int)

    def test_changes_nothing_and_refuses_when_the_value_does_not_fit(
        self,
    ) -> None:
        prop = make_property(value="abc", value_type=datatypes.String)

        with pytest.raises(InvalidValueError):
            SetValueType(ModelChangeObserver(), prop, datatypes.Int)

        assert (prop.value_type, prop.value) == (datatypes.String, "abc")

    def test_knows_when_it_would_change_nothing(self) -> None:
        prop = make_property(value="x", value_type=datatypes.String)

        command = SetValueType(ModelChangeObserver(), prop, datatypes.String)

        assert command.is_noop

    def test_reports_the_change_of_the_owner_when_applied_and_reverted(
        self,
    ) -> None:
        observer = ModelChangeObserver()
        received: list[Change] = []
        observer.subscribe(received.append)
        prop = make_property(value="1", value_type=datatypes.String)
        stack = CommandStack()

        stack.push(SetValueType(observer, prop, datatypes.Int))
        stack.undo()

        assert [change.target for change in received] == [prop, prop]

    def test_names_the_attributes_it_converts(self) -> None:
        rng = _range(datatypes.Int, None, 9)

        command = SetValueType(ModelChangeObserver(), rng, datatypes.Long)

        assert command.value_names == ("max",)
