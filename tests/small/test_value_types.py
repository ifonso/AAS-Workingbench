"""Parsing and formatting text as values of the XSD value types."""

import datetime
import decimal
import math

from basyx.aas.model import datatypes
from dateutil import relativedelta
import pytest

from aas_workingbench.domain import value_types
from aas_workingbench.domain.value_types import InvalidValueError


def test_xsd_types_list_every_type_that_the_sdk_names() -> None:
    assert set(value_types.XSD_TYPES) == set(datatypes.XSD_TYPE_NAMES)
    assert len(value_types.XSD_TYPES) == 31


def test_xsd_types_are_sorted_by_name() -> None:
    names = [value_types.type_name(t) for t in value_types.XSD_TYPES]

    assert names[:3] == ["xs:anyURI", "xs:base64Binary", "xs:boolean"]
    assert names[-1] == "xs:unsignedShort"


def test_type_from_name_accepts_the_name_with_and_without_prefix() -> None:
    assert value_types.type_from_name("xs:int") is datatypes.Int
    assert value_types.type_from_name("int") is datatypes.Int
    assert value_types.type_from_name(" xs:gYearMonth ") is datatypes.GYearMonth


def test_type_from_name_refuses_a_name_that_is_no_type() -> None:
    with pytest.raises(InvalidValueError, match="xs:string or xs:int"):
        value_types.type_from_name("xs:number")


def test_type_name_refuses_a_class_that_is_no_value_type() -> None:
    with pytest.raises(InvalidValueError, match="not an XSD value type"):
        value_types.type_name(list)


# Every type with a text that it accepts and the text that shows it again.
VALID = [
    (datatypes.String, "  keep spaces ", "  keep spaces "),
    (datatypes.String, "", ""),
    (datatypes.NormalizedString, "a b", "a b"),
    (
        datatypes.AnyURI,
        "https://example.com/a?b=c#d",
        "https://example.com/a?b=c#d",
    ),
    (datatypes.AnyURI, "", ""),
    (datatypes.Boolean, "true", "true"),
    (datatypes.Boolean, "false", "false"),
    (datatypes.Boolean, "1", "true"),
    (datatypes.Boolean, "0", "false"),
    (datatypes.Boolean, "True", "true"),
    (datatypes.Integer, "+12", "12"),
    (datatypes.Long, "-9223372036854775808", "-9223372036854775808"),
    (datatypes.Int, " 12 ", "12"),
    (datatypes.Short, "-32768", "-32768"),
    (datatypes.Byte, "127", "127"),
    (datatypes.NonPositiveInteger, "0", "0"),
    (datatypes.NegativeInteger, "-1", "-1"),
    (datatypes.NonNegativeInteger, "0", "0"),
    (datatypes.PositiveInteger, "1", "1"),
    (datatypes.UnsignedLong, "18446744073709551615", "18446744073709551615"),
    (datatypes.UnsignedInt, "4294967295", "4294967295"),
    (datatypes.UnsignedShort, "65535", "65535"),
    (datatypes.UnsignedByte, "255", "255"),
    (datatypes.Decimal, "12.50", "12.50"),
    (datatypes.Decimal, ".5", "0.5"),
    (datatypes.Decimal, "-3.", "-3"),
    (datatypes.Float, "1.5", "1.5"),
    (datatypes.Float, "-INF", "-INF"),
    (datatypes.Double, "2E10", "20000000000.0"),
    (datatypes.Double, "NaN", "NaN"),
    (datatypes.Duration, "P1Y2M3DT4H5M6S", "P1Y2M3DT4H5M6S"),
    (datatypes.Duration, "-PT0.5S", "-PT0.5S"),
    (datatypes.Duration, "PT90M", "PT1H30M"),
    (datatypes.DateTime, "2024-05-31T13:45:00", "2024-05-31T13:45:00"),
    (datatypes.DateTime, "2024-05-31T13:45:00Z", "2024-05-31T13:45:00+00:00"),
    (
        datatypes.DateTime,
        "2024-05-31T13:45:00.5+02:00",
        "2024-05-31T13:45:00.500000+02:00",
    ),
    (datatypes.Date, "2024-02-29", "2024-02-29"),
    (datatypes.Date, "2024-05-31+02:00", "2024-05-31+02:00"),
    (datatypes.Time, "13:45:00", "13:45:00"),
    (datatypes.GYearMonth, "2024-05", "2024-05"),
    (datatypes.GYear, "2024", "2024"),
    (datatypes.GMonthDay, "--02-29", "--02-29"),
    (datatypes.GMonth, "--05", "--05"),
    (datatypes.GDay, "---31", "---31"),
    (datatypes.Base64Binary, "SGVsbG8=", "SGVsbG8="),
    (datatypes.HexBinary, "48656c", "48656c"),
    (datatypes.HexBinary, "48656C", "48656c"),
]


