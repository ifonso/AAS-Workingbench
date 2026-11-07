"""A small, Qt-free list of callbacks, shared by the observer and the stack."""

from collections.abc import Callable
import inspect
import itertools
import logging
from typing import cast
from typing import Generic
from typing import ParamSpec
import weakref

_P = ParamSpec("_P")

_logger = logging.getLogger(__name__)


def _resolver(
    listener: Callable[_P, None],
) -> Callable[[], Callable[_P, None] | None]:
    """Returns a function that gives the callback back, or None once gone."""
    if inspect.ismethod(listener):
        return cast(
            "Callable[[], Callable[_P, None] | None]",
            weakref.WeakMethod(listener),
        )
    return lambda: listener


class Subscription:
    """The handle of one registered callback."""

    def __init__(self, cancel: Callable[[], None]) -> None:
        self._cancel = cancel

    def cancel(self) -> None:
        """Stops the callbacks. Calling it again does nothing."""
        self._cancel()


class Listeners(Generic[_P]):
    """Callbacks that are called together with the same arguments.

    A bound method is held weakly, so a view or model that subscribes with one
    of its methods does not stay alive just because of the subscription. It is
    dropped once its object is gone. Any other callable is held strongly, and
    stays registered until it is cancelled.

    One failing callback does not stop the others. The failure is logged,
    because the change that caused the call has happened already, and every
    other view still has to learn about it.
    """

    def __init__(self) -> None:
        self._entries: dict[int, Callable[[], Callable[_P, None] | None]] = {}
        self._ids = itertools.count()

    def subscribe(self, listener: Callable[_P, None]) -> Subscription:
        """Registers a callback.

        Args:
            listener: What to call. A bound method is held weakly.

        Returns:
            A handle that unregisters the callback.
        """
        key = next(self._ids)
        self._entries[key] = _resolver(listener)

        def cancel() -> None:
            self._entries.pop(key, None)

        return Subscription(cancel)

    def notify(self, *args: _P.args, **kwargs: _P.kwargs) -> None:
        """Calls every live callback in the order they were registered."""
        for key, resolve in list(self._entries.items()):
            listener = resolve()
            if listener is None:
                self._entries.pop(key, None)
                continue
            try:
                listener(*args, **kwargs)
            except Exception:
                _logger.exception("Listener failed: %r", listener)

    def __len__(self) -> int:
        return sum(1 for resolve in self._entries.values() if resolve())
