"""Reads and writes AAS packages through the BaSyx adapters.

All AAS content goes through `basyx`. These things need more than its public
API, and all are isolated here and covered by tests:

* `_TolerantReader` overrides protected methods of `AASXReader`. The SDK
  raises `KeyError` when a File element points to a part that is not in the
  package, even in failsafe mode, and it does not read files under
  annotations. The reader also notes which part it parses and which objects
  each part holds, because the SDK skips an object whose id an earlier part
  has without a log record.
* `reader.reader` is also used to read every file that an AAS part declares
  with an `aas-suppl` relationship. The SDK reads only the files that a File
  element or the thumbnail names, so the other declared files of a package,
  such as five of the six images of the Technical Data template, were lost
  silently. This is a narrow exception to "all AAS content goes through
  `basyx`" (D3), because a file that a package declares is the user's content
  and is kept. The write side needs no exception: `AASXWriter` takes
  `additional_relationships`, and its public `writer` opens the parts, so the
  files that nothing refers to are written with the same SDK calls (ADR 0030).
* `_accept_old_relationships` wraps a method of the reader inside the SDK.
  Many AASX files have the `www.` relationship types of the first versions. The
  SDK accepts that for the origin only, and then finds no AAS part in the file.
* `_SdkLogCapture` listens to the logger of the SDK during one read. Failsafe
  mode logs every object it skips, and that is the only account of it.
* `_read_thumbnail` reads the part name and the content type of the package
  thumbnail through `reader.reader`, because `get_thumbnail` returns only bytes.
* `_ThumbnailLinkingWriter` marks a part that the SDK has written already as
  the package thumbnail, because `write_thumbnail` would add a second zip entry
  with the same name.

This module must not import the legacy `Package`.
"""

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from types import TracebackType
from typing import Any
from typing import BinaryIO
from typing import cast

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import RELATIONSHIP_TYPE_AAS_SUPL
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from basyx.aas.adapter.json import AASToJsonEncoder

# The SDK functions take **kwargs without annotations, which strict mode
# reports as partially unknown types.
from basyx.aas.adapter.json import (
    read_aas_json_file_into,  # pyright: ignore[reportUnknownVariableType]
)
from basyx.aas.adapter.json import (
    write_aas_json_file,  # pyright: ignore[reportUnknownVariableType]
)
from basyx.aas.adapter.xml import (
    read_aas_xml_file_into,  # pyright: ignore[reportUnknownVariableType]
)
from basyx.aas.adapter.xml import (
    write_aas_xml_file,  # pyright: ignore[reportUnknownVariableType]
)
from pyecma376_2.package_model import RELATIONSHIP_TYPE_THUMBNAIL
from pyecma376_2.package_model import OPCRelationship
from pyecma376_2.package_model import OPCTargetMode
from pyecma376_2.package_model import normalize_part_name

from aas_workingbench.application.save import PackageFormat
from aas_workingbench.application.save import SaveOptions
from aas_workingbench.application.save import SaveSource
from aas_workingbench.application.save import package_format
from aas_workingbench.domain.file_references import file_references
from aas_workingbench.domain.file_references import is_package_path
from aas_workingbench.domain.load_report import LoadIssue
from aas_workingbench.domain.load_report import LoadReport
from aas_workingbench.domain.load_report import RawRecord
from aas_workingbench.domain.load_report import Severity
from aas_workingbench.domain.load_report import build_report
from aas_workingbench.domain.load_report import declared_file_not_loaded
from aas_workingbench.domain.load_report import duplicate_in_other_part
from aas_workingbench.domain.ordered_store import OrderedIdentifiableStore
from aas_workingbench.domain.part_names import find_clash
from aas_workingbench.domain.part_names import is_valid
from aas_workingbench.domain.parts import CoreProperties
from aas_workingbench.domain.parts import MissingFile
from aas_workingbench.domain.parts import Thumbnail
from aas_workingbench.domain.walking import is_annotation
from aas_workingbench.domain.walking import walk_elements

logger = logging.getLogger(__name__)


