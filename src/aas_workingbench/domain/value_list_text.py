"""Value list pairs from text, such as the clipboard.

An IEC 61360 value list holds pairs of a value and a reference to the concept
that defines it. A user copies them from a spreadsheet, a web page, a text, or
from another AAS tool. This module reads three forms:

- **Lines.** One pair a line, `value, valueId`. A tab also separates the two,
  which is what a spreadsheet copies. A comma inside the value is fine when
  the line has a tab, and otherwise the last comma separates, because a value
  id is an IRDI or an IRI and has no comma.
- **A JSON array** of `{"value": ..., "valueId": {...}}` objects, with the
  reference in the JSON of the metamodel.
- **One JSON object**, either one pair or a whole `valueList` with its
  `valueReferencePairs`.

The text comes from anywhere, so it is never evaluated. JSON goes through the
JSON decoder of the SDK, which builds the pairs and checks every key type and
every length. A pair with a problem is reported with its line or its place in
the array, and the other pairs are still read.

A pair needs a value id. The SDK writes a pair without one as `"valueId": null`
in JSON, and its own reader refuses that, so the pair would not survive a
save: reading the file again drops it, with all the others of the list.

Example:
    Reading two lines::

        result = parse_value_pairs("Red, 0173-1#07-AAA#001\\nGreen, urn:green")
        pairs = result.pairs  # two ValueReferencePair objects
"""

from collections.abc import Iterable
from dataclasses import dataclass
import json
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from basyx.aas.adapter.json import StrictAASFromJsonDecoder

# Larger text is a file, not a list that someone copied.
MAX_CHARS = 5_000_000
MAX_PAIRS = 20_000


@dataclass(frozen=True, eq=False)
class ParsedPair:
    """One entry of the text, with its outcome.

    Attributes:
        place: Where it came from, such as `Line 3` or `Entry 2`.
        source: The text of the entry, shortened if it is long.
        pair: The pair, or None if the entry is not usable.
        problem: Why the entry is not usable, or None.
    """

    place: str
    source: str
    pair: model.ValueReferencePair | None
    problem: str | None


@dataclass(frozen=True)
class ValueListParse:
    """What was read from a text.

    Attributes:
        entries: Every entry, in order, with its outcome.
        error: A reason why nothing could be read at all, or None. Then
            `entries` is empty.
    """

    entries: tuple[ParsedPair, ...] = ()
    error: str | None = None

    @property
    def pairs(self) -> tuple[model.ValueReferencePair, ...]:
        """The pairs that were read."""
        return tuple(e.pair for e in self.entries if e.pair is not None)

    @property
    def problems(self) -> tuple[ParsedPair, ...]:
        """The entries that are not usable."""
        return tuple(e for e in self.entries if e.problem is not None)


NO_VALUE_ID = (
    "has no valueId. Write the pair as 'value, valueId'. A pair without one "
    "is lost when the package is saved as JSON and read again"
)


def parse_value_pairs(text: str) -> ValueListParse:
    """Reads value list pairs from text.

    Args:
        text: Lines, or JSON, as described in the module.

    Returns:
        The entries, or an error when the text is empty, too large, or starts
        like JSON but is not.
    """
    text = text.lstrip("﻿")
    if not text.strip():
        return ValueListParse(error="There is no text to read.")
    if len(text) > MAX_CHARS:
        return ValueListParse(
            error=f"The text has {len(text):,} characters. Reading stops at "
            f"{MAX_CHARS:,}: this looks like a file, not a list."
        )
    if text.lstrip()[0] in "[{":
        return _parse_json(text)
    return _parse_lines(text)


