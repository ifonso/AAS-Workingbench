"""What replacing a submodel element by a new one would do, and what it loses.

Two features replace an element by a newly built one: the conversion to
another element type (`aas_workingbench.domain.conversion`) and the rebuild of a
list with other settings (`aas_workingbench.domain.list_settings`). The SDK offers
no way to change the class of an element, or what a list fixes, so both build
a new element through the constructor of the SDK and swap it in place.

A plan is found without changing anything. It lists everything that the new
element does not have: the editor shows that list and asks before it goes on,
so nothing is lost silently (see ADR 0012). It also tells where the items of
the element went, because a reference to an item names it by its idShort or
its position.
"""

from collections.abc import Callable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field

from basyx.aas import model


class ConversionRefused(ValueError):
    """A replacement that cannot be made, with a message for the user."""


@dataclass(frozen=True)
class Loss:
    """One thing the new element does not have.

    Attributes:
        what: Which attribute or part, such as `maximum` or `item`.
        detail: Its value or name, written for the user.
    """

    what: str
    detail: str

    def __str__(self) -> str:
        """Returns the loss as one line."""
        return f"{self.what}: {self.detail}"


@dataclass(frozen=True, eq=False)
class Outcome:
    """The new element and what came with it.

    Attributes:
        element: The new element, with no parent.
        losses: What the new element does not have.
        notes: Values the new element got that the user did not set, such as
            the language of a text. They are not losses.
        child_keys: Where the direct items of the old element went, by the
            key a reference uses for them: the idShort, or the position in a
            list. The value is the key in the new element, or None if the
            item is gone. An item that is not listed has the same key.
    """

    element: model.SubmodelElement
    losses: tuple[Loss, ...] = ()
    notes: tuple[str, ...] = ()
    child_keys: Mapping[str, str | None] = field(default_factory=lambda: {})


@dataclass(frozen=True, eq=False)
class ReplacementPlan:
    """A new element for an old one, found without changing anything.

    Attributes:
        source: The element that is replaced. It is not changed.
        target_type: The class of the new element.
        preview: The new element as it would be now.
        losses: What the new element does not have.
        notes: Values the new element got that the user did not set.
        child_keys: Where the direct items of the old element went, see
            `Outcome`.
        description: Text for Undo and Redo.
    """

    source: model.SubmodelElement
    target_type: type[model.SubmodelElement]
    preview: model.SubmodelElement
    losses: tuple[Loss, ...]
    notes: tuple[str, ...]
    child_keys: Mapping[str, str | None]
    description: str
    _builder: Callable[[], Outcome] = field(repr=False)

    @property
    def has_losses(self) -> bool:
        """Whether the new element lacks something the old one has."""
        return bool(self.losses)

    def build(self) -> model.SubmodelElement:
        """Builds the new element again, from the source as it is now.

        The command calls this when it is applied, after the references
        inside the source were updated, so that the copies of the items carry
        the updated references.
        """
        return self._builder().element
