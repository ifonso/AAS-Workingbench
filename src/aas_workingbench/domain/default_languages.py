"""The languages that a new multi-language text starts with (F-EDT-04 AC2).

Package Explorer has an option `DefaultLangs`, a list of language tags such as
`en,de`. A new MultiLanguageProperty has one empty row for each of them, and a
new row of a language list starts with the first one. The editor keeps the
list as text in its settings. This module reads that text, and says what is
wrong with a text that the user typed in the settings dialog.

A text that cannot be read never stops the editor: `default_languages` falls
back to English, so a hand-edited settings file does no harm.

Example:
    >>> parse_default_languages("en, de")
    ('en', 'de')
    >>> default_languages("not a language!")
    ('en',)
"""

from aas_workingbench.domain.language_tags import check_language_tags

FALLBACK_LANGUAGES: tuple[str, ...] = ("en",)
"""The languages when none are set, or the setting cannot be read."""

DEFAULT_LANGUAGES_TEXT = "en"
"""What the setting holds until the user changes it."""


class DefaultLanguagesError(ValueError):
    """The text is no list of language tags. The message is for the user."""


def parse_default_languages(text: str) -> tuple[str, ...]:
    """Reads a comma separated list of language tags.

    Args:
        text: The tags separated by commas. Blanks around a tag are ignored,
            and so are empty entries, as in `en,,de,`.

    Returns:
        The tags in the order given.

    Raises:
        DefaultLanguagesError: If no tag is given, a tag is not well-formed
            (BCP 47), or a tag occurs twice.
    """
    tags = tuple(part.strip() for part in text.split(",") if part.strip())
    if not tags:
        raise DefaultLanguagesError(
            "Give at least one language, such as en or en,de"
        )
    problems = check_language_tags(tags)
    if problems:
        raise DefaultLanguagesError("; ".join(problems))
    return tags


def default_languages(text: str | None) -> tuple[str, ...]:
    """Returns the languages of a setting, and English if it cannot be read.

    Args:
        text: The stored setting, or None if there is none.

    Returns:
        The tags, or `FALLBACK_LANGUAGES`.
    """
    if text is None:
        return FALLBACK_LANGUAGES
    try:
        return parse_default_languages(text)
    except DefaultLanguagesError:
        return FALLBACK_LANGUAGES


def first_default_language(text: str | None) -> str:
    """Returns the language for a single new entry, the first of the list."""
    return default_languages(text)[0]
