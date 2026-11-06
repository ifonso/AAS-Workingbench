"""Values that describe the parts of an AASX package besides its AAS objects."""

from dataclasses import dataclass

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
