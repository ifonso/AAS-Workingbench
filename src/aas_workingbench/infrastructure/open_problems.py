"""Says in plain words why a file cannot be opened as a package.

The SDK reports a file that it cannot read with the exception of whatever
library failed first: a `KeyError` about namespaces, a `ValueError` about an
ECMA376-2 file, a `JSONDecodeError`. A person who double-clicked a file should
not have to read those. `diagnose` looks at the file and the exception, and
answers with a sentence for the causes that a person can act on:

* the file is gone, or the editor may not read it;
* the extension is not one that the editor opens;
* the file is empty, not a ZIP archive, or not an OPC package;
* the file is not valid JSON or XML;
* the file was made for an older version of the metamodel (1.x or 2.x), which
  the SDK cannot read at all.

For all of these, reading the file again without the parts that fail (the
failsafe branch) cannot give a useful package, so the editor does not offer it.
Any other error is left to the caller: the file is a version 3 file that the
SDK refuses in part, and failsafe mode can keep the rest.

This module must not import the legacy `Package`.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re
import zipfile
from typing import Any
from typing import cast

from aas_workingbench.application.save import package_format

# The namespace of an XML file of any version of the metamodel. Version 3 uses
# `https://admin-shell.io/aas/3/0` and `/3/1`. The older ones used `www.`.
_NAMESPACE = re.compile(
    rb"xmlns(?::\w+)?\s*=\s*[\"']https?://(?:www\.)?admin-shell\.io/aas/"
    rb"(\d+)/(\d+)"
)
# How much of a part is read to find its namespace.
_HEAD_BYTES = 16384
# The keys that only the JSON of metamodel 1 and 2 has.
_OLD_JSON_TOP_LEVEL = ("assets", "views")
_OLD_JSON_OBJECT = "identification"
_SUPPORTED = "The editor opens version 3.0 and 3.1."
_CONVERT = (
    "Open the file in AASX Package Explorer, save it as a version 3 file, "
    "and open that file here."
)


@dataclass(frozen=True)
class OpenProblem:
    """Why a file cannot be opened, for the person who chose it.

    Attributes:
        summary: One sentence, with the name of the file.
        advice: What the person can do about it.
    """

    summary: str
    advice: str


def diagnose(path: Path, error: BaseException) -> OpenProblem | None:
    """Explains an error of reading a package, when the cause is known.

    Args:
        path: The file that was read.
        error: What reading it raised.

    Returns:
        The problem in plain words, or None when the cause is not one of the
        known ones and the SDK's own message is all there is.
    """
    name = path.name
    if isinstance(error, FileNotFoundError) or not path.exists():
        return OpenProblem(
            f"{name} does not exist.",
            "It may have been moved, renamed or deleted. Choose it again "
            "from its new place.",
        )
    if isinstance(error, PermissionError):
        return OpenProblem(
            f"{name} cannot be read.",
            "The editor is not allowed to read it, or another program has "
            "it open and locked it. Close it there and try again.",
        )
    if isinstance(error, TypeError) and _unsupported_extension(path):
        shown = path.suffix or "without an extension"
        return OpenProblem(
            f"{name} is not a file that the editor opens ({shown}).",
            "The editor opens AASX packages (.aasx), JSON files (.json) and "
            "XML files (.xml) that hold an Asset Administration Shell.",
        )
    if path.is_file() and path.stat().st_size == 0:
        return OpenProblem(
            f"{name} is empty.", "There is nothing in it to open."
        )
    old = _older_version(path)
    if old is not None:
        return OpenProblem(
            f"{name} was made for version {old} of the AAS metamodel.",
            f"{_SUPPORTED} {_CONVERT}",
        )
    return _damaged(path, error)


def _unsupported_extension(path: Path) -> bool:
    try:
        package_format(path)
    except TypeError:
        return True
    return False


def _damaged(path: Path, error: BaseException) -> OpenProblem | None:
    name = path.name
    text = str(error)
    if isinstance(error, (zipfile.BadZipFile, ValueError)) and (
        "not a valid ECMA376-2" in text or "not a zip file" in text
    ):
        if "not a zip file" in text.lower():
            return OpenProblem(
                f"{name} is not an AASX package.",
                "An AASX file is a ZIP archive, and this is not one. The "
                "file may be damaged, or may have been saved under the wrong "
                "name or extension.",
            )
        return OpenProblem(
            f"{name} is a ZIP archive, but not an AASX package.",
            "It lacks the parts that every AASX package has, such as "
            "[Content_Types].xml. It may be damaged, or made by another "
            "program.",
        )
    if isinstance(error, json.JSONDecodeError):
        return OpenProblem(
            f"{name} is not valid JSON: {error.msg}, at line {error.lineno} "
            f"column {error.colno}.",
            "Correct it in a text editor, or export it again from the "
            "program that made it.",
        )
    # lxml is a dependency of the SDK and ships no type stubs, so its error is
    # found by name.
    if type(error).__name__ == "XMLSyntaxError":
        return OpenProblem(
            f"{name} is not well-formed XML: {error}.",
            "Correct it in a text editor, or export it again from the "
            "program that made it.",
        )
    return None


def _older_version(path: Path) -> str | None:
    """Finds out that a file is for metamodel 1 or 2, or returns None."""
    try:
        suffix = path.suffix.lower()
        if suffix == ".xml":
            return _version_of_xml(path.read_bytes()[:_HEAD_BYTES])
        if suffix == ".json":
            return _version_of_json(path.read_bytes())
        if suffix == ".aasx":
            return _version_in_archive(path)
    except (OSError, zipfile.BadZipFile, ValueError, KeyError):
        return None
    return None


def _version_of_xml(head: bytes) -> str | None:
    found = _NAMESPACE.search(head)
    if found is None or int(found.group(1)) >= 3:
        return None
    return f"{found.group(1).decode()}.{found.group(2).decode()}"


def _version_of_json(data: bytes) -> str | None:
    loaded: object = json.loads(data)
    if not isinstance(loaded, dict):
        return None
    content = cast("dict[str, Any]", loaded)
    if any(key in content for key in _OLD_JSON_TOP_LEVEL):
        return "1 or 2"
    for key in ("assetAdministrationShells", "submodels"):
        entries: object = content.get(key)
        if isinstance(entries, list) and any(
            isinstance(entry, dict) and _OLD_JSON_OBJECT in entry
            for entry in cast("list[object]", entries)
        ):
            return "1 or 2"
    return None


def _version_in_archive(path: Path) -> str | None:
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            lowered = info.filename.lower()
            if lowered.startswith(("_rels/", "docprops/")) or lowered in (
                "[content_types].xml",
            ):
                continue
            if lowered.endswith(".xml"):
                with archive.open(info) as part:
                    found = _version_of_xml(part.read(_HEAD_BYTES))
            elif lowered.endswith(".json"):
                with archive.open(info) as part:
                    found = _version_of_json(part.read())
            else:
                continue
            if found is not None:
                return found
    return None
