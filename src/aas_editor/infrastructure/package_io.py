"""Reads and writes AAS packages through the BaSyx adapters.

All AAS content goes through `basyx`. Three things need more than its public
API, and all are isolated here and covered by tests:

* `_TolerantReader` overrides two protected methods of `AASXReader`. The SDK
  raises `KeyError` when a File element points to a part that is not in the
  package, even in failsafe mode, and it does not read files under annotations.
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
import logging
import os
from pathlib import Path
import tempfile
from typing import BinaryIO

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer

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
from pyecma376_2.package_model import normalize_part_name

from aas_editor.application.save import PackageFormat
from aas_editor.application.save import SaveOptions
from aas_editor.application.save import SaveSource
from aas_editor.application.save import package_format
from aas_editor.domain.file_references import file_references
from aas_editor.domain.file_references import is_package_path
from aas_editor.domain.ordered_store import OrderedIdentifiableStore
from aas_editor.domain.parts import CoreProperties
from aas_editor.domain.parts import MissingFile
from aas_editor.domain.parts import Thumbnail
from aas_editor.domain.walking import is_annotation
from aas_editor.domain.walking import walk_elements

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
        partial: True if the package was read in failsafe mode.
        source_file: The file that was read, or None for a new package.
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


class _TolerantReader(AASXReader):
    """An AASX reader that records files it cannot find and does not fail.

    The SDK raises `KeyError` for a File element whose part is missing, in
    strict and in failsafe mode. This reader keeps the File value as it is,
    records it, and goes on. It also reads the files under annotations, which
    the SDK skips.
    """

    def __init__(self, file: str, failsafe: bool) -> None:
        super().__init__(file, failsafe=failsafe)  # pyright: ignore[reportUnknownMemberType]
        self.missing_files: list[MissingFile] = []

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


def read_package(path: Path, failsafe: bool = False) -> PackageParts:
    """Reads an AASX, JSON, or XML file.

    Every reader is closed before this function returns, so that the file can
    be replaced afterwards on Windows.

    Args:
        path: The file to read.
        failsafe: Skip defective objects instead of raising. The package is
            then marked as partial, because the SDK does not say what it
            skipped.

    Returns:
        The content of the file.

    Raises:
        TypeError: If the extension is not supported.
        Exception: Whatever the SDK raises for a file it cannot read, such as
            `ValueError` or `KeyError`.
    """
    parts = PackageParts(partial=failsafe, source_file=path)
    file_format = package_format(path)
    if file_format is PackageFormat.XML:
        read_aas_xml_file_into(parts.objects, path, failsafe=failsafe)
    elif file_format is PackageFormat.JSON:
        read_aas_json_file_into(parts.objects, path, failsafe=failsafe)
    else:
        reader = _TolerantReader(path.as_posix(), failsafe=failsafe)
        with reader:
            reader.read_into(parts.objects, parts.files)  # pyright: ignore[reportUnknownMemberType]
            parts.thumbnail = _read_thumbnail(reader)
            parts.core_properties = _non_empty(reader.get_core_properties())
            parts.missing_files = tuple(reader.missing_files)
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
        writer.write_all_aas_objects(
            f"/aasx/data.{extension}",
            source.objects,
            source.files,
            write_json=options.write_json_in_aasx,
        )
        thumbnail = source.thumbnail
        if thumbnail is not None:
            if _is_written_as_file(thumbnail.name, source):
                # The part is the default thumbnail of a shell, or a File, so
                # the writer has written it. Writing it again adds a second zip
                # entry with the same name. Only the relationship that marks
                # it as the package thumbnail is missing.
                writer.link_written_thumbnail(thumbnail.name)
            else:
                writer.write_thumbnail(
                    thumbnail.name,
                    bytearray(thumbnail.data),
                    thumbnail.content_type,
                )
        if source.core_properties is not None:
            writer.write_core_properties(source.core_properties)


def _is_written_as_file(part_name: str, source: SaveSource) -> bool:
    """Tells whether the SDK writes a part as a supplementary file."""
    normalized = normalize_part_name(part_name)
    return any(
        normalize_part_name(ref.path) == normalized
        for ref in file_references(source.objects)
        if not ref.in_annotation and ref.path in source.files
    )


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
