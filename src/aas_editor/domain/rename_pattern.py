"""The pattern language for changing an attribute of many objects at once.

A pattern is text with fields in braces. The text is copied as it is, and each
field is replaced by a value of the object that is being changed, which a
chain of filters can change on the way. The language is small on purpose: it
has no variables, no loops and no regular expressions, and nothing in it is
evaluated as code.

    ABC_{old}                           Foo   becomes ABC_Foo
    {old|upper}                         foo   becomes FOO
    Item{number|pad(3)}                 the 7th object becomes Item007
    {old|replace("Temp","Temperature")} TempMax becomes TemperatureMax

Grammar:

    pattern := ( text | '{{' | '}}' | field )*
    field   := '{' name ( '|' filter )* '}'
    filter  := name [ '(' argument ( ',' argument )* ')' ]
    argument:= whole number | "quoted text"

`{{` and `}}` are literal braces. In a quoted text, `\\"` is a quote and `\\\\`
is a backslash. Spaces around names, bars, commas, and parentheses are
ignored.

Fields:
    old      The current value of the attribute that is changed.
    idShort  The idShort of the object.
    parent   The idShort of its parent, or empty.
    type     The class of the object, such as Property.
    number   The position of the object among the selected ones, from 1.
    count    How many objects are selected.

Filters:
    upper, lower        Letter case of the whole text.
    capitalize          The first character in upper case, the rest unchanged.
    trim                Drops spaces at both ends.
    reverse             Reverses the characters.
    slice(a), slice(a,b)  The characters from a up to b, counted from 0.
                        A negative number counts from the end.
    replace("x","y")    Replaces every x by y. x must not be empty.
    remove("x")         Drops every x.
    strip_prefix("x")   Drops x from the start, if the text starts with it.
    strip_suffix("x")   Drops x from the end, if the text ends with it.
    default("x")        Gives x when the text is empty.
    pad(n), pad(n,"c")  Puts c (default 0) at the start up to n characters.
    add(n)              Adds the whole number n to a text that is a number.
    to_id_short         Repairs the text into a valid idShort.

Example:
    Numbering the selected elements::

        pattern = compile_pattern("Sensor{number|pad(2)}")
        render(pattern, PatternContext("Old", 3, 5, "Old", "", "Property"))
        # 'Sensor03'
"""

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import Final

from aas_editor.domain.ids import fix_id_short

MAX_PATTERN_CHARS: Final = 1000
"""The longest pattern that is accepted."""
MAX_RESULT_CHARS: Final = 10_000
"""The longest text a field, a filter, or a whole pattern may give."""

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"[+-]?[0-9]+")
_WHOLE_NUMBER = re.compile(r"[+-]?[0-9]+")

FIELD_NAMES: Final = ("old", "idShort", "parent", "type", "number", "count")
"""The fields of the language, in the order the documentation lists them."""

_Argument = int | str


class PatternError(ValueError):
    """A pattern that cannot be used, or a value it cannot be applied to.

    Attributes:
        position: Where in the pattern the problem is, counted from 0.
    """

    def __init__(self, message: str, position: int) -> None:
        """Creates the error.

        Args:
            message: What is wrong, for the user.
            position: Where in the pattern, counted from 0.
        """
        super().__init__(f"{message} (at position {position + 1})")
        self.position = position


@dataclass(frozen=True)
class PatternContext:
    """What the fields of a pattern give for one object.

    Attributes:
        old: The current value of the attribute that is changed.
        number: The position of the object among the selected ones, from 1.
        count: How many objects are selected.
        id_short: The idShort of the object, or empty.
        parent: The idShort of its parent, or empty.
        type_name: The name of its class.
    """

    old: str
    number: int
    count: int
    id_short: str
    parent: str
    type_name: str


@dataclass(frozen=True)
class _FilterCall:
    name: str
    arguments: tuple[_Argument, ...]
    position: int


@dataclass(frozen=True)
class _Field:
    name: str
    filters: tuple[_FilterCall, ...]


@dataclass(frozen=True)
class Pattern:
    """A pattern that was read successfully."""

    parts: tuple[str | _Field, ...]


@dataclass(frozen=True)
class _FilterSpec:
    kinds: tuple[type, ...]
    required: int
    run: Callable[[str, tuple[_Argument, ...]], str]


def _text(argument: _Argument) -> str:
    return str(argument)


def _number(argument: _Argument) -> int:
    return int(argument)


def _slice(text: str, args: tuple[_Argument, ...]) -> str:
    start = _number(args[0])
    end = _number(args[1]) if len(args) > 1 else None
    return text[start:end]


def _replace(text: str, args: tuple[_Argument, ...]) -> str:
    return text.replace(_text(args[0]), _text(args[1]))


def _remove(text: str, args: tuple[_Argument, ...]) -> str:
    return text.replace(_text(args[0]), "")


def _strip_prefix(text: str, args: tuple[_Argument, ...]) -> str:
    return text.removeprefix(_text(args[0]))


def _strip_suffix(text: str, args: tuple[_Argument, ...]) -> str:
    return text.removesuffix(_text(args[0]))


