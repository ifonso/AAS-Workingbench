"""Small constructors that keep the model code of the example short.

Each constructor takes the name of a concept of `arm_concepts.CONCEPTS`. It
sets the semantic id from it, the display name in English, German and
Portuguese, and the description from the definition of the concept. So every
element that the script makes carries its meaning, and the model code only says
what is specific: the value.
"""

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Sequence
import datetime
from typing import Any

from basyx.aas import model

from arm_concepts import NAMESPACE
from arm_concepts import concept
from arm_concepts import semantic_id
from arm_concepts import value_id

LANGUAGES = ("en", "de", "pt")
SERIAL_NUMBER = "PP6-2026-000417"
MANUFACTURER_ID = f"{NAMESPACE}/company/workingbench-example-robotics"
AAS_ID = f"{NAMESPACE}/aas/pp6/{SERIAL_NUMBER}"
ASSET_ID = f"{NAMESPACE}/asset/pp6/{SERIAL_NUMBER}"
ASSET_TYPE = f"{NAMESPACE}/asset-type/pp6"

DATASHEET_PATH = "/aasx/files/pp6_datasheet.pdf"
QUICKSTART_PATH = "/aasx/files/pp6_quickstart_en.pdf"
QUICKSTART_DE_PATH = "/aasx/files/pp6_quickstart_de.pdf"
PICTURE_PATH = "/aasx/files/pp6_arm.png"
ENVELOPE_PATH = "/aasx/files/pp6_work_envelope.png"
THUMBNAIL_PATH = "/aasx/files/pp6_thumbnail.png"
LOGO_PATH = "/aasx/files/pp6_logo.png"
MARKING_PATH = "/aasx/files/pp6_marking.png"

Number = int | float


def submodel_id(name: str) -> str:
    """Builds the id of a submodel of the example.

    Args:
        name: The short name of the submodel.

    Returns:
        An id below the namespace of the example.
    """
    return f"{NAMESPACE}/submodel/pp6/{SERIAL_NUMBER}/{name}"


def names(en: str, de: str | None = None, pt: str | None = None) -> Any:
    """Builds a multi-language name.

    Args:
        en: The English text.
        de: The German text, if any.
        pt: The Portuguese text, if any.

    Returns:
        The name as the SDK holds it.
    """
    return model.MultiLanguageNameType(_present(en, de, pt))


def texts(
    en: str, de: str | None = None, pt: str | None = None
) -> model.MultiLanguageTextType:
    """Builds a multi-language text.

    Args:
        en: The English text.
        de: The German text, if any.
        pt: The Portuguese text, if any.

    Returns:
        The text as the SDK holds it.
    """
    return model.MultiLanguageTextType(_present(en, de, pt))


def _present(*values: str | None) -> dict[str, str]:
    return {
        lang: text
        for lang, text in zip(LANGUAGES, values, strict=True)
        if text is not None
    }


def meaning(concept_name: str) -> dict[str, Any]:
    """Gives the arguments that every element takes from its concept.

    Args:
        concept_name: The name of the concept.

    Returns:
        The semantic id, the display name and the description.
    """
    entry = concept(concept_name)
    return {
        "semantic_id": semantic_id(concept_name),
        "display_name": names(*entry.names),
        "description": texts(*entry.definitions),
    }


def external(value: str) -> model.ExternalReference:
    """Builds an external reference to a global thing.

    Args:
        value: The identifier, such as an IRI.

    Returns:
        A reference with one `GlobalReference` key.
    """
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),)
    )


def reference_to(
    element: model.Referable | model.Identifiable,
) -> model.ModelReference[Any]:
    """Builds a model reference to an object that is already in its parent.

    Args:
        element: A shell, a submodel, or an element inside a submodel.

    Returns:
        The model reference with the keys from the submodel down.
    """
    return model.ModelReference.from_referable(element)  # pyright: ignore[reportArgumentType]


def reference_to_shell(shell_id: str) -> model.ModelReference[Any]:
    """Builds a model reference to a shell.

    Args:
        shell_id: The id of the shell.

    Returns:
        A model reference with one key.
    """
    return model.ModelReference(
        (model.Key(model.KeyTypes.ASSET_ADMINISTRATION_SHELL, shell_id),),
        model.AssetAdministrationShell,
    )


