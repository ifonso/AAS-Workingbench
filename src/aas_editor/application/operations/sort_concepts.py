"""Sorting the concept descriptions of a package for good (F-EDT-05 AC11, AC12).

A view order (`aas_editor.domain.concept_order`) changes what a tree shows. A
permanent sort changes the order of the store, which is the order that a save
writes. It is `Sort according above order` of Package Explorer, and unlike
there, one undo step brings the old order back.

Only the orders that put each description in a place of its own can sort (see
`can_sort_permanently`). The others give `CANNOT_SORT`, as in the original.
The shells and submodels keep the places that they have in the store, and the
descriptions take the places of the descriptions, sorted.

Example:
    Sorting by idShort::

        plan = plan_sort(package.objStore, ConceptOrder.ID_SHORT)
        stack.push(sort_command(observer, package.objStore, plan))
"""

from collections.abc import Iterable
from dataclasses import dataclass

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import ReorderMembers
from aas_editor.domain.concept_order import CANNOT_SORT
from aas_editor.domain.concept_order import ConceptOrder
from aas_editor.domain.concept_order import can_sort_permanently
from aas_editor.domain.concept_order import ranks_for
from aas_editor.domain.concept_order import sort_key
from aas_editor.domain.ordered_store import OrderedIdentifiableStore

NOTHING_TO_SORT = "The package has no concept descriptions to sort"
"""The log text of Package Explorer for an empty package."""


class SortRefused(ValueError):
    """The order cannot be applied for good. The message is for the user."""


@dataclass(frozen=True, eq=False)
class SortPlan:
    """What a permanent sort would do.

    Attributes:
        order: The order that sorts.
        new_order: Every object of the store in the order it would have.
        changes: Whether the store has another order now.
    """

    order: ConceptOrder
    new_order: tuple[model.Identifiable, ...]
    changes: bool


def plan_sort(
    store: Iterable[model.Identifiable], order: ConceptOrder
) -> SortPlan:
    """Plans sorting the descriptions of a store.

    Args:
        store: The identifiables of the package, in the order of its store.
        order: The order to sort by.

    Returns:
        The plan. Nothing changes.

    Raises:
        SortRefused: If the order cannot be applied for good (`CANNOT_SORT`),
            or the store holds no description (`NOTHING_TO_SORT`).
    """
    held = list(store)
    concepts = [o for o in held if isinstance(o, ConceptDescription)]
    if not can_sort_permanently(order):
        raise SortRefused(CANNOT_SORT)
    if not concepts:
        raise SortRefused(NOTHING_TO_SORT)
    ranks = ranks_for(order, held)
    ordered = iter(sorted(concepts, key=lambda c: sort_key(order, c, ranks)))
    new_order = tuple(
        next(ordered) if isinstance(o, ConceptDescription) else o for o in held
    )
    changes = any(a is not b for a, b in zip(held, new_order, strict=True))
    return SortPlan(order, new_order, changes)


def sort_command(
    observer: ModelChangeObserver,
    store: OrderedIdentifiableStore,
    plan: SortPlan,
) -> Command:
    """Builds the command that gives the store the order of a plan.

    Args:
        observer: Where the command reports.
        store: The store of the package.
        plan: What `plan_sort` made.

    Returns:
        One command. Undo puts the old order back.
    """
    return ReorderMembers(
        observer,
        store,
        plan.new_order,
        description=f"Sort concept descriptions by {plan.order.label}",
    )
