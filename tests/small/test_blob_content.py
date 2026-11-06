"""Showing the bytes of a Blob as text or as hex."""

import pytest

from aas_editor.domain import blob_content
from aas_editor.domain.blob_content import BlobText
from aas_editor.domain.value_types import InvalidValueError


def test_as_text_reads_ascii_as_text() -> None:
    assert blob_content.as_text(b"hello") == BlobText("hello", "\n")


def test_as_text_reads_utf8_with_umlauts_and_symbols_as_text() -> None:
    data = "Größe 5 µm €".encode()

    assert blob_content.as_text(data) == BlobText("Größe 5 µm €", "\n")


def test_as_text_reads_empty_bytes_as_empty_text() -> None:
    assert blob_content.as_text(b"") == BlobText("", "\n")


def test_as_text_keeps_tabs_and_unix_line_breaks() -> None:
    assert blob_content.as_text(b"a\tb\nc") == BlobText("a\tb\nc", "\n")


def test_as_text_remembers_windows_line_breaks() -> None:
    assert blob_content.as_text(b"a\r\nb\r\n") == BlobText("a\nb\n", "\r\n")


@pytest.mark.parametrize(
    "data",
    [
        b"\xff\xfe",
        b"\x89PNG\r\n\x1a\n\x00",
        b"a\x00b",
        b"\x01\x02",
        b"a\x1bb",
        b"a\rb",
        b"a\r\nb\nc",
        b"a\n\r\nb",
    ],
    ids=[
        "invalid utf-8",
        "png header",
        "nul",
        "control characters",
        "escape",
        "lone carriage return",
        "mixed line breaks",
        "line feed before windows break",
    ],
)
def test_as_text_is_none_when_the_bytes_are_not_text(data: bytes) -> None:
    assert blob_content.as_text(data) is None


@pytest.mark.parametrize(
    "data",
    [b"", b"hello", b"a\nb\n", b"a\r\nb\r\n", "Größe €\n".encode()],
)
def test_from_text_gives_back_the_bytes_that_as_text_read(data: bytes) -> None:
    shown = blob_content.as_text(data)

    assert shown is not None
    assert blob_content.from_text(shown.text, shown.newline) == data


def test_from_text_encodes_as_utf8_with_the_given_line_breaks() -> None:
    assert blob_content.from_text("ä\nb", "\r\n") == b"\xc3\xa4\r\nb"


def test_to_hex_shows_16_bytes_per_line() -> None:
    data = bytes(range(20))

    shown = blob_content.to_hex(data)

    assert shown == (
        "00 01 02 03 04 05 06 07 08 09 0a 0b 0c 0d 0e 0f\n10 11 12 13"
    )


def test_to_hex_shows_nothing_for_no_bytes() -> None:
    assert blob_content.to_hex(b"") == ""


def test_from_hex_reads_what_to_hex_shows() -> None:
    data = bytes(range(256)) * 3

    assert blob_content.from_hex(blob_content.to_hex(data)) == data


def test_from_hex_ignores_spaces_colons_and_line_breaks() -> None:
    assert blob_content.from_hex("DE:AD be\nef") == b"\xde\xad\xbe\xef"


def test_from_hex_reads_empty_text_as_no_bytes() -> None:
    assert blob_content.from_hex("  \n") == b""


def test_from_hex_names_the_character_that_is_no_digit() -> None:
    with pytest.raises(
        InvalidValueError, match="'g' is not a hexadecimal digit"
    ):
        blob_content.from_hex("01 0g")


def test_from_hex_refuses_a_digit_that_is_left_over() -> None:
    with pytest.raises(InvalidValueError, match="digit left over"):
        blob_content.from_hex("012")


def test_guess_content_type_follows_the_extension() -> None:
    assert blob_content.guess_content_type("picture.png") == "image/png"
    assert blob_content.guess_content_type("C:/dir/data.json") == (
        "application/json"
    )
    assert blob_content.guess_content_type("noextension") is None


def test_guess_extension_follows_the_media_type() -> None:
    assert blob_content.guess_extension("image/png") == ".png"
    assert blob_content.guess_extension("image/png; charset=binary") == ".png"
    assert blob_content.guess_extension("application/x-unknown-thing") == ""
    assert blob_content.guess_extension(None) == ""


def test_decode_base64_spells_the_bytes_of_the_text() -> None:
    assert blob_content.decode_base64(b"SGVsbG8=") == b"Hello"


def test_decode_base64_ignores_blanks_and_line_breaks() -> None:
    assert blob_content.decode_base64(b"SGVs\r\nbG8 =\n") == b"Hello"


def test_decode_base64_reads_bytes_that_are_no_text() -> None:
    assert blob_content.decode_base64(b"AAEC/w==") == b"\x00\x01\x02\xff"


@pytest.mark.parametrize(
    ("data", "reason"),
    [
        (b"SGVsbG8!", "'!' at character 8 is not in the Base64 alphabet"),
        (b"SGVs\xffbG8=", "the byte 0xff at character 5"),
        (b"SGVsbG8", "it has 7 characters, and Base64 needs a multiple of 4"),
        (b"", "nothing to decode"),
        (b" \n", "nothing to decode"),
    ],
    ids=["bad character", "no ASCII", "bad length", "empty", "only blanks"],
)
def test_decode_base64_refuses_with_the_reason(
    data: bytes, reason: str
) -> None:
    with pytest.raises(InvalidValueError, match=reason):
        blob_content.decode_base64(data)


def test_encode_base64_spells_the_bytes_as_text() -> None:
    assert blob_content.encode_base64(b"\x00\x01\x02\xff") == b"AAEC/w=="


def test_encode_base64_refuses_nothing() -> None:
    with pytest.raises(InvalidValueError, match="nothing to encode"):
        blob_content.encode_base64(b"")


@pytest.mark.parametrize(
    "data", [b"x", b"Hello, world", bytes(range(256)), b"\xff" * 1000]
)
def test_decoding_the_base64_of_bytes_gives_the_bytes_back(
    data: bytes,
) -> None:
    assert blob_content.decode_base64(blob_content.encode_base64(data)) == data