@pytest.mark.parametrize(
    ("value_type", "text", "shown"),
    VALID,
    ids=[f"{value_types.type_name(t)}-{s!r}" for t, s, _ in VALID],
)
def test_parse_gives_a_value_of_the_type_when_text_is_valid(
    value_type: type, text: str, shown: str
) -> None:
    value = value_types.parse(text, value_type)

    assert isinstance(value, value_type)
    assert value_types.format_value(value) == shown
    assert value_types.check(text, value_type) is None


# A text that no value of the type has, for each type that can refuse text.
INVALID = [
    (datatypes.NormalizedString, "two\nlines"),
    (datatypes.NormalizedString, "tab\there"),
    (datatypes.AnyURI, "has space"),
    (datatypes.AnyURI, "new\nline"),
    (datatypes.Boolean, "yes"),
    (datatypes.Integer, "abc"),
    (datatypes.Integer, "1_000"),
    (datatypes.Integer, "1.5"),
    (datatypes.Long, "9223372036854775808"),
    (datatypes.Int, "2147483648"),
    (datatypes.Short, "32768"),
    (datatypes.Byte, "128"),
    (datatypes.NonPositiveInteger, "1"),
    (datatypes.NegativeInteger, "0"),
    (datatypes.NonNegativeInteger, "-1"),
    (datatypes.PositiveInteger, "0"),
    (datatypes.UnsignedLong, "18446744073709551616"),
    (datatypes.UnsignedInt, "4294967296"),
    (datatypes.UnsignedShort, "65536"),
    (datatypes.UnsignedByte, "256"),
    (datatypes.Decimal, "1e3"),
    (datatypes.Decimal, "NaN"),
    (datatypes.Decimal, "1,5"),
    (datatypes.Float, "3.5e38"),
    (datatypes.Float, "inf"),
    (datatypes.Float, "1.2.3"),
    (datatypes.Double, "1e400"),
    (datatypes.Double, "nan"),
    (datatypes.Double, "infinity"),
    (datatypes.Duration, "1h"),
    (datatypes.Duration, "P"),
    (datatypes.Duration, "PT"),
    (datatypes.Duration, "P1YT"),
    (datatypes.DateTime, "2024-13-01T00:00:00"),
    (datatypes.DateTime, "2024-05-31"),
    (datatypes.DateTime, "-0001-01-01T00:00:00"),
    (datatypes.DateTime, "12345-01-01T00:00:00"),
    (datatypes.Date, "2024-02-30"),
    (datatypes.Date, "31.05.2024"),
    (datatypes.Time, "25:00:00"),
    (datatypes.GYearMonth, "2024-13"),
    (datatypes.GYear, "24"),
    (datatypes.GMonthDay, "--02-30"),
    (datatypes.GMonthDay, "--13-01"),
    (datatypes.GMonth, "--13"),
    (datatypes.GDay, "---32"),
    (datatypes.Base64Binary, "SGVsbG8"),
    (datatypes.Base64Binary, "SGV!bG8="),
    (datatypes.HexBinary, "486"),
    (datatypes.HexBinary, "4G"),
]


@pytest.mark.parametrize(
    ("value_type", "text"),
    INVALID,
    ids=[f"{value_types.type_name(t)}-{s!r}" for t, s in INVALID],
)
def test_parse_refuses_text_that_the_type_does_not_have(
    value_type: type, text: str
) -> None:
    with pytest.raises(InvalidValueError):
        value_types.parse(text, value_type)

    message = value_types.check(text, value_type)
    assert message is not None
    assert value_types.type_name(value_type) in message


@pytest.mark.parametrize(
    ("value_type", "lowest", "highest"),
    [
        (datatypes.Long, -(2**63), 2**63 - 1),
        (datatypes.Int, -(2**31), 2**31 - 1),
        (datatypes.Short, -(2**15), 2**15 - 1),
        (datatypes.Byte, -(2**7), 2**7 - 1),
        (datatypes.NonPositiveInteger, None, 0),
        (datatypes.NegativeInteger, None, -1),
        (datatypes.NonNegativeInteger, 0, None),
        (datatypes.PositiveInteger, 1, None),
        (datatypes.UnsignedLong, 0, 2**64 - 1),
        (datatypes.UnsignedInt, 0, 2**32 - 1),
        (datatypes.UnsignedShort, 0, 2**16 - 1),
        (datatypes.UnsignedByte, 0, 2**8 - 1),
    ],
    ids=lambda value: (
        value_types.type_name(value) if isinstance(value, type) else str(value)
    ),
)
def test_parse_accepts_the_limits_and_refuses_one_beyond(
    value_type: type, lowest: int | None, highest: int | None
) -> None:
    if lowest is not None:
        assert value_types.parse(str(lowest), value_type) == lowest
        with pytest.raises(InvalidValueError, match="out of the range"):
            value_types.parse(str(lowest - 1), value_type)
    if highest is not None:
        assert value_types.parse(str(highest), value_type) == highest
        with pytest.raises(InvalidValueError, match="out of the range"):
            value_types.parse(str(highest + 1), value_type)


