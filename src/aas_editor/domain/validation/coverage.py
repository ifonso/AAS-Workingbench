"""Which constraints of metamodel V3.1 the SDK enforces, and which the editor does.

The table is the result of probing the pinned SDK (ADR 0004) with real objects:
for each constraint, an object that breaks it was built through the
constructor and through a later edit, and the outcome is in `evidence`. The
tests in `tests/small/test_validation_coverage.py` keep the table and the rules
in step. The list of constraints is the one in Part 1 V3.1.2, checked against
the V3.2 text in the sibling specification folder, which adds AASd-137 and
AASd-138.
"""

from dataclasses import dataclass
import enum

from aas_editor.domain.validation.rules import ALL_RULES


class Enforcement(enum.Enum):
    """Who stops a violation of a constraint."""

    SDK = "sdk"
    """The SDK refuses it in every way that a user can make it."""

    PARTIAL = "partial"
    """The SDK refuses some ways, and a rule of the editor finds the rest."""

    RULE = "rule"
    """The SDK does not check it, and a rule of the editor does."""

    NEITHER = "neither"
    """No check is possible on the objects of a package."""

    NOT_V31 = "not-v31"
    """The constraint is not part of metamodel V3.1."""


@dataclass(frozen=True)
class ConstraintCoverage:
    """What stops a violation of one constraint.

    Attributes:
        constraint: The constraint, such as `AASd-020`.
        subject: What it is about, in a few words.
        enforcement: Who stops a violation.
        rule_ids: The rules of the editor that check it.
        evidence: What the probe of the SDK showed, or why no check is
            possible.
    """

    constraint: str
    subject: str
    enforcement: Enforcement
    rule_ids: tuple[str, ...]
    evidence: str


def _sdk(constraint: str, subject: str, evidence: str) -> ConstraintCoverage:
    return ConstraintCoverage(
        constraint, subject, Enforcement.SDK, (), evidence
    )


def _reference(constraint: str, subject: str) -> ConstraintCoverage:
    return _sdk(
        constraint,
        subject,
        "Refused when the Reference is made. A Reference and its Keys cannot "
        "be changed afterwards, so no invalid one exists in memory.",
    )


