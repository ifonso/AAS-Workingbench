"""The global switch between editing and reading (decision D18).

The editor starts in Edit mode. In Read mode no package can be changed: the
command stacks refuse every push, undo, and redo, and the views disable their
editing actions. One switch serves all open packages, so a user who only wants
to look at a package cannot change it by accident.
"""

from collections.abc import Callable

from aas_workingbench.application.listeners import Listeners
from aas_workingbench.application.listeners import Subscription


class EditMode:
    """Tells whether packages may be changed, and who wants to know."""

    def __init__(self) -> None:
        self._editing = True
        self._listeners: Listeners[[bool]] = Listeners()

    @property
    def is_editing(self) -> bool:
        """True in Edit mode, False in Read mode."""
        return self._editing

    def set_editing(self, editing: bool) -> None:
        """Switches the mode and tells the subscribers if it changed.

        Args:
            editing: True for Edit mode, False for Read mode.
        """
        if editing == self._editing:
            return
        self._editing = editing
        self._listeners.notify(editing)

    def subscribe(self, listener: Callable[[bool], None]) -> Subscription:
        """Registers a callback for every change of the mode.

        Args:
            listener: Called with the new value of `is_editing`. A bound
                method is held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)


_edit_mode = EditMode()


def edit_mode() -> EditMode:
    """Returns the one switch of the application."""
    return _edit_mode
