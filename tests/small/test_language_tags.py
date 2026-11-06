"""Checking language tags against BCP 47."""

from basyx.aas import model
import pytest

from aas_editor.domain import language_tags

WELL_FORMED = [
    "en",
    "de",
    "EN",
    "en-US",
    "en-us",
    "de-DE",
    "zh-Hant",
    "zh-Hant-TW",
    "es-419",
    "sl-rozaj-biske",
    "de-CH-1901",
    "en-a-bbb-x-a-ccc",
    "x-private",
    "i-klingon",
    "zh-min-nan",
    "en-GB-oed",
    "yue-HK",
    "zh-yue-HK",
    "fil",
    "tlh",
    "abcde",
    "abcdefgh",
]

MALFORMED = [
    ("", "it is empty"),
    (" ", "must not contain spaces"),
    ("en ", "must not contain spaces"),
    ("en US", "must not contain spaces"),
    ("en_US", "use a hyphen, not an underscore"),
    ("en-US!", "only letters, digits, and hyphens"),
    ("ö", "only letters, digits, and hyphens"),
    ("en--US", "empty part"),
    ("-en", "empty part"),
    ("en-", "empty part"),
    ("en-abcdefghi", "at most 8 characters"),
    ("1en", "begin with a language"),
    ("e", "must look like"),
    ("en-US-US", "must look like"),
    ("abcdefghi", "at most 8 characters"),
]


@pytest.mark.parametrize("tag", WELL_FORMED)
def test_check_language_tag_accepts_a_well_formed_tag(tag: str) -> None:
    assert language_tags.check_language_tag(tag) is None
    assert language_tags.is_valid_language_tag(tag) is True


@pytest.mark.parametrize(("tag", "reason"), MALFORMED)
def test_check_language_tag_says_what_is_wrong_with_a_malformed_tag(
    tag: str, reason: str
) -> None:
    message = language_tags.check_language_tag(tag)

    assert message is not None
    assert message.startswith(f"'{tag}' is not a language tag: ")
    assert reason in message
    assert language_tags.is_valid_language_tag(tag) is False


@pytest.mark.parametrize("tag", [*WELL_FORMED, *[tag for tag, _ in MALFORMED]])
def test_is_valid_language_tag_agrees_with_the_sdk(tag: str) -> None:
    try:
        model.MultiLanguageNameType({tag: "text"})
    except ValueError:
        sdk_accepts = False
    else:
        sdk_accepts = True

    assert language_tags.is_valid_language_tag(tag) is sdk_accepts


def test_is_valid_language_tag_refuses_a_tag_with_a_trailing_line_break() -> (
    None
):
    # The SDK pattern ends in `$`, which lets "en\n" through.
    assert language_tags.is_valid_language_tag("en\n") is False


def test_check_language_tags_reports_every_malformed_tag() -> None:
    messages = language_tags.check_language_tags(["en", "e_n", "de", "1"])

    assert len(messages) == 2
    assert messages[0].startswith("'e_n' is not a language tag")
    assert messages[1].startswith("'1' is not a language tag")


def test_check_language_tags_reports_a_tag_that_occurs_twice() -> None:
    messages = language_tags.check_language_tags(["en", "de", "EN"])

    assert messages == ["The language 'EN' is used more than once"]


def test_check_language_tags_is_empty_when_all_tags_are_fine() -> None:
    assert language_tags.check_language_tags(["en", "de-DE"]) == []


def test_common_language_tags_are_the_languages_of_the_completer() -> None:
    assert language_tags.COMMON_LANGUAGE_TAGS == (
        "de",
        "en",
        "es",
        "fi",
        "fr",
        "it",
        "ja",
        "ko",
        "nl",
        "no",
        "pt",
        "sv",
        "zh",
    )