def _shown(text: str, longest: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= longest else f"{text[: longest - 1]}…"


def _too_many(count: int) -> str | None:
    if count > MAX_PAIRS:
        return (
            f"There are {count:,} entries. At most {MAX_PAIRS:,} are read at "
            "a time."
        )
    return None


def _parse_lines(text: str) -> ValueListParse:
    lines = text.splitlines()
    error = _too_many(len(lines))
    if error is not None:
        return ValueListParse(error=error)
    entries: list[ParsedPair] = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        entries.append(_parse_line(f"Line {number}", line))
    if not entries:
        return ValueListParse(error="There is no text to read.")
    return ValueListParse(tuple(entries))


def _split_line(line: str) -> tuple[str, str]:
    if "\t" in line:
        value, _, value_id = line.partition("\t")
        return value.strip(), value_id.strip().strip("\t").strip()
    if "," in line:
        value, _, value_id = line.rpartition(",")
        return value.strip(), value_id.strip()
    return line.strip(), ""


def _parse_line(place: str, line: str) -> ParsedPair:
    source = _shown(line)
    value, value_id = _split_line(line)
    if not value_id:
        return ParsedPair(place, source, None, NO_VALUE_ID)
    if not value:
        return ParsedPair(place, source, None, "has no value")
    try:
        pair = model.ValueReferencePair(
            value,
            model.ExternalReference(
                (model.Key(model.KeyTypes.GLOBAL_REFERENCE, value_id),)
            ),
        )
    except (ValueError, model.AASConstraintViolation) as error:
        return ParsedPair(place, source, None, _plain(error))
    return ParsedPair(place, source, pair, None)


def _plain(error: BaseException) -> str:
    return " ".join(str(error).split())


def _parse_json(text: str) -> ValueListParse:
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        return ValueListParse(
            error=f"The text starts like JSON but cannot be read: "
            f"{error.msg} (line {error.lineno}, column {error.colno})."
        )
    except RecursionError:
        return ValueListParse(error="The JSON is nested too deeply.")
    items = _items_of(document)
    if isinstance(items, str):
        return ValueListParse(error=items)
    error = _too_many(len(items))
    if error is not None:
        return ValueListParse(error=error)
    return ValueListParse(
        tuple(
            _parse_item(f"Entry {n}", item) for n, item in enumerate(items, 1)
        )
    )


def _items_of(document: object) -> list[object] | str:
    if isinstance(document, list):
        items = cast("list[object]", document)
    elif isinstance(document, dict):
        mapping = cast("dict[str, object]", document)
        listed = mapping.get("valueReferencePairs")
        if isinstance(listed, list):
            items = cast("list[object]", listed)
        elif "value" in mapping:
            items = [cast("object", mapping)]
        else:
            return (
                "The JSON is an object without 'value' or "
                "'valueReferencePairs'. Expected a pair, a list of pairs, or "
                "a value list."
            )
    else:
        return "The JSON is neither a list of pairs nor a pair."
    if not items:
        return "The JSON list has no pairs."
    return items


def _parse_item(place: str, item: object) -> ParsedPair:
    source = _shown(json.dumps(item, ensure_ascii=False))
    if not isinstance(item, dict):
        return ParsedPair(
            place, source, None, "is not an object with 'value' and 'valueId'"
        )
    mapping = cast("dict[str, Any]", item)
    if mapping.get("valueId") is None:
        return ParsedPair(place, source, None, NO_VALUE_ID)
    pairs, problem = _decode_pairs([mapping])
    if problem is not None or not pairs:
        return ParsedPair(place, source, None, problem or "cannot be read")
    return ParsedPair(place, source, pairs[0], None)


def _skeleton() -> dict[str, Any]:
    """The JSON the SDK writes for a content, to put pairs into.

    The SDK makes the JSON and reads it back, so no AAS JSON is written here.
    """
    content = model.DataSpecificationIEC61360(
        model.PreferredNameTypeIEC61360({"en": "x"})
    )
    return cast(
        "dict[str, Any]",
        json.loads(json.dumps(content, cls=AASToJsonEncoder)),
    )


def _decode_pairs(
    items: Iterable[dict[str, Any]],
) -> tuple[list[model.ValueReferencePair], str | None]:
    document = _skeleton()
    document["valueList"] = {"valueReferencePairs": list(items)}
    try:
        content = json.loads(json.dumps(document), cls=StrictAASFromJsonDecoder)
    except (
        KeyError,
        TypeError,
        ValueError,
        model.AASConstraintViolation,
    ) as error:
        return [], _reason(error)
    value_list = getattr(content, "value_list", None)
    return list(value_list or ()), None


def _reason(error: BaseException) -> str:
    """Shortens the SDK message to its last, specific part."""
    message = _plain(error)
    if ">>>" in message:
        message = message.split(">>>")[0]
    for marker in ("ValueReferencePair:", "ValueReferencePair "):
        if marker in message:
            message = message.rsplit(marker, 1)[1]
    return message.strip(" '\"") or "cannot be read"
