"""What the detail of an object reads for texts in languages and for semantics.

A text in several languages read as `en="Time that one cyc..."`, the semanticId
as the last key of a reference, and the unit of a value was in the concept
description below the attributes, not beside the value. This module says what
the detail shows instead, as plain data, so that the view only lays it out:

* the text of a multi-language value in the language that the user prefers,
  with a badge such as `en +2` (proposal 3.4),
* the name of the concept that a semanticId names, with its id under it, as a
  link to the concept description (proposal 3.5),
* the unit that the concept gives a value, with the concept it comes from
  (proposal 3.7).

Example:
    >>> text = preferred_text({"de": "Zykluszeit", "en": "Cycle time"}, ["en"])
    >>> text.text, language_badge(text)
    ('Cycle time', 'en +1')
"""

from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_workingbench.domain.concept_summary import concept_named_by
from aas_workingbench.domain.data_specifications import iec_content_of

FALLBACK_LANGUAGE = "en"
"""The language that is read when the preferred ones have no text."""


@dataclass(frozen=True)
class LanguageText:
    """The text of a multi-language value that is shown.

    Attributes:
        text: The text in the language that is shown.
        language: The language tag of that text, such as `en`.
        others: How many other languages the value has.
    """

    text: str
    language: str
    others: int


def _base(tag: str) -> str:
    return tag.split("-", 1)[0].lower()


def preferred_text(
    texts: Mapping[str, str], preferred: Sequence[str]
) -> LanguageText | None:
    """Picks the text of a multi-language value to show.

    The first preferred language that has a text wins, then English, then the
    first language of the value. A preferred `en` also takes an `en-US`.

    Args:
        texts: The texts by their language tags, such as a `LangStringSet`.
        preferred: The languages of the user, the first being the one they
            read best.

    Returns:
        The text to show, or None when the value has no text.
    """
    entries = [(str(tag), str(text)) for tag, text in texts.items() if text]
    if not entries:
        return None
    for wanted in (*preferred, FALLBACK_LANGUAGE):
        for tag, text in entries:
            if tag.lower() == wanted.lower():
                return LanguageText(text, tag, len(entries) - 1)
        for tag, text in entries:
            if _base(tag) == _base(wanted):
                return LanguageText(text, tag, len(entries) - 1)
    tag, text = entries[0]
    return LanguageText(text, tag, len(entries) - 1)


def language_badge(text: LanguageText) -> str:
    """Says which language is shown and how many more there are: `en +2`."""
    if text.others:
        return f"{text.language} +{text.others}"
    return text.language


@dataclass(frozen=True)
class SemanticLink:
    """What a semanticId names, as the detail shows it.

    Attributes:
        concept: The concept description of the package that it names.
        label: The name of the concept: its preferred name in the language
            that the user prefers, its display name, or its idShort.
        address: The id that the semanticId holds, shown below the label.
        unit: The unit that the concept gives, or an empty string.
    """

    concept: ConceptDescription
    label: str
    address: str
    unit: str

    @property
    def source(self) -> str:
        """Names the concept that the label and the unit come from."""
        return self.concept.id_short or self.concept.id


def reference_address(reference: model.Reference) -> str:
    """Gives the id that a reference holds: the value of its first key."""
    keys = list(reference.key)
    return keys[0].value if keys else ""


def _iec_records(
    concept: ConceptDescription,
) -> list[model.DataSpecificationIEC61360]:
    return [
        content
        for record in concept.embedded_data_specifications
        if (content := iec_content_of(record)) is not None
    ]


def concept_label(concept: ConceptDescription, preferred: Sequence[str]) -> str:
    """Names a concept description as a person reads it.

    Args:
        concept: The description.
        preferred: The languages of the user.

    Returns:
        The preferred name of its first IEC 61360 record, its display name, its
        idShort, or its id, in that order of what it has.
    """
    for content in _iec_records(concept):
        if content.preferred_name:
            text = preferred_text(content.preferred_name, preferred)
            if text is not None:
                return text.text
    if concept.display_name:
        text = preferred_text(concept.display_name, preferred)
        if text is not None:
            return text.text
    return concept.id_short or concept.id


def concept_unit(concept: ConceptDescription) -> str:
    """Gives the unit of the first IEC 61360 record that has one."""
    for content in _iec_records(concept):
        if content.unit:
            return str(content.unit)
    return ""


def semantic_link(
    objects: Iterable[model.Identifiable],
    reference: model.Reference | None,
    preferred: Sequence[str],
) -> SemanticLink | None:
    """Finds what the detail shows for a semanticId.

    Args:
        objects: The identifiables of the package.
        reference: The semanticId, or None.
        preferred: The languages of the user.

    Returns:
        The link to the concept description that the reference names, or None
        when it names none of the package. The detail then shows the reference
        as before.
    """
    if reference is None:
        return None
    concept = concept_named_by(objects, reference)
    if concept is None:
        return None
    return SemanticLink(
        concept=concept,
        label=concept_label(concept, preferred),
        address=reference_address(reference),
        unit=concept_unit(concept),
    )
