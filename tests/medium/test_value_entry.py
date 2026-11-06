"""Entering values that follow a value type, through the item models."""

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def entry(model_support):
    """Opens one element in a tab model and edits its attributes by name."""

    class Entry:
        def __init__(self, *elements: model.SubmodelElement) -> None:
            self.table = model_support.pack_table(
                make_submodel(elements=elements)
            )
            self.package = model_support.package_of(self.table)

        def details(self, *names: str):
            return model_support.detail_table(self.table, *SUBMODEL, *names)

        def set(self, details, attribute: str, value: object) -> bool:
            index = model_support.find(details, attribute)
            return details.setData(index, value, Qt.ItemDataRole.EditRole)

        def message(self, details, attribute: str) -> str:
            from aas_editor.settings.app_settings import DATA_CHANGE_FAILED_ROLE

            index = model_support.find(details, attribute)
            return details.data(index, DATA_CHANGE_FAILED_ROLE)

        def undo(self) -> None:
            self.package.commandStack.undo()

    return Entry


def test_typing_an_integer_sets_an_int_when_the_property_is_xs_int(
    entry,
) -> None:
    prop = make_property("p", 3, datatypes.Int)
    shown = entry(prop)
    details = shown.details("p")

    edited = shown.set(details, "value", "12")

    assert edited
    assert prop.value == 12
    assert isinstance(prop.value, datatypes.Int)


def test_typing_an_integer_sets_it_when_the_property_has_no_value(
    entry,
) -> None:
    prop = make_property("p", None, datatypes.Int)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", "12")

    assert prop.value == 12
    assert isinstance(prop.value, datatypes.Int)


def test_text_that_is_no_integer_is_refused_with_a_clear_message(entry) -> None:
    prop = make_property("p", 3, datatypes.Int)
    shown = entry(prop)
    details = shown.details("p")

    edited = shown.set(details, "value", "abc")

    assert not edited
    assert prop.value == 3
    assert shown.message(details, "value") == (
        "'abc' is not a valid xs:int: it must be a whole number such as 12 or -3"
    )
    assert not shown.package.commandStack.can_undo


def test_a_number_beyond_the_type_is_refused_with_the_range(entry) -> None:
    prop = make_property("p", 1, datatypes.Short)
    shown = entry(prop)
    details = shown.details("p")

    edited = shown.set(details, "value", "32768")

    assert not edited
    assert "out of the range of xs:short" in shown.message(details, "value")


@pytest.mark.parametrize(
    ("value_type", "text", "expected"),
    [
        (
            datatypes.Integer,
            "123456789012345678901234567890",
            123456789012345678901234567890,
        ),
        (datatypes.Long, "9223372036854775807", 9223372036854775807),
        (datatypes.UnsignedLong, "18446744073709551615", 18446744073709551615),
    ],
    ids=["integer", "long", "unsignedLong"],
)
def test_typing_a_number_beyond_32_bits_works_for_the_big_types(
    entry, value_type: type, text: str, expected: int
) -> None:
    prop = make_property("p", None, value_type)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", text)

    assert prop.value == expected
    assert isinstance(prop.value, value_type)


def test_typing_a_date_sets_a_date_when_the_property_is_xs_date(entry) -> None:
    prop = make_property("p", None, datatypes.Date)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", "2024-05-31")

    assert isinstance(prop.value, datatypes.Date)
    assert prop.value.isoformat() == "2024-05-31"


def test_typing_a_boolean_sets_a_bool_when_the_property_is_xs_boolean(
    entry,
) -> None:
    prop = make_property("p", None, datatypes.Boolean)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", "true")

    assert prop.value is True


def test_typing_text_keeps_the_spaces_when_the_property_is_xs_string(
    entry,
) -> None:
    prop = make_property("p", "a", datatypes.String)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", " 12 ")

    assert prop.value == " 12 "


def test_clearing_the_text_of_a_number_removes_the_value(entry) -> None:
    prop = make_property("p", 3, datatypes.Int)
    shown = entry(prop)

    shown.set(shown.details("p"), "value", "")

    assert prop.value is None


def test_typing_in_the_package_tree_parses_the_value_too(model_support) -> None:
    from aas_editor.settings.app_settings import DATA_CHANGE_FAILED_ROLE

    prop = make_property("p", 3, datatypes.Int)
    table = model_support.pack_table(make_submodel(elements=[prop]))
    cell = model_support.find_path(table, "", *SUBMODEL, "p").siblingAtColumn(
        model_support.column(table, "value")
    )

    assert table.setData(cell, "12", Qt.ItemDataRole.EditRole)
    assert isinstance(prop.value, datatypes.Int)
    assert not table.setData(cell, "x", Qt.ItemDataRole.EditRole)
    assert "xs:int" in table.data(cell, DATA_CHANGE_FAILED_ROLE)
    assert prop.value == 12


def test_an_edit_of_a_value_is_one_undoable_step(entry) -> None:
    prop = make_property("p", 3, datatypes.Int)
    shown = entry(prop)
    before = snapshot(shown.package.objStore)

    shown.set(shown.details("p"), "value", "12")
    shown.undo()

    assert snapshot(shown.package.objStore) == before


