"""Identifiers and idShorts of new AAS objects (decisions D13 and D14).

The SDK checks an idShort and an id when they are set, but it offers no help to
find a good value. This module generates ids for new shells, submodels and
concept descriptions, makes an idShort unique among its siblings, and repairs
text that is not a valid idShort.

Example:
    Naming the copy of an element::

        name = unique_id_short("Pump", {"Pump", "Pump_1"})  # "Pump_2"
"""

from collections.abc import Callable
from collections.abc import Collection
import random
import re
import unicodedata
import uuid

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

# The longest idShort the SDK accepts (NameType).
MAX_ID_SHORT_LENGTH = 128

_INVALID_RUN = re.compile(r"[^A-Za-z0-9_-]+")
_NUMBERED = re.compile(r"(.*)_(\d+)")

# Letters that Unicode normalization does not reduce to ASCII.
_TRANSLITERATIONS = {"ß": "ss", "æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}

# What the original's editor puts in front of a generated idShort, by type. The
# order matters only for classes with the same base: a subclass comes first.
_PREFIXES: tuple[tuple[type, str], ...] = (
    (model.MultiLanguageProperty, "MLP"),
    (model.Property, "Prop"),
    (model.Range, "Range"),
    (model.Blob, "Blob"),
    (model.File, "File"),
    (model.ReferenceElement, "Ref"),
    (model.AnnotatedRelationshipElement, "ARel"),
    (model.RelationshipElement, "Rel"),
    (model.Capability, "Cap"),
    (model.Operation, "Op"),
    (model.Entity, "Ent"),
    (model.BasicEventElement, "Evt"),
    (model.SubmodelElementCollection, "SMC"),
    (model.SubmodelElementList, "SML"),
    (model.Submodel, "SM"),
    (model.AssetAdministrationShell, "AAS"),
    (ConceptDescription, "CD"),
)
_DEFAULT_PREFIX = "Id"


def new_identifier() -> str:
    """Returns a new id for a shell, submodel or concept description (D14).

    Returns:
        A `urn:uuid:` URN with a random UUID, so two calls never repeat.
    """
    return f"urn:uuid:{uuid.uuid4()}"


def is_valid_id_short(text: str) -> bool:
    """Tells whether the SDK accepts a text as an idShort (AASd-002).

    Args:
        text: The text to check.

    Returns:
        True if the text starts with a letter, holds only letters, digits,
        underscores and hyphens, does not end with a hyphen, and has at most
        128 characters.
    """
    try:
        model.Referable.validate_id_short(text)
    except (ValueError, model.AASConstraintViolation):
        return False
    return True


def id_short_prefix(obj: object) -> str:
    """Returns the short name for the type of an object, such as `Prop`.

    Args:
        obj: An AAS object or its class.

    Returns:
        The prefix for generated idShorts, or `Id` for an unknown type.
    """
    cls = obj if isinstance(obj, type) else type(obj)
    for known, prefix in _PREFIXES:
        if issubclass(cls, known):
            return prefix
    return _DEFAULT_PREFIX


def fix_id_short(
    text: str,
    prefix: str = _DEFAULT_PREFIX,
    digits: Callable[[], str] | None = None,
) -> str:
    """Turns any text into a valid idShort, keeping as much of it as possible.

    A text that is valid already is returned as it is. Otherwise letters with
    accents lose them, every other run of invalid characters becomes one
    underscore, a hyphen or underscore at the start or a hyphen at the end is
    dropped, the first letter becomes a capital, and a text that starts with a
    digit gets the prefix. A text with nothing left becomes the prefix followed
    by six digits.

    Args:
        text: The text to repair, such as what a user typed.
        prefix: The start for a text without usable characters, usually from
            `id_short_prefix`.
        digits: Returns the six digits for a text without usable characters.
            None uses random digits.

    Returns:
        A text for which `is_valid_id_short` is true.
    """
    if is_valid_id_short(text):
        return text
    cleaned = _INVALID_RUN.sub("_", _to_ascii(text)).strip("_-")
    cleaned = cleaned.rstrip("-")
    if cleaned and cleaned[0].isdigit():
        cleaned = f"{prefix}{cleaned}"
    cleaned = cleaned[:MAX_ID_SHORT_LENGTH].rstrip("-")
    if not cleaned:
        return f"{prefix}{(digits or _random_digits)()}"
    cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned if is_valid_id_short(cleaned) else f"{prefix}{cleaned}"


def unique_id_short(
    wanted: str, taken: Collection[str], max_length: int = MAX_ID_SHORT_LENGTH
) -> str:
    """Returns the idShort, or a numbered variant of it that is not taken (D13).

    A name that ends in an underscore and a number is counted up, so the copy
    of `Pump_1` is `Pump_2`. Any other name gets `_1`, then `_2`, and so on.

    Args:
        wanted: The idShort the new object should have.
        taken: The idShorts of the siblings. Names are compared exactly.
        max_length: The longest idShort allowed. The base is shortened to fit.

    Returns:
        `wanted` if it is free, otherwise the first free numbered variant.
    """
    if wanted not in taken:
        return wanted
    numbered = _NUMBERED.fullmatch(wanted)
    if numbered is None:
        base, number = wanted, 1
    else:
        base, number = numbered.group(1), int(numbered.group(2)) + 1
    while True:
        suffix = f"_{number}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
        number += 1


def _to_ascii(text: str) -> str:
    text = "".join(_TRANSLITERATIONS.get(char, char) for char in text)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )


def _random_digits() -> str:
    return f"{random.SystemRandom().randrange(1_000_000):06d}"
