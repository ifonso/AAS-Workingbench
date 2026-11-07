"""What the SDK left out when a package was read in failsafe mode.

In failsafe mode the BaSyx reader skips what it cannot construct and logs one
record for each thing it skipped. This module turns those records into
`LoadIssue` values and a `LoadReport` that the editor can show, count, copy,
and keep with the package. It knows the text of the records of the pinned SDK
(ADR 0004) and nothing else: no logging, no files, no Qt.

Parsing is best effort. A record that no pattern knows becomes an issue whose
outcome is `Outcome.UNKNOWN` and whose text is the whole record, so that
nothing the SDK said is lost.

An error record of the XML reader says that the construct it names was left
out. That is the last of its `->` lines, and the lines before it are the
causes, so a nested failure is one issue and not several. A warning record is
not a loss as a rule, and only the patterns below say what it means.
"""

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import PurePosixPath
import re
from typing import Any
from typing import Final


class Severity(Enum):
    """The level at which the SDK logged a record."""

    ERROR = "error"
    WARNING = "warning"


class Outcome(Enum):
    """What happened to the thing a record is about."""

    LEFT_OUT = "left out"
    """It was skipped, so it is not in the package."""
    KEPT = "kept"
    """It was kept as it is, and the SDK only had a remark."""
    UNKNOWN = "unknown"
    """No pattern knows the record, so what it means is not known."""


class Scope(Enum):
    """How much of the package a thing is."""

    OBJECT = "object"
    """A shell, a submodel, or a concept description."""
    ELEMENT = "element"
    """A submodel element, with everything below it."""
    DETAIL = "detail"
    """A part of an object or element, such as a reference or a text."""
    PART = "part"
    """A whole part of the package file."""
    OTHER = "other"
    """Something else, or not known."""


@dataclass(frozen=True)
class RawRecord:
    """A log record of the SDK, as the reader captured it.

    Attributes:
        severity: The level of the record.
        logger: The name of the logger that wrote it.
        message: The formatted message, with all its lines.
        part: The OPC part that was read when the record was written, or an
            empty string for a plain JSON or XML file.
    """

    severity: Severity
    logger: str
    message: str
    part: str = ""


@dataclass(frozen=True)
class LoadIssue:
    """One thing that the SDK reported while it read a package.

    Attributes:
        severity: The level at which the SDK logged it.
        outcome: Whether the thing was left out, kept, or is not known.
        scope: How much of the package the thing is.
        subject: What it is, in words, such as "submodel" or "reference".
        location: Where it is, as `id <identifier>` or `line <number>`, or an
            empty string when the record does not say.
        part: The OPC part that was read, or an empty string.
        reason: Why, in the words of the SDK.
        text: The record of the SDK, in full. For an issue that merges two
            records, both.
    """

    severity: Severity
    outcome: Outcome
    scope: Scope
    subject: str
    location: str
    part: str
    reason: str
    text: str

    def describe(self, full_part: bool = False) -> str:
        """Writes the issue as one line of text for the user.

        Args:
            full_part: Name the part with its whole path. By default only the
                last segment is named, which is what tells the parts of a
                package apart.
        """
        part = self.part if full_part else PurePosixPath(self.part).name
        where = ", ".join(x for x in (self.location, part) if x)
        place = f" ({where})" if where else ""
        if self.outcome is Outcome.LEFT_OUT:
            return f"Left out {self.subject}{place}: {self.reason}"
        if self.outcome is Outcome.KEPT:
            return f"Kept {self.subject}{place}, with a remark: {self.reason}"
        return f"Not understood{place}: {_one_line(self.text)}"

    def to_data(self) -> dict[str, str]:
        """Turns the issue into plain strings, for a file."""
        return {
            "severity": self.severity.value,
            "outcome": self.outcome.value,
            "scope": self.scope.value,
            "subject": self.subject,
            "location": self.location,
            "part": self.part,
            "reason": self.reason,
            "text": self.text,
        }

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> "LoadIssue":
        """Builds an issue from `to_data`.

        Raises:
            KeyError: If a field is missing.
            ValueError: If an enumeration value is not known.
        """
        return cls(
            Severity(data["severity"]),
            Outcome(data["outcome"]),
            Scope(data["scope"]),
            str(data["subject"]),
            str(data["location"]),
            str(data["part"]),
            str(data["reason"]),
            str(data["text"]),
        )


