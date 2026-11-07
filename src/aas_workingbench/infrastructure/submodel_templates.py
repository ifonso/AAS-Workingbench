"""The submodel templates that come with the program, read one at a time.

The folder holds more than 250 files. Reading all of them takes seconds, so a
window that did it at its start made the user wait for a menu that most of them
never open. This module lists the files, which takes milliseconds, and reads a
file when the user first asks for what is in it.

Nothing here changes what it read. A reader that wants to change a submodel
copies it first, as the paste of a template does.

Example:
    >>> templates = SubmodelTemplates(Path("submodel_templates"))
    >>> names = templates.files()  # doctest: +SKIP
    >>> content = templates.read(names[0])  # doctest: +SKIP
"""

from dataclasses import dataclass
import logging
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_workingbench.infrastructure.package_io import read_package

_SUFFIXES = (".aasx", ".xml", ".json")
"""The kinds of file that a template can be, in the order they are listed."""


@dataclass(frozen=True)
class TemplateContent:
    """What one template file holds.

    Attributes:
        objects: The shells, submodels, and concept descriptions.
        files: The supplementary files of an AASX, or None for a JSON or XML
            file, which has none.
    """

    objects: model.AbstractObjectStore[model.Identifier, model.Identifiable]
    files: AbstractSupplementaryFileContainer | None


class SubmodelTemplates:
    """The template files of one folder, read when they are asked for.

    Attributes:
        folder: The folder that holds the templates, with its subfolders.
    """

    def __init__(self, folder: Path) -> None:
        """Remembers the folder without reading anything from it.

        Args:
            folder: The folder that holds the templates. It is created if it
                does not exist, as the program always did.
        """
        self.folder = folder
        self._read: dict[Path, TemplateContent | None] = {}

    def files(self) -> list[Path]:
        """Lists the template files, without reading them.

        Returns:
            The paths relative to the folder: the AASX files first, then XML,
            then JSON, each in the order of the file system.
        """
        if not self.folder.is_dir():
            self.folder.mkdir()
        found: list[Path] = []
        for suffix in _SUFFIXES:
            found.extend(
                path.relative_to(self.folder)
                for path in self.folder.rglob(f"*{suffix}")
            )
        return found

    def read(self, relative: Path) -> TemplateContent | None:
        """Reads one template file, once.

        Args:
            relative: A path as `files` gives it.

        Returns:
            What the file holds, or None if it cannot be read. The reason is
            logged the first time, and a file that failed is not tried again.
        """
        if relative not in self._read:
            self._read[relative] = self._load(relative)
        return self._read[relative]

    def _load(self, relative: Path) -> TemplateContent | None:
        path = self.folder / relative
        try:
            suffix = path.suffix.lower().strip()
            if suffix == ".aasx":
                # Failsafe, as before. The tolerant reader also closes the
                # file and opens templates with missing files.
                parts = read_package(path, failsafe=True)
                return TemplateContent(parts.objects, parts.files)
            if suffix in (".xml", ".json"):
                # The SDK functions that read these skip a defective object
                # unless told otherwise, and templates were always read so.
                return TemplateContent(
                    read_package(path, failsafe=True).objects, None
                )
            raise TypeError("Wrong file type:", path.suffix)
        except Exception as error:
            # A template with an error is skipped, and the others still work.
            logging.exception(
                f"Error while reading {path}: {error}. Submodels can not be read"
            )
            return None
