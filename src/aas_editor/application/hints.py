"""The global switch for hints (F-EDT-06).

In hints mode the editor shows advice next to the object that it is about, and
under the fields of the dialogs that make one. The advice comes from the
validation rules and the hint rules, and it never blocks anything: a value that
a hint complains about stays in the model and can be saved. The mode is on at
first, as in Package Explorer.
"""

from collections.abc import Callable

from aas_editor.application.listeners import Listeners
from aas_editor.application.listeners import Subscription


class HintsMode:
    """Tells whether hints are shown, and who wants to know."""

    def __init__(self) -> None:
        self._on = True
        self._listeners: Listeners[[bool]] = Listeners()

    @property
    def is_on(self) -> bool:
        """True if hints are shown."""
        return self._on

    def set_on(self, on: bool) -> None:
        """Switches hints on or off, and tells the subscribers if it changed.

        Args:
            on: True to show hints.
        """
        if on == self._on:
            return
        self._on = on
        self._listeners.notify(on)

    def subscribe(self, listener: Callable[[bool], None]) -> Subscription:
        """Registers a callback for every change of the mode.

        Args:
            listener: Called with the new value of `is_on`. A bound method is
                held weakly.

        Returns:
            A handle that stops the callbacks.
        """
        return self._listeners.subscribe(listener)


_hints_mode = HintsMode()


def hints_mode() -> HintsMode:
    """Returns the one switch of the application."""
    return _hints_mode
