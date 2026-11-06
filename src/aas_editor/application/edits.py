"""The commands for the edits of the editor, addressed by AAS objects (D9).

Every command holds the BaSyx objects it changes, never a row or an index of a
view, and reports what it did to the `ModelChangeObserver` of the package. In
`apply` and in `revert` alike, so every view that shows the objects follows,
whether the user edited, undid, or redid.

A command that removes a member remembers its position, and its `revert` puts
it back there. A set has no position, and a mapping member is a pair of key
and value. See `aas_editor.domain.containers`.

Example:
    Deleting an element, then taking it back::

        stack.push(RemoveMember(observer, submodel.submodel_element, element))
        stack.undo()
"""

from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import MutableMapping
import io
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.application.changes import Change
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack
from aas_editor.domain import containers
from aas_editor.domain import ordering
from aas_editor.domain import typed_values


def describe(obj: object) -> str:
    """Returns a short name of an object for a description of a step."""
    if isinstance(obj, tuple):
        pair = cast("tuple[Any, ...]", obj)
        if len(pair) == 2:
            return str(pair[0])
        return "entry"
    id_short = getattr(obj, "id_short", None)
    if isinstance(id_short, str) and id_short:
        return id_short
    return type(obj).__name__


def _is_mapping_member_change(container: object) -> bool:
    return isinstance(container, MutableMapping)


def _member_added(
    container: object, member: object, position: int | None
) -> Change:
    if _is_mapping_member_change(container):
        return Change.changed(container)
    return Change.added(container, member, position)


def _member_removed(
    container: object, member: object, position: int | None
) -> Change:
    if _is_mapping_member_change(container):
        return Change.changed(container)
    return Change.removed(container, member, position)


class SetAttribute(Command):
    """Sets one attribute of an object, such as a category or an idShort.

    An idShort is renamed in place, so the element keeps its position (D19).
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        owner: object,
        name: str,
        value: object,
        description: str | None = None,
        origin: object | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            owner: The object that has the attribute.
            name: The name of the attribute.
            value: The new value.
            description: Text for Undo and Redo. Defaults to the attribute.
            origin: The subscriber that updates itself when it pushes the
                command. Only the first report names it; later ones, from
                undo and redo, are for everyone.
        """
        self.description = description or f"Edit {name} of {describe(owner)}"
        self._observer = observer
        self._owner = owner
        self._name = name
        self._value = value
        self._previous: object = None
        self._origin = origin

    @property
    def owner(self) -> object:
        """The object that has the attribute."""
        return self._owner

    @property
    def name(self) -> str:
        """The name of the attribute."""
        return self._name

    @property
    def is_noop(self) -> bool:
        """Whether the attribute has the new value already."""
        current = getattr(self._owner, self._name)
        return type(current) is type(self._value) and bool(
            current == self._value
        )

    def apply(self) -> None:
        """Sets the new value."""
        previous = getattr(self._owner, self._name)
        self._assign(self._value)
        self._previous = previous
        origin, self._origin = self._origin, None
        self._observer.notify(Change.changed(self._owner, origin))

    def revert(self) -> None:
        """Sets the previous value again."""
        self._assign(self._previous)
        self._observer.notify(Change.changed(self._owner))

    def _assign(self, value: object) -> None:
        if self._name == "id_short" and isinstance(
            self._owner, model.Referable
        ):
            ordering.set_id_short(self._owner, value)  # pyright: ignore[reportArgumentType]
        else:
            setattr(self._owner, self._name, value)


class SetValueType(Command):
    """Changes the value type of an object, and its values with it.

    A Property, a Range, a Qualifier, and an Extension hold values of their
    value type. The values are converted through their text, in the same step
    as the type, so undo gives back the old type and the old values together.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        owner: object,
        value_type: Any,
        description: str | None = None,
        origin: object | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            owner: A Property, Range, Qualifier, or Extension.
            value_type: The new value type, a class of
                `basyx.aas.model.datatypes`.
            description: Text for Undo and Redo.
            origin: The subscriber that updates itself when it pushes the
                command. Only the first report names it.

        Raises:
            InvalidValueError: If a value does not fit the new type. Nothing
                has changed, and the message tells the user what to do.
        """
        self.description = description or (
            f"Change the value type of {describe(owner)}"
        )
        self._observer = observer
        self._owner: Any = owner
        self._value_type = value_type
        self._values = typed_values.type_change_values(owner, value_type)
        self._previous_type: Any = None
        self._previous_values: dict[str, Any] = {}
        self._origin = origin

    @property
    def owner(self) -> object:
        """The object that has the value type."""
        return self._owner

    @property
    def value_type(self) -> Any:
        """The value type that the command sets."""
        return self._value_type

    @property
    def value_names(self) -> tuple[str, ...]:
        """The names of the attributes whose values the command converts."""
        return tuple(self._values)

    @property
    def is_noop(self) -> bool:
        """Whether the owner has the new value type already."""
        return getattr(self._owner, "value_type", None) is self._value_type

    def apply(self) -> None:
        """Sets the new type and the converted values."""
        self._previous_type = self._owner.value_type
        self._previous_values = {
            name: getattr(self._owner, name) for name in self._values
        }
        self._owner.value_type = self._value_type
        for name, value in self._values.items():
            setattr(self._owner, name, value)
        origin, self._origin = self._origin, None
        self._observer.notify(Change.changed(self._owner, origin))

    def revert(self) -> None:
        """Sets the old type and the old values again."""
        self._owner.value_type = self._previous_type
        for name, value in self._previous_values.items():
            setattr(self._owner, name, value)
        self._observer.notify(Change.changed(self._owner))


