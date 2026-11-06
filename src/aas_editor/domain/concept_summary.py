"""What the embedded display shows about a concept description (F-EDT-03 AC15, F-EDT-05 AC14).

The panel of a submodel or an element that has a semantic id shows the concept
description that the semantic id names, below the attributes of the object.
This module decides what is shown, as plain text, so that the panel only has
to lay it out and tests need no Qt:

- the title and the id of the description,
- for each IEC 61360 record the attributes that have a value, and for the value
  list the first pairs,
- the number of `isCaseOf` references and the SAMM element, if any,
- what to say when the semantic id names no description of the package.

The display is read-only. The description is changed in its own tab.

Example:
    Listing what a description says::

        summary = summarize(concept)
        for row in summary.rows:
            print(f"{row.label}: {row.text}")
"""

from collections.abc import Iterable
from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.data_specifications import Iec61360Draft
from aas_editor.domain.data_specifications import draft_of
from aas_editor.domain.data_specifications import iec_content_of
from aas_editor.domain.references import describe_reference
from aas_editor.domain.samm import samm_element_of

NOT_FOUND = "The package has no concept description that this semantic id names"
"""The title of the group that Package Explorer shows for a missing description."""

# How many pairs of a value list are written out before the rest is counted.
MAX_PAIRS = 5


@dataclass(frozen=True)
class SummaryRow:
    """One line of the display.

    Attributes:
        label: The attribute, such as `Preferred name`.
        text: Its value as one line of text.
    """

    label: str
    text: str


@dataclass(frozen=True)
class ConceptSummary:
    """What the display says about one concept description.

    Attributes:
        title: The idShort of the description, or its id.
        concept_id: The id of the description.
        headline: One line to show while the display is collapsed: the
            preferred name, or the definition.
        rows: The attributes that have a value, in the order of the display.
    """

    title: str
    concept_id: str
    headline: str
    rows: tuple[SummaryRow, ...]


def concept_named_by(
    objects: Iterable[model.Identifiable], reference: model.Reference
) -> ConceptDescription | None:
    """Finds the description that a semantic id names.

    A semantic id names a description when one of its keys holds the id of
    the description (ADR 0014).

    Args:
        objects: The identifiables of the package.
        reference: The semantic id.

    Returns:
        The description of the first key that names one, or None.
    """
    concepts = {o.id: o for o in objects if isinstance(o, ConceptDescription)}
    for key in reference.key:
        if key.value in concepts:
            return concepts[key.value]
    return None


def _languages(rows: Iterable[tuple[str, str]]) -> str:
    return "; ".join(f"{language}: {text}" for language, text in rows if text)


def _pairs(content: model.DataSpecificationIEC61360) -> str:
    value_list = content.value_list
    if not value_list:
        return ""
    pairs = sorted(
        value_list,
        key=lambda p: (p.value.lower(), p.value),
    )
    shown = [
        f"{pair.value} = {describe_reference(pair.value_id)}"
        if pair.value_id is not None
        else pair.value
        for pair in pairs[:MAX_PAIRS]
    ]
    more = len(pairs) - len(shown)
    count = f"{len(pairs)} pair{'' if len(pairs) == 1 else 's'}: "
    text = count + "; ".join(shown)
    return text + (f"; and {more} more" if more > 0 else "")


def _record_rows(
    draft: Iec61360Draft, content: model.DataSpecificationIEC61360
) -> list[SummaryRow]:
    candidates = [
        ("Preferred name", _languages(draft.preferred_name)),
        ("Short name", _languages(draft.short_name)),
        ("Definition", _languages(draft.definition)),
        ("Data type", draft.data_type.name if draft.data_type else ""),
        ("Unit", draft.unit),
        ("Unit id", draft.unit_id),
        ("Symbol", draft.symbol),
        ("Value format", draft.value_format),
        ("Value", draft.value),
        (
            "Level types",
            ", ".join(
                sorted(level.name.lower() for level in draft.level_types)
            ),
        ),
        ("Value list", _pairs(content)),
        ("Source of definition", draft.source_of_definition),
    ]
    return [SummaryRow(label, text) for label, text in candidates if text]


def summarize(concept: ConceptDescription) -> ConceptSummary:
    """Lists what the display shows for a description.

    Args:
        concept: The description that the semantic id names.

    Returns:
        The title, a headline, and a row for each attribute that has a value.
        A description with several IEC 61360 records lists the first one's
        attributes, and says that there are more.
    """
    rows: list[SummaryRow] = []
    records = [
        content
        for record in concept.embedded_data_specifications
        if (content := iec_content_of(record)) is not None
    ]
    headline = ""
    if records:
        first = records[0]
        draft = draft_of(first)
        rows.extend(_record_rows(draft, first))
        headline = _languages(draft.preferred_name[:1]) or _languages(
            draft.definition[:1]
        )
        if len(records) > 1:
            rows.append(
                SummaryRow(
                    "More records",
                    f"{len(records) - 1} further IEC 61360 "
                    f"record{'' if len(records) == 2 else 's'} not shown",
                )
            )
    else:
        rows.append(SummaryRow("Data specification", "No IEC 61360 record"))
    cases = list(concept.is_case_of)
    if cases:
        rows.append(
            SummaryRow(
                "Is case of", "; ".join(describe_reference(c) for c in cases)
            )
        )
    samm = samm_element_of(concept)
    if samm is not None:
        rows.append(
            SummaryRow(
                "SAMM element", f"{samm.type_name} (version {samm.version})"
            )
        )
    return ConceptSummary(
        title=concept.id_short or concept.id,
        concept_id=concept.id,
        headline=headline,
        rows=tuple(rows),
    )