def test_the_text_of_a_value_is_refused_in_read_mode(entry) -> None:
    from aas_editor.application.editing import edit_mode

    prop = make_property("p", 3, datatypes.Int)
    shown = entry(prop)
    details = shown.details("p")
    edit_mode().set_editing(False)

    edited = shown.set(details, "value", "12")

    assert not edited
    assert prop.value == 3


class TestRange:
    def _range(self, minimum, maximum, value_type=datatypes.Int):
        return model.Range("r", value_type=value_type, min=minimum, max=maximum)

    def test_typing_the_limits_parses_them_for_the_value_type(
        self, entry
    ) -> None:
        rng = self._range(None, None)
        shown = entry(rng)
        details = shown.details("r")

        shown.set(details, "min", "1")
        shown.set(details, "max", "9")

        assert (rng.min, rng.max) == (1, 9)
        assert isinstance(rng.max, datatypes.Int)

    def test_a_minimum_above_the_maximum_is_refused(self, entry) -> None:
        rng = self._range(0, 10)
        shown = entry(rng)
        details = shown.details("r")

        edited = shown.set(details, "min", "11")

        assert not edited
        assert rng.min == 0
        assert shown.message(details, "min") == (
            "The minimum 11 is more than the maximum 10"
        )

    def test_a_maximum_below_the_minimum_is_refused(self, entry) -> None:
        rng = self._range(5, 10)
        shown = entry(rng)

        edited = shown.set(shown.details("r"), "max", "4")

        assert not edited
        assert rng.max == 10

    def test_equal_limits_are_accepted(self, entry) -> None:
        rng = self._range(5, 10)
        shown = entry(rng)

        assert shown.set(shown.details("r"), "max", "5")

    def test_text_that_is_no_number_is_refused(self, entry) -> None:
        rng = self._range(0, 10)
        shown = entry(rng)

        edited = shown.set(shown.details("r"), "max", "ten")

        assert not edited
        assert rng.max == 10

    def test_dates_are_compared(self, entry) -> None:
        low = datatypes.Date(2024, 5, 31)
        high = datatypes.Date(2024, 6, 30)
        rng = self._range(low, high, datatypes.Date)
        shown = entry(rng)

        edited = shown.set(shown.details("r"), "min", "2024-07-01")

        assert not edited


class TestChangingTheValueType:
    def test_the_value_follows_the_new_type_and_undo_gives_both_back(
        self, entry
    ) -> None:
        prop = make_property("p", "12", datatypes.String)
        shown = entry(prop)
        before = snapshot(shown.package.objStore)

        edited = shown.set(shown.details("p"), "value_type", datatypes.Int)
        converted = (prop.value_type, prop.value)
        shown.undo()

        assert edited
        assert converted == (datatypes.Int, 12)
        assert isinstance(converted[1], datatypes.Int)
        assert snapshot(shown.package.objStore) == before

    def test_the_change_is_refused_when_the_value_does_not_fit(
        self, entry
    ) -> None:
        prop = make_property("p", "abc", datatypes.String)
        shown = entry(prop)
        details = shown.details("p")

        edited = shown.set(details, "value_type", datatypes.Int)

        assert not edited
        assert (prop.value_type, prop.value) == (datatypes.String, "abc")
        assert shown.message(details, "value_type") == (
            "The value type cannot change to xs:int: the value 'abc' is not a "
            "valid xs:int: it must be a whole number such as 12 or -3. "
            "Clear or change the value first"
        )
        assert not shown.package.commandStack.can_undo

    def test_the_change_works_after_the_value_was_cleared(self, entry) -> None:
        prop = make_property("p", "abc", datatypes.String)
        shown = entry(prop)
        details = shown.details("p")

        shown.set(details, "value", None)
        edited = shown.set(details, "value_type", datatypes.Int)

        assert edited
        assert (prop.value_type, prop.value) == (datatypes.Int, None)

    def test_both_limits_of_a_range_are_converted(self, entry) -> None:
        rng = model.Range("r", datatypes.Int, 1, 9)
        shown = entry(rng)

        shown.set(shown.details("r"), "value_type", datatypes.Double)

        assert (rng.min, rng.max) == (1.0, 9.0)
        assert isinstance(rng.min, float)

    def test_the_other_rows_of_the_tab_show_the_converted_value(
        self, entry, model_support
    ) -> None:
        from aas_editor.settings.app_settings import VALUE_COLUMN

        prop = make_property("p", "12", datatypes.String)
        shown = entry(prop)
        details = shown.details("p")
        value_row = model_support.find(details, "value")

        shown.set(details, "value_type", datatypes.Int)

        item = details.objByIndex(value_row)
        assert isinstance(item.obj, datatypes.Int)
        assert (
            details.index(value_row.row(), VALUE_COLUMN).data(
                Qt.ItemDataRole.EditRole
            )
            == 12
        )

    def test_a_property_in_a_list_cannot_leave_the_type_of_the_list(
        self, entry
    ) -> None:
        item = make_property("a", 1, datatypes.Int)
        number_list = make_list(
            "Numbers",
            [item],
            type_value_list_element=model.Property,
            value_type_list_element=datatypes.Int,
        )
        shown = entry(number_list)
        # The child keeps the idShort it was given.
        details = shown.details("Numbers", "a")

        edited = shown.set(details, "value_type", datatypes.Long)

        assert not edited
        assert item.value_type is datatypes.Int
        assert "AASd-109" in shown.message(details, "value_type")
