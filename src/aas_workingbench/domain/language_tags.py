"""Checks language tags of multi-language texts against BCP 47.

The display name, the description, and the value of a MultiLanguageProperty
map a language tag such as `en` or `de-DE` to a text. The tag must follow
BCP 47 (RFC 5646). The BaSyx `LangStringSet` refuses a malformed tag with one
sentence, when the object is built. This module answers earlier, while a user
types, and says what is wrong. It uses the same syntax as the SDK, and no
registry: it tells whether a tag is *well-formed*, not whether `zz` is a
language that exists. The validation rules of the editor reuse it.

Example:
    >>> check_language_tag("en-US") is None
    True
    >>> check_language_tag("en_US")
    "'en_US' is not a language tag: use a hyphen, not an underscore, as in en-US"
"""

from collections.abc import Iterable
import re

_ALPHANUM = "[a-zA-Z0-9]"
_SINGLETON = "[0-9A-WY-Za-wy-z]"
_EXTENSION = f"{_SINGLETON}(-({_ALPHANUM}){{2,8}})+"
_EXTLANG = "[a-zA-Z]{3}(-[a-zA-Z]{3}){0,2}"
_IRREGULAR = (
    "(en-GB-oed|i-ami|i-bnn|i-default|i-enochian|i-hak|"
    "i-klingon|i-lux|i-mingo|i-navajo|i-pwn|i-tao|i-tay|"
    "i-tsu|sgn-BE-FR|sgn-BE-NL|sgn-CH-DE)"
)
_REGULAR = (
    "(art-lojban|cel-gaulish|no-bok|no-nyn|zh-guoyu|zh-hakka|"
    "zh-min|zh-min-nan|zh-xiang)"
)
_LANGUAGE = f"([a-zA-Z]{{2,3}}(-{_EXTLANG})?|[a-zA-Z]{{4}}|[a-zA-Z]{{5,8}})"
_SCRIPT = "[a-zA-Z]{4}"
_REGION = "([a-zA-Z]{2}|[0-9]{3})"
_VARIANT = f"(({_ALPHANUM}){{5,8}}|[0-9]({_ALPHANUM}){{3}})"
_PRIVATE_USE = f"[xX](-({_ALPHANUM}){{1,8}})+"
_LANGTAG = (
    f"{_LANGUAGE}(-{_SCRIPT})?(-{_REGION})?(-{_VARIANT})*(-{_EXTENSION})*"
    f"(-{_PRIVATE_USE})?"
)
_WELL_FORMED = re.compile(
    f"({_LANGTAG}|{_PRIVATE_USE}|({_IRREGULAR}|{_REGULAR}))"
)

# The tags that the editor offers when a language is chosen.
COMMON_LANGUAGE_TAGS: tuple[str, ...] = (
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


def is_valid_language_tag(tag: str) -> bool:
    """Tells whether a tag is well-formed according to BCP 47.

    Args:
        tag: The language tag, such as `en` or `zh-Hant-TW`.

    Returns:
        True if the SDK accepts the tag in a `LangStringSet`.
    """
    return _WELL_FORMED.fullmatch(tag) is not None


def check_language_tag(tag: str) -> str | None:
    """Tells why a tag is not a well-formed language tag.

    Args:
        tag: The language tag typed by the user.

    Returns:
        A message for the user that starts with the tag, or None if the tag
        is well-formed.
    """
    if is_valid_language_tag(tag):
        return None
    return f"'{tag}' is not a language tag: {_reason(tag)}"


def check_language_tags(tags: Iterable[str]) -> list[str]:
    """Checks several tags, and reports each problem once.

    Args:
        tags: The tags of one multi-language text.

    Returns:
        One message for each malformed tag, and one for each tag that occurs
        twice, which would overwrite the text of the first. Empty if all are
        fine.
    """
    messages: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        message = check_language_tag(tag)
        if message is not None:
            messages.append(message)
        elif tag.lower() in seen:
            messages.append(f"The language '{tag}' is used more than once")
        seen.add(tag.lower())
    return messages


def _reason(tag: str) -> str:
    if not tag:
        return "it is empty. Use a language such as en or de"
    if tag != tag.strip() or " " in tag:
        return "it must not contain spaces"
    if "_" in tag:
        return "use a hyphen, not an underscore, as in en-US"
    if re.search(r"[^a-zA-Z0-9-]", tag):
        return "it may contain only letters, digits, and hyphens"
    parts = tag.split("-")
    if "" in parts:
        return "it has an empty part between hyphens"
    if any(len(part) > 8 for part in parts):
        return "a part between hyphens has at most 8 characters"
    if not parts[0].isalpha():
        return "it must begin with a language such as en or de"
    return "it must look like en, de-DE, or zh-Hant-TW"
