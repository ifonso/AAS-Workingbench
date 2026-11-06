"""The save flow: check what a save would lose or cannot do, then write.

The flow takes the content to save as a `SaveSource` and the settings that
change the output as explicit `SaveOptions`, so that it knows neither the
legacy `Package` nor the application settings. The caller supplies the writer
and the question to the user as functions.

The checks follow the editor plan:

* A package that cannot be written is refused, with no way to save anyway:
  a File that points to a package path with no stored file (D5), a File under
  an annotation, which the SDK skips when it writes, and a partial package
  that would overwrite its own source (D6).
* Content that a save drops is a warning, and the user may save anyway (D7):
  stored files that nothing refers to, and everything that only an AASX holds
  when the target is JSON or XML.
"""

from collections.abc import Callable
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
from typing import Protocol

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.domain.file_references import file_references
from aas_editor.domain.file_references import missing_files
from aas_editor.domain.file_references import unreferenced_files
from aas_editor.domain.parts import CoreProperties
from aas_editor.domain.parts import Thumbnail

# How many names an issue lists before it summarizes the rest.
MAX_LISTED = 10


class PackageFormat(Enum):
    """A file format that packages can be saved in."""

    AASX = "aasx"
    JSON = "json"
    XML = "xml"


def package_format(path: Path) -> PackageFormat:
    """Finds the format of a package file from its extension.

    Args:
        path: A package file, which may not exist yet.

    Returns:
        The format of the file.

    Raises:
        TypeError: If the extension is not `.aasx`, `.json`, or `.xml`.
    """
    suffix = path.suffix.lower().strip()
    for package_format_ in PackageFormat:
        if suffix == f".{package_format_.value}":
            return package_format_
    raise TypeError("Wrong file type:", path.suffix)


@dataclass(frozen=True)
class SaveOptions:
    """The settings that change what a save writes.

    Attributes:
        write_json_in_aasx: Write the AAS part of an AASX as JSON, not XML.
        pretty_json: Indent JSON files.
        sort_json_keys: Order the keys of JSON files alphabetically.
    """

    write_json_in_aasx: bool = False
    pretty_json: bool = True
    sort_json_keys: bool = True


class SaveSource(Protocol):
    """What a save needs to know about the package it saves."""

    @property
    def objects(
        self,
    ) -> model.AbstractObjectStore[model.Identifier, model.Identifiable]:
        """The shells, submodels, and concept descriptions."""
        ...

    @property
    def files(self) -> AbstractSupplementaryFileContainer:
        """The supplementary files stored in the package."""
        ...

    @property
    def thumbnail(self) -> Thumbnail | None:
        """The thumbnail of the package, if it has one."""
        ...

    @property
    def core_properties(self) -> CoreProperties | None:
        """The OPC core properties of the package, if it has any."""
        ...

    @property
    def partial(self) -> bool:
        """True if the package was opened in failsafe mode.

        The SDK does not report what failsafe mode skipped, so the package may
        be missing objects, and must not overwrite its source.
        """
        ...

    @property
    def source_file(self) -> Path | None:
        """The file that the package was read from, or None for a new one."""
        ...


class PackageWriter(Protocol):
    """Writes the content to a file, all or nothing."""

    def __call__(
        self, target: Path, source: SaveSource, options: SaveOptions
    ) -> None:
        """Writes the package.

        Args:
            target: The file to create or replace.
            source: The content to write.
            options: The settings that change the output.
        """
        ...


@dataclass(frozen=True)
class SaveIssue:
    """One reason that a save is refused or needs the user's confirmation.

    Attributes:
        message: A sentence for the user.
        details: The names that the sentence is about, such as file paths.
    """

    message: str
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class SaveCheck:
    """The result of checking a save before it writes.

    Attributes:
        blockers: Reasons that the save cannot go on. There is no way around
            them.
        warnings: Content that the save drops. The user may save anyway.
    """

    blockers: tuple[SaveIssue, ...] = ()
    warnings: tuple[SaveIssue, ...] = ()


class SaveChecker(Protocol):
    """Finds what would stop a save or be lost by it."""

    def __call__(
        self, source: SaveSource, target: Path, options: SaveOptions
    ) -> SaveCheck:
        """Checks a save.

        Args:
            source: The content to save.
            target: The file to save to.
            options: The settings that change the output.

        Returns:
            The blockers and the warnings.
        """
        ...


class SaveStatus(Enum):
    """How a save ended."""

    SAVED = "saved"
    CANCELLED = "cancelled"
    REFUSED = "refused"


