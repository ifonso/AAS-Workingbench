"""Parses, formats, and checks text as values of the XSD value types.

A Property, a Range, a Qualifier, and an Extension hold a value of the type
that their `value_type` names (`DataTypeDefXsd`). The BaSyx SDK has the
parser for the lexical form, `basyx.aas.model.datatypes.from_xsd`, and the
writer, `xsd_repr`. This module uses both. It adds what the SDK does not
check, so that a typo is refused with a message instead of turning into a
different value:

* Python accepts `1_000`, ` 12`, `infinity`, and `nan` where XSD does not.
* `from_xsd` does not check the alphabet of `base64Binary` and `hexBinary`.
* A `float` or `double` that is too large silently becomes infinity.
* `anyURI` is not checked at all, and `gMonthDay` accepts `--02-31`.

The whitespace of every type except `string` and `normalizedString` is
collapsed, as XSD says, so ` 12 ` is the integer 12.

Example:
    >>> from basyx.aas.model import datatypes
    >>> parse("12", datatypes.Int)
    12
    >>> check("abc", datatypes.Int)
    "'abc' is not a valid xs:int: it must be a whole number such as 12 or -3"
"""

import calendar
import decimal
import math
import re
from typing import Any
from typing import cast

from basyx.aas.model import datatypes

XsdType = type[Any]

# The types in the order of the combo boxes: by name, as `sorted` orders them.
XSD_TYPES: tuple[XsdType, ...] = tuple(
    sorted(
        cast("dict[XsdType, str]", datatypes.XSD_TYPE_NAMES),
        key=lambda value_type: datatypes.XSD_TYPE_NAMES[value_type].lower(),
    )
)

_MAX_FLOAT = 3.4028235677973366e38  # the largest finite xs:float, rounded up

_INTEGER_TYPES: tuple[XsdType, ...] = (
    datatypes.Integer,
    datatypes.Long,
    datatypes.Int,
    datatypes.Short,
    datatypes.Byte,
    datatypes.NonPositiveInteger,
    datatypes.NegativeInteger,
    datatypes.NonNegativeInteger,
    datatypes.PositiveInteger,
    datatypes.UnsignedLong,
    datatypes.UnsignedInt,
    datatypes.UnsignedShort,
    datatypes.UnsignedByte,
)
_TEXT_TYPES: tuple[XsdType, ...] = (
    datatypes.String,
    datatypes.NormalizedString,
)
_ORDERED_TYPES: tuple[XsdType, ...] = (
    *_INTEGER_TYPES,
    datatypes.Decimal,
    datatypes.Float,
    datatypes.Double,
    datatypes.Date,
    datatypes.DateTime,
    datatypes.Time,
)

_INTEGER_RE = re.compile(r"[+-]?[0-9]+")
_DECIMAL_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)")
_FLOAT_RE = re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)([eE][+-]?[0-9]+)?")
_FLOAT_SPECIAL = {"INF": math.inf, "+INF": math.inf, "-INF": -math.inf}
_BASE64_RE = re.compile(
    r"([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?"
)
_HEX_RE = re.compile(r"([0-9A-Fa-f]{2})*")
_FORBIDDEN_IN_URI = re.compile(r"[\x00-\x20\x7f]")

_HINTS: dict[XsdType, str] = {
    datatypes.Boolean: "it must be true or false",
    datatypes.Duration: "it must look like P1Y2M3DT4H5M6S or PT30M",
    datatypes.DateTime: "it must look like 2024-05-31T13:45:00Z",
    datatypes.Date: "it must look like 2024-05-31",
    datatypes.Time: "it must look like 13:45:00",
    datatypes.GYearMonth: "it must look like 2024-05",
    datatypes.GYear: "it must look like 2024",
    datatypes.GMonthDay: "it must look like --05-31",
    datatypes.GMonth: "it must look like --05",
    datatypes.GDay: "it must look like ---31",
    datatypes.Base64Binary: "it must be Base64 text such as SGVsbG8=",
    datatypes.HexBinary: "it must be pairs of hexadecimal digits such as 48656C",
    datatypes.Float: "it must be a number such as 1.5, 2E10, INF, or NaN",
    datatypes.Double: "it must be a number such as 1.5, 2E10, INF, or NaN",
    datatypes.Decimal: "it must be a decimal number such as 12.5 or -3",
    datatypes.AnyURI: "it must not contain spaces or control characters",
    datatypes.NormalizedString: "it must not contain line breaks or tabs",
}
for _integer_type in _INTEGER_TYPES:
    _HINTS[_integer_type] = "it must be a whole number such as 12 or -3"