def semantics_of(submodel: model.Submodel) -> Iterator[model.Reference]:
    """Yields every semantic id and supplemental semantic id in a submodel.

    Args:
        submodel: The submodel.

    Yields:
        The references of the submodel and of all its elements, including the
        statements of entities, the variables of operations and the
        annotations.
    """
    stack: list[Any] = [submodel]
    while stack:
        node = stack.pop()
        if node.semantic_id is not None:
            yield node.semantic_id
        yield from node.supplemental_semantic_id
        if isinstance(node, model.Submodel):
            stack.extend(node.submodel_element)
        elif isinstance(
            node, (model.SubmodelElementCollection, model.SubmodelElementList)
        ):
            stack.extend(node.value)
        elif isinstance(node, model.Entity):
            stack.extend(node.statement)
        elif isinstance(node, model.Operation):
            stack.extend(node.input_variable)
            stack.extend(node.output_variable)
            stack.extend(node.in_output_variable)
        elif isinstance(node, model.AnnotatedRelationshipElement):
            stack.extend(node.annotation)


def find(submodel: model.Submodel, *path: str | int) -> model.SubmodelElement:
    """Finds an element of a submodel by its path.

    Args:
        submodel: The submodel to search.
        *path: The idShorts from the submodel down, and an index for the
            items of a list.

    Returns:
        The element.
    """
    current: Any = submodel
    for step in path:
        if isinstance(step, int):
            current = list(current.value)[step]
        else:
            current = current.get_referable(step)
    return current


def qualifier(
    kind: str,
    value_type: type,
    value: Any,
    concept_name: str | None = None,
) -> model.Qualifier:
    """Builds a qualifier whose type is described by a concept.

    Args:
        kind: The type of the qualifier, as the modeler writes it.
        value_type: The XSD type of the value.
        value: The value.
        concept_name: The concept that defines the qualifier. It defaults to
            `kind`.

    Returns:
        A concept qualifier.
    """
    return model.Qualifier(
        kind,
        value_type,
        value,
        semantic_id=semantic_id(concept_name or kind),
    )


def extension(
    name: str,
    value_type: type | None,
    value: Any,
    refers_to: Iterable[model.ModelReference[Any]] = (),
) -> model.Extension:
    """Builds an extension whose name is described by a concept.

    Args:
        name: The name, which is also the name of the concept.
        value_type: The XSD type of the value.
        value: The value.
        refers_to: The elements that the extension is about.

    Returns:
        The extension.
    """
    return model.Extension(
        name,
        value_type,
        value,
        refers_to=refers_to,
        semantic_id=semantic_id(name),
    )


def fictional() -> model.Extension:
    """Builds the extension that marks an object as part of a fictional example."""
    return extension("FictionalExample", bool, True)


def prop(
    id_short: str | None,
    value_type: type,
    value: Any,
    concept_name: str | None = None,
    coded: bool = False,
    qualifiers: Iterable[model.Qualifier] = (),
) -> model.Property:
    """Builds a Property from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        value_type: The XSD type of the value.
        value: The value.
        concept_name: The concept. It defaults to the idShort.
        coded: True when the value is one of the value list of the concept,
            so that `valueId` points at it.
        qualifiers: Qualifiers of the element.

    Returns:
        The property.
    """
    name = concept_name or id_short
    assert name is not None
    return model.Property(
        id_short,
        value_type,
        value,
        value_id=value_id(name, value) if coded else None,
        qualifier=qualifiers,
        **meaning(name),
    )


def mlp(
    id_short: str | None,
    en: str,
    de: str | None = None,
    pt: str | None = None,
    concept_name: str | None = None,
) -> model.MultiLanguageProperty:
    """Builds a MultiLanguageProperty from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        en: The English text.
        de: The German text, if any.
        pt: The Portuguese text, if any.
        concept_name: The concept. It defaults to the idShort.

    Returns:
        The multi-language property.
    """
    name = concept_name or id_short
    assert name is not None
    return model.MultiLanguageProperty(
        id_short, texts(en, de, pt), **meaning(name)
    )


