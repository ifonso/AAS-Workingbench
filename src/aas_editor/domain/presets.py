"""Presets: qualifiers, extensions, and the like that a user adds by name.

A preset file is a JSON array. Each entry has a `name`, which the list shows,
and the member itself in the JSON of the metamodel, under a key that depends
on the kind of the file:

    qualifiers.json            "qualifier"
    extensions.json            "extension"
    specific-asset-ids.json    "specificAssetId"
    data-specifications.json   "embeddedDataSpecification"

The member is read by the SDK's JSON adapter (see
`aas_editor.domain.member_json`), so a preset is exactly as valid as the
element it makes. A name such as `Submodel templates | Cardinality` is shown
as it is, and the text before the bar groups the list.

The files are data from outside, and may be edited by hand, so nothing here
raises for bad content. `parse_presets` keeps the entries that are good and
reports each bad entry, or the whole file, as a `Problem` with a reason.

Also read, for files that were made for Package Explorer:

- whole lines that start with `//` are comments,
- `pair` for `specificAssetId`,
- a qualifier without `valueType` is an `xs:string`, as is an extension that
  has a value and no `valueType`,
- an entry `{"name": ..., "value": <url>}` in a file of data specifications,
  for the IEC 61360 template only, because the SDK has no content class for
  another one,
- `upgradeFrom` is ignored.

Example:
    Reading a file and making the member of a preset::

        result = parse_presets(text, MemberKind.QUALIFIER, "user")
        for problem in result.problems:
            show(problem.where, problem.message)
        qualifier = result.presets[0].make()
"""

from collections.abc import Iterable
from dataclasses import dataclass
import json
from typing import Any
from typing import Final
from typing import cast

from aas_editor.domain.member_json import Member
from aas_editor.domain.member_json import MemberJsonError
from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.member_json import member_from_data
from aas_editor.domain.member_json import to_data

MAX_FILE_CHARS: Final = 2_000_000
"""The largest preset file that is read, in characters."""
MAX_ENTRIES: Final = 5000
"""The most entries in one file."""
MAX_NAME_CHARS: Final = 200
"""The longest name of a preset."""

_PAYLOAD_KEYS: Final = {
    MemberKind.QUALIFIER: ("qualifier",),
    MemberKind.EXTENSION: ("extension",),
    MemberKind.SPECIFIC_ASSET_ID: ("specificAssetId", "pair"),
    MemberKind.EMBEDDED_DATA_SPECIFICATION: ("embeddedDataSpecification",),
}
_IEC_FRAGMENT: Final = "DataSpecificationIec61360"
_PLACEHOLDER_NAME: Final = "Preferred name"

FILE_NAMES: Final = {
    MemberKind.QUALIFIER: "qualifiers.json",
    MemberKind.EXTENSION: "extensions.json",
    MemberKind.SPECIFIC_ASSET_ID: "specific-asset-ids.json",
    MemberKind.EMBEDDED_DATA_SPECIFICATION: "data-specifications.json",
}
"""The name of the preset file for each kind."""


class PresetValueError(ValueError):
    """A preset that needs a value was used without one."""


@dataclass(frozen=True)
class Problem:
    """Something in a preset file that was refused.

    Attributes:
        where: `File`, or the entry, such as `Entry 3 ('Name')`.
        message: Why, for the user.
    """

    where: str
    message: str

    def __str__(self) -> str:
        """Returns the problem as one line."""
        return f"{self.where}: {self.message}"


@dataclass(frozen=True, eq=False)
class Preset:
    """A named member that can be made again and again.

    Attributes:
        name: What the list shows.
        kind: What the preset makes.
        data: The JSON of the member, as the SDK writes it.
        source: Where it came from, such as `shipped` or `user`.
    """

    name: str
    kind: MemberKind
    data: dict[str, Any]
    source: str
    value_required: bool = False

    def make(self, value: str | None = None) -> Member:
        """Makes a new member, which has no parent.

        Args:
            value: The value for a preset that has none (`value_required`).
                The SDK does not accept a specific asset id with an empty
                value, so the user gives it when the preset is used. A
                preset that has a value ignores it.

        Returns:
            A member that nothing else holds, so it can be added to an owner.

        Raises:
            PresetValueError: If the preset needs a value and `value` is
                missing or blank.
        """
        data = self.data
        if self.value_required:
            if value is None or not value.strip():
                raise PresetValueError(
                    f"The preset '{self.name}' needs a value"
                )
            data = {**data, "value": value.strip()}
        return member_from_data(data, self.kind)

    @property
    def group(self) -> str:
        """The text of the name before the first bar, or empty."""
        head, bar, _ = self.name.partition("|")
        return head.strip() if bar else ""

    @property
    def title(self) -> str:
        """The text of the name after the first bar, or the whole name."""
        _, bar, tail = self.name.partition("|")
        return tail.strip() if bar else self.name


@dataclass(frozen=True)
class PresetFile:
    """What one preset file gave.

    Attributes:
        presets: The entries that are good, in the order of the file.
        problems: The entries or the file that were refused.
    """

    presets: tuple[Preset, ...]
    problems: tuple[Problem, ...]


def strip_comments(text: str) -> str:
    """Drops the lines that consist of a `//` comment.

    A line break cannot be inside a JSON text, so a line that starts with
    `//` is never part of one. A `//` in a line with other content stays.
    """
    return "\n".join(
        line for line in text.split("\n") if not line.lstrip().startswith("//")
    )