def _default(text: str, args: tuple[_Argument, ...]) -> str:
    return text or _text(args[0])


def _pad(text: str, args: tuple[_Argument, ...]) -> str:
    width = _number(args[0])
    fill = _text(args[1]) if len(args) > 1 else "0"
    if width > MAX_RESULT_CHARS:
        raise _RenderLimit
    return text.rjust(width, fill)


def _add(text: str, args: tuple[_Argument, ...]) -> str:
    literal = text.strip()
    if not _WHOLE_NUMBER.fullmatch(literal):
        raise _NotANumber(text)
    try:
        return str(int(literal) + _number(args[0]))
    except ValueError:
        raise _NotANumber(text) from None


def _to_id_short(text: str, args: tuple[_Argument, ...]) -> str:
    del args
    return fix_id_short(text, digits=lambda: "000000")


class _RenderLimit(Exception):
    """A filter would give more text than allowed."""


class _NotANumber(Exception):
    """A filter that needs a number got other text."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.text = text


_FILTERS: Final[dict[str, _FilterSpec]] = {
    "upper": _FilterSpec((), 0, lambda text, _: text.upper()),
    "lower": _FilterSpec((), 0, lambda text, _: text.lower()),
    "capitalize": _FilterSpec(
        (), 0, lambda text, _: text[:1].upper() + text[1:]
    ),
    "trim": _FilterSpec((), 0, lambda text, _: text.strip()),
    "reverse": _FilterSpec((), 0, lambda text, _: text[::-1]),
    "slice": _FilterSpec((int, int), 1, _slice),
    "replace": _FilterSpec((str, str), 2, _replace),
    "remove": _FilterSpec((str,), 1, _remove),
    "strip_prefix": _FilterSpec((str,), 1, _strip_prefix),
    "strip_suffix": _FilterSpec((str,), 1, _strip_suffix),
    "default": _FilterSpec((str,), 1, _default),
    "pad": _FilterSpec((int, str), 1, _pad),
    "add": _FilterSpec((int,), 1, _add),
    "to_id_short": _FilterSpec((), 0, _to_id_short),
}

FILTER_NAMES: Final = tuple(_FILTERS)
"""The filters of the language."""

_EXAMPLES: Final = (
    ("{old}", "Leaves the value as it is"),
    ("ABC_{old}", "Puts ABC_ before the value"),
    ("{old}_XYZ", "Puts _XYZ after the value"),
    ("{old|upper}", "Upper case"),
    ("{old|capitalize}", "First letter in upper case"),
    ("{old|slice(3)}", "Drops the first three characters"),
    ('{old|replace("Temp","Temperature")}', "Replaces a word"),
    ("Item{number|pad(3)}", "Item001, Item002, ..."),
    ("{parent}_{old}", "Puts the name of the parent before the value"),
)


def examples() -> tuple[tuple[str, str], ...]:
    """Returns patterns to offer in a dialog, each with what it does."""
    return _EXAMPLES


def compile_pattern(text: str) -> Pattern:
    """Reads a pattern.

    Args:
        text: The pattern.

    Returns:
        The pattern, ready for `render`.

    Raises:
        PatternError: If the pattern is too long, has an unclosed or single
            brace, or names a field or filter that does not exist, or gives
            a filter arguments that do not fit.
    """
    if len(text) > MAX_PATTERN_CHARS:
        raise PatternError(
            f"The pattern is longer than {MAX_PATTERN_CHARS} characters", 0
        )
    parts: list[str | _Field] = []
    literal: list[str] = []
    position = 0
    while position < len(text):
        char = text[position]
        following = text[position + 1 : position + 2]
        if char in "{}" and following == char:
            literal.append(char)
            position += 2
        elif char == "{":
            if literal:
                parts.append("".join(literal))
                literal = []
            field, position = _read_field(text, position + 1)
            parts.append(field)
        elif char == "}":
            raise PatternError(
                "Found a single closing brace; write '}}' for a literal brace",
                position,
            )
        else:
            literal.append(char)
            position += 1
    if literal:
        parts.append("".join(literal))
    return Pattern(tuple(parts))


def render(pattern: Pattern, context: PatternContext) -> str:
    """Applies a pattern to one object.

    Args:
        pattern: What `compile_pattern` returned.
        context: The values of the object.

    Returns:
        The new text.

    Raises:
        PatternError: If a filter cannot work on the value, such as `add` on
            text that is no number, or the text gets too long.
    """
    values = {
        "old": context.old,
        "idShort": context.id_short,
        "parent": context.parent,
        "type": context.type_name,
        "number": str(context.number),
        "count": str(context.count),
    }
    pieces: list[str] = []
    for part in pattern.parts:
        if isinstance(part, str):
            pieces.append(part)
            continue
        text = values[part.name]
        for call in part.filters:
            text = _run(call, text)
        pieces.append(text)
    result = "".join(pieces)
    if len(result) > MAX_RESULT_CHARS:
        raise PatternError(_too_long(), 0)
    return result


def _too_long() -> str:
    return f"The result is longer than {MAX_RESULT_CHARS} characters"


def _run(call: _FilterCall, text: str) -> str:
    try:
        result = _FILTERS[call.name].run(text, call.arguments)
    except _RenderLimit:
        raise PatternError(_too_long(), call.position) from None
    except _NotANumber as error:
        raise PatternError(
            f"'{error.text}' is not a whole number, so '{call.name}' cannot "
            "work on it",
            call.position,
        ) from None
    if len(result) > MAX_RESULT_CHARS:
        raise PatternError(_too_long(), call.position)
    return result


def _skip_spaces(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position


def _read_field(text: str, position: int) -> tuple[_Field, int]:
    position = _skip_spaces(text, position)
    found = _NAME.match(text, position)
    if found is None:
        raise PatternError("Expected a field name after '{'", position)
    name = found.group()
    if name not in FIELD_NAMES:
        raise PatternError(
            f"Unknown field '{name}'. The fields are {', '.join(FIELD_NAMES)}",
            position,
        )
    position = found.end()
    filters: list[_FilterCall] = []
    while True:
        position = _skip_spaces(text, position)
        if position >= len(text):
            raise PatternError("The field has no closing brace '}'", position)
        char = text[position]
        if char == "}":
            return _Field(name, tuple(filters)), position + 1
        if char != "|":
            raise PatternError(
                "Expected '|' or the closing brace '}' after the field "
                "or filter",
                position,
            )
        call, position = _read_filter(text, position + 1)
        filters.append(call)


def _read_filter(text: str, position: int) -> tuple[_FilterCall, int]:
    position = _skip_spaces(text, position)
    found = _NAME.match(text, position)
    if found is None:
        raise PatternError("Expected a filter name after '|'", position)
    name = found.group()
    if name not in _FILTERS:
        raise PatternError(
            f"Unknown filter '{name}'. The filters are "
            f"{', '.join(FILTER_NAMES)}",
            position,
        )
    start = position
    position = _skip_spaces(text, found.end())
    arguments: list[_Argument] = []
    if position < len(text) and text[position] == "(":
        arguments, position = _read_arguments(text, position + 1)
    _check_arguments(name, arguments, start)
    return _FilterCall(name, tuple(arguments), start), position


def _read_arguments(text: str, position: int) -> tuple[list[_Argument], int]:
    arguments: list[_Argument] = []
    position = _skip_spaces(text, position)
    if text[position : position + 1] == ")":
        return arguments, position + 1
    while True:
        argument, position = _read_argument(text, position)
        arguments.append(argument)
        position = _skip_spaces(text, position)
        char = text[position : position + 1]
        if char == ")":
            return arguments, position + 1
        if char != ",":
            raise PatternError(
                "Expected ',' or a closing parenthesis ')' after the argument",
                position,
            )
        position = _skip_spaces(text, position + 1)


def _read_argument(text: str, position: int) -> tuple[_Argument, int]:
    if text[position : position + 1] == '"':
        return _read_quoted(text, position)
    found = _NUMBER.match(text, position)
    if found is None:
        raise PatternError(
            "An argument is a whole number or a text in double quotes",
            position,
        )
    return int(found.group()), found.end()


def _read_quoted(text: str, position: int) -> tuple[str, int]:
    start = position
    position += 1
    characters: list[str] = []
    while position < len(text):
        char = text[position]
        if char == "\\" and text[position + 1 : position + 2] in ('"', "\\"):
            characters.append(text[position + 1])
            position += 2
        elif char == '"':
            return "".join(characters), position + 1
        else:
            characters.append(char)
            position += 1
    raise PatternError("A text in double quotes is unclosed", start)


def _check_arguments(
    name: str, arguments: list[_Argument], position: int
) -> None:
    spec = _FILTERS[name]
    most = len(spec.kinds)
    if most == 0 and arguments:
        raise PatternError(f"Filter '{name}' takes no arguments", position)
    if len(arguments) > most:
        raise PatternError(
            f"Filter '{name}' takes at most {most} arguments", position
        )
    if len(arguments) < spec.required:
        raise PatternError(
            f"Filter '{name}' needs {_count_text(spec)} arguments", position
        )
    for number, (argument, kind) in enumerate(
        zip(arguments, spec.kinds, strict=False), start=1
    ):
        if not isinstance(argument, kind):
            wanted = (
                "a whole number" if kind is int else "a text in double quotes"
            )
            raise PatternError(
                f"Argument {number} of filter '{name}' must be {wanted}",
                position,
            )
    _check_values(name, arguments, position)


def _count_text(spec: _FilterSpec) -> str:
    if spec.required == len(spec.kinds):
        return str(spec.required)
    return f"{spec.required} or {len(spec.kinds)}"


def _check_values(name: str, arguments: list[_Argument], position: int) -> None:
    if name == "replace" and arguments[0] == "":
        raise PatternError(
            "The text to replace in 'replace' must not be empty", position
        )
    if name == "pad":
        if _number(arguments[0]) < 0:
            raise PatternError(
                "The width in 'pad' must not be negative", position
            )
        if len(arguments) > 1 and len(_text(arguments[1])) != 1:
            raise PatternError(
                "The fill of 'pad' must be one character", position
            )