@dataclass(frozen=True)
class LoadReport:
    """What the SDK left out, or remarked on, while it read a package.

    Attributes:
        issues: One issue for each thing, in the order of the SDK.
    """

    issues: tuple[LoadIssue, ...] = ()

    def __bool__(self) -> bool:
        """Tells whether there is anything to show."""
        return bool(self.issues)

    @property
    def left_out(self) -> tuple[LoadIssue, ...]:
        """The issues about something that is not in the package."""
        return self._with(Outcome.LEFT_OUT)

    @property
    def unknown(self) -> tuple[LoadIssue, ...]:
        """The issues that no pattern could classify."""
        return self._with(Outcome.UNKNOWN)

    @property
    def kept(self) -> tuple[LoadIssue, ...]:
        """The issues about something that was kept as it is."""
        return self._with(Outcome.KEPT)

    @property
    def left_out_objects(self) -> tuple[LoadIssue, ...]:
        """The shells, submodels, and concept descriptions that are missing."""
        return tuple(i for i in self.left_out if i.scope is Scope.OBJECT)

    def by_weight(self) -> tuple[LoadIssue, ...]:
        """Orders the issues with the biggest losses first.

        Whatever was left out comes before the rest, and objects before
        elements before details. Issues of one weight keep the order of the
        SDK.
        """
        return tuple(
            sorted(
                self.issues,
                key=lambda i: (
                    i.outcome is not Outcome.LEFT_OUT,
                    _WEIGHT[i.scope],
                ),
            )
        )

    def count(self, scope: Scope) -> int:
        """Counts what was left out, of one scope."""
        return sum(1 for i in self.left_out if i.scope is scope)

    def summary(self) -> str:
        """Says in a few sentences how much was left out, and what.

        Returns:
            Plain text without a list of single items, or an empty string for
            an empty report.
        """
        if not self.issues:
            return ""
        sentences: list[str] = []
        parts = self._counts_by_scope()
        if parts:
            sentences.append(f"Left out: {_join(parts)}.")
        unknown = len(self.unknown)
        if unknown:
            sentences.append(
                f"{_number(unknown, 'message')} of the SDK could not be "
                "classified, so what they left out is not known."
            )
        kept = len(self.kept)
        if kept:
            sentences.append(
                f"{_number(kept, 'remark')} concern content that was kept."
            )
        return " ".join(sentences)

    def text(self) -> str:
        """Writes the whole report as text to copy, with the SDK's records."""
        if not self.issues:
            return ""
        lines = [self.summary(), ""]
        for number, issue in enumerate(self.by_weight(), 1):
            lines.append(f"{number}. {issue.describe(full_part=True)}")
            for raw_line in issue.text.splitlines():
                lines.append(f"      SDK: {raw_line}")
        return "\n".join(lines)

    def to_data(self) -> list[dict[str, str]]:
        """Turns the report into plain data, for a file."""
        return [issue.to_data() for issue in self.issues]

    @classmethod
    def from_data(cls, data: list[dict[str, Any]]) -> "LoadReport":
        """Builds a report from `to_data`.

        Raises:
            KeyError: If a field is missing.
            ValueError: If an enumeration value is not known.
        """
        return cls(tuple(LoadIssue.from_data(entry) for entry in data))

    def _with(self, outcome: Outcome) -> tuple[LoadIssue, ...]:
        return tuple(i for i in self.issues if i.outcome is outcome)

    def _counts_by_scope(self) -> list[str]:
        words = (
            (Scope.OBJECT, "object"),
            (Scope.ELEMENT, "element"),
            (Scope.DETAIL, "detail"),
            (Scope.PART, "part"),
            (Scope.OTHER, "other item"),
        )
        found: list[str] = []
        for scope, word in words:
            if not self.count(scope):
                continue
            chunk = _number(self.count(scope), word)
            if scope is Scope.OBJECT:
                # Which objects, because that is what a user looks for.
                kinds = Counter(i.subject for i in self.left_out_objects)
                listed = ", ".join(
                    _number(count, kind) for kind, count in kinds.most_common()
                )
                chunk = f"{chunk} ({listed})"
            found.append(chunk)
        return found