@dataclass
class PackageParts:
    """Everything that a package file holds, as read or about to be written.

    It satisfies `SaveSource`.

    Attributes:
        objects: The shells, submodels, and concept descriptions.
        files: The supplementary files of an AASX.
        thumbnail: The package thumbnail of an AASX, if any.
        core_properties: The OPC core properties of an AASX, if any.
        missing_files: The File elements that pointed to a part that is not in
            the package when it was read.
        partial: True if the package was read in failsafe mode, or if the
            reader found that it skipped an object without saying so.
        source_file: The file that was read, or None for a new package.
        load_report: What the SDK reported while it read the package. Empty for
            a package that was read strictly and a new one.
    """

    objects: model.SetIdentifiableStore[model.Identifiable] = field(
        default_factory=OrderedIdentifiableStore
    )
    files: DictSupplementaryFileContainer = field(
        default_factory=DictSupplementaryFileContainer
    )
    thumbnail: Thumbnail | None = None
    core_properties: CoreProperties | None = None
    missing_files: tuple[MissingFile, ...] = ()
    partial: bool = False
    source_file: Path | None = None
    load_report: LoadReport = field(default_factory=LoadReport)


class _SdkLogCapture:
    """Collects what the SDK logs while one package is read.

    Failsafe mode skips what it cannot construct and logs a record for each
    thing at warning or error level. This is a context manager that adds a
    handler to the `basyx` logger on entry and takes it off on exit, also when
    the read raises. It lowers the level of that logger only if the level is
    above warning, since the records would not exist otherwise, and puts it
    back. It keeps only the records of the thread that entered, so that a
    package read in the background does not take the records of another.

    Attributes:
        part: The OPC part being read now. The reader sets it, and the records
            that follow carry it.
        records: What was captured, in order.
    """

    def __init__(self) -> None:
        self.part = ""
        self.records: list[RawRecord] = []
        self._logger = logging.getLogger("basyx")
        self._handler = _CaptureHandler(self)
        self._level: int | None = None
        self._thread = threading.get_ident()

    def __enter__(self) -> "_SdkLogCapture":
        self._thread = threading.get_ident()
        self._logger.addHandler(self._handler)
        if self._logger.getEffectiveLevel() > logging.WARNING:
            self._level = self._logger.level
            self._logger.setLevel(logging.WARNING)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._logger.removeHandler(self._handler)
        if self._level is not None:
            self._logger.setLevel(self._level)
            self._level = None

    def add(self, record: logging.LogRecord) -> None:
        """Keeps a log record if it is of this thread and of interest."""
        if record.thread != self._thread or record.levelno < logging.WARNING:
            return
        severity = (
            Severity.ERROR
            if record.levelno >= logging.ERROR
            else Severity.WARNING
        )
        self.records.append(
            RawRecord(severity, record.name, record.getMessage(), self.part)
        )


class _CaptureHandler(logging.Handler):
    """Hands the records of the `basyx` logger to a capture."""

    def __init__(self, capture: _SdkLogCapture) -> None:
        super().__init__(level=logging.WARNING)
        self._capture = capture

    def emit(self, record: logging.LogRecord) -> None:
        self._capture.add(record)


_OLD_RELATIONSHIPS = "http://www.admin-shell.io/aasx/relationships/"
_RELATIONSHIPS = "http://admin-shell.io/aasx/relationships/"


def _accept_old_relationships(opc_reader: Any) -> None:
    """Makes a package reader report old relationship types as current ones.

    The result of `get_related_parts_by_type` is cached by the reader, so the
    types are moved in that result, once for each part. A save writes the
    current types, which migrates the file.

    Args:
        opc_reader: The `pyecma376_2` reader that the `AASXReader` holds.
    """
    original = opc_reader.get_related_parts_by_type

    def related_parts(part_name: str = "/") -> Any:
        related = original(part_name)
        for old_type in [
            name for name in related if name.startswith(_OLD_RELATIONSHIPS)
        ]:
            current = _RELATIONSHIPS + old_type[len(_OLD_RELATIONSHIPS) :]
            related[current].extend(related.pop(old_type))
        return related

    opc_reader.get_related_parts_by_type = related_parts