@dataclass(frozen=True)
class SaveOutcome:
    """The end of a save, with the check that led to it.

    Attributes:
        status: Whether the package was written.
        check: What the check found, for the caller to show when the save was
            refused.
    """

    status: SaveStatus
    check: SaveCheck


def check_save(
    source: SaveSource, target: Path, options: SaveOptions
) -> SaveCheck:
    """Finds what would stop a save or be lost by it.

    Args:
        source: The content to save.
        target: The file to save to.
        options: The settings that change the output. No check depends on
            them yet.

    Returns:
        The blockers and the warnings, both empty if the save is safe.

    Raises:
        TypeError: If the extension of the target is not supported.
    """
    del options
    target_format = package_format(target)
    blockers: list[SaveIssue] = []
    warnings: list[SaveIssue] = []

    if (
        source.partial
        and source.source_file is not None
        and _same_file(source.source_file, target)
    ):
        blockers.append(
            SaveIssue(
                "This package was opened in recovery mode, so objects that "
                "could not be read are missing. It cannot overwrite its "
                "source. Use Save As to write a copy."
            )
        )

    references = file_references(source.objects)
    stored_files = list(source.files)

    if target_format is PackageFormat.AASX:
        in_annotations = [ref for ref in references if ref.in_annotation]
        if in_annotations:
            blockers.append(
                SaveIssue(
                    "A File under an annotation cannot be saved to an AASX "
                    "file, because the SDK skips annotations when it writes "
                    "the files. Save as JSON or XML, or move the File out of "
                    "the annotation.",
                    _listed(
                        f"{ref.location} ({ref.path})" for ref in in_annotations
                    ),
                )
            )
        dangling = missing_files(
            (ref for ref in references if not ref.in_annotation), stored_files
        )
        if dangling:
            blockers.append(
                SaveIssue(
                    "A File points to a file that is not in the package, so "
                    "the package cannot be written. Remove the path, or add "
                    "the file.",
                    _listed(f"{ref.location} ({ref.path})" for ref in dangling),
                )
            )
        unreferenced = unreferenced_files(references, stored_files)
        if unreferenced:
            warnings.append(
                SaveIssue(
                    "These files are in the package, but no File element or "
                    "thumbnail refers to them. They are not saved.",
                    _listed(unreferenced),
                )
            )
    else:
        if stored_files:
            warnings.append(
                SaveIssue(
                    f"{target_format.value.upper()} files cannot hold "
                    "supplementary files. These files are not saved.",
                    _listed(stored_files),
                )
            )
        dropped = [
            name
            for name, present in (
                ("The package thumbnail", source.thumbnail is not None),
                (
                    "The package properties",
                    source.core_properties is not None,
                ),
            )
            if present
        ]
        if dropped:
            warnings.append(
                SaveIssue(
                    f"{target_format.value.upper()} files cannot hold "
                    "package metadata. These are not saved.",
                    tuple(dropped),
                )
            )

    return SaveCheck(tuple(blockers), tuple(warnings))


def save(
    source: SaveSource,
    target: Path,
    options: SaveOptions,
    writer: PackageWriter,
    confirm: Callable[[SaveCheck], bool],
    checker: SaveChecker = check_save,
) -> SaveOutcome:
    """Checks a save, asks the user about warnings, and writes.

    Args:
        source: The content to save.
        target: The file to save to.
        options: The settings that change the output.
        writer: Writes the content. It must leave the target untouched when it
            fails.
        confirm: Called with the check when there are warnings and no
            blockers. Returns True to save anyway.
        checker: Makes the check. `check_save` by default. The save gate
            passes one that adds the findings of the validation rules (D5).

    Returns:
        The status. The writer was called only if it is `SAVED`.

    Raises:
        TypeError: If the extension of the target is not supported.
    """
    check = checker(source, target, options)
    if check.blockers:
        return SaveOutcome(SaveStatus.REFUSED, check)
    if check.warnings and not confirm(check):
        return SaveOutcome(SaveStatus.CANCELLED, check)
    writer(target, source, options)
    return SaveOutcome(SaveStatus.SAVED, check)


def _same_file(first: Path, second: Path) -> bool:
    # normcase ignores the case of Windows paths, where files are case-blind.
    return os.path.normcase(first.resolve()) == os.path.normcase(
        second.resolve()
    )


def _listed(names: Iterable[str]) -> tuple[str, ...]:
    listed = list(names)
    if len(listed) <= MAX_LISTED:
        return tuple(listed)
    rest = len(listed) - MAX_LISTED
    return (*listed[:MAX_LISTED], f"... and {rest} more")
