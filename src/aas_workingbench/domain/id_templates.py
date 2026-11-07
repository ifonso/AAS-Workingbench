"""Ids made from a template such as `urn:x:DDDD` (F-EDT-06 AC5).

Package Explorer builds the id that Generate gives from a template that the
user sets in an option, one for shells, asset ids, submodels of each kind and
concept descriptions. The editor keeps the format, so that the templates of
existing option files work, and adds what the specification of the original
recommends (its decision D5):

- `D` stands for a decimal digit, `X` for an uppercase hexadecimal digit and
  `A` for a letter from A to Z. Every other character is copied.
- A backslash makes the next character literal, so `\\D` is a `D` and `\\\\` is
  a backslash. Without it, every uppercase `D`, `X` and `A` of a host name
  would turn into a random character.
- The characters come from a cryptographically random source, not from the
  time of day, so two calls do not repeat unless the template is short.

An empty template means no template: the editor generates a `urn:uuid:` URN
then (decision D14). A template needs a placeholder, because without one each
Generate would give the same id.

Example:
    >>> generate_id("urn:x:DDDD", lambda limit: 7)
    'urn:x:7777'
    >>> generate_id(r"urn:\\Dx:DD", lambda limit: 0)
    'urn:Dx:00'
"""

from collections.abc import Callable
import enum
import secrets

from aas_workingbench.domain.ids import new_identifier

PLACEHOLDERS = {
    "D": "0123456789",
    "X": "0123456789ABCDEF",
    "A": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
}
"""The characters that each placeholder is replaced by, one at random."""

ESCAPE = "\\"

MAX_ID_LENGTH = 2048
"""The longest id the metamodel allows."""


class IdKind(enum.Enum):
    """What an id is for. Each kind has its own template."""

    AAS = "shell"
    ASSET = "global asset id"
    SUBMODEL_INSTANCE = "submodel of kind Instance"
    SUBMODEL_TEMPLATE = "submodel of kind Template"
    CONCEPT_DESCRIPTION = "concept description"


def check_id_template(template: str) -> str | None:
    """Tells why a template cannot make ids.

    Args:
        template: The text the user typed. An empty text is no template, and
            is fine.

    Returns:
        A sentence that says what to change, or None if the template is
        empty or can make ids.
    """
    if not template.strip():
        return None
    if template != template.strip():
        return "The template must not start or end with a blank"
    placeholders = 0
    length = 0
    position = 0
    while position < len(template):
        char = template[position]
        if char == ESCAPE:
            if position + 1 >= len(template):
                return (
                    "The template ends with a backslash. A backslash makes "
                    "the next character literal, so write \\\\ for one"
                )
            position += 1
        elif char in PLACEHOLDERS:
            placeholders += 1
        length += 1
        position += 1
    if not placeholders:
        return (
            "The template needs at least one D (a digit), X (a hexadecimal "
            "digit) or A (a letter), because every id it makes would be the "
            "same otherwise. A backslash before one of them makes it literal"
        )
    if length > MAX_ID_LENGTH:
        return f"The ids would have {length} characters, and {MAX_ID_LENGTH} are allowed"
    return None


def generate_id(
    template: str, randrange: Callable[[int], int] = secrets.randbelow
) -> str:
    """Makes an id from a template, or a `urn:uuid:` when there is none.

    Args:
        template: The template. An empty or unusable one (see
            `check_id_template`) means a generated UUID.
        randrange: Returns a random integer below its argument. Tests give a
            seeded generator.

    Returns:
        The id.
    """
    if not template.strip() or check_id_template(template) is not None:
        return new_identifier()
    made: list[str] = []
    position = 0
    while position < len(template):
        char = template[position]
        if char == ESCAPE:
            position += 1
            made.append(template[position])
        elif char in PLACEHOLDERS:
            choices = PLACEHOLDERS[char]
            made.append(choices[randrange(len(choices))])
        else:
            made.append(char)
        position += 1
    return "".join(made)