def build_report(records: list[RawRecord]) -> LoadReport:
    """Turns the records of one read into a report.

    Args:
        records: What the SDK logged, in order.

    Returns:
        A report with an issue for each thing the SDK reported. Two records
        that tell the same loss, which the JSON reader writes, are one issue.
    """
    issues = [parse_record(record) for record in records]
    return LoadReport(tuple(_merge_json_followups(issues)))


def duplicate_in_other_part(
    type_name: str, identifier: str, part: str, first_part: str
) -> LoadIssue:
    """Describes an object that the SDK skipped without saying so.

    The AASX reader skips an object whose id was read from an earlier part of
    the package, and writes no record. The editor finds these itself.

    Args:
        type_name: The class of the object, such as `ConceptDescription`.
        identifier: The id of the object.
        part: The part that holds the object that was skipped.
        first_part: The part that holds the object that was kept.

    Returns:
        The issue.
    """
    reason = (
        f"The same id is in {first_part}, which was read first, and that "
        "object was kept. The SDK skips this one without a message."
    )
    return LoadIssue(
        Severity.ERROR,
        Outcome.LEFT_OUT,
        Scope.OBJECT,
        _words(type_name),
        f"id {identifier}",
        part,
        reason,
        f"{type_name}[{identifier}] in {part} has the id of an object in "
        f"{first_part}. Found by the editor, not logged by the SDK.",
    )


def declared_file_not_loaded(name: str, part: str, reason: str) -> LoadIssue:
    """Describes a file that a package declares and the editor could not load.

    An AASX declares its supplementary files with an `aas-suppl` relationship
    from the part of an AAS. The editor keeps all of them, so one that it
    cannot read is told to the user, who would find it missing from the file
    after a save.

    Args:
        name: The part name that the relationship points to.
        part: The AAS part that declares it.
        reason: Why it was not loaded, in a sentence.

    Returns:
        The issue.
    """
    return LoadIssue(
        Severity.WARNING,
        Outcome.LEFT_OUT,
        Scope.PART,
        "declared file",
        name,
        part,
        reason,
        f"{part} declares the file {name} with an aas-suppl relationship. "
        f"{reason} Found by the editor, not logged by the SDK.",
    )


# The order of `LoadReport.by_weight`: a lost submodel is not to be buried
# under the texts that follow it.
_WEIGHT: Final = {
    Scope.OBJECT: 0,
    Scope.PART: 1,
    Scope.ELEMENT: 2,
    Scope.OTHER: 3,
    Scope.DETAIL: 4,
}

# -- parsing -----------------------------------------------------------------

_TOP_LEVEL_TYPES: Final = frozenset(
    {
        "Submodel",
        "AssetAdministrationShell",
        "ConceptDescription",
        "submodel",
        "assetAdministrationShell",
        "conceptDescription",
    }
)
_ELEMENT_TYPES: Final = frozenset(
    {
        "SubmodelElement",
        "Property",
        "MultiLanguageProperty",
        "Range",
        "File",
        "Blob",
        "ReferenceElement",
        "RelationshipElement",
        "AnnotatedRelationshipElement",
        "Capability",
        "Entity",
        "Operation",
        "BasicEventElement",
        "SubmodelElementCollection",
        "SubmodelElementList",
    }
)
_OBJECT_CONSTRUCTORS: Final = frozenset(
    {
        "construct_submodel",
        "construct_asset_administration_shell",
        "construct_concept_description",
    }
)
_ELEMENT_CONSTRUCTORS: Final = frozenset(
    {"construct_submodel_element", "construct_operation_variable"}
)

