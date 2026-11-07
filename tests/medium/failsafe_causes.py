"""Why a package needs the failsafe branch, found by reading it both ways.

The editor opens a package strictly first, and offers the failsafe branch when
that raises (D6). The SDK logs every object that failsafe mode drops, and
`read_package` turns those records into a load report (ADR 0018). These helpers
count the same records by cause, with a handler of their own, and turn the
exception of the strict read into a short label, so that a test can pin the
causes for the whole corpus and the documentation can count them.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
import json
import logging
from pathlib import Path
import re
from typing import Any

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from basyx.aas.adapter.json import AASToJsonEncoder
from basyx.aas.adapter.json.json_deserialization import AASFromJsonDecoder
from basyx.aas.adapter.xml.xml_deserialization import AASFromXmlDecoder

from aas_workingbench.infrastructure.package_io import _TolerantReader
from aas_workingbench.infrastructure.package_io import read_package

TEMPLATES_DIR = (
    Path(__file__).parents[2]
    / "src"
    / "aas_workingbench"
    / "submodel_templates"
)

DUPLICATE_ID = "duplicate id"
EMPTY_TEXT = "empty text"
MISSING_CHILD = "missing mandatory child"
NO_KEYS = "reference without keys"
INVALID_ENUM = "invalid enumeration text"
SHORT_NAME = "short name over 18 characters"
UNPARSEABLE = "value not parseable for its type"

_CONSTRAINT = re.compile(r"\(Constraint (AASd-\d+)\)")
_LABELS: tuple[tuple[str, str], ...] = (
    ("duplicate identifier", DUPLICATE_ID),
    ("has no text", EMPTY_TEXT),
    ("has no child", MISSING_CHILD),
    ("must have at least one key", NO_KEYS),
    ("has invalid text", INVALID_ENUM),
    ("ShortNameTypeIEC61360", SHORT_NAME),
    ("could not convert", UNPARSEABLE),
)


def label_of(message: str) -> str:
    """Turns an error message of the SDK into a short cause."""
    constraint = _CONSTRAINT.search(message)
    if constraint:
        return constraint.group(1)
    for fragment, label in _LABELS:
        if fragment in message:
            return label
    return f"other: {message[:60]}"


def templates() -> list[Path]:
    """Lists the bundled AASX templates in a stable order."""
    return sorted(TEMPLATES_DIR.rglob("*.aasx"))


def relative_name(path: Path) -> str:
    """Names a template by its path below the templates folder."""
    return path.relative_to(TEMPLATES_DIR).as_posix()


def strict_cause(path: Path) -> str | None:
    """Reads a package strictly and returns the cause of the first failure.

    Returns:
        A label, or None if the package opens strictly.
    """
    try:
        read_package(path, failsafe=False)
    except Exception as error:  # noqa: BLE001 - any SDK error is a cause
        root: BaseException = error
        while root.__cause__ is not None:
            root = root.__cause__
        return label_of(str(root))
    return None


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def skipped_causes(path: Path) -> Counter[str]:
    """Reads a package in failsafe mode and counts what it logged by cause.

    Each record is an object or a part that the SDK dropped.
    """
    records = _Records()
    sdk = logging.getLogger("basyx")
    sdk.addHandler(records)
    try:
        read_package(path, failsafe=True)
    finally:
        sdk.removeHandler(records)
    return Counter(label_of(message) for message in records.messages)


@dataclass
class DuplicateKinds:
    """What the objects that share an id are, in one package.

    Attributes:
        identical: Groups of concept descriptions with equal content.
        different: Groups of concept descriptions with different content.
        submodel_and_concept: Groups of a submodel and a concept description.
    """

    identical: int = 0
    different: int = 0
    submodel_and_concept: int = 0
    other: int = 0
    _seen: dict[str, list[model.Identifiable]] = field(default_factory=dict)

    @property
    def only_identical(self) -> bool:
        """True if the package has duplicates and all are equal copies."""
        return (
            self.identical > 0
            and self.different == 0
            and self.submodel_and_concept == 0
            and self.other == 0
        )


def duplicate_kinds(path: Path) -> DuplicateKinds:
    """Finds what the objects with a shared id are, by reading with a recorder.

    The SDK drops the second object of an id before the caller sees it. A
    decoder that records each object it constructs, passed through the
    documented `decoder` option, shows both.
    """
    constructed: list[model.Identifiable] = []
    xml_decoder, json_decoder = _recording_decoders(constructed.append)
    reader = _DecodingReader(path.as_posix(), xml_decoder, json_decoder)
    with reader:
        reader.read_into(
            model.SetIdentifiableStore[model.Identifiable](),
            DictSupplementaryFileContainer(),
        )
    by_id: dict[str, list[model.Identifiable]] = {}
    for obj in constructed:
        by_id.setdefault(obj.id, []).append(obj)
    kinds = DuplicateKinds()
    for group in by_id.values():
        if len(group) < 2:
            continue
        types = {type(obj) for obj in group}
        texts = {json.dumps(obj, cls=AASToJsonEncoder) for obj in group}
        if types == {ConceptDescription} and len(texts) == 1:
            kinds.identical += 1
        elif types == {ConceptDescription}:
            kinds.different += 1
        elif model.Submodel in types and ConceptDescription in types:
            kinds.submodel_and_concept += 1
        else:
            kinds.other += 1
    return kinds


class _DecodingReader(_TolerantReader):
    """A failsafe reader that decodes with the given decoders."""

    def __init__(
        self, file: str, xml_decoder: type[Any], json_decoder: type[Any]
    ) -> None:
        super().__init__(file, failsafe=True)
        self._xml_decoder = xml_decoder
        self._json_decoder = json_decoder

    def _parse_aas_part(self, part_name: str, **kwargs: Any) -> Any:
        content_type = self.reader.get_content_type(part_name)
        extension = part_name.rsplit(".", 1)[-1]
        is_json = content_type.split(";")[0] in (
            "text/json",
            "application/json",
        ) or (content_type == "" and extension == "json")
        kwargs["decoder"] = self._json_decoder if is_json else self._xml_decoder
        return super()._parse_aas_part(part_name, **kwargs)


def _recording_decoders(
    record: Callable[[model.Identifiable], None],
) -> tuple[type[Any], type[Any]]:
    class Xml(AASFromXmlDecoder):
        @classmethod
        def construct_submodel(
            cls,
            element: Any,
            object_class: Any = model.Submodel,
            **kwargs: Any,
        ) -> Any:
            obj = super().construct_submodel(element, object_class, **kwargs)
            record(obj)
            return obj

        @classmethod
        def construct_concept_description(
            cls,
            element: Any,
            object_class: Any = ConceptDescription,
            **kwargs: Any,
        ) -> Any:
            obj = super().construct_concept_description(
                element, object_class, **kwargs
            )
            record(obj)
            return obj

        @classmethod
        def construct_asset_administration_shell(
            cls,
            element: Any,
            object_class: Any = model.AssetAdministrationShell,
            **kwargs: Any,
        ) -> Any:
            obj = super().construct_asset_administration_shell(
                element, object_class, **kwargs
            )
            record(obj)
            return obj

    class Json(AASFromJsonDecoder):
        @classmethod
        def object_hook(cls, dct: dict[str, object]) -> object:
            obj = super().object_hook(dct)
            if isinstance(obj, model.Identifiable):
                record(obj)
            return obj

    return Xml, Json


def template_by_name() -> dict[str, Path]:
    """Maps the names of `relative_name` to the template files."""
    return {relative_name(path): path for path in templates()}


def skipped_summary(names: list[str]) -> dict[str, tuple[int, int]]:
    """Counts what failsafe mode drops in the named templates, by cause.

    Returns:
        For each cause, the number of packages that have it and the number of
        objects or parts dropped for it.
    """
    by_name = template_by_name()
    packages: dict[str, set[str]] = {}
    dropped: Counter[str] = Counter()
    for name in names:
        for cause, count in skipped_causes(by_name[name]).items():
            packages.setdefault(cause, set()).add(name)
            dropped[cause] += count
    return {
        cause: (len(found), dropped[cause]) for cause, found in packages.items()
    }


@dataclass
class DuplicateTotals:
    """The groups of objects that share an id in several packages.

    Attributes:
        packages: How many packages were looked at.
        identical: Groups of concept descriptions with equal content.
        different: Groups of concept descriptions with different content.
        submodel_and_concept: Groups of a submodel and a concept description.
        only_equal_packages: Packages whose only shared ids are equal copies,
            which failsafe mode could drop without a loss.
    """

    packages: int = 0
    identical: int = 0
    different: int = 0
    submodel_and_concept: int = 0
    only_equal_packages: int = 0


def duplicate_summary(names: list[str]) -> DuplicateTotals:
    """Adds up `duplicate_kinds` over the named templates."""
    by_name = template_by_name()
    totals = DuplicateTotals()
    for name in names:
        kinds = duplicate_kinds(by_name[name])
        totals.packages += 1
        totals.identical += kinds.identical
        totals.different += kinds.different
        totals.submodel_and_concept += kinds.submodel_and_concept
        totals.only_equal_packages += int(kinds.only_identical)
    return totals