class InvalidValueError(ValueError):
    """Text does not fit the value type, or a value cannot change its type.

    The message is written for the user, so that a view can show it as it is.
    """


def type_name(value_type: XsdType) -> str:
    """Returns the XSD name of a value type, such as `xs:int`.

    Args:
        value_type: A class of `basyx.aas.model.datatypes`.

    Raises:
        InvalidValueError: If the class is not a value type.
    """
    try:
        return datatypes.XSD_TYPE_NAMES[value_type]
    except KeyError:
        raise InvalidValueError(
            f"'{getattr(value_type, '__name__', value_type)}' "
            "is not an XSD value type"
        ) from None


def type_from_name(name: str) -> XsdType:
    """Returns the value type for an XSD name such as `xs:int` or `int`.

    Args:
        name: The name, with or without the `xs:` prefix.

    Raises:
        InvalidValueError: If no value type has this name.
    """
    wanted = name.strip()
    if not wanted.startswith("xs:"):
        wanted = f"xs:{wanted}"
    try:
        return datatypes.XSD_TYPE_CLASSES[wanted]
    except KeyError:
        raise InvalidValueError(
            f"'{name}' is not an XSD value type such as xs:string or xs:int"
        ) from None


def keeps_whitespace(value_type: XsdType) -> bool:
    """Tells whether the type is made of text that spaces belong to.

    Args:
        value_type: A value type.

    Returns:
        True for `xs:string` and `xs:normalizedString`. All other types ignore
        the whitespace around the value.
    """
    return value_type in _TEXT_TYPES


def is_ordered(value_type: XsdType) -> bool:
    """Tells whether two values of the type can be compared as less or more.

    Args:
        value_type: A value type.

    Returns:
        True for numbers, dates, date and times, and times. A Range of any
        other type has no order to check.
    """
    return value_type in _ORDERED_TYPES


def parse(text: str, value_type: XsdType) -> Any:
    """Turns text into a value of the type.

    Args:
        text: What the user typed.
        value_type: The type to parse for, such as `datatypes.Int`.

    Returns:
        The value, an instance of `value_type`.

    Raises:
        InvalidValueError: If the text is not in the lexical space of the type
            or out of its range.
    """
    name = type_name(value_type)
    literal = text if keeps_whitespace(value_type) else text.strip()
    try:
        _precheck(literal, value_type)
        return _from_xsd(literal, value_type)
    except InvalidValueError:
        raise
    except (ValueError, NotImplementedError, OverflowError) as error:
        raise InvalidValueError(
            _describe(text, name, value_type, error)
        ) from None


def check(text: str, value_type: XsdType) -> str | None:
    """Tells why the text is no value of the type.

    Args:
        text: What the user typed.
        value_type: The type to check for.

    Returns:
        A message for the user, or None if the text is a valid value.
    """
    try:
        parse(text, value_type)
    except InvalidValueError as error:
        return str(error)
    return None


def format_value(value: Any) -> str:
    """Returns the text that shows and saves a value.

    This is the lexical form that the SDK writes into JSON and XML, except for
    a decimal, which never uses an exponent here.

    Args:
        value: A value of an XSD type.
    """
    if isinstance(value, decimal.Decimal) and value.is_finite():
        return format(value, "f")
    return datatypes.xsd_repr(value)


def convert(value: Any, value_type: XsdType) -> Any:
    """Gives a value another type through its text, or refuses.

    Args:
        value: The current value.
        value_type: The new type.

    Returns:
        The same text read as the new type, for example the string `"12"` as
        an `xs:int`, or the int 12 as an `xs:double`.

    Raises:
        InvalidValueError: If the text is not a value of the new type.
    """
    return parse(format_value(value), value_type)


def compare(first: Any, second: Any) -> int | None:
    """Compares two values of an ordered type.

    Args:
        first: A value.
        second: A value of the same type.

    Returns:
        A negative number, zero, or a positive number as `first` is less, equal
        or more. None if they cannot be compared, for example a number that
        is not a number, or a time with a time zone and one without.
    """
    try:
        if first != first or second != second:  # NaN, the only unequal self
            return None
        if first < second:
            return -1
        return 1 if first > second else 0
    except TypeError:
        return None