_DUPLICATE: Final = re.compile(
    r"^(\w+)\[(.*)\] has a duplicate identifier already parsed in the "
    r"document! [Ss]kipping it\.\.\.$",
    re.DOTALL,
)
_CHAIN_SEPARATOR: Final = "\n -> "
_CONSTRUCT: Final = re.compile(
    r"^Failed to construct (\S+) on line (\d+) using (\w+)!$"
)
_CAUSE: Final = re.compile(r"^(\w+): (.*)$", re.DOTALL)
_JSON_CONVERT: Final = re.compile(
    r"^Error while trying to convert JSON object into (\w+): "
    r"(.*?) >>> (.*)$",
    re.DOTALL,
)
_JSON_CONVERT_OTHER: Final = "Error while trying to convert JSON object into"
_JSON_UNKNOWN_TYPE: Final = re.compile(
    r'^Found JSON object with modelType="([^"]*)", which is not a known AAS '
    r"class$"
)
_JSON_EXPECTED: Final = re.compile(
    r"^Expected a (\w+) in (.*?), but found (.*?)(?:\. Skipping it\.\.\.)?$",
    re.DOTALL,
)
_CHILD_TAG: Final = re.compile(
    r"^(\S+)(?: on line (\d+))?, child of \S+(?: on line \d+)?, doesn't "
    r"match the expected tag (\S+)!$"
)
_PART_FORMAT: Final = re.compile(
    r"^Could not determine part format of AASX part (\S+) \(Content Type"
)
_MODEL_TYPE: Final = re.compile(r"""['"]modelType['"]: ['"](\w+)['"]""")
_ID: Final = re.compile(r"""(?<![\w])['"]id['"]: (['"])(.*?)\1[,}]""")
_ID_SHORT: Final = re.compile(r"""['"]idShort['"]: (['"])(.*?)\1[,}]""")

# Warnings whose text says that nothing was lost, or what was.
_KEPT_WARNINGS: Final = (
    "of last key of reference to",
    "was in the wrong list",
)
_PARTLY_LOST_WARNINGS: Final = (
    ("has more than one submodel element, using the first one", "variable"),
    (
        "has more than one data specification, using the first one",
        "extra data specification",
    ),
    ("has invalid levelType", "level type"),
    ("has invalid boolean", "level type"),
    ("Ignoring 'revision' attribute", "revision"),
)


def parse_record(record: RawRecord) -> LoadIssue:
    """Turns one record of the SDK into an issue.

    Args:
        record: The record.

    Returns:
        The issue. If no pattern knows the record, its outcome is
        `Outcome.UNKNOWN`.
    """
    text = record.message
    for parser in (
        _parse_duplicate,
        _parse_construct_chain,
        _parse_json_convert,
        _parse_json_unknown_type,
        _parse_json_expected,
        _parse_child_tag,
        _parse_part_format,
        _parse_warning,
    ):
        issue = parser(record)
        if issue is not None:
            return issue
    return LoadIssue(
        record.severity,
        Outcome.UNKNOWN,
        Scope.OTHER,
        "",
        "",
        record.part,
        text,
        text,
    )


def _parse_duplicate(record: RawRecord) -> LoadIssue | None:
    match = _DUPLICATE.match(record.message)
    if match is None:
        return None
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        Scope.OBJECT,
        _words(match.group(1)),
        f"id {match.group(2)}",
        record.part,
        "Another object in the file has the same id. The first one was kept.",
        record.message,
    )


