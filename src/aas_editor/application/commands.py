"""Undoable edits, in one history for each package (decision D9).

A `Command` holds the BaSyx objects it changes, not rows or indexes of a view.
Each open tab has its own item model, so a row number or a persistent model
index means nothing to another tab. Objects are the same in all of them.

A command also reports what it did to a `ModelChangeObserver`, in `apply` and
in `revert`, so every view updates itself. Position matters: a command that
removes an object remembers where it was, and its `revert` puts it back there
with `aas_editor.domain.ordering`.

Example:
    A command that adds an element at a position::

        class AddElement(Command):
            def __init__(self, observer, submodel, element, index):
                self.description = f"Add {element.id_short}"
                self._observer = observer
                self._elements = submodel.submodel_element
                self._element = element
                self._index = index

            def apply(self):
                ordering.insert_at(self._elements, self._element, self._index)
                self._observer.notify(
                    Change.added(self._elements, self._element, self._index)
                )

            def revert(self):
                self._elements.remove(self._element)
                self._observer.notify(
                    Change.removed(self._elements, self._element, self._index)
                )


        stack.push(AddElement(observer, submodel, element, 0))
        stack.undo()
"""

import abc
from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Sequence
import contextlib

from aas_editor.application.listeners import Listeners
from aas_editor.application.listeners import Subscription


class Command(abc.ABC):
    """One edit that can be applied again and taken back.

    Attributes:
        description: A short text for the Undo and Redo actions, such as
            "Rename Pump".
    """

    description: str

    @abc.abstractmethod
    def apply(self) -> None:
        """Makes the edit, and reports it to the observer.

        It is called for the first time when the command is pushed, and again
        by every redo. If it raises, it must have changed nothing.
        """

    @abc.abstractmethod
    def revert(self) -> None:
        """Takes the edit back, and reports that to the observer.

        It only runs after `apply` succeeded, and puts every object back where
        it was, including its position.
        """


class CommandGroup(Command):
    """Several commands that are undone and redone as one step.

    A cascade, such as deleting an element together with the references that
    point to it, is one group, so that a single Undo brings everything back.
    """

    def __init__(
        self, description: str, commands: Sequence[Command] = ()
    ) -> None:
        self.description = description
        self._commands = list(commands)

    @property
    def commands(self) -> tuple[Command, ...]:
        """The commands of the group, in the order they were applied."""
        return tuple(self._commands)

    def append(self, command: Command) -> None:
        """Adds a command that was applied already."""
        self._commands.append(command)

    def apply(self) -> None:
        """Applies every command in order, or none of them if one raises."""
        applied: list[Command] = []
        try:
            for command in self._commands:
                command.apply()
                applied.append(command)
        except Exception:
            _revert_all(applied)
            raise

    def revert(self) -> None:
        """Reverts every command, last one first."""
        _revert_all(self._commands)


def _revert_all(commands: Sequence[Command]) -> None:
    for command in reversed(commands):
        command.revert()


class CommandStack:
    """The undo history of one package, with a marker for the saved state.

    Attributes:
        limit: The most steps kept. The oldest are dropped first.
    """

    def __init__(self, limit: int = 100) -> None:
        if limit < 1:
            raise ValueError(f"Limit must be at least 1: {limit}")
        self.limit = limit
        self._done: list[Command] = []
        self._undone: list[Command] = []
        self._open_groups: list[CommandGroup] = []
        # The number of done steps when the package was saved. None when that
        # state can no longer be reached by undo and redo.
        self._saved_depth: int | None = 0
        self._listeners: Listeners[[]] = Listeners()

    def push(self, command: Command) -> None:
        """Applies a command and records it as the newest step.

        Inside `group`, the command becomes part of the open group instead.
        Recording a step discards everything that could be redone.

        Args:
            command: The edit to make.

        Raises:
            Exception: Whatever `command.apply` raises. Nothing is recorded.
        """
        command.apply()
        if self._open_groups:
            self._open_groups[-1].append(command)
            return
        self._record(command)

    @contextlib.contextmanager
    def group(self, description: str) -> Generator[None]:
        """Collects the commands pushed inside the block into one step.

        The commands are applied as they are pushed. If the block raises, the
        commands pushed so far are reverted, last one first, and nothing is
        recorded. Groups can be nested. An inner group is one command of the
        outer one. A group without commands records nothing.

        Args:
            description: The text for the Undo and Redo actions.

        Yields:
            Nothing. Call `push` inside the block.
        """
        group = CommandGroup(description)
        self._open_groups.append(group)
        try:
            yield
        except BaseException:
            self._open_groups.pop()
            _revert_all(group.commands)
            raise
        self._open_groups.pop()
        if not group.commands:
            return
        if self._open_groups:
            self._open_groups[-1].append(group)
        else:
            self._record(group)

    @property
    def can_undo(self) -> bool:
        """Whether there is a step to take back."""
        return bool(self._done) and not self._open_groups

    @property
    def can_redo(self) -> bool:
        """Whether there is a step to apply again."""
        return bool(self._undone) and not self._open_groups

    @property
    def undo_description(self) -> str:
        """The description of the step that Undo takes back, or empty."""
        return self._done[-1].description if self._done else ""

    @property
    def redo_description(self) -> str:
        """The description of the step that Redo applies, or empty."""
        return self._undone[-1].description if self._undone else ""

    def undo(self) -> None:
        """Takes back the newest step.

        Raises:
            RuntimeError: If there is nothing to undo, or a group is open.
            Exception: Whatever `revert` raises. The step stays recorded.
        """
        if not self.can_undo:
            raise RuntimeError("Nothing to undo")
        self._done[-1].revert()
        self._undone.append(self._done.pop())
        self._listeners.notify()

    def redo(self) -> None:
        """Applies the step that was taken back last.

        Raises:
            RuntimeError: If there is nothing to redo, or a group is open.
            Exception: Whatever `apply` raises. The step stays undone.
        """
        if not self.can_redo:
            raise RuntimeError("Nothing to redo")
        self._undone[-1].apply()
        self._done.append(self._undone.pop())
        self._listeners.notify()

    def mark_saved(self) -> None:
        """Remembers the current state as the one that is saved on disk.

        Raises:
            RuntimeError: If a group is open.
        """
        if self._open_groups:
            raise RuntimeError("Cannot mark the state as saved inside a group")
        self._saved_depth = len(self._done)
        self._listeners.notify()

    @property
    def is_clean(self) -> bool:
        """Whether the current state is the saved one."""
        return not self._open_groups and self._saved_depth == len(self._done)

    def clear(self) -> None:
        """Forgets all steps. The current state stays as it is.

        Raises:
            RuntimeError: If a group is open.
        """
        if self._open_groups:
            raise RuntimeError("Cannot clear the history inside a group")
        was_clean = self.is_clean
        self._done.clear()
        self._undone.clear()
        self._saved_depth = 0 if was_clean else None
        self._listeners.notify()

    def subscribe(self, listener: Callable[[], None]) -> Subscription:
        """Registers a callback for every change of the history or the marker.

        A view uses it to enable the Undo and Redo actions and to show the
        modified state of the package.

        Args:
            listener: Called without arguments. A bound method is held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)

    def _record(self, step: Command) -> None:
        if self._saved_depth is not None and self._saved_depth > len(
            self._done
        ):
            # The saved state was in the part that can no longer be redone.
            self._saved_depth = None
        self._undone.clear()
        self._done.append(step)
        if len(self._done) > self.limit:
            del self._done[0]
            if self._saved_depth is not None:
                self._saved_depth -= 1
                if self._saved_depth < 0:
                    self._saved_depth = None
        self._listeners.notify()