def parse_presets(text: str, kind: MemberKind, source: str) -> PresetFile:
    """Reads the text of a preset file.

    Args:
        text: The content of the file.
        kind: What the file holds.
        source: Where the file came from, kept in each preset.

    Returns:
        The good entries, and a problem for each refused entry. A file that
        is no array gives no presets and one problem for `File`.
    """
    entries, refused = _entries(text)
    if refused is not None:
        return PresetFile((), (Problem("File", refused),))
    presets: list[Preset] = []
    problems: list[Problem] = []
    names: set[str] = set()
    for number, entry in enumerate(entries, start=1):
        label = f"Entry {number}"
        try:
            preset = _read_entry(entry, kind, source, label, names)
        except _EntryProblem as error:
            problems.append(Problem(error.where, error.message))
            continue
        names.add(preset.name)
        presets.append(preset)
    return PresetFile(tuple(presets), tuple(problems))


def merge_presets(
    shipped: Iterable[Preset], user: Iterable[Preset]
) -> list[Preset]:
    """Combines the presets of the app and the presets of the user.

    Args:
        shipped: The presets that come with the app.
        user: The presets of the user. One with the name of a shipped preset
            replaces it.

    Returns:
        The presets sorted by name without regard to case, so that the
        entries of a group stand together.
    """
    by_name = {preset.name: preset for preset in shipped}
    by_name.update({preset.name: preset for preset in user})
    return sorted(by_name.values(), key=lambda preset: preset.name.casefold())


class _EntryProblem(Exception):
    def __init__(self, where: str, message: str) -> None:
        super().__init__(message)
        self.where = where
        self.message = message


def _entries(text: str) -> tuple[list[object], str | None]:
    if len(text) > MAX_FILE_CHARS:
        return (
            [],
            f"The file is too large (more than {MAX_FILE_CHARS} characters)",
        )
    if not text.strip():
        return [], "The file is empty"
    try:
        loaded = cast("object", json.loads(strip_comments(text)))
    except json.JSONDecodeError as error:
        return [], f"The file is not valid JSON: {error}"
    except RecursionError:
        return [], "The file is nested too deeply"
    if not isinstance(loaded, list):
        return [], "The file must be an array of presets"
    entries = cast("list[object]", loaded)
    if len(entries) > MAX_ENTRIES:
        return [], f"The file has more than {MAX_ENTRIES} entries"
    return entries, None


def _read_entry(
    entry: object,
    kind: MemberKind,
    source: str,
    label: str,
    names: set[str],
) -> Preset:
    if not isinstance(entry, dict):
        raise _EntryProblem(label, "The entry is not an object")
    fields = cast("dict[str, object]", entry)
    name = fields.get("name")
    if not isinstance(name, str) or not name.strip():
        raise _EntryProblem(label, "The entry needs a name, as text")
    name = name.strip()
    label = f"{label} ('{name[:MAX_NAME_CHARS]}')"
    if len(name) > MAX_NAME_CHARS:
        raise _EntryProblem(
            label, f"The name is longer than {MAX_NAME_CHARS} characters"
        )
    if name in names:
        raise _EntryProblem(
            label, "The name is used by an earlier entry of the file"
        )
    payload = _payload(fields, kind, label)
    needs_value = _needs_value(payload, kind)
    if needs_value:
        payload = {**cast("dict[str, object]", payload), "value": "-"}
    try:
        member = member_from_data(payload, kind)
        data = to_data(member)
        member_from_data(data, kind)
    except MemberJsonError as error:
        raise _EntryProblem(label, str(error)) from None
    if needs_value:
        data["value"] = ""
    return Preset(name, kind, data, source, needs_value)


def _needs_value(payload: object, kind: MemberKind) -> bool:
    """Tells whether a specific asset id has no value, which the SDK refuses."""
    if kind is not MemberKind.SPECIFIC_ASSET_ID or not isinstance(
        payload, dict
    ):
        return False
    value = cast("dict[str, object]", payload).get("value")
    return value is None or value == ""


def _payload(fields: dict[str, object], kind: MemberKind, label: str) -> object:
    keys = _PAYLOAD_KEYS[kind]
    for key in keys:
        if key in fields:
            return _with_defaults(fields[key], kind)
    if kind is MemberKind.EMBEDDED_DATA_SPECIFICATION and "value" in fields:
        return _legacy_data_specification(fields["value"], label)
    raise _EntryProblem(
        label, f"The entry has no '{keys[0]}' with the {kind.label}"
    )


def _with_defaults(payload: object, kind: MemberKind) -> object:
    """Adds the value type that files for Package Explorer leave out."""
    if not isinstance(payload, dict):
        return payload
    data = dict(cast("dict[str, object]", payload))
    if data.get("valueType") is None:
        if kind is MemberKind.QUALIFIER or (
            kind is MemberKind.EXTENSION and data.get("value") is not None
        ):
            data["valueType"] = "xs:string"
    return data


def _legacy_data_specification(url: object, label: str) -> dict[str, object]:
    if not isinstance(url, str) or _IEC_FRAGMENT not in url:
        raise _EntryProblem(
            label,
            "Only the IEC 61360 template can be stored: the SDK has no "
            "content class for another data specification",
        )
    return {
        "dataSpecification": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": url}],
        },
        "dataSpecificationContent": {
            "modelType": "DataSpecificationIec61360",
            "preferredName": [{"language": "en", "text": _PLACEHOLDER_NAME}],
        },
    }