def _parse_construct_chain(record: RawRecord) -> LoadIssue | None:
    lines = record.message.split(_CHAIN_SEPARATOR)
    if len(lines) < 2:
        return None
    construct = _CONSTRUCT.match(lines[-1])
    if construct is None:
        return None
    tag, line, constructor = construct.groups()
    cause = _CAUSE.match(lines[0])
    reason = cause.group(2) if cause else lines[0]
    constructor = constructor.lstrip("_")
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        _xml_scope(constructor),
        _xml_subject(tag, constructor),
        f"line {line}",
        record.part,
        _one_line(reason),
        record.message,
    )


def _parse_json_convert(record: RawRecord) -> LoadIssue | None:
    text = record.message
    match = _JSON_CONVERT.match(text)
    if match is None:
        if text.startswith(_JSON_CONVERT_OTHER):
            return LoadIssue(
                record.severity,
                Outcome.LEFT_OUT,
                Scope.DETAIL,
                "part of an object",
                "",
                record.part,
                _one_line(text[len(_JSON_CONVERT_OTHER) :].strip()),
                text,
            )
        return None
    model_type, reason, found = match.groups()
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        _json_scope(model_type),
        _words(model_type),
        _json_location(found),
        record.part,
        _one_line(reason),
        text,
    )


def _parse_json_unknown_type(record: RawRecord) -> LoadIssue | None:
    match = _JSON_UNKNOWN_TYPE.match(record.message)
    if match is None:
        return None
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        Scope.OTHER,
        f"item of the unknown type {match.group(1)}",
        "",
        record.part,
        "The modelType is not a class of the metamodel.",
        record.message,
    )


def _parse_json_expected(record: RawRecord) -> LoadIssue | None:
    match = _JSON_EXPECTED.match(record.message)
    if match is None:
        return None
    expected, context, found = match.groups()
    found_type = _first(_MODEL_TYPE, found) or expected
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        _json_scope(found_type),
        _words(found_type),
        _json_location(found),
        record.part,
        f"It is not a valid {_words(expected)} for {context}.",
        record.message,
    )


def _parse_child_tag(record: RawRecord) -> LoadIssue | None:
    match = _CHILD_TAG.match(record.message)
    if match is None:
        return None
    tag, line, expected = match.groups()
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        Scope.DETAIL,
        _words(_local_name(tag)),
        f"line {line}" if line else "",
        record.part,
        f"It is not the {_local_name(expected)} that was expected there.",
        record.message,
    )


def _parse_part_format(record: RawRecord) -> LoadIssue | None:
    match = _PART_FORMAT.match(record.message)
    if match is None:
        return None
    return LoadIssue(
        record.severity,
        Outcome.LEFT_OUT,
        Scope.PART,
        "part",
        match.group(1),
        record.part,
        "The format of the part is neither XML nor JSON.",
        record.message,
    )


def _parse_warning(record: RawRecord) -> LoadIssue | None:
    if record.severity is not Severity.WARNING:
        return None
    text = record.message
    for fragment in _KEPT_WARNINGS:
        if fragment in text:
            return LoadIssue(
                record.severity,
                Outcome.KEPT,
                Scope.OTHER,
                "content",
                "",
                record.part,
                _one_line(text),
                text,
            )
    for fragment, subject in _PARTLY_LOST_WARNINGS:
        if fragment in text:
            return LoadIssue(
                record.severity,
                Outcome.LEFT_OUT,
                Scope.DETAIL,
                subject,
                "",
                record.part,
                _one_line(text),
                text,
            )
    return None


def _merge_json_followups(issues: list[LoadIssue]) -> list[LoadIssue]:
    """Joins the two records that the JSON reader writes for one loss.

    The decoder logs why an object could not be converted, and the list that
    would hold it logs that the item was skipped. The second names the object
    again, so the pair is merged into the second, with the reason of the
    first. The match is on the model type, the id, and the idShort.
    """
    merged: list[LoadIssue] = []
    for position, issue in enumerate(issues):
        if _is_json_cause(issue) and any(
            _is_json_followup(later) and _same_item(issue, later)
            for later in issues[position + 1 :]
        ):
            continue
        merged.append(issue)
    result: list[LoadIssue] = []
    for issue in merged:
        if not _is_json_followup(issue):
            result.append(issue)
            continue
        cause = next(
            (
                earlier
                for earlier in issues
                if _is_json_cause(earlier) and _same_item(earlier, issue)
            ),
            None,
        )
        if cause is None:
            result.append(issue)
            continue
        result.append(
            LoadIssue(
                issue.severity,
                Outcome.LEFT_OUT,
                issue.scope,
                issue.subject,
                issue.location or cause.location,
                issue.part,
                cause.reason,
                f"{cause.text}\n{issue.text}",
            )
        )
    return result


