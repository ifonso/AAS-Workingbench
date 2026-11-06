"""Values that describe the parts of an AASX package besides its AAS objects."""

from dataclasses import dataclass
from pathlib import PurePosixPath
import re

from pyecma376_2.core_properties import OPCCoreProperties

# The OPC core properties (title, creator, and so on) of a package. The SDK
# returns this type, so it is the one the editor keeps and writes back.
CoreProperties = OPCCoreProperties


@dataclass(frozen=True)
class Thumbnail:
    """The thumbnail image of a package.

    The SDK returns only the bytes, so the part name and the content type are
    captured when the package is opened, to write the same part again.

    Attributes:
        name: The OPC part name, such as `/docProps/thumbnail.png`.
        content_type: The media type of the image.
        data: The content of the image.
    """

    name: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class MissingFile:
    """A File element whose package path has no stored file.

    Attributes:
        part_name: The OPC part that holds the File element.
        path: The path as written in the File element.
    """

    part_name: str
    path: str


THUMBNAIL_FOLDER = "/docProps"
"""Where the part of a package thumbnail goes, as in packages of the original."""

_EXTENSION = re.compile(r"^\.[a-z0-9]{1,10}$")


class ThumbnailError(ValueError):
    """A file cannot be the package thumbnail. The message is for the user."""


def new_thumbnail(file_name: str, data: bytes, content_type: str) -> Thumbnail:
    """Makes the package thumbnail from an image file.

    Args:
        file_name: The name of the file on disk. Its extension is kept in the
            name of the part.
        data: The content of the image.
        content_type: The media type of the image.

    Returns:
        The thumbnail, as `/docProps/thumbnail` and the extension of the file.

    Raises:
        ThumbnailError: If the file is no image, is empty, or has no usable
            extension.
    """
    base = content_type.split(";")[0].strip().lower()
    if not base.startswith("image/"):
        raise ThumbnailError(
            f"'{file_name}' is not an image (its media type is "
            f"{content_type}), so it cannot be the package thumbnail."
        )
    if not data:
        raise ThumbnailError(f"'{file_name}' is empty.")
    suffix = PurePosixPath(file_name.replace("\\", "/")).suffix.lower()
    if not _EXTENSION.match(suffix):
        raise ThumbnailError(
            f"'{file_name}' has no usable file extension, such as .png."
        )
    return Thumbnail(
        f"{THUMBNAIL_FOLDER}/thumbnail{suffix}", content_type, data
    )