COVERAGE: tuple[ConstraintCoverage, ...] = (
    ConstraintCoverage(
        "AASd-002",
        "idShort pattern",
        Enforcement.PARTIAL,
        ("AASd-002",),
        "Refused: a leading digit, a trailing hyphen, other characters, on "
        "make and on set. Accepted: a one-letter idShort, which the pattern "
        "refuses.",
    ),
    ConstraintCoverage(
        "AASd-005",
        "revision needs a version",
        Enforcement.PARTIAL,
        ("AASd-005",),
        "Refused when AdministrativeInformation is made with a revision only. "
        "Accepted: setting version to None afterwards.",
    ),
    ConstraintCoverage(
        "AASd-006",
        "qualifier value equals coded value of valueId",
        Enforcement.RULE,
        ("AASd-006",),
        "Accepted by the SDK. The rule can compare only when valueId is the "
        "id of a pair in a value list of the package. A valueId that points "
        "outside the package (ECLASS, IEC CDD) cannot be resolved offline.",
    ),
    ConstraintCoverage(
        "AASd-007",
        "property value equals coded value of valueId",
        Enforcement.RULE,
        ("AASd-007",),
        "Accepted by the SDK. Same limit as AASd-006.",
    ),
    ConstraintCoverage(
        "AASd-012",
        "multi-language value and valueId have the same meaning",
        Enforcement.NEITHER,
        (),
        "Accepted by the SDK. The constraint compares meanings, and a value "
        "list has one text for a coded value, not one for each language. "
        "Nothing on the objects can be checked.",
    ),
    ConstraintCoverage(
        "AASd-013",
        "range with kind Instance has min or max",
        Enforcement.NOT_V31,
        (),
        "Not in Part 1 V3.0, V3.1 or V3.2, and a Range has no kind in V3. "
        "The SDK docstring still cites it, and `Range` has no `kind` "
        "argument. The work package listed it from the SDK docstring.",
    ),
    _sdk(
        "AASd-014",
        "self-managed entity has an asset id",
        "Refused on make, when entity_type is set to SelfManagedEntity, and "
        "when the last asset id is cleared.",
    ),
    ConstraintCoverage(
        "AASd-020",
        "qualifier value fits value type",
        Enforcement.PARTIAL,
        ("AASd-020", "EDT-VALUE-TYPE"),
        "Refused on make and on set of the value. Accepted: changing "
        "value_type afterwards, which leaves the value in the old type. The "
        "same gap exists in Property, Range and Extension (EDT-VALUE-TYPE).",
    ),
    _sdk(
        "AASd-021",
        "one qualifier of each type",
        "Refused on add, and on editing the type to a taken one.",
    ),
    _sdk(
        "AASd-022",
        "unique idShort in a namespace",
        "Refused on add, and on editing the idShort to a taken one.",
    ),
    _sdk(
        "AASd-077",
        "unique extension name",
        "Refused on add, and on editing the name to a taken one.",
    ),
    _sdk(
        "AASd-107",
        "list item semantic id equals semanticIdListElement",
        "Refused on add, and on editing the semantic id of an item.",
    ),
    _sdk(
        "AASd-108",
        "list items have the list element type",
        "Refused on add. The type of a list cannot be changed.",
    ),
    ConstraintCoverage(
        "AASd-109",
        "list items have the list value type",
        Enforcement.PARTIAL,
        ("AASd-109",),
        "Refused on add and on make without valueTypeListElement. Accepted: "
        "changing value_type of an item afterwards.",
    ),
    _sdk(
        "AASd-114",
        "list items with a semantic id share it",
        "Refused on add, and on editing the semantic id of an item.",
    ),
    ConstraintCoverage(
        "AASd-115",
        "missing item semantic id is the list's",
        Enforcement.NEITHER,
        (),
        "A rule of interpretation ('is assumed'), so nothing can be "
        "violated. The SDK applies it.",
    ),
    ConstraintCoverage(
        "AASd-116",
        "globalAssetId is a reserved name",
        Enforcement.RULE,
        ("AASd-116",),
        "Accepted by the SDK in any case ('globalAssetId', 'GLOBALASSETID').",
    ),
    _sdk(
        "AASd-117",
        "idShort is set outside lists",
        "Refused on add and on clearing the idShort, in Submodel, "
        "Collection, Entity, Operation and annotations.",
    ),
    ConstraintCoverage(
        "AASd-118",
        "supplemental semantic id needs a semantic id",
        Enforcement.PARTIAL,
        ("AASd-118",),
        "Refused: adding a supplemental id to an object with no semantic id, "
        "and clearing the semantic id of one that has supplemental ids. "
        "Accepted: making Property, Qualifier, Extension or SpecificAssetId "
        "with a supplemental id and no semantic id.",
    ),
    ConstraintCoverage(
        "AASd-119",
        "template qualifier needs a template element",
        Enforcement.RULE,
        ("AASd-119",),
        "Accepted by the SDK. In V3.1 only a Submodel has a kind.",
    ),
    _reference("AASd-121", "first key of a reference"),
    _reference("AASd-122", "first key of an external reference"),
    _reference("AASd-123", "first key of a model reference"),
    _reference("AASd-124", "last key of an external reference"),
    _reference("AASd-125", "later keys of a model reference"),
    _reference("AASd-126", "fragment keys in a model reference"),
    _reference("AASd-127", "FragmentReference after File or Blob"),
    _reference("AASd-128", "position after a SubmodelElementList"),
    ConstraintCoverage(
        "AASd-129",
        "template qualifier needs a template submodel",
        Enforcement.RULE,
        ("AASd-129",),
        "Accepted by the SDK. The rule uses the V3.1 text, which has no "
        "exception for operation variables (V3.2 adds one).",
    ),
    ConstraintCoverage(
        "AASd-130",
        "strings have only XML characters",
        Enforcement.PARTIAL,
        ("AASd-130",),
        "Refused for names, texts, ids and paths. Accepted: a control "
        "character in the value of a Property, Range, Qualifier or "
        "Extension. The XML writer then raises ValueError, JSON writes it.",
    ),
    _sdk(
        "AASd-131",
        "asset information has a global or specific asset id",
        "Refused on make, and when the last asset id is cleared.",
    ),
    ConstraintCoverage(
        "AASd-133",
        "external subject id is an external reference",
        Enforcement.RULE,
        ("AASd-133",),
        "Accepted by the SDK: a model reference is stored.",
    ),
    _sdk(
        "AASd-134",
        "unique idShort among operation variables",
        "Refused on add, across the three sets, and on editing the idShort.",
    ),
    ConstraintCoverage(
        "AASd-137",
        "no AAS Referable key in an external reference",
        Enforcement.NOT_V31,
        (),
        "New in V3.2. The SDK targets V3.1 and does not check it.",
    ),
    ConstraintCoverage(
        "AASd-138",
        "list in a template or operation variable has one item",
        Enforcement.NOT_V31,
        (),
        "New in V3.2. The SDK targets V3.1 and does not check it.",
    ),
)

# Rules that are not tied to a constraint number.
EDITOR_RULE_REASONS: dict[str, str] = {
    "EDT-DUPLICATE-ID": (
        "The object store checks an id on add only, so an edit or a paste "
        "can leave two objects with one id."
    ),
    "EDT-DANGLING-REFERENCE": "A model reference whose target is not there.",
    "EDT-MISSING-FILE": "The SDK cannot write a File with no stored file.",
    "EDT-FILE-IN-ANNOTATION": "The SDK skips annotations when it writes files.",
    "EDT-UNREFERENCED-FILE": (
        "A stored file that nothing uses is kept by an AASX save, and shows "
        "here so that a leftover is seen."
    ),
    "EDT-VALUE-TYPE": "A value must fit its value type (see AASd-020).",
    "EDT-RANGE-ORDER": "The minimum of a Range is above its maximum.",
    "EDT-LANGUAGE-TAG": "BCP 47 tags: well-formed, and one entry for each.",
}


def rules_for(constraint: str) -> tuple[str, ...]:
    """Returns the ids of the rules that check a constraint.

    Args:
        constraint: A constraint such as `AASd-020`.

    Returns:
        The ids of the rules, empty if the SDK enforces it or none is possible.
    """
    for entry in COVERAGE:
        if entry.constraint == constraint:
            return entry.rule_ids
    return ()


def known_rule_ids() -> frozenset[str]:
    """Returns the ids of all rules of the editor."""
    return frozenset(rule.rule_id for rule in ALL_RULES)