def test_parse_keeps_all_digits_when_integer_is_beyond_64_bits() -> None:
    digits = "123456789" * 20

    value = value_types.parse(digits, datatypes.Integer)

    assert value == int(digits)
    assert value_types.format_value(value) == digits


def test_parse_refuses_an_integer_with_more_digits_than_python_reads() -> None:
    with pytest.raises(InvalidValueError, match="out of the range"):
        value_types.parse("9" * 5000, datatypes.Integer)


def test_parse_keeps_the_exact_digits_when_decimal_has_many_places() -> None:
    value = value_types.parse("0.1234567890123456789", datatypes.Decimal)

    assert value == decimal.Decimal("0.1234567890123456789")


def test_format_value_never_uses_an_exponent_when_decimal_is_tiny() -> None:
    value = decimal.Decimal("0.0000001")

    assert value_types.format_value(value) == "0.0000001"


def test_parse_reads_the_largest_float_and_double() -> None:
    assert value_types.parse("3.4028234663852886e38", datatypes.Float) == (
        3.4028234663852886e38
    )
    assert value_types.parse("1.7976931348623157e308", datatypes.Double) == (
        1.7976931348623157e308
    )


def test_parse_gives_infinity_and_not_a_number_for_their_literals() -> None:
    assert value_types.parse("INF", datatypes.Double) == math.inf
    assert value_types.parse("+INF", datatypes.Double) == math.inf
    assert value_types.parse("-INF", datatypes.Float) == -math.inf
    assert math.isnan(value_types.parse("NaN", datatypes.Double))


def test_parse_reads_a_whole_number_as_a_double() -> None:
    value = value_types.parse("3", datatypes.Double)

    assert isinstance(value, float)
    assert value == 3.0


def test_parse_ignores_spaces_around_a_value_except_for_strings() -> None:
    assert value_types.parse("  7  ", datatypes.Int) == 7
    assert value_types.parse("  a  ", datatypes.String) == "  a  "


def test_parse_reads_a_duration_as_a_relative_delta() -> None:
    value = value_types.parse("P1Y2M3DT4H5M6S", datatypes.Duration)

    assert value == relativedelta.relativedelta(
        years=1, months=2, days=3, hours=4, minutes=5, seconds=6
    )


def test_parse_reads_the_time_zone_of_a_date_and_time() -> None:
    value = value_types.parse("2024-05-31T13:45:00+02:00", datatypes.DateTime)

    assert value.utcoffset() == datetime.timedelta(hours=2)


def test_parse_reads_midnight_as_24_hours_as_the_next_day() -> None:
    value = value_types.parse("2024-05-31T24:00:00", datatypes.DateTime)

    assert value == datetime.datetime(2024, 6, 1, 0, 0, 0)


def test_parse_reads_base64_and_hex_as_bytes() -> None:
    assert value_types.parse("SGVsbG8=", datatypes.Base64Binary) == b"Hello"
    assert value_types.parse("48656c6c6f", datatypes.HexBinary) == b"Hello"


def test_parse_ignores_line_breaks_inside_base64() -> None:
    value = value_types.parse("SGVs\nbG8=", datatypes.Base64Binary)

    assert value == b"Hello"


def test_parse_says_what_is_missing_when_text_is_empty() -> None:
    message = value_types.check("", datatypes.Int)

    assert message == "A value is required, it cannot be empty"


def test_parse_names_the_text_and_the_type_in_the_message() -> None:
    message = value_types.check("abc", datatypes.Int)

    assert message == (
        "'abc' is not a valid xs:int: it must be a whole number such as 12 or -3"
    )


def test_parse_shortens_long_text_in_the_message() -> None:
    message = value_types.check("x" * 100, datatypes.Int)

    assert message is not None
    assert message.startswith(f"'{'x' * 37}...' is not a valid xs:int")


def test_parse_explains_the_day_when_the_month_does_not_have_it() -> None:
    message = value_types.check("2024-02-30", datatypes.Date)

    assert message is not None
    assert "day is out of range for month" in message