def span(
    id_short: str | None,
    value_type: type,
    low: Number,
    high: Number,
    concept_name: str | None = None,
    qualifiers: Iterable[model.Qualifier] = (),
) -> model.Range:
    """Builds a Range from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        value_type: The XSD type of the bounds.
        low: The minimum.
        high: The maximum.
        concept_name: The concept. It defaults to the idShort.
        qualifiers: Qualifiers of the element.

    Returns:
        The range.
    """
    name = concept_name or id_short
    assert name is not None
    return model.Range(
        id_short,
        value_type,
        low,
        high,
        qualifier=qualifiers,
        **meaning(name),
    )


def collection(
    id_short: str | None,
    children: Iterable[model.SubmodelElement],
    concept_name: str | None = None,
) -> model.SubmodelElementCollection:
    """Builds a SubmodelElementCollection from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        children: The elements of the collection.
        concept_name: The concept. It defaults to the idShort.

    Returns:
        The collection.
    """
    name = concept_name or id_short
    assert name is not None
    return model.SubmodelElementCollection(id_short, children, **meaning(name))


def listing(
    id_short: str,
    element_type: type,
    items: Iterable[model.SubmodelElement],
    item_concept: str,
    concept_name: str | None = None,
    value_type: type | None = None,
) -> model.SubmodelElementList:
    """Builds a SubmodelElementList from a concept.

    Args:
        id_short: The idShort.
        element_type: The class of the items.
        items: The items, made with `id_short=None`.
        item_concept: The concept that every item has as its semantic id.
        concept_name: The concept of the list. It defaults to the idShort.
        value_type: The XSD type of the items of a list of properties.

    Returns:
        The list.
    """
    return model.SubmodelElementList(
        id_short,
        element_type,
        items,
        semantic_id_list_element=semantic_id(item_concept),
        value_type_list_element=value_type,
        **meaning(concept_name or id_short),
    )


def file_element(
    id_short: str | None,
    path: str,
    content_type: str,
    concept_name: str | None = None,
) -> model.File:
    """Builds a File from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        path: The path of the file in the package.
        content_type: The media type.
        concept_name: The concept. It defaults to the idShort.

    Returns:
        The file element.
    """
    name = concept_name or id_short
    assert name is not None
    return model.File(id_short, content_type, path, **meaning(name))


def link(
    id_short: str | None,
    target: model.Reference,
    concept_name: str | None = None,
) -> model.ReferenceElement:
    """Builds a ReferenceElement from a concept.

    Args:
        id_short: The idShort, or None for an item of a list.
        target: What the element points at.
        concept_name: The concept. It defaults to the idShort.

    Returns:
        The reference element.
    """
    name = concept_name or id_short
    assert name is not None
    return model.ReferenceElement(id_short, target, **meaning(name))


def fill(
    target: model.Submodel
    | model.SubmodelElementCollection
    | model.Entity
    | model.SubmodelElementList,
    elements: Sequence[model.SubmodelElement],
) -> None:
    """Adds elements to a submodel, a collection, an entity or a list.

    Args:
        target: The parent.
        elements: The elements to add, in order.
    """
    members: Any
    if isinstance(target, model.Submodel):
        members = target.submodel_element
    elif isinstance(target, model.Entity):
        members = target.statement
    else:
        members = target.value
    for element in elements:
        members.add(element)


def moment(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> datetime.datetime:
    """Builds a UTC time, which is what an `xs:dateTime` value holds here.

    Args:
        year: The year.
        month: The month.
        day: The day.
        hour: The hour.
        minute: The minute.
        second: The second.

    Returns:
        A timezone-aware date and time.
    """
    return datetime.datetime(
        year, month, day, hour, minute, second, tzinfo=datetime.UTC
    )


def own_submodel(
    name: str,
    id_short: str,
    elements: Iterable[model.SubmodelElement],
    concept_name: str,
) -> model.Submodel:
    """Builds a submodel that no template covers.

    Args:
        name: The short name that ends the id of the submodel.
        id_short: The idShort.
        elements: The elements of the submodel.
        concept_name: The concept that is the semantic id of the submodel.

    Returns:
        An instance submodel of version 1.0 that names the manufacturer as its
        creator and carries the extension that marks the example as fictional.
    """
    return model.Submodel(
        submodel_id(name),
        elements,
        id_short=id_short,
        administration=model.AdministrativeInformation(
            version="1", revision="0", creator=external(MANUFACTURER_ID)
        ),
        kind=model.ModellingKind.INSTANCE,
        extension=[fictional()],
        **meaning(concept_name),
    )
