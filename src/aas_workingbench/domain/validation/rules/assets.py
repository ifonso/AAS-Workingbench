"""Rules about asset ids: the reserved name and the external subject."""

from collections.abc import Iterator
from typing import cast

from basyx.aas import model

from aas_workingbench.domain.validation.context import ValidationContext
from aas_workingbench.domain.validation.findings import Finding
from aas_workingbench.domain.validation.findings import Severity
from aas_workingbench.domain.validation.rule import Rule

RESERVED_NAME = "AASd-116"
EXTERNAL_SUBJECT = "AASd-133"

_RESERVED = "globalassetid"


def reserved_asset_name(context: ValidationContext) -> Iterator[Finding]:
    """Finds a specific asset id named `globalAssetId`, in any case.

    The name is reserved for the global asset id. The SDK accepts it.
    """
    for held in context.specific_asset_ids:
        asset_id = held.part
        if (
            isinstance(asset_id, model.SpecificAssetId)
            and asset_id.name.lower() == _RESERVED
        ):
            yield Finding(
                RESERVED_NAME,
                Severity.ERROR,
                f"The name '{asset_id.name}' is reserved for the global "
                "asset id. Use another name, or set the global asset id",
                asset_id,
                held.anchor,
                "name",
            )


def external_subject_is_external(
    context: ValidationContext,
) -> Iterator[Finding]:
    """Finds an external subject id that is not an external reference.

    The SDK accepts a model reference there.
    """
    for held in context.specific_asset_ids:
        asset_id = held.part
        if not isinstance(asset_id, model.SpecificAssetId):
            continue
        # The SDK types the attribute as an ExternalReference, and stores
        # whatever it is given.
        subject = cast("model.Reference | None", asset_id.external_subject_id)
        if subject is not None and not isinstance(
            subject, model.ExternalReference
        ):
            yield Finding(
                EXTERNAL_SUBJECT,
                Severity.ERROR,
                f"The external subject id of '{asset_id.name}' must be an "
                "external reference (a global reference), not a model "
                "reference",
                asset_id,
                held.anchor,
                "external_subject_id",
            )


RULES = (
    Rule(
        RESERVED_NAME,
        "globalAssetId is not a specific asset id name",
        "Part 1, constraint AASd-116, in the V3.1 wording: 'globalAssetId' "
        "(case-insensitive) is reserved. The SDK does not check it.",
        reserved_asset_name,
    ),
    Rule(
        EXTERNAL_SUBJECT,
        "An external subject id is an external reference",
        "Part 1, constraint AASd-133. The SDK does not check it.",
        external_subject_is_external,
    ),
)