class _TolerantReader(AASXReader):
    """An AASX reader that records files it cannot find and does not fail.

    The SDK raises `KeyError` for a File element whose part is missing, in
    strict and in failsafe mode. This reader keeps the File value as it is,
    records it, and goes on. It also reads the files under annotations, which
    the SDK skips.

    It notes the part it parses and the objects each part holds. The SDK skips
    an object whose id an earlier part has, in strict mode as well, and logs
    nothing, so `silent_duplicates` finds those from the note.

    Attributes:
        missing_files: The File elements whose part is not in the package.
    """

    def __init__(
        self,
        file: str,
        failsafe: bool,
        capture: _SdkLogCapture | None = None,
    ) -> None:
        super().__init__(file, failsafe=failsafe)  # pyright: ignore[reportUnknownMemberType]
        _accept_old_relationships(self.reader)
        self.missing_files: list[MissingFile] = []
        self._capture = capture
        self._parts: list[tuple[str, list[model.Identifiable]]] = []
        self._aas_part_names: list[str] = []

    def _parse_aas_part(
        self, part_name: str, **kwargs: Any
    ) -> model.DictIdentifiableStore[model.Identifiable]:
        if self._capture is not None:
            self._capture.part = part_name
        if part_name not in self._aas_part_names:
            self._aas_part_names.append(part_name)
        parsed = cast(
            "model.DictIdentifiableStore[model.Identifiable]",
            super()._parse_aas_part(part_name, **kwargs),  # pyright: ignore[reportUnknownMemberType]
        )
        self._parts.append((part_name, list(parsed)))
        return parsed

    def read_declared_files(
        self, file_store: AbstractSupplementaryFileContainer
    ) -> list[LoadIssue]:
        """Loads the files that the AAS parts declare and nothing refers to.

        The SDK stores the files that File elements and the thumbnail name.
        An AAS part declares its files with `aas-suppl` relationships, and the
        rest of them are loaded here, with their content types. A file that
        is stored already, also under a spelling that differs in case, is not
        read again, and a file that is declared twice or by two parts is
        loaded once. The old `www.` relationship type counts, because
        `_accept_old_relationships` has moved it already.

        Args:
            file_store: The container that `read_into` filled.

        Returns:
            One issue for each declared file that could not be loaded, because
            its part is not in the package or its name cannot be kept. Nothing
            is raised for them.
        """
        issues: list[LoadIssue] = []
        seen: set[str] = set()
        # The SDK writes the target of a relationship in lower case, and OPC
        # compares names without case. The file keeps the name of its part.
        spelled = {
            normalize_part_name(item): item for item in self.reader.list_items()
        }
        for aas_part in self._aas_part_names:
            related = self.reader.get_related_parts_by_type(aas_part)
            for declared_name in related.get(RELATIONSHIP_TYPE_AAS_SUPL, ()):
                name = spelled.get(
                    normalize_part_name(declared_name), declared_name
                )
                if (
                    name in seen
                    or find_clash(name, list(file_store)) is not None
                ):
                    continue
                seen.add(name)
                reason = self._add_declared_file(name, file_store)
                if reason is not None:
                    logger.warning(
                        "Declared file not loaded: %s (declared by %s): %s",
                        name,
                        aas_part,
                        reason,
                    )
                    issues.append(
                        declared_file_not_loaded(name, aas_part, reason)
                    )
        return issues

    def _add_declared_file(
        self, name: str, file_store: AbstractSupplementaryFileContainer
    ) -> str | None:
        """Stores one declared part, and says why it could not be stored."""
        if not is_valid(name):
            return (
                "The name is not one that the editor can keep as a file of "
                "the package, so a save would not write it."
            )
        try:
            with self.reader.open_part(name) as part:
                content_type = self.reader.get_content_type(name)
                file_store.add_file(name, part, content_type)
        except (KeyError, ValueError, OSError) as error:
            return (
                "The package declares the file, but it has no such part"
                f" or cannot read it ({type(error).__name__}: {error})."
            )
        return None

    def silent_duplicates(self) -> list[LoadIssue]:
        """Finds the objects that the SDK skipped without a log record.

        An object that equals the one kept, as the SDK writes it to JSON, is
        not a loss and is not reported.

        Returns:
            One issue for each object whose id an earlier part has, and which
            differs from that object.
        """
        first: dict[str, tuple[str, model.Identifiable]] = {}
        found: list[LoadIssue] = []
        for part_name, objects in self._parts:
            for obj in objects:
                kept = first.get(obj.id)
                if kept is None:
                    first[obj.id] = (part_name, obj)
                elif not _same_content(kept[1], obj):
                    found.append(
                        duplicate_in_other_part(
                            type(obj).__name__, obj.id, part_name, kept[0]
                        )
                    )
        return found

    def _add_supplementary_file(
        self,
        part_name: str,
        file_path: str,
        file_store: AbstractSupplementaryFileContainer,
    ) -> str | None:
        try:
            return super()._add_supplementary_file(
                part_name, file_path, file_store
            )
        except KeyError:
            logger.warning(
                "Missing file in package: %s (referenced in %s)",
                file_path,
                part_name,
            )
            self.missing_files.append(MissingFile(part_name, file_path))
            return None

    def _collect_supplementary_files(
        self,
        part_name: str,
        root_element: model.AssetAdministrationShell | model.Submodel,
        file_store: AbstractSupplementaryFileContainer,
    ) -> None:
        super()._collect_supplementary_files(
            part_name, root_element, file_store
        )
        if not isinstance(root_element, model.Submodel):
            return
        for element in walk_elements(root_element):
            if (
                isinstance(element, model.File)
                and is_annotation(element)
                and element.value is not None
                and is_package_path(element.value)
            ):
                stored_name = self._add_supplementary_file(
                    part_name, element.value, file_store
                )
                if stored_name:
                    element.value = stored_name


