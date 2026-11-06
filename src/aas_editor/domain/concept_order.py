"""The order in which a view lists concept descriptions (decision D16).

The SDK keeps concept descriptions in a set. Their order is not saved and
changes from run to run, so the original's `Static order` cannot exist here
and a description cannot be moved. What a user can choose is how the *view*
lists them, and this module defines the choices:

- **Name**, the default: the text the tree shows, which is the idShort. The
  comparison ignores case, so `alpha` is not listed after `Zeta`. Descriptions
  with the same name, such as those without an idShort, which the tree shows by
  their class, are listed by id. Without that tie-break their order would be
  the order of the set, which changes between runs.
- **idShort**: like Name, but a description without an idShort comes last.
- **Id**: by the id, ignoring case.
- **First use**: in the order in which submodels first use them, as the
  original's `By AasSubmodel`. The submodels are taken by idShort, because the
  shell keeps its references in a set. The elements follow in their saved
  order. Descriptions that nothing uses come last, by name.

Example:
    Sorting descriptions by the order of their first use::

        ranks = first_use_ranks(package.objStore)
        ordered = sorted(
            concepts, key=lambda c: sort_key(ConceptOrder.FIRST_USE, c, ranks)
        )
"""

from collections.abc import Iterable
from collections.abc import Mapping
import enum

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.domain.concepts import holders_of


class ConceptOrder(enum.Enum):
    """How a view lists concept descriptions."""

    NAME = "name"
    ID_SHORT = "id_short"
    ID = "id"
    FIRST_USE = "first_use"

    @property
    def label(self) -> str:
        """The text for the user."""
        return {
            ConceptOrder.NAME: "Name (as shown)",
            ConceptOrder.ID_SHORT: "idShort",
            ConceptOrder.ID: "Id",
            ConceptOrder.FIRST_USE: "First use in the submodels",
        }[self]


SortKey = tuple[int, str, str, str]


def first_use_ranks(objects: Iterable[model.Identifiable]) -> dict[str, int]:
    """Numbers the descriptions in the order in which submodels first use them.

    Args:
        objects: The identifiables of the package.

    Returns:
        For the id of each description that a semantic id or a supplemental
        semantic id names, the rank of its first use, counting from 0.
    """
    all_objects = list(objects)
    concept_ids = {
        o.id for o in all_objects if isinstance(o, ConceptDescription)
    }
    submodels = sorted(
        (o for o in all_objects if isinstance(o, model.Submodel)),
        key=lambda s: ((s.id_short or "").lower(), s.id),
    )
    ranks: dict[str, int] = {}
    for submodel in submodels:
        for holder in holders_of([submodel]):
            references = [holder.reference] if holder.reference else []
            references.extend(
                getattr(holder.owner, "supplemental_semantic_id", ())
            )
            for reference in references:
                for key in reference.key:
                    if key.value in concept_ids and key.value not in ranks:
                        ranks[key.value] = len(ranks)
    return ranks


def sort_key(
    order: ConceptOrder,
    concept: ConceptDescription,
    ranks: Mapping[str, int] | None = None,
) -> SortKey:
    """Returns the key that lists a description in an order.

    Args:
        order: The order the view uses.
        concept: The description.
        ranks: For `FIRST_USE`, what `first_use_ranks` made.

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
    if order is ConceptOrder.FIRST_USE:
        rank = (ranks or {}).get(concept.id)
        if rank is None:
            return (1, shown, identifier, concept.id)
        return (0, f"{rank:012d}", identifier, concept.id)
    return (0, shown, identifier, concept.id)
