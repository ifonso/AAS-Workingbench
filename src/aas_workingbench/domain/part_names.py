"""Names of the files stored in a package (decision D15).

A stored file is an OPC part, so its name is a path such as
`/aasx/files/datasheet.pdf`. The SDK container accepts any text as a name and
leaves the check to the writer, which fails late with a `ValueError`. Names
also come from the file being edited, so they cannot be trusted. This module
makes names that the writer accepts, refuses the others with a reason, and
finds names that the OPC rules treat as equal.

Example:
    Placing a file chosen by the user::

        name = part_name(DEFAULT_FOLDER, "report final.pdf")
        # "/aasx/files/report_final.pdf"
"""

from collections.abc import Collection
import mimetypes
import re

from pyecma376_2.package_model import check_part_name
from pyecma376_2.package_model import normalize_part_name

# Where new files go unless the user chooses another folder (D15).
DEFAULT_FOLDER = "/aasx/files"

# The media type of a file whose extension is not known.
UNKNOWN_CONTENT_TYPE = "application/octet-stream"

# Characters that a part name keeps. Others are replaced by an underscore.
_UNSAFE_RUN = re.compile(r"[^A-Za-z0-9\-._~]+")
_COUNTED = re.compile(r"(.*)_(\d{4})")
# The longest name a local file system takes for one file, with some room.
_MAX_LOCAL_NAME = 120
# Names that Windows reserves for devices, whatever their extension.
_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{n}" for n in range(1, 10)),
    *(f"lpt{n}" for n in range(1, 10)),
}


class InvalidPartNameError(ValueError):
    """A name that cannot be the name of a file in the package."""


def validate(name: str) -> str:
    """Checks that a name is a valid, safe part name.

    Besides the OPC rules, a name must not contain a backslash, a `.` or `..`
    segment, or an empty segment, so that no name can leave the package folder
    when a file is extracted.

    Args:
        name: The name of a stored file.

    Returns:
        The same name.

    Raises:
        InvalidPartNameError: If the name is not valid. The message says why.
    """
    if "\\" in name:
        raise InvalidPartNameError(
            f"'{name}' contains a backslash. Use '/' to separate folders."
        )
    if not name.startswith("/"):
        raise InvalidPartNameError(f"'{name}' must start with '/'.")
    segments = name.split("/")[1:]
    if any(segment in ("", ".", "..") for segment in segments):
        raise InvalidPartNameError(
            f"'{name}' must not have an empty, '.' or '..' folder name."
        )
    if name.endswith("/"):
        raise InvalidPartNameError(f"'{name}' must name a file, not a folder.")
    try:
        check_part_name(name)
    except ValueError as error:
        raise InvalidPartNameError(
            f"'{name}' is not a valid name for a file in the package. Use "
            "letters, digits, '-', '.', '_' and '~', and no folder or file "
            "name that ends with a dot."
        ) from error
    return name


def is_valid(name: str) -> bool:
    """Tells whether a name is a valid, safe part name. See `validate`."""
    try:
        validate(name)
    except InvalidPartNameError:
        return False
    return True


def sanitize_file_name(file_name: str) -> str:
    """Turns the name of a local file into a name that a part can have.

    Folders are dropped, runs of other characters become one underscore, and
    leading dots are removed, so that `report final.pdf` becomes
    `report_final.pdf`.

    Args:
        file_name: A file name or a path on the machine of the user.

    Returns:
        A name without folders.

    Raises:
        InvalidPartNameError: If nothing is left of the name.
    """
    base = file_name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = _UNSAFE_RUN.sub("_", base).lstrip(".")
    cleaned = cleaned.rstrip(".")
    if not cleaned.strip("_"):
        raise InvalidPartNameError(
            f"'{file_name}' has no usable file name. Use letters or digits."
        )
    return cleaned


