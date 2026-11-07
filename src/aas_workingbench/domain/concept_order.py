"""The order in which a view lists concept descriptions (decision D16, ADR 0021).

A view lists the descriptions of a package in one of these orders. Choosing one
changes the view only. `domain.concepts` and the store keep the package as it
was, and `can_sort_permanently` says which of the orders a permanent sort can
use.

- **Name**, the default: the text the tree shows, which is the idShort. The
  comparison ignores case, so `alpha` is not listed after `Zeta`. Descriptions
  with the same name, such as those without an idShort, which the tree shows by
  their class, are listed by id. Without that tie-break their order would be
  the order of the set, which changes between runs.
- **List index**: the order of the store of the package, which is the order of
  the file when it was read, followed by the descriptions added since. Unlike
  the others it is the order that a save writes (ADR 0021).
- **idShort**: like Name, but a description without an idShort comes last.
- **Id**: by the id, ignoring case.
- **First use**: in the order in which submodels first use them, as the
  original's `By AasSubmodel`. The submodels are taken by idShort, because the
  shell keeps its references in a set. The elements follow in their saved
  order. Descriptions that nothing uses come last, by name.
- **By submodel elements**: like First use, but only the semantic ids of
  elements count. A description that only a submodel uses comes last.
- **Structured**: the descriptions of SAMM elements that an Aspect reaches come
  first, from each Aspect down its links; then those that submodels use, in the
  order of first use; then the rest, by name. The original shows these three
  as branches of the tree. This view lists them in one row of descriptions.

Example:
    Sorting descriptions by the order of their first use::

        ranks = ranks_for(ConceptOrder.FIRST_USE, package.objStore)
        ordered = sorted(
            concepts, key=lambda c: sort_key(ConceptOrder.FIRST_USE, c, ranks)
        )
"""

from collections.abc import Iterable
from collections.abc import Mapping
import enum

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_workingbench.domain.concepts import holders_of
from aas_workingbench.domain.samm import samm_element_of
from aas_workingbench.domain.samm import samm_links


class ConceptOrder(enum.Enum):
    """How a view lists concept descriptions."""

    NAME = "name"
    LIST_INDEX = "list_index"
    ID_SHORT = "id_short"
    ID = "id"
    FIRST_USE = "first_use"
    BY_ELEMENTS = "by_elements"
    STRUCTURED = "structured"

    @property
    def label(self) -> str:
        """The text for the user."""
        return {
            ConceptOrder.NAME: "Name (as shown)",
            ConceptOrder.LIST_INDEX: "List index (the order of the file)",
            ConceptOrder.ID_SHORT: "idShort",
            ConceptOrder.ID: "Id",
            ConceptOrder.FIRST_USE: "First use in the submodels",
            ConceptOrder.BY_ELEMENTS: "By submodel elements",
            ConceptOrder.STRUCTURED: "Structured (SAMM, submodels, others)",
        }[self]


SortKey = tuple[int, str, str, str]

# What a permanent sort of the store can use: the orders that put every
# description in a place of their own. The order of the file, the elements,
# and the structure are views of something the store has no say in.
_SORTABLE = frozenset(
    {
        ConceptOrder.NAME,
        ConceptOrder.ID_SHORT,
        ConceptOrder.ID,
        ConceptOrder.FIRST_USE,
    }
)

CANNOT_SORT = "The file cannot keep this order, so nothing was sorted"
"""The text of Package Explorer for an order that cannot be applied."""


def can_sort_permanently(order: ConceptOrder) -> bool:
    """Tells whether a permanent sort can use an order.

    Args:
        order: The order of the view.

    Returns:
        False for the list index, which is the order that a sort would
        change, and for the orders by elements and by structure, which group
        descriptions by what uses them, and so cannot name one order of the
        store. These are the three that Package Explorer refuses with
        `CANNOT_SORT`.
    """
    return order in _SORTABLE


def _concept_ids(objects: Iterable[model.Identifiable]) -> list[str]:
    return [o.id for o in objects if isinstance(o, ConceptDescription)]


def _submodels(
    objects: Iterable[model.Identifiable],
) -> list[model.Submodel]:
    return sorted(
        (o for o in objects if isinstance(o, model.Submodel)),
        key=lambda s: ((s.id_short or "").lower(), s.id),
    )