def check_range(minimum: Any, maximum: Any, value_type: XsdType) -> str | None:
    """Tells whether a Range with these limits is the wrong way around.

    Args:
        minimum: The lowest value, or None if it is missing.
        maximum: The highest value, or None if it is missing.
        value_type: The type of both.

    Returns:
        A message if `minimum` is more than `maximum`, otherwise None. A Range
        of an unordered type, or with a missing limit, is never refused.
    """
    if minimum is None or maximum is None or not is_ordered(value_type):
        return None
    if compare(minimum, maximum) == 1:
        return (
            f"The minimum {format_value(minimum)} is more than the "
            f"maximum {format_value(maximum)}"
        )
    return None


def _from_xsd(literal: str, value_type: XsdType) -> Any:
    if value_type in (datatypes.Float, datatypes.Double):
        return _parse_float(literal, value_type)
    if value_type is datatypes.Boolean:
        return datatypes.from_xsd(literal.lower(), value_type)
    return datatypes.from_xsd(literal, value_type)


def _parse_float(literal: str, value_type: XsdType) -> Any:
    if literal == "NaN":
        return value_type("nan")
    if literal in _FLOAT_SPECIAL:
        return value_type(_FLOAT_SPECIAL[literal])
    number = float(literal)
    limit = _MAX_FLOAT if value_type is datatypes.Float else math.inf
    if math.isinf(number) or abs(number) > limit:
        raise InvalidValueError(
            f"'{literal}' is too large for {type_name(value_type)}"
        )
    return value_type(number)


def _precheck(literal: str, value_type: XsdType) -> None:
    """Refuses text that Python reads but XSD does not."""
    if not literal and value_type not in (*_TEXT_TYPES, datatypes.AnyURI):
        raise InvalidValueError("A value is required, it cannot be empty")
    if value_type in _INTEGER_TYPES:
        _require(_INTEGER_RE, literal)
    elif value_type is datatypes.Decimal:
        _require(_DECIMAL_RE, literal)
    elif value_type in (datatypes.Float, datatypes.Double):
        if literal not in _FLOAT_SPECIAL and literal != "NaN":
            _require(_FLOAT_RE, literal)
    elif value_type is datatypes.Duration:
        _check_duration(literal)
    elif value_type is datatypes.Base64Binary:
        _require(_BASE64_RE, re.sub(r"\s+", "", literal))
    elif value_type is datatypes.HexBinary:
        _require(_HEX_RE, literal)
    elif value_type is datatypes.AnyURI:
        if _FORBIDDEN_IN_URI.search(literal):
            raise ValueError(
                "a URI cannot contain spaces or control characters"
            )
    elif value_type is datatypes.GMonthDay:
        _check_month_day(literal)


def _check_duration(literal: str) -> None:
    # The SDK pattern also matches "P", "PT", and "P1YT", which have no value.
    if literal.lstrip("-") == "P" or literal.endswith("T"):
        raise ValueError("a duration needs at least one number")


def _require(pattern: re.Pattern[str], literal: str) -> None:
    if pattern.fullmatch(literal) is None:
        raise ValueError("not in the lexical form")


def _check_month_day(literal: str) -> None:
    match = re.match(r"--(\d\d)-(\d\d)", literal)
    if match is None:
        return
    month, day = int(match[1]), int(match[2])
    if 1 <= month <= 12 and day > calendar.monthrange(2000, month)[1]:
        raise ValueError(f"month {month} has no day {day}")


def _describe(
    text: str, name: str, value_type: XsdType, error: Exception
) -> str:
    reason = str(error)
    if "out of the allowed range" in reason or "Exceeds the limit" in reason:
        detail = f"it is out of the range of {name}"
    elif isinstance(error, NotImplementedError):
        detail = "years before 1 and after 9999 are not supported"
    else:
        hint = _HINTS.get(value_type)
        # The SDK and datetime explain a few cases better than the hint does,
        # like a day that the month does not have.
        specific = reason and not any(
            part in reason
            for part in (
                "valid XSD",
                "not a valid",
                "lexical",
                "Invalid literal",
            )
        )
        if hint and specific:
            detail = f"{hint} ({reason})"
        else:
            detail = hint or reason
    shown = text if len(text) <= 40 else f"{text[:37]}..."
    return f"'{shown}' is not a valid {name}: {detail}"