class AddMember(Command):
    """Adds an object to a container, at a position where there is an order."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        container: object,
        member: object,
        index: int | None = None,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            container: A `NamespaceSet`, list, set, or mapping.
            member: What to add. For a mapping, a pair of key and value.
            index: The wanted position. None appends.
            description: Text for Undo and Redo.
        """
        self.description = description or f"Add {describe(member)}"
        self._observer = observer
        self._container = container
        self._member = member
        self._index = index

    def apply(self) -> None:
        """Adds the member, again at the position it had the first time."""
        position = containers.add_member(
            self._container, self._member, self._index
        )
        self._index = position
        self._observer.notify(
            _member_added(self._container, self._member, position)
        )

    def revert(self) -> None:
        """Removes the member."""
        position = containers.remove_member(self._container, self._member)
        self._observer.notify(
            _member_removed(self._container, self._member, position)
        )


class RemoveMember(Command):
    """Removes an object from a container, and puts it back where it was."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        container: object,
        member: object,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            container: A `NamespaceSet`, list, set, or mapping.
            member: What to remove. For a mapping, a pair of key and value.
            description: Text for Undo and Redo.
        """
        self.description = description or f"Delete {describe(member)}"
        self._observer = observer
        self._container = container
        self._member = member
        self._position: int | None = None

    def apply(self) -> None:
        """Removes the member and remembers its position."""
        self._position = containers.remove_member(self._container, self._member)
        self._observer.notify(
            _member_removed(self._container, self._member, self._position)
        )

    def revert(self) -> None:
        """Adds the member at the position it had."""
        containers.add_member(self._container, self._member, self._position)
        self._observer.notify(
            _member_added(self._container, self._member, self._position)
        )


class ReplaceMember(Command):
    """Swaps a member of a container for another object in place."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        container: object,
        old: object,
        new: object,
        description: str | None = None,
        origin: object | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            container: A `NamespaceSet`, list, set, or mapping.
            old: The member to replace. For a mapping, a pair.
            new: The object that takes its place. For a mapping, a pair.
            description: Text for Undo and Redo.
            origin: The subscriber that updates itself when it pushes the
                command. Only the first report names it.
        """
        self.description = description or f"Edit {describe(old)}"
        self._observer = observer
        self._container = container
        self._old = old
        self._new = new
        self._origin = origin

    @property
    def new(self) -> object:
        """The object that takes the place of the old one."""
        return self._new

    def apply(self) -> None:
        """Puts the new object in the place of the old one."""
        containers.replace_member(self._container, self._old, self._new)
        origin, self._origin = self._origin, None
        self._observer.notify(Change.changed(self._container, origin))

    def revert(self) -> None:
        """Puts the old object back."""
        containers.replace_member(self._container, self._new, self._old)
        self._observer.notify(Change.changed(self._container))


class AddSupplementaryFile(Command):
    """Stores a file in the package, and removes it again on undo."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        file_store: AbstractSupplementaryFileContainer,
        name: str,
        data: bytes,
        content_type: str,
        shown: object,
        on_stored: Callable[[str | None], None],
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            file_store: The files of the package.
            name: The wanted part name. The store may choose another one if it
                is taken.
            data: The content.
            content_type: The media type of the content.
            shown: The object that views show for the file.
            on_stored: Called with the name the store chose after each add,
                and with None after each revert, so the object that views
                show follows the store.
            description: Text for Undo and Redo.
        """
        self.description = description or f"Add file {name}"
        self._observer = observer
        self._file_store = file_store
        self._name = name
        self._data = data
        self._content_type = content_type
        self._shown = shown
        self._on_stored = on_stored
        self._stored_name: str | None = None

    def apply(self) -> None:
        """Adds the file to the store."""
        self._stored_name = self._file_store.add_file(
            self._name, io.BytesIO(self._data), self._content_type
        )
        self._on_stored(self._stored_name)
        self._observer.notify(Change.added(self._file_store, self._shown))

    def revert(self) -> None:
        """Deletes the file from the store."""
        if self._stored_name is not None:
            self._file_store.delete_file(self._stored_name)
        self._on_stored(None)
        self._observer.notify(Change.removed(self._file_store, self._shown))


def _reference_to(submodel: model.Submodel) -> "model.ModelReference[Any]":
    return cast(
        "model.ModelReference[Any]",
        model.ModelReference.from_referable(submodel),  # pyright: ignore[reportUnknownMemberType]
    )


def link_submodels(
    stack: CommandStack,
    observer: ModelChangeObserver,
    shell: model.AssetAdministrationShell,
    submodels: Iterable[model.Submodel],
) -> int:
    """Adds a reference to each Submodel that the shell does not refer to.

    All references are one step: a single Undo takes them all back.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        shell: The shell to add the references to.
        submodels: The Submodels to refer to.

    Returns:
        The number of references that were added.
    """
    missing: list[model.ModelReference[Any]] = []
    for submodel in submodels:
        reference = _reference_to(submodel)
        if reference not in shell.submodel:
            missing.append(reference)
    if not missing:
        return 0
    with stack.group("Link Submodels to the AAS"):
        for reference in missing:
            stack.push(
                AddMember(
                    observer,
                    shell.submodel,
                    reference,
                    description=f"Link {describe(shell)}",
                )
            )
    return len(missing)
