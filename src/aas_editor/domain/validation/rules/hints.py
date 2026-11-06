"""Hints: advice that is not a rule of the specification (F-EDT-06).

Package Explorer shows a hint for what is legal but probably wrong, or only
worth a look. These are the hints of this editor. They use the machinery of the
rules, but `ALL_RULES` does not list them: the validation dock and the save gate
show the rules, and hints mode shows these as well.

A hint that Package Explorer calls High is a warning here. One that it calls
Notice is info.
"""

from collections.abc import Iterator

from basyx.aas import model

from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.field_checks import copy_name_problem
from aas_editor.domain.validation.field_checks import (
    entity_global_asset_id_problem,
)
from aas_editor.domain.validation.field_checks import global_asset_id_problem
from aas_editor.domain.validation.field_checks import key_value_problem
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.rule import Rule

KEY_WHITESPACE = "EDT-HINT-KEY-WHITESPACE"
CATEGORY_DEPRECATED = "EDT-HINT-CATEGORY"
COPY_NAME = "EDT-HINT-COPY-NAME"
ASSET_ID_EMPTY = "EDT-HINT-ASSET-ID-EMPTY"
ASSET_ID_DUPLICATE = "EDT-HINT-ASSET-ID-DUPLICATE"
ENTITY_GLOBAL_ID = "EDT-HINT-ENTITY-GLOBAL-ID"
DISPLAY_NAME_MISSING = "EDT-HINT-DISPLAY-NAME-MISSING"
DISPLAY_NAME_ONE_LANGUAGE = "EDT-HINT-DISPLAY-NAME-ONE-LANGUAGE"
DESCRIPTION_MISSING = "EDT-HINT-DESCRIPTION-MISSING"
DESCRIPTION_ONE_LANGUAGE = "EDT-HINT-DESCRIPTION-ONE-LANGUAGE"


def key_whitespace(context: ValidationContext) -> Iterator[Finding]:
    """Finds whitespace in the keys of a semantic id (F-EDT-06 AC9)."""
    for held in context.semantic_holders:
        part = held.part
        if not isinstance(part, model.HasSemantics):
            continue
        references = [part.semantic_id, *part.supplemental_semantic_id]
        for reference in references:
            if reference is None:
                continue
            for key in reference.key:
                problem = key_value_problem(key.value)
                if problem is not None:
                    yield Finding(
                        KEY_WHITESPACE,
                        Severity.WARNING,
                        f"{problem}: '{key.value}'",
                        part,
                        held.anchor,
                        "semantic_id",
                    )


def category_deprecated(context: ValidationContext) -> Iterator[Finding]:
    """Finds a category, which the specification deprecates (F-EDT-06 AC16)."""
    for referable in context.referables:
        if referable.category:
            yield Finding(
                CATEGORY_DEPRECATED,
                Severity.INFO,
                f"The category '{referable.category}' is deprecated. Do not "
                "plan to use it in new developments",
                referable,
                referable,
                "category",
            )


def copy_name(context: ValidationContext) -> Iterator[Finding]:
    """Finds an idShort that looks named by a copy and paste."""
    for referable in context.referables:
        if referable.id_short is None:
            continue
        problem = copy_name_problem(referable.id_short)
        if problem is not None:
            yield Finding(
                COPY_NAME,
                Severity.WARNING,
                problem,
                referable,
                referable,
                "id_short",
            )


def empty_asset_id(context: ValidationContext) -> Iterator[Finding]:
    """Finds a shell with an empty global asset id (F-EDT-02 AC9)."""
    for shell in _shells(context):
        problem = global_asset_id_problem(
            shell.asset_information.global_asset_id
        )
        if problem is not None:
            yield Finding(
                ASSET_ID_EMPTY,
                Severity.WARNING,
                problem,
                shell.asset_information,
                shell,
                "global_asset_id",
            )


def duplicate_asset_id(context: ValidationContext) -> Iterator[Finding]:
    """Finds shells that share one global asset id (F-EDT-02 AC9)."""
    by_id: dict[str, list[model.AssetAdministrationShell]] = {}
    for shell in _shells(context):
        asset_id = shell.asset_information.global_asset_id
        if asset_id:
            by_id.setdefault(asset_id, []).append(shell)
    for asset_id, shells in by_id.items():
        if len(shells) < 2:
            continue
        for shell in shells:
            yield Finding(
                ASSET_ID_DUPLICATE,
                Severity.WARNING,
                f"{len(shells)} shells have the global asset id '{asset_id}'",
                shell.asset_information,
                shell,
                "global_asset_id",
            )