def _is_json_cause(issue: LoadIssue) -> bool:
    return issue.text.startswith(
        (_JSON_CONVERT_OTHER, "Found JSON object with modelType=")
    )


def _is_json_followup(issue: LoadIssue) -> bool:
    return issue.text.startswith("Expected a ") and ", but found " in issue.text


def _same_item(cause: LoadIssue, followup: LoadIssue) -> bool:
    """Tells whether two JSON records name the same item."""
    first = _signature(cause.text)
    second = _signature(followup.text)
    if first is None or second is None:
        return False
    pairs = zip(first, second, strict=True)
    return all(a is None or b is None or a == b for a, b in pairs) and any(
        a is not None and a == b for a, b in zip(first, second, strict=True)
    )


def _signature(text: str) -> tuple[str | None, str | None, str | None] | None:
    """Reads the model type, id, and idShort that a JSON record names."""
    unknown = _JSON_UNKNOWN_TYPE.match(text)
    if unknown is not None:
        return (unknown.group(1), None, None)
    convert = _JSON_CONVERT.match(text)
    if convert is not None:
        body = convert.group(3)
        return (
            convert.group(1),
            _first(_ID, body, 2),
            _first(_ID_SHORT, body, 2),
        )
    expected = _JSON_EXPECTED.match(text)
    if expected is not None:
        body = expected.group(3)
        return (
            _first(_MODEL_TYPE, body),
            _first(_ID, body, 2),
            _first(_ID_SHORT, body, 2),
        )
    return None


# -- words -------------------------------------------------------------------


def _xml_scope(constructor: str) -> Scope:
    if constructor in _OBJECT_CONSTRUCTORS:
        return Scope.OBJECT
    if constructor in _ELEMENT_CONSTRUCTORS:
        return Scope.ELEMENT
    return Scope.DETAIL


def _xml_subject(tag: str, constructor: str) -> str:
    name = _words(_local_name(tag))
    noun = _words(constructor.removeprefix("construct_"))
    if name in noun or noun in name or constructor in _ELEMENT_CONSTRUCTORS:
        return name
    return f'{noun} "{name}"'


def _json_scope(model_type: str) -> Scope:
    if model_type in _TOP_LEVEL_TYPES:
        return Scope.OBJECT
    if model_type in _ELEMENT_TYPES:
        return Scope.ELEMENT
    return Scope.DETAIL


def _json_location(body: str) -> str:
    identifier = _first(_ID, body, 2)
    if identifier:
        return f"id {identifier}"
    id_short = _first(_ID_SHORT, body, 2)
    return f"idShort {id_short}" if id_short else ""


def _first(pattern: re.Pattern[str], text: str, group: int = 1) -> str | None:
    match = pattern.search(text)
    return match.group(group) if match else None


def _local_name(tag: str) -> str:
    """Removes the namespace or the prefix from an XML tag."""
    return re.split(r"[}:]", tag)[-1]


def _words(name: str) -> str:
    """Turns `SubmodelElementList` or `submodel_element` into words."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.replace("_", " "))
    return spaced.lower()


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _number(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {_plural(noun)}"


def _plural(noun: str) -> str:
    if noun.endswith("y"):
        return noun[:-1] + "ies"
    if noun.endswith("s"):
        return noun + "es"
    return noun + "s"


def _join(items: list[str]) -> str:
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
