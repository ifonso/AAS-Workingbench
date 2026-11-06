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
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.samm import is_samm
from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.field_checks import copy_name_problem
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
NO_DATA_SPECIFICATION = "EDT-HINT-NO-DATA-SPEC"


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


def concept_without_data_specification(
    context: ValidationContext,
) -> Iterator[Finding]:
    """Finds a concept description with no data specification (F-EDT-05).

    Part 1 says that a concept description has at least one data specification
    template associated. A description that carries a SAMM element is left out
    (AC18): it defines its concept in the extension, not in a record.
    """
    for obj in context.objects:
        if (
            isinstance(obj, ConceptDescription)
            and not obj.embedded_data_specifications
            and not is_samm(obj)
        ):
            yield Finding(
                NO_DATA_SPECIFICATION,
                Severity.WARNING,
                "The concept description has no data specification, so it "
                "defines nothing. Add an IEC 61360 record",
                obj,
                obj,
                "embedded_data_specifications",
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
        NO_DATA_SPECIFICATION,
        "A concept description has a data specification",
        "F-EDT-05: Part 1 gives a concept description at least one data "
        "specification. One with a SAMM element is left out (AC18).",
        concept_without_data_specification,
    ),
)
