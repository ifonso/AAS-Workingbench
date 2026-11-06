"""Concept descriptions and the objects that refer to them by semantic id.

A semantic id says what an element or a submodel means. When it names a
concept description of the package, a tool can show the definition. This module
answers questions about that link that do not change anything:

- which objects below a selection have a semantic id,
- what a new description for a semantic id looks like,
- which description an element without a semantic id probably belongs to,
- which descriptions carry no information at all.

A description is found by the **id** in the keys of the semantic id. That is
the rule of the original editor and of the reference index of this editor: an
external reference counts when any of its keys holds the id, a model reference
when its first key does.

Example:
    Describing the concept behind a property::

        concept = new_concept_for(prop, adaptive=True)
"""

from collections.abc import Iterable
from collections.abc import Iterator
from dataclasses import dataclass
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.data_specifications import DEFAULT_LANGUAGE
from aas_editor.domain.data_specifications import MAX_DEFINITION
from aas_editor.domain.data_specifications import MAX_PREFERRED_NAME
from aas_editor.domain.data_specifications import MAX_SHORT_NAME
from aas_editor.domain.data_specifications import template_reference
from aas_editor.domain.ids import fix_id_short
from aas_editor.domain.ids import new_identifier
from aas_editor.domain.references import ReferenceIndex

# The longest display name the SDK accepts (MultiLanguageNameType).
MAX_DISPLAY_NAME = 128

_DATA_TYPES: dict[type, model.DataTypeIEC61360] = {
    model.datatypes.String: model.DataTypeIEC61360.STRING,
    model.datatypes.Boolean: model.DataTypeIEC61360.BOOLEAN,
    model.datatypes.Date: model.DataTypeIEC61360.DATE,
    model.datatypes.Time: model.DataTypeIEC61360.TIME,
    model.datatypes.DateTime: model.DataTypeIEC61360.TIMESTAMP,
}


@dataclass(frozen=True, eq=False)
class SemanticHolder:
    """A submodel or element, and its semantic id.

    Attributes:
        owner: The submodel or element.
        reference: Its semantic id, or None if it has none.
    """

    owner: model.Submodel | model.SubmodelElement
    reference: model.Reference | None

    @property
    def id_short(self) -> str | None:
        """The idShort of the owner, or None for an item of a list.

        The SDK gives an item of a `SubmodelElementList` a generated name that
        is never saved.
        """
        if isinstance(self.owner.parent, model.SubmodelElementList):
            return None
        return self.owner.id_short


def children_of(obj: model.Referable) -> Iterator[model.SubmodelElement]:
    """Yields the elements directly below an object.

    Collections, lists, entities, operations (their variables), and annotated
    relationships all count.
    """
    for namespace_set in cast(
        "Iterable[Iterable[object]]", getattr(obj, "namespace_element_sets", ())
    ):
        for member in namespace_set:
            if isinstance(member, model.SubmodelElement):
                yield member


def holders_of(
    roots: Iterable[model.Referable], below: bool = True
) -> list[SemanticHolder]:
    """Finds the submodels and elements that can have a semantic id.

    Args:
        roots: The selected submodels and elements.
        below: Whether to include everything below them.

    Returns:
        Each submodel or element once, in the order of the roots and of the
        saved order below them, with its semantic id or None. Shells and other
        objects are skipped.
    """
    found: list[SemanticHolder] = []
    seen: set[int] = set()

    def visit(obj: model.Referable) -> None:
        if id(obj) in seen:
            return
        seen.add(id(obj))
        if isinstance(obj, (model.Submodel, model.SubmodelElement)):
            found.append(SemanticHolder(obj, obj.semantic_id))
        if below:
            for child in children_of(obj):
                visit(child)
        if below and isinstance(obj, model.Submodel):
            for element in obj.submodel_element:
                visit(element)

    for root in roots:
        visit(root)
    return found


def concept_id_of(reference: model.Reference) -> str:
    """Returns the id that a description for a semantic id gets.

    That is the value of the first key, as in the original editor.
    """
    return reference.key[0].value


def fitting_texts(
    texts: Iterable[tuple[str, str]] | None, longest: int
) -> dict[str, str]:
    """Copies the entries of a multi-language text that fit a length."""
    return (
        {lang: text for lang, text in texts if 1 <= len(text) <= longest}
        if texts
        else {}
    )


def data_type_for(holder: model.Referable) -> model.DataTypeIEC61360 | None:
    """Suggests the IEC 61360 data type for the value of an element.

    Only types that map without a guess: strings, booleans, dates, times,
    timestamps, and multi-language texts. A number can be a count, a measure,
    or a currency, and those need a unit (AASc-3a-009), so it is left open.
    """
    if isinstance(holder, model.MultiLanguageProperty):
        return model.DataTypeIEC61360.STRING_TRANSLATABLE
    if isinstance(holder, model.Property):
        return _DATA_TYPES.get(holder.value_type)
    return None


def new_empty_concept() -> ConceptDescription:
    """Builds a description with a generated id and nothing else.

    This is `Create empty` of Package Explorer (F-EDT-11 AC15). The user fills
    it in afterwards, so it has no data specification yet.

    Returns:
        A description that is not part of a package yet, with a `urn:uuid:` id.
    """
    return ConceptDescription(id_=new_identifier())