def entity_global_id(context: ValidationContext) -> Iterator[Finding]:
    """Finds a self-managed entity without a global asset id (F-EDT-04 AC17).

    Its specific asset ids satisfy AASd-014, so the SDK accepts the entity. The
    original still asks for the global one.
    """
    for referable in context.referables:
        if not isinstance(referable, model.Entity):
            continue
        problem = entity_global_asset_id_problem(
            referable.entity_type is model.EntityType.SELF_MANAGED_ENTITY,
            referable.global_asset_id,
        )
        if problem is not None:
            yield Finding(
                ENTITY_GLOBAL_ID,
                Severity.INFO,
                problem,
                referable,
                referable,
                "global_asset_id",
            )


def display_name_missing(context: ValidationContext) -> Iterator[Finding]:
    """Finds a Referable without a display name (F-EDT-06 AC1)."""
    for referable in context.referables:
        if not referable.display_name:
            yield Finding(
                DISPLAY_NAME_MISSING,
                Severity.INFO,
                "The use of a display name is recommended to express a "
                "human readable name for the Referable in multiple languages",
                referable,
                referable,
                "display_name",
            )


def display_name_one_language(context: ValidationContext) -> Iterator[Finding]:
    """Finds a display name in one language only (F-EDT-06 AC1)."""
    for referable in context.referables:
        if referable.display_name and len(referable.display_name) < 2:
            yield Finding(
                DISPLAY_NAME_ONE_LANGUAGE,
                Severity.INFO,
                "Consider having a display name in multiple languages",
                referable,
                referable,
                "display_name",
            )


def description_missing(context: ValidationContext) -> Iterator[Finding]:
    """Finds a Referable without a description (F-EDT-06 AC1)."""
    for referable in context.referables:
        if not referable.description:
            yield Finding(
                DESCRIPTION_MISSING,
                Severity.INFO,
                "The use of a description is recommended, to let the "
                "consumer of a Referable understand the nature of it",
                referable,
                referable,
                "description",
            )


def description_one_language(context: ValidationContext) -> Iterator[Finding]:
    """Finds a description in one language only (F-EDT-06 AC1)."""
    for referable in context.referables:
        if referable.description and len(referable.description) < 2:
            yield Finding(
                DESCRIPTION_ONE_LANGUAGE,
                Severity.INFO,
                "Consider having a description in multiple languages",
                referable,
                referable,
                "description",
            )


def _shells(
    context: ValidationContext,
) -> Iterator[model.AssetAdministrationShell]:
    for obj in context.objects:
        if isinstance(obj, model.AssetAdministrationShell):
            yield obj


HINT_RULES = (
    Rule(
        KEY_WHITESPACE,
        "A semantic id has no whitespace",
        "F-EDT-06: whitespace in a key could lead to matching problems.",
        key_whitespace,
    ),
    Rule(
        CATEGORY_DEPRECATED,
        "A category is deprecated",
        "F-EDT-06: Part 1 deprecates the category of a Referable.",
        category_deprecated,
    ),
    Rule(
        COPY_NAME,
        "An idShort is not named by a copy",
        "F-EDT-06: three dashes mark a name that a copy and paste made.",
        copy_name,
    ),
    Rule(
        ASSET_ID_EMPTY,
        "A global asset id has text",
        "F-EDT-02 AC9: an empty global asset id identifies nothing.",
        empty_asset_id,
    ),
    Rule(
        ASSET_ID_DUPLICATE,
        "A global asset id is used once",
        "F-EDT-02 AC9: two shells for one asset id are probably a mistake.",
        duplicate_asset_id,
    ),
    Rule(
        ENTITY_GLOBAL_ID,
        "A self-managed entity has a global asset id",
        "F-EDT-04 AC17: the original asks a self-managed entity for the "
        "global identifier of its asset.",
        entity_global_id,
    ),
    Rule(
        DISPLAY_NAME_MISSING,
        "A Referable has a display name",
        "F-EDT-06 AC1: a display name is recommended.",
        display_name_missing,
    ),
    Rule(
        DISPLAY_NAME_ONE_LANGUAGE,
        "A display name has several languages",
        "F-EDT-06 AC1: a display name in one language only.",
        display_name_one_language,
    ),
    Rule(
        DESCRIPTION_MISSING,
        "A Referable has a description",
        "F-EDT-06 AC1: a description is recommended.",
        description_missing,
    ),
    Rule(
        DESCRIPTION_ONE_LANGUAGE,
        "A description has several languages",
        "F-EDT-06 AC1: a description in one language only.",
        description_one_language,
    ),
)