def normalize_folder(folder: str) -> str:
    """Makes a folder path that starts with '/' and does not end with one.

    Args:
        folder: A folder as the user typed it, such as `aasx\\files\\`.

    Returns:
        The folder, such as `/aasx/files`, or `/` for the top.

    Raises:
        InvalidPartNameError: If a folder name is not valid.
    """
    segments = [
        segment
        for segment in folder.replace("\\", "/").split("/")
        if segment.strip()
    ]
    for segment in segments:
        if segment in (".", ".."):
            raise InvalidPartNameError(
                f"'{folder}' must not contain '.' or '..' folder names."
            )
    cleaned = [
        _UNSAFE_RUN.sub("_", segment).lstrip(".") for segment in segments
    ]
    if any(not segment.strip("_") for segment in cleaned):
        raise InvalidPartNameError(f"'{folder}' is not a valid folder.")
    return "/" + "/".join(cleaned)


def part_name(folder: str, file_name: str) -> str:
    """Builds the name of a stored file from a folder and a file name.

    Args:
        folder: The folder, such as `/aasx/files`.
        file_name: The file name, or the path of a local file.

    Returns:
        A valid part name.

    Raises:
        InvalidPartNameError: If the folder or the file name is not valid.
    """
    folder = normalize_folder(folder)
    name = sanitize_file_name(file_name)
    joined = f"{folder}/{name}" if folder != "/" else f"/{name}"
    return validate(joined)


def folder_of(name: str) -> str:
    """Returns the folder of a stored file, `/` for the top."""
    return name.rsplit("/", 1)[0] or "/"


def file_name_of(name: str) -> str:
    """Returns the last segment of a stored file name."""
    return name.rsplit("/", 1)[-1]


def same_part(first: str, second: str) -> bool:
    """Tells whether two names are the same part for OPC.

    Part names are compared without regard to case, and after percent-encoding.
    """
    return normalize_part_name(first) == normalize_part_name(second)


def find_clash(name: str, taken: Collection[str]) -> str | None:
    """Finds the stored name that OPC treats as equal to a name.

    Args:
        name: The wanted name.
        taken: The names that exist.

    Returns:
        The name in `taken` that is the same part, or None.
    """
    key = normalize_part_name(name)
    for other in taken:
        if normalize_part_name(other) == key:
            return other
    return None


def unique_name(name: str, taken: Collection[str]) -> str:
    """Returns the name, or a numbered variant when it is taken.

    The variant is made as the SDK does, `a.txt` becomes `a_0001.txt`, and
    names that differ only in case are taken as equal.

    Args:
        name: The wanted name.
        taken: The names that exist.

    Returns:
        A name that is not in `taken`.
    """
    keys = {normalize_part_name(other) for other in taken}
    if normalize_part_name(name) not in keys:
        return name
    folder, _, file_name = name.rpartition("/")
    stem, dot, extension = file_name.rpartition(".")
    if not dot:
        stem, extension = file_name, ""
    counted = _COUNTED.fullmatch(stem)
    if counted:
        stem = counted.group(1)
    number = 1
    while True:
        candidate = f"{folder}/{stem}_{number:04d}" + (
            f".{extension}" if dot else ""
        )
        if normalize_part_name(candidate) not in keys:
            return candidate
        number += 1


def guess_content_type(file_name: str) -> str:
    """Guesses the media type of a file from its extension.

    Args:
        file_name: A file name or path.

    Returns:
        The media type, or `application/octet-stream` for an unknown
        extension, as the original's `text/plain` would mislabel the bytes.
    """
    content_type, _ = mimetypes.guess_type(file_name)
    return content_type or UNKNOWN_CONTENT_TYPE


def is_text_type(content_type: str) -> bool:
    """Tells whether files of a media type are meant to be read as text."""
    base = content_type.split(";")[0].strip().lower()
    return (
        base.startswith("text/")
        or base.endswith(("+xml", "+json"))
        or base
        in (
            "application/json",
            "application/xml",
            "application/javascript",
            "application/x-yaml",
        )
    )


def local_file_name(name: str) -> str:
    """Returns a name for the file on disk when a stored file is extracted.

    Only the last segment is used, and characters and names that a file
    system refuses are replaced, so a stored name can never choose a folder.

    Args:
        name: The name of a stored file, which may be hostile.

    Returns:
        A plain file name.
    """
    last = name.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", last).strip(" .")
    if not cleaned or cleaned.strip("_") == "":
        cleaned = "file"
    stem = cleaned.split(".", 1)[0].lower()
    if stem in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:_MAX_LOCAL_NAME]
