"""A small environment whose objects refer to each other in every way.

Tests of references, renames and deletes start from this environment, so each
test names only what it changes. All objects are real BaSyx objects.
"""

from dataclasses import dataclass

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel

CONCEPT_ID = "urn:test:concept"
MAIN_ID = "urn:test:main"
OTHER_ID = "urn:test:other"
SHELL_ID = "urn:test:shell"


@dataclass
class Linked:
    """The objects of the environment, for tests to change and check.

    The main submodel `Main` holds the property `Name`, the collection `Group`
    with the property `Inner`, the list `Items` of two properties, and the
    reference elements `Link` (to `Inner`), `ListLink` (to the second item
    of the list), and `ConceptLink` (to the concept description). The
    relationship `Rel` goes from `Name` to `Inner`. The submodel `Other` holds
    `Pointer`, a reference element that refers to `Name`.
    """

    store: model.SetIdentifiableStore
    shell: model.AssetAdministrationShell
    main: model.Submodel
    other: model.Submodel
    concept: model.ConceptDescription
    name: model.Property
    group: model.SubmodelElementCollection
    inner: model.Property
    items: model.SubmodelElementList
    second_item: model.Property
    link: model.ReferenceElement
    list_link: model.ReferenceElement
    concept_link: model.ReferenceElement
    relationship: model.RelationshipElement
    pointer: model.ReferenceElement


def _item(value: str) -> model.Property:
    """A property for a list, which has no idShort of its own."""
    return model.Property(
        id_short=None, value_type=model.datatypes.String, value=value
    )


def make_linked() -> Linked:
    """Builds the environment. Every call gives new objects."""
    concept = make_concept_description(CONCEPT_ID, "Concept")
    name = make_property("Name")
    name.semantic_id = make_external_reference(CONCEPT_ID)
    inner = make_property("Inner")
    inner.semantic_id = make_external_reference(CONCEPT_ID)
    group = make_collection("Group", [inner])
    first_item = _item("one")
    second_item = _item("two")
    items = make_list("Items", [first_item, second_item])
    link = _reference_element("Link")
    list_link = _reference_element("ListLink")
    concept_link = _reference_element("ConceptLink")
    main = make_submodel(
        MAIN_ID,
        "Main",
        [name, group, items, link, list_link, concept_link],
    )
    # A reference to an element needs the element to be in its submodel.
    relationship = model.RelationshipElement(
        id_short="Rel",
        first=make_reference_to(name),
        second=make_reference_to(inner),
    )
    main.submodel_element.add(relationship)
    link.value = make_reference_to(inner)
    list_link.value = make_reference_to(second_item)
    concept_link.value = make_reference_to(concept)
    pointer = _reference_element("Pointer")
    other = make_submodel(OTHER_ID, "Other", [pointer])
    pointer.value = make_reference_to(name)
    shell = make_shell(SHELL_ID, "Shell", [main, other])
    return Linked(
        store=make_store(shell, main, other, concept),
        shell=shell,
        main=main,
        other=other,
        concept=concept,
        name=name,
        group=group,
        inner=inner,
        items=items,
        second_item=second_item,
        link=link,
        list_link=list_link,
        concept_link=concept_link,
        relationship=relationship,
        pointer=pointer,
    )


def _reference_element(id_short: str) -> model.ReferenceElement:
    return model.ReferenceElement(id_short=id_short)
