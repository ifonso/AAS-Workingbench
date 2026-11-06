"""Rules about concept descriptions with IEC 61360 content (Part 3a).

The category of a concept description limits the data type of its IEC 61360
data specification. The constraints are AASc-3a-004 to AASc-3a-007 of Part 3a.
The SDK does not check them. The sets of data types are those of the text of
Part 3a, "Specification of the Asset Administration Shell, Part 3a: Data
Specification IEC 61360" (IDTA-01003-a, V3.1.1), constraints AASc-3a-004 to
AASc-3a-007. They were compared with the published source,
`documentation/IDTA-01003-a/modules/ROOT/pages/includes/constraints.adoc` in
https://github.com/admin-shell-io/aas-specs-iec61360 (tag v3.1.1, licensed
CC BY 4.0). The messages of the findings are this project's own:

- AASc-3a-004: category PROPERTY or VALUE, the data type is mandatory and one
  of DATE, STRING, STRING_TRANSLATABLE, INTEGER_MEASURE, INTEGER_COUNT,
  INTEGER_CURRENCY, REAL_MEASURE, REAL_COUNT, REAL_CURRENCY, BOOLEAN,
  RATIONAL, RATIONAL_MEASURE, TIME, TIMESTAMP.
- AASc-3a-005: category REFERENCE, the data type is one of STRING, IRI, IRDI.
- AASc-3a-006: category DOCUMENT, the data type is one of FILE, BLOB, HTML.
- AASc-3a-007: category QUALIFIER_TYPE, the data type is mandatory.

Each rule looks at every IEC 61360 record of the description, as the original
does. A category that no rule names, or none, is never reported.

The category is deprecated in V3.1 (see `EDT-HINT-CATEGORY`), but a file that
still sets it is held to these constraints.
"""

from collections.abc import Iterator

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.data_specifications import iec_content_of
from aas_editor.domain.validation.context import ValidationContext
from aas_editor.domain.validation.findings import Finding
from aas_editor.domain.validation.findings import Severity
from aas_editor.domain.validation.rule import Rule

PROPERTY_OR_VALUE = "AASc-3a-004"
REFERENCE = "AASc-3a-005"
DOCUMENT = "AASc-3a-006"
QUALIFIER_TYPE = "AASc-3a-007"

_TYPES = model.DataTypeIEC61360

DATA_TYPES_FOR_PROPERTY_OR_VALUE = frozenset(
    {
        _TYPES.DATE,
        _TYPES.STRING,
        _TYPES.STRING_TRANSLATABLE,
        _TYPES.INTEGER_MEASURE,
        _TYPES.INTEGER_COUNT,
        _TYPES.INTEGER_CURRENCY,
        _TYPES.REAL_MEASURE,
        _TYPES.REAL_COUNT,
        _TYPES.REAL_CURRENCY,
        _TYPES.BOOLEAN,
        _TYPES.RATIONAL,
        _TYPES.RATIONAL_MEASURE,
        _TYPES.TIME,
        _TYPES.TIMESTAMP,
    }
)
DATA_TYPES_FOR_REFERENCE = frozenset({_TYPES.STRING, _TYPES.IRI, _TYPES.IRDI})
DATA_TYPES_FOR_DOCUMENT = frozenset({_TYPES.FILE, _TYPES.BLOB, _TYPES.HTML})


def _names(types: frozenset[model.DataTypeIEC61360]) -> str:
    return ", ".join(sorted(t.name for t in types))


def _concepts(context: ValidationContext) -> Iterator[ConceptDescription]:
    for obj in context.objects:
        if isinstance(obj, ConceptDescription):
            yield obj


def _contents(
    concept: ConceptDescription,
) -> Iterator[model.DataSpecificationIEC61360]:
    for record in concept.embedded_data_specifications:
        content = iec_content_of(record)
        if content is not None:
            yield content


def _check(
    context: ValidationContext,
    rule_id: str,
    categories: frozenset[str],
    allowed: frozenset[model.DataTypeIEC61360] | None,
    wording: str,
) -> Iterator[Finding]:
    """Reports each record whose data type does not fit the category.

    Args:
        context: The package.
        rule_id: The constraint.
        categories: The categories the constraint is about.
        allowed: The data types that fit, or None when any one fits as long as
            there is a data type.
        wording: How the finding says what is wrong, ending in a full stop.
    """
    for concept in _concepts(context):
        if concept.category not in categories:
            continue
        for content in _contents(concept):
            data_type = content.data_type
            if data_type is None or (
                allowed is not None and data_type not in allowed
            ):
                yield Finding(
                    rule_id,
                    Severity.ERROR,
                    f"The category '{concept.category}' with an IEC 61360 "
                    f"data specification {wording}"
                    + (
                        " The data type is missing."
                        if data_type is None
                        else f" The data type is {data_type.name}."
                    ),
                    content,
                    concept,
                    "data_type",
                )


def property_or_value_data_type(
    context: ValidationContext,
) -> Iterator[Finding]:
    """AASc-3a-004: a property or a value needs a data type of its group."""
    yield from _check(
        context,
        PROPERTY_OR_VALUE,
        frozenset({"PROPERTY", "VALUE"}),
        DATA_TYPES_FOR_PROPERTY_OR_VALUE,
        "needs a data type, one of "
        f"{_names(DATA_TYPES_FOR_PROPERTY_OR_VALUE)}.",
    )


def reference_data_type(context: ValidationContext) -> Iterator[Finding]:
    """AASc-3a-005: a reference has the data type STRING, IRI or IRDI."""
    yield from _check(
        context,
        REFERENCE,
        frozenset({"REFERENCE"}),
        DATA_TYPES_FOR_REFERENCE,
        f"needs a data type, one of {_names(DATA_TYPES_FOR_REFERENCE)}.",
    )


def document_data_type(context: ValidationContext) -> Iterator[Finding]:
    """AASc-3a-006: a document has the data type FILE, BLOB or HTML."""
    yield from _check(
        context,
        DOCUMENT,
        frozenset({"DOCUMENT"}),
        DATA_TYPES_FOR_DOCUMENT,
        f"needs a data type, one of {_names(DATA_TYPES_FOR_DOCUMENT)}.",
    )


def qualifier_type_data_type(context: ValidationContext) -> Iterator[Finding]:
    """AASc-3a-007: a qualifier type has a data type."""
    yield from _check(
        context,
        QUALIFIER_TYPE,
        frozenset({"QUALIFIER_TYPE"}),
        None,
        "needs a data type.",
    )


RULES = (
    Rule(
        PROPERTY_OR_VALUE,
        "A property or value description has a data type of its group",
        "Part 3a, constraint AASc-3a-004. The SDK does not check it.",
        property_or_value_data_type,
    ),
    Rule(
        REFERENCE,
        "A reference description has a reference data type",
        "Part 3a, constraint AASc-3a-005. The SDK does not check it.",
        reference_data_type,
    ),
    Rule(
        DOCUMENT,
        "A document description has a document data type",
        "Part 3a, constraint AASc-3a-006. The SDK does not check it.",
        document_data_type,
    ),
    Rule(
        QUALIFIER_TYPE,
        "A qualifier type description has a data type",
        "Part 3a, constraint AASc-3a-007. The SDK does not check it.",
        qualifier_type_data_type,
    ),
)
