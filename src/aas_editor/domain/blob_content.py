"""Shows the bytes of a Blob as text or as hex, and reads them back.

A Blob holds bytes of any kind: a JSON document, a PNG image, a short key. An
editor must show text where there is text, and hex where there is not, and
must hand back exactly the bytes it was given when the user changes nothing.

Text counts as text when it is valid UTF-8, has no control characters other
than tab and line breaks, and uses one kind of line break. Anything else is
shown as hex. A Windows text with `\\r\\n` is text, and keeps its line breaks,
because the text widgets of Qt only know `\\n`.
"""

import base64
import binascii
from dataclasses import dataclass
import mimetypes
import re
import unicodedata

from aas_editor.domain.value_types import InvalidValueError

# Above this size an editor does not show the content, only its size.
MAX_SHOWN_BYTES = 1024 * 1024

_HEX_DIGITS = re.compile(r"[0-9A-Fa-f]*")
_BASE64_BLANKS = re.compile(rb"[ \t\r\n]+")
_BASE64_ALPHABET = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
)
_BYTES_PER_LINE = 16


@dataclass(frozen=True)
class BlobText:
    """The content of a Blob read as text.

    Attributes:
        text: The text, with `\\n` as the only line break.
        newline: The line break the bytes use, `\\n` or `\\r\\n`, so that
            `from_text` can write the same bytes again.
    """

    text: str
    newline: str


def as_text(data: bytes) -> BlobText | None:
    """Reads bytes as text, if they are text.

    Args:
        data: The content of a Blob.

    Returns:
        The text, or None if the bytes are not valid UTF-8, contain control
        characters, or mix line breaks.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(
        unicodedata.category(char) == "Cc" and char not in "\t\r\n"
        for char in text
    ):
        return None
    crlf = text.count("\r\n")
    if text.count("\r") != crlf:
        return None
    if crlf and text.count("\n") != crlf:
        return None
    if crlf:
        return BlobText(text.replace("\r\n", "\n"), "\r\n")
    return BlobText(text, "\n")


def from_text(text: str, newline: str = "\n") -> bytes:
    """Turns text from an editor into bytes.

    Args:
        text: The text, with `\\n` as the only line break.
        newline: The line break to write, `\\n` or `\\r\\n`.

    Returns:
        The text as UTF-8.
    """
    if newline != "\n":
        text = text.replace("\n", newline)
    return text.encode("utf-8")


def to_hex(data: bytes) -> str:
    """Shows bytes as hexadecimal, 16 bytes in a line.

    Args:
        data: The content of a Blob.

    Returns:
        Lines of pairs of lowercase hexadecimal digits, separated by spaces.
    """
    lines = [
        data[start : start + _BYTES_PER_LINE].hex(" ")
        for start in range(0, len(data), _BYTES_PER_LINE)
    ]
    return "\n".join(lines)


def from_hex(text: str) -> bytes:
    """Reads bytes from hexadecimal digits.

    Args:
        text: Pairs of hexadecimal digits. Spaces, line breaks, and colons
            between them are ignored.

    Returns:
        The bytes.

    Raises:
        InvalidValueError: If a character is not a hexadecimal digit, or a
            digit is left over.
    """
    digits = re.sub(r"[\s:]", "", text)
    if _HEX_DIGITS.fullmatch(digits) is None:
        bad = next(
            char for char in digits if char not in "0123456789abcdefABCDEF"
        )
        raise InvalidValueError(
            f"'{bad}' is not a hexadecimal digit. "
            "Use pairs of the digits 0 to 9 and a to f"
        )
    if len(digits) % 2:
        raise InvalidValueError(
            "The hexadecimal text has a digit left over. Bytes are pairs of digits"
        )
    return bytes.fromhex(digits)


def decode_base64(data: bytes) -> bytes:
    """Reads the content of a Blob as Base64 text, and returns the bytes it spells.

    The JSON and XML of the metamodel store the bytes of a Blob as Base64
    already. This is about a Blob whose bytes are themselves Base64 text, for
    example because the text was pasted in, and so the file would hold the
    Base64 of Base64 text.

    Args:
        data: The content of a Blob: ASCII text in the Base64 alphabet. Blanks
            and line breaks between the characters are ignored.

    Returns:
        The decoded bytes.

    Raises:
        InvalidValueError: If the content is empty, is not text, has a
            character outside the Base64 alphabet, or has a wrong length or
            padding. The message names the first problem.
    """
    squeezed = _BASE64_BLANKS.sub(b"", data)
    if not squeezed:
        raise InvalidValueError(
            "The content is empty, so there is nothing to decode"
        )
    for position, byte in enumerate(data):
        if byte not in _BASE64_ALPHABET and byte not in b" \t\r\n":
            shown = (
                repr(chr(byte))
                if 32 <= byte < 127
                else f"the byte 0x{byte:02x}"
            )
            raise InvalidValueError(
                f"The content is not Base64 text: {shown} at character "
                f"{position + 1} is not in the Base64 alphabet "
                "(A to Z, a to z, 0 to 9, + / and = at the end)"
            )
    try:
        return base64.b64decode(squeezed, validate=True)
    except binascii.Error as error:
        raise InvalidValueError(
            f"The content is not valid Base64 text: {_base64_reason(squeezed, error)}"
        ) from error


def _base64_reason(squeezed: bytes, error: binascii.Error) -> str:
    if len(squeezed) % 4:
        return (
            f"it has {len(squeezed)} characters, and Base64 needs a multiple "
            "of 4 (the end is filled up with =)"
        )
    return str(error)


def encode_base64(data: bytes) -> bytes:
    """Spells bytes as Base64 text, which is what the new content of a Blob is.

    Args:
        data: The content of a Blob.

    Returns:
        ASCII bytes in the Base64 alphabet, on one line.

    Raises:
        InvalidValueError: If the content is empty.
    """
    if not data:
        raise InvalidValueError(
            "The content is empty, so there is nothing to encode"
        )
    return base64.b64encode(data)


def guess_content_type(file_name: str) -> str | None:
    """Guesses the media type of a file from its name.

    Args:
        file_name: A file name or path.

    Returns:
        The media type, such as `image/png`, or None if the extension is
        unknown.
    """
    content_type, _ = mimetypes.guess_type(file_name)
    return content_type


def guess_extension(content_type: str | None) -> str:
    """Suggests the file extension for a media type.

    Args:
        content_type: A media type such as `image/png`, or None.

    Returns:
        The extension with its dot, or an empty string if none is known.
    """
    if not content_type:
        return ""
    return mimetypes.guess_extension(content_type.split(";")[0].strip()) or ""
