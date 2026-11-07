"""The validation report of a package, kept up to date for the views that show it.

The validation dock and the hints of the tabs read the same report, so one
service for each package runs the rules, no matter how many views listen. A run
takes about 45 ms for the largest bundled template. It runs in the thread of the
UI, because the rules read the same BaSyx objects that the user edits, and
moving it to another thread would mean reading them while they change.

Runs are debounced instead: every change of the package, and every step of its
history, only restarts a short timer. A burst of changes, such as a paste or a
bulk delete, is followed by one run. Nothing runs while no view listens.

The run is linear in the size of the package, so a very large package would
make the window stop for a moment after every burst of changes. The wait grows
with the cost of the last run, so that the rules never take more than about a
sixth of the time of the UI (ADR 0029).
"""

from typing import Protocol
import time
import weakref

from PyQt6 import sip
from PyQt6.QtCore import QObject
from PyQt6.QtCore import QTimer
from PyQt6.QtCore import pyqtSignal

from aas_workingbench.application.changes import Change
from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.listeners import Subscription
from aas_workingbench.application.validation import ValidationSource
from aas_workingbench.application.validation import package_findings
from aas_workingbench.application.validation import validate_package
from aas_workingbench.domain.validation import ValidationReport

# How long the service waits after the last change before it runs the rules.
DEBOUNCE_MS = 250
# The wait is at least this many times the cost of the last run. A run that
# takes 60 ms keeps the minimum, and one that takes 300 ms waits 1.5 s.
WAIT_PER_RUN = 5


class ValidatedPackage(Protocol):
    """What the service needs of a package: a source to read, and a history."""

    def save_source(self) -> ValidationSource:
        """The objects and files of the package as they are now."""
        ...


class ValidationService(QObject):
    """Runs the rules for one package when something listens and it changed.

    Attributes:
        report_changed: Emitted after each run. The new report is `report`.
    """

    report_changed = pyqtSignal()

    def __init__(
        self,
        package: ValidatedPackage,
        parent: QObject | None = None,
    ) -> None:
        """Starts following a package. Nothing runs until a view listens.

        Args:
            package: The package. It scopes the change observer and the
                command stack. The service keeps no strong reference to it.
            parent: The Qt parent.
        """
        super().__init__(parent)
        self._package = weakref.ref(package)
        self._report = ValidationReport()
        self._hint_report = ValidationReport()
        self._stale = True
        # The views that want the report, and whether each wants the hints.
        self._listeners: dict[int, bool] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(DEBOUNCE_MS)
        self._last_run_ms = 0.0
        self._timer.timeout.connect(self.refresh)
        self._subscriptions: tuple[Subscription, ...] = (
            observer_for(package).subscribe(self._on_change),
        )
        stack = getattr(package, "commandStack", None)
        if stack is not None:
            self._subscriptions += (stack.subscribe(self._on_history),)

    @property
    def report(self) -> ValidationReport:
        """The findings of the package check, from the last run."""
        return self._report

    @property
    def hint_report(self) -> ValidationReport:
        """The findings and hints, from the last run made with hints."""
        return self._hint_report

    @property
    def last_run_ms(self) -> float:
        """How long the last run took, in milliseconds."""
        return self._last_run_ms

    @property
    def wait_ms(self) -> int:
        """How long the service waits after a change before it runs."""
        return max(DEBOUNCE_MS, round(WAIT_PER_RUN * self._last_run_ms))

    @property
    def is_stale(self) -> bool:
        """Whether the package changed since the last run."""
        return self._stale

    @property
    def _with_hints(self) -> bool:
        return any(self._listeners.values())

    @property
    def is_listened_to(self) -> bool:
        """Whether a view wants the report."""
        return bool(self._listeners)

    def listen(self, owner: object, with_hints: bool = False) -> None:
        """Tells the service that a view wants the report.

        The first listener makes the service run if the report is out of date.

        Args:
            owner: The view. It is named by identity, so that the same view
                can listen again and stop once.
            with_hints: Whether the view also wants the hints of hints mode.
        """
        had_hints = self._with_hints
        self._listeners[id(owner)] = with_hints
        if self._stale or (self._with_hints and not had_hints):
            self.refresh()

    def stop_listening(self, owner: object) -> None:
        """Tells the service that a view no longer wants the report."""
        self._listeners.pop(id(owner), None)
        if not self._listeners:
            self._stop_timer()

    def refresh(self) -> None:
        """Runs the rules now, and tells the listeners."""
        self._stop_timer()
        if not self._listeners:
            return
        package = self._package()
        if package is None:
            return
        started = time.perf_counter()
        full = validate_package(
            package.save_source(), with_hints=self._with_hints
        )
        self._last_run_ms = (time.perf_counter() - started) * 1000
        if not sip.isdeleted(self._timer):
            self._timer.setInterval(self.wait_ms)
        self._hint_report = full
        self._report = package_findings(full)
        self._stale = False
        self.report_changed.emit()

    def _on_change(self, change: Change) -> None:
        del change
        self._schedule()

    def _on_history(self) -> None:
        self._schedule()

    def _schedule(self) -> None:
        self._stale = True
        if self._listeners and not sip.isdeleted(self._timer):
            self._timer.start()

    def _stop_timer(self) -> None:
        # When the application closes, Qt can destroy the timer before the
        # views say that they stopped listening.
        if not sip.isdeleted(self._timer):
            self._timer.stop()


_services: weakref.WeakKeyDictionary[ValidatedPackage, ValidationService] = (
    weakref.WeakKeyDictionary()
)


def service_for(package: ValidatedPackage) -> ValidationService:
    """Returns the one service of a package, made on first use.

    Args:
        package: A `Package`, or anything with `save_source()`, a
            `commandStack`, and an observer.

    Returns:
        The service. It lives as long as the package does.
    """
    service = _services.get(package)
    if service is None:
        service = ValidationService(package)
        _services[package] = service
    return service