def new_concept_for(
    holder: SemanticHolder, adaptive: bool, language: str = DEFAULT_LANGUAGE
) -> ConceptDescription:
    """Builds the description that a semantic id names.

    The description gets the id of the first key, the idShort and the
    description of the holder. In the adaptive form it also gets an IEC 61360
    record: the preferred name from the display name or the idShort, the
    definition from the description, and a data type where the value allows
    one.

    Args:
        holder: A submodel or element with a semantic id.
        adaptive: Whether to add the IEC 61360 record.
        language: The language of a name that comes from the idShort.

    Returns:
        A description that is not part of a package yet.

    Raises:
        ValueError: If the holder has no semantic id.
    """
    if holder.reference is None:
        raise ValueError("The object has no semantic id")
    owner = holder.owner
    id_short = holder.id_short
    description = fitting_texts(
        owner.description.items() if owner.description else None,
        MAX_DEFINITION,
    )
    concept = ConceptDescription(
        id_=concept_id_of(holder.reference),
        id_short=id_short,
        description=(
            model.MultiLanguageTextType(dict(owner.description or {}))
            if owner.description
            else None
        ),
    )
    if adaptive:
        concept.embedded_data_specifications.append(
            model.EmbeddedDataSpecification(
                template_reference(),
                _content_for(holder, description, language),
            )
        )
    return concept


def _content_for(
    holder: SemanticHolder, description: dict[str, str], language: str
) -> model.DataSpecificationIEC61360:
    owner = holder.owner
    names = fitting_texts(
        owner.display_name.items() if owner.display_name else None,
        MAX_PREFERRED_NAME,
    )
    if not names:
        name = holder.id_short or _last_key_value(holder)
        names = {language: name[:MAX_PREFERRED_NAME]}
    return model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360(names),
        definition=(
            model.DefinitionTypeIEC61360(description) if description else None
        ),
        data_type=data_type_for(owner),
    )


def _last_key_value(holder: SemanticHolder) -> str:
    assert holder.reference is not None
    return holder.reference.key[-1].value


def concept_for_pair(
    pair: model.ValueReferencePair, language: str = DEFAULT_LANGUAGE
) -> ConceptDescription:
    """Builds the description of one pair of a value list.

    The id is the first key of the value id. The idShort and the display name
    come from the value, which may be shortened to fit the SDK. The IEC 61360
    record has the value as its preferred name, short name (if it has at most
    18 characters), and definition, and the data type
    `STRING_TRANSLATABLE`.

    Args:
        pair: A pair with a value id.
        language: The language of the texts.

    Raises:
        ValueError: If the pair has no value id.
    """
    if pair.value_id is None:
        raise ValueError("The pair has no value id")
    value = pair.value
    concept = ConceptDescription(
        id_=concept_id_of(pair.value_id),
        id_short=fix_id_short(value, "CD"),
        display_name=model.MultiLanguageNameType(
            {language: value[:MAX_DISPLAY_NAME]}
        ),
    )
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            template_reference(),
            model.DataSpecificationIEC61360(
                preferred_name=model.PreferredNameTypeIEC61360(
                    {language: value[:MAX_PREFERRED_NAME]}
                ),
                short_name=(
                    model.ShortNameTypeIEC61360({language: value})
                    if len(value) <= MAX_SHORT_NAME
                    else None
                ),
                definition=model.DefinitionTypeIEC61360(
                    {language: value[:MAX_DEFINITION]}
                ),
                data_type=model.DataTypeIEC61360.STRING_TRANSLATABLE,
            ),
        )
    )
    return concept


def concept_reference(concept: ConceptDescription) -> model.ExternalReference:
    """Builds the semantic id that names a description.

    An external reference with one `GlobalReference` key holding the id, which
    is the form the metamodel recommends for a semantic id, and the one that
    the templates of the IDTA use.
    """
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, concept.id),)
    )


def concepts_by_id_short(
    objects: Iterable[model.Identifiable], id_short: str
) -> list[ConceptDescription]:
    """Finds the descriptions that match an idShort.

    An exact match wins. If there is none, descriptions that differ only in
    case match.

    Args:
        objects: The identifiables of the package.
        id_short: The idShort of the element.

    Returns:
        Zero, one, or several descriptions.
    """
    concepts = [o for o in objects if isinstance(o, ConceptDescription)]
    exact = [c for c in concepts if c.id_short == id_short]
    if exact:
        return exact
    lowered = id_short.lower()
    return [c for c in concepts if c.id_short and c.id_short.lower() == lowered]


def is_empty_concept(concept: ConceptDescription) -> bool:
    """Tells whether a description says nothing about its concept.

    The metamodel says a description is defined by a data specification
    template, and the original editor warns when it has no record. A
    description is empty here when it has no embedded data specification, no
    `is_case_of` reference, and no extension (a SAMM description keeps its
    content in extensions). It may still have an idShort, a description, or a
    display name: those do not define a concept.
    """
    return not (
        concept.embedded_data_specifications
        or concept.is_case_of
        or len(concept.extension)
    )


def empty_concepts(
    objects: Iterable[model.Identifiable],
) -> list[ConceptDescription]:
    """Lists the empty concept descriptions of a package, in a stable order."""
    found = [
        o
        for o in objects
        if isinstance(o, ConceptDescription) and is_empty_concept(o)
    ]
    return sorted(found, key=lambda c: (c.id_short or "", c.id))


def usage_count(index: ReferenceIndex, concept: ConceptDescription) -> int:
    """Counts the references that point at a description."""
    return len(index.usages_of([concept]))