class _ThumbnailLinkingWriter(AASXWriter):
    """An AASX writer that can mark a part it already wrote as the thumbnail.

    The package thumbnail of many real packages is also the default thumbnail
    of the shell, so the SDK writes the part as a supplementary file.
    `write_thumbnail` would write it a second time. The relationship that
    marks the thumbnail is written from `_thumbnail_part` when the writer
    closes, so setting it is all that is needed.
    """

    def link_written_thumbnail(self, name: str) -> None:
        """Marks an already written part as the package thumbnail.

        Args:
            name: The OPC part name.

        Raises:
            RuntimeError: If the package already has a thumbnail.
        """
        if self._thumbnail_part is not None:
            raise RuntimeError(
                f"package thumbnail has already been written to "
                f"{self._thumbnail_part}."
            )
        self._thumbnail_part = name


def _same_content(
    first: model.Identifiable, second: model.Identifiable
) -> bool:
    """Tells whether the SDK writes two objects to the same JSON."""
    return type(first) is type(second) and json.dumps(
        first, cls=AASToJsonEncoder, sort_keys=True
    ) == json.dumps(second, cls=AASToJsonEncoder, sort_keys=True)


def read_package(path: Path, failsafe: bool = False) -> PackageParts:
    """Reads an AASX, JSON, or XML file.

    Every reader is closed before this function returns, so that the file can
    be replaced afterwards on Windows.

    Args:
        path: The file to read.
        failsafe: Skip defective objects instead of raising. The package is
            then marked as partial, and `load_report` lists what the SDK
            logged about the objects it skipped.

    Returns:
        The content of the file.

    Raises:
        TypeError: If the extension is not supported.
        Exception: Whatever the SDK raises for a file it cannot read, such as
            `ValueError` or `KeyError`.
    """
    parts = PackageParts(partial=failsafe, source_file=path)
    file_format = package_format(path)
    capture = _SdkLogCapture()
    silent: list[LoadIssue] = []
    declared: list[LoadIssue] = []
    with capture:
        if file_format is PackageFormat.XML:
            read_aas_xml_file_into(parts.objects, path, failsafe=failsafe)
        elif file_format is PackageFormat.JSON:
            read_aas_json_file_into(parts.objects, path, failsafe=failsafe)
        else:
            reader = _TolerantReader(
                path.as_posix(), failsafe=failsafe, capture=capture
            )
            with reader:
                reader.read_into(parts.objects, parts.files)  # pyright: ignore[reportUnknownMemberType]
                parts.thumbnail = _read_thumbnail(reader)
                parts.core_properties = _non_empty(reader.get_core_properties())
                parts.missing_files = tuple(reader.missing_files)
                silent = reader.silent_duplicates()
                declared = reader.read_declared_files(parts.files)
    # A strict read raises where a failsafe read skips, so its records are
    # remarks about content that was kept, and the editor does not show them.
    report = build_report(capture.records if failsafe else [])
    if silent:
        # Not logged by the SDK, so also not logged in strict mode, where
        # nothing else would say that the package lost an object.
        report = LoadReport((*report.issues, *silent))
        parts.partial = True
    if declared:
        # The package is not partial: the part is not in the file, so a save
        # does not lose anything that the file holds.
        report = LoadReport((*report.issues, *declared))
    parts.load_report = report
    return parts