def test_convert_keeps_the_text_when_a_string_becomes_an_integer() -> None:
    value = value_types.convert("12", datatypes.Int)

    assert value == 12
    assert isinstance(value, datatypes.Int)


def test_convert_keeps_the_number_when_an_int_becomes_a_double() -> None:
    value = value_types.convert(datatypes.Int(3), datatypes.Double)

    assert value == 3.0
    assert isinstance(value, float)


def test_convert_refuses_when_the_text_is_no_value_of_the_new_type() -> None:
    with pytest.raises(InvalidValueError, match="xs:int"):
        value_types.convert("abc", datatypes.Int)


def test_convert_refuses_when_the_number_is_beyond_the_new_type() -> None:
    with pytest.raises(InvalidValueError, match="out of the range"):
        value_types.convert(datatypes.Int(300), datatypes.Byte)


def test_convert_refuses_when_a_date_should_become_a_date_and_time() -> None:
    value = value_types.parse("2024-05-31", datatypes.Date)

    with pytest.raises(InvalidValueError, match="xs:dateTime"):
        value_types.convert(value, datatypes.DateTime)


@pytest.mark.parametrize(
    ("value_type", "ordered"),
    [
        (datatypes.Int, True),
        (datatypes.Integer, True),
        (datatypes.Decimal, True),
        (datatypes.Double, True),
        (datatypes.Date, True),
        (datatypes.DateTime, True),
        (datatypes.Time, True),
        (datatypes.String, False),
        (datatypes.Boolean, False),
        (datatypes.Duration, False),
        (datatypes.GYear, False),
        (datatypes.HexBinary, False),
    ],
)
def test_is_ordered_is_true_when_values_of_the_type_can_be_compared(
    value_type: type, ordered: bool
) -> None:
    assert value_types.is_ordered(value_type) is ordered


def test_check_range_refuses_a_minimum_above_the_maximum() -> None:
    message = value_types.check_range(
        datatypes.Int(5), datatypes.Int(3), datatypes.Int
    )

    assert message == "The minimum 5 is more than the maximum 3"


def test_check_range_accepts_equal_limits() -> None:
    assert (
        value_types.check_range(
            datatypes.Int(3), datatypes.Int(3), datatypes.Int
        )
        is None
    )


def test_check_range_accepts_a_range_with_one_missing_limit() -> None:
    assert value_types.check_range(None, 3, datatypes.Int) is None
    assert value_types.check_range(3, None, datatypes.Int) is None


def test_check_range_compares_dates() -> None:
    first = value_types.parse("2024-05-31", datatypes.Date)
    second = value_types.parse("2024-01-01", datatypes.Date)

    message = value_types.check_range(first, second, datatypes.Date)

    assert message == (
        "The minimum 2024-05-31 is more than the maximum 2024-01-01"
    )


def test_check_range_compares_decimals_exactly() -> None:
    low = decimal.Decimal("0.1000000000000000000001")
    high = decimal.Decimal("0.1")

    assert value_types.check_range(low, high, datatypes.Decimal) is not None


def test_check_range_does_not_compare_strings() -> None:
    assert value_types.check_range("b", "a", datatypes.String) is None


def test_check_range_does_not_compare_not_a_number() -> None:
    assert value_types.check_range(math.nan, 1.0, datatypes.Double) is None


def test_check_range_does_not_compare_a_time_with_and_without_zone() -> None:
    aware = value_types.parse("2024-05-31T10:00:00Z", datatypes.DateTime)
    naive = value_types.parse("2024-05-31T09:00:00", datatypes.DateTime)

    assert value_types.check_range(aware, naive, datatypes.DateTime) is None


def test_keeps_whitespace_is_true_for_strings_only() -> None:
    assert value_types.keeps_whitespace(datatypes.String) is True
    assert value_types.keeps_whitespace(datatypes.NormalizedString) is True
    assert value_types.keeps_whitespace(datatypes.Int) is False
    assert value_types.keeps_whitespace(datatypes.AnyURI) is False


def test_cast_value_gives_an_int_the_type_when_it_fits() -> None:
    value = value_types.cast_value(7, datatypes.Short)

    assert value == 7
    assert isinstance(value, datatypes.Short)


def test_cast_value_refuses_an_int_beyond_the_range_of_the_type() -> None:
    with pytest.raises(InvalidValueError, match="xs:byte"):
        value_types.cast_value(300, datatypes.Byte)


def test_cast_value_refuses_a_float_for_an_integer_type() -> None:
    with pytest.raises(InvalidValueError, match="xs:int"):
        value_types.cast_value(1.5, datatypes.Int)
