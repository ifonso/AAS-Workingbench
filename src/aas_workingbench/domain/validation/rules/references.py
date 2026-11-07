"""Rules about references: dangling targets and semantic ids."""

from collections.abc import Iterator

from basyx.aas import model

from aas_workingbench.domain.validation.context import ValidationContext
from aas_workingbench.domain.validation.findings import Finding
from aas_workingbench.domain.validation.findings import Severity
from aas_workingbench.domain.validation.rule import Rule

DANGLING_REFERENCE = "EDT-DANGLING-REFERENCE"
SUPPLEMENTAL_NEEDS_SEMANTIC = "AASd-118"


def dangling_references(context: ValidationContext) -> Iterator[Finding]:
    """Finds model references whose target is not in the package.

    This is a warning, not an error: the specification allows a reference to
    an object in another package, and the editor cannot tell the two apart.
    External references never count.
    """
    for dangling in context.index.dangling():
        slot = dangling.slot
        yield Finding(
            DANGLING_REFERENCE,
            Severity.WARNING,
            f"The reference in '{slot.attribute}' points at nothing: "
            f"{dangling.reason}",
            slot.owner,
            slot.anchor,
            slot.attribute,
        )


def supplemental_needs_semantic(
    context: ValidationContext,
) -> Iterator[Finding]:
    """Finds supplemental semantic ids on an object with no semantic id.

    The SDK refuses to clear a semantic id while supplemental ids exist, and
    refuses to add a supplemental id to an object that has no semantic id. It
    accepts an object that is made with a supplemental id and no semantic id.
    """
    for held in context.semantic_holders:
        part = held.part
        if not isinstance(part, model.HasSemantics):
            continue
        if part.supplemental_semantic_id and part.semantic_id is None:
            yield Finding(
                SUPPLEMENTAL_NEEDS_SEMANTIC,
                Severity.ERROR,
                "There is a supplemental semantic id, but no semantic id",
                part,
                held.anchor,
                "supplemental_semantic_id",
            )


RULES = (
    Rule(
        DANGLING_REFERENCE,
        "Model references point at something",
        "A model reference is followed through the ids and idShorts of its "
        "keys (Part 1, Reference). Uses ReferenceIndex.dangling.",
        dangling_references,
    ),
    Rule(
        SUPPLEMENTAL_NEEDS_SEMANTIC,
        "A supplemental semantic id needs a semantic id",
        "Part 1, constraint AASd-118. The SDK checks it on add and on clear, "
        "not when an object is made with a supplemental id and no semantic id.",
        supplemental_needs_semantic,
    ),
)
