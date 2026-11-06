"""Rules about names and ids: unique ids, the idShort pattern, versions."""

from collections.abc import Iterator
import re

from aas_editor.domain.references import describe_object
from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.rule import Rule

DUPLICATE_ID = "EDT-DUPLICATE-ID"
ID_SHORT_PATTERN = "AASd-002"
VERSION_FOR_REVISION = "AASd-005"

# AASd-002 as the specification writes it. The SDK checks the characters and
# the first and last one, but accepts an idShort of one letter, which the
# pattern refuses because it needs a second character class at the end.
_ID_SHORT = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9_]+")
# The longest idShort the specification allows (NameType).
_MAX_ID_SHORT_LENGTH = 128


def duplicate_ids(context: ValidationContext) -> Iterator[Finding]:
    """Finds ids that more than one shell, submodel or description has.

    The object store cannot hold two, and an AASX that holds both is read back
    with only one of them. Edits and pastes can make this state, because the
    store checks the id only when an object is added.
    """
    for id_, objects in context.index.duplicate_ids().items():
        names = ", ".join(describe_object(o) for o in objects)
        for obj in objects:
            yield Finding(
                DUPLICATE_ID,
                Severity.ERROR,
                f"The id '{id_}' is used by {len(objects)} objects: {names}. "
                "A saved file keeps only one of them when it is read again",
                obj,
                obj,
                "id",
            )


def id_short_pattern(context: ValidationContext) -> Iterator[Finding]:
    """Finds an idShort that does not match the pattern of AASd-002."""
    for referable in context.referables:
        id_short = referable.id_short
        if id_short is None or _is_valid(id_short):
            continue
        yield Finding(
            ID_SHORT_PATTERN,
            Severity.ERROR,
            f"The idShort '{id_short}' must have at least two characters, "
            "start with a letter, use only letters, digits, hyphens and "
            "underscores, and not end with a hyphen",
            referable,
            referable,
            "id_short",
        )


def revision_needs_version(context: ValidationContext) -> Iterator[Finding]:
    """Finds administrative information with a revision but no version."""
    for obj in context.objects:
        administration = obj.administration
        if administration is None:
            continue
        if administration.revision and not administration.version:
            yield Finding(
                VERSION_FOR_REVISION,
                Severity.ERROR,
                f"The revision '{administration.revision}' needs a version. "
                "Without a version there is no revision",
                administration,
                obj,
                "revision",
            )


def _is_valid(id_short: str) -> bool:
    return (
        len(id_short) <= _MAX_ID_SHORT_LENGTH
        and _ID_SHORT.fullmatch(id_short) is not None
    )


RULES = (
    Rule(
        DUPLICATE_ID,
        "Ids are unique",
        "Identifiables are found by their id, so two objects must not share "
        "one (Part 1, Identifiable). The SDK checks this only on add.",
        duplicate_ids,
    ),
    Rule(
        ID_SHORT_PATTERN,
        "idShort matches the pattern",
        "Part 1, constraint AASd-002. The SDK accepts a one-letter idShort.",
        id_short_pattern,
    ),
    Rule(
        VERSION_FOR_REVISION,
        "A revision needs a version",
        "Part 1, constraint AASd-005. The SDK checks it only when the "
        "administrative information is made, not when the version is cleared.",
        revision_needs_version,
    ),
)