def write_package(
    target: Path, source: SaveSource, options: SaveOptions
) -> None:
    """Writes a package to a file, all or nothing.

    The package is written to a temporary file in the folder of the target,
    with `failsafe=False`, and then moved over the target in one step. If
    anything fails, the target stays as it was and the temporary file is
    removed.

    Args:
        target: The file to create or replace. Its extension sets the format.
        source: The content to write.
        options: The settings that change the output.

    Raises:
        TypeError: If the extension is not supported.
        Exception: Whatever the SDK or the file system raises. `KeyError` means
            that a File element has no stored file.
    """
    file_format = package_format(target)
    with _replacing(target) as handle:
        if file_format is PackageFormat.XML:
            write_aas_xml_file(handle, source.objects)
        elif file_format is PackageFormat.JSON:
            _write_json(handle, source, options)
        else:
            _write_aasx(handle, source, options)


def _write_json(
    handle: BinaryIO, source: SaveSource, options: SaveOptions
) -> None:
    # newline="\n" keeps the file the same on every platform.
    text = io.TextIOWrapper(handle, encoding="utf-8", newline="\n")
    write_aas_json_file(
        text,
        source.objects,
        indent=2 if options.pretty_json else None,
        sort_keys=options.sort_json_keys,
    )
    text.flush()
    text.detach()


def _write_aasx(
    handle: BinaryIO, source: SaveSource, options: SaveOptions
) -> None:
    extension = "json" if options.write_json_in_aasx else "xml"
    writer = _ThumbnailLinkingWriter(handle, failsafe=False)
    with writer:
        # The SDK writes the files that a File element or a shell thumbnail
        # refers to. The others are the user's content as well (ADR 0030), so
        # their parts are opened here, and declared through the relationships
        # that the SDK writes for the AAS part.
        unreferenced = _unreferenced_names(source)
        for name in unreferenced:
            with writer.writer.open_part(
                name, source.files.get_content_type(name)
            ) as part:
                source.files.write_file(name, part)
        writer.write_all_aas_objects(
            f"/aasx/data.{extension}",
            source.objects,
            source.files,
            write_json=options.write_json_in_aasx,
            additional_relationships=[
                OPCRelationship(
                    f"s{number}",
                    RELATIONSHIP_TYPE_AAS_SUPL,
                    name,
                    OPCTargetMode.INTERNAL,
                )
                for number, name in enumerate(unreferenced)
            ],
        )
        thumbnail = source.thumbnail
        if thumbnail is not None:
            if _is_written_as_file(thumbnail.name, source):
                # The part is a stored file, so it has been written. Writing it
                # again adds a second zip entry with the same name. Only the
                # relationship that marks it as the package thumbnail is
                # missing.
                writer.link_written_thumbnail(thumbnail.name)
            else:
                writer.write_thumbnail(
                    thumbnail.name,
                    bytearray(thumbnail.data),
                    thumbnail.content_type,
                )
        if source.core_properties is not None:
            writer.write_core_properties(source.core_properties)


def _unreferenced_names(source: SaveSource) -> list[str]:
    """Lists the stored files that the SDK writer would not write.

    The writer writes the files that a File element or the default thumbnail
    of a shell refers to. A File under an annotation is not one of them.
    """
    referenced = {
        ref.path
        for ref in file_references(source.objects)
        if not ref.in_annotation
    }
    return [name for name in source.files if name not in referenced]


def _is_written_as_file(part_name: str, source: SaveSource) -> bool:
    """Tells whether a part is written as a stored file.

    Every stored file is written, by the SDK or by `_write_aasx`.
    """
    normalized = normalize_part_name(part_name)
    return any(normalize_part_name(name) == normalized for name in source.files)


def _read_thumbnail(reader: AASXReader) -> Thumbnail | None:
    # The SDK's get_thumbnail returns the bytes only. The part name and the
    # content type are needed to write the thumbnail again.
    parts = reader.reader.get_related_parts_by_type()
    names = parts.get(RELATIONSHIP_TYPE_THUMBNAIL)
    if not names:
        return None
    name = names[0]
    with reader.reader.open_part(name) as part:
        data = part.read()
    return Thumbnail(name, reader.reader.get_content_type(name), data)


def _non_empty(properties: CoreProperties) -> CoreProperties | None:
    """Returns None when the package has no core properties.

    The SDK returns an empty object then, and writing it back would add a part
    that the original did not have.
    """
    return properties if any(vars(properties).values()) else None


@contextmanager
def _replacing(target: Path) -> Generator[BinaryIO]:
    """Yields a temporary file that replaces the target when the block ends."""
    descriptor, name = tempfile.mkstemp(
        dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            yield handle
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic on one file system, which holds because the temporary file is
        # in the folder of the target.
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