def first_use_ranks(
    objects: Iterable[model.Identifiable], elements_only: bool = False
) -> dict[str, int]:
    """Numbers the descriptions in the order in which submodels first use them.

    Args:
        objects: The identifiables of the package.
        elements_only: Count the semantic ids of elements only, and not those
            of the submodels themselves.

    Returns:
        For the id of each description that a semantic id or a supplemental
        semantic id names, the rank of its first use, counting from 0.
    """
    all_objects = list(objects)
    concept_ids = set(_concept_ids(all_objects))
    ranks: dict[str, int] = {}
    for submodel in _submodels(all_objects):
        for holder in holders_of([submodel]):
            if elements_only and isinstance(holder.owner, model.Submodel):
                continue
            references = [holder.reference] if holder.reference else []
            references.extend(
                getattr(holder.owner, "supplemental_semantic_id", ())
            )
            for reference in references:
                for key in reference.key:
                    if key.value in concept_ids and key.value not in ranks:
                        ranks[key.value] = len(ranks)
    return ranks


def list_index_ranks(
    objects: Iterable[model.Identifiable],
) -> dict[str, int]:
    """Numbers the descriptions in the order of the store.

    Args:
        objects: The identifiables of the package, in the order of its store.

    Returns:
        The position of each description among the descriptions.
    """
    return {id_: number for number, id_ in enumerate(_concept_ids(objects))}


def structured_ranks(
    objects: Iterable[model.Identifiable],
) -> dict[str, int]:
    """Numbers the descriptions of the structured order.

    The descriptions of SAMM elements that an Aspect reaches come first. They
    follow the links of each Aspect, depth first, each description once. The
    Aspects are taken by idShort. Descriptions that submodels use come next, in
    the order of first use. Others get no rank and are listed last by name.

    Args:
        objects: The identifiables of the package.

    Returns:
        The rank of each description of the first two groups.
    """
    all_objects = list(objects)
    concepts = {
        o.id: o for o in all_objects if isinstance(o, ConceptDescription)
    }
    links = {
        id_: samm_links(element)
        for id_, concept in concepts.items()
        if (element := samm_element_of(concept)) is not None
    }
    aspects = sorted(
        (
            concept
            for concept in concepts.values()
            if (element := samm_element_of(concept)) is not None
            and element.type_name == "Aspect"
        ),
        key=lambda c: ((c.id_short or "").lower(), c.id),
    )
    ranks: dict[str, int] = {}

    def visit(id_: str) -> None:
        if id_ in ranks or id_ not in links:
            return
        ranks[id_] = len(ranks)
        for linked in links[id_]:
            visit(linked)

    for aspect in aspects:
        visit(aspect.id)
    for id_, _ in sorted(
        first_use_ranks(all_objects).items(), key=lambda item: item[1]
    ):
        if id_ not in ranks:
            ranks[id_] = len(ranks)
    return ranks


def ranks_for(
    order: ConceptOrder, objects: Iterable[model.Identifiable]
) -> dict[str, int] | None:
    """Works out the ranks that an order needs.

    Args:
        order: The order of the view.
        objects: The identifiables of the package, in the order of its store.

    Returns:
        The rank of each description for the orders that use ranks, or None
        for the orders that compare the descriptions themselves.
    """
    if order is ConceptOrder.LIST_INDEX:
        return list_index_ranks(objects)
    if order is ConceptOrder.FIRST_USE:
        return first_use_ranks(objects)
    if order is ConceptOrder.BY_ELEMENTS:
        return first_use_ranks(objects, elements_only=True)
    if order is ConceptOrder.STRUCTURED:
        return structured_ranks(objects)
    return None


def sort_key(
    order: ConceptOrder,
    concept: ConceptDescription,
    ranks: Mapping[str, int] | None = None,
) -> SortKey:
    """Returns the key that lists a description in an order.

    Args:
        order: The order the view uses.
        concept: The description.
        ranks: For the orders that use ranks, what `ranks_for` made.

    Returns:
        A tuple to compare. It differs between two descriptions with
        different ids, so a sort is the same on every run.
    """
    name = (concept.id_short or "").lower()
    shown = name or "conceptdescription"
    identifier = concept.id.lower()
    if order is ConceptOrder.ID:
        return (0, identifier, "", concept.id)
    if order is ConceptOrder.ID_SHORT:
        return (0 if name else 1, name, identifier, concept.id)
    if order in (
        ConceptOrder.FIRST_USE,
        ConceptOrder.BY_ELEMENTS,
        ConceptOrder.STRUCTURED,
        ConceptOrder.LIST_INDEX,
    ):
        rank = (ranks or {}).get(concept.id)
        if rank is None:
            return (1, shown, identifier, concept.id)
        return (0, f"{rank:012d}", identifier, concept.id)
    return (0, shown, identifier, concept.id)
