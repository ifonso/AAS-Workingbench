"""The setting of default languages, as text."""

import pytest

from aas_workingbench.domain.default_languages import DefaultLanguagesError
from aas_workingbench.domain.default_languages import default_languages
from aas_workingbench.domain.default_languages import first_default_language
from aas_workingbench.domain.default_languages import parse_default_languages


def test_the_tags_are_read_in_the_order_given() -> None:
    assert parse_default_languages("en,de") == ("en", "de")


def test_blanks_and_empty_entries_are_ignored() -> None:
    assert parse_default_languages(" en , ,de-DE,") == ("en", "de-DE")


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        ("", "at least one language"),
        (" , ", "at least one language"),
        ("en_US", "use a hyphen, not an underscore"),
        ("en,de,EN", "'EN' is used more than once"),
        ("en de", "must not contain spaces"),
    ],
)
def test_a_text_that_is_no_list_of_tags_says_what_is_wrong(
    text: str, reason: str
) -> None:
    with pytest.raises(DefaultLanguagesError, match=reason):
        parse_default_languages(text)


def test_a_setting_that_cannot_be_read_gives_english() -> None:
    assert default_languages(None) == ("en",)
    assert default_languages("") == ("en",)
    assert default_languages("not a tag!") == ("en",)


def test_the_first_language_is_the_one_for_a_single_entry() -> None:
    assert first_default_language("de,en") == "de"
    assert first_default_language("broken!") == "en"
