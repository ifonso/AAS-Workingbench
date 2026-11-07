"""The counts of errors and warnings, and the hints of the current object, in the
status bar.

The counts of errors and warnings say what the rules of the specification found
in the current package, with the Validation panel closed, and a click opens the
panel that lists them. The hints are different. Almost every element has a few
(no display name, no description), so a count for the whole package never
reaches zero and reads like a count of defects. The status bar says how many
hints the object that is current has, such as "3 hints here", and nothing when
it has none, when hints mode is off, or when its kinds are turned off. A click
on it opens the Hints view of the panel, which has the count of the package, by
kind.

The widget listens to the validation service of the package for as long as the
package is current, so the counts are right whatever the state of the panel
(ADR 0029, ADR 0031).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget

from aas_editor.application.hints import hint_count_here
from aas_editor.application.hints import hint_kinds
from aas_editor.application.hints import hints_here_text
from aas_editor.application.hints import hints_mode
from aas_editor.application.validation import FindingCounts
from aas_editor.application.validation import count_findings
from aas_editor.application.validation import count_text
from aas_editor.application.validation import hints_for
from aas_editor.ui.validation_service import ValidatedPackage
from aas_editor.ui.validation_service import ValidationService
from aas_editor.ui.validation_service import service_for

FINDINGS_TIP = (
    "Errors and warnings that the package breaks in the rules of the "
    "specification. Click to list them in the Validation panel. F8 goes to the "
    "next one."
)
HINTS_TIP = (
    "Hints about the object that is current. Hints are advice, not rules. "
    "Click to list the hints of the whole package in the Validation panel, "
    "where you can turn a kind off."
)


def findings_text(counts: FindingCounts) -> str:
    """Words the errors and warnings, such as `1 error, 2 warnings`."""
    return (
        f"{count_text(counts.errors, 'error')}, "
        f"{count_text(counts.warnings, 'warning')}"
    )


def findings_state(counts: FindingCounts) -> str:
    """Names the worst thing in the counts: error, warning or ok."""
    if counts.errors:
        return "error"
    return "warning" if counts.warnings else "ok"


def _make_button(name: str, accessible: str, tip: str) -> QToolButton:
    button = QToolButton()
    button.setObjectName(name)
    button.setAutoRaise(True)
    button.setToolTip(tip)
    button.setAccessibleName(accessible)
    button.setAccessibleDescription(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class ValidationStatus(QWidget):
    """Shows the findings of the current package and the hints of the current
    object.

    Attributes:
        findings_button: The errors and warnings of the package. A click emits
            `opened`.
        hints_button: The hints of the current object, such as `3 hints here`.
            It is hidden while the object has none, and while hints mode is
            off. A click emits `hints_opened`.
        opened: Emitted when the user asks to see the findings.
        hints_opened: Emitted when the user asks to see the hints.
    """

    opened = pyqtSignal()
    hints_opened = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("validationStatus")
        self.findings_button = _make_button(
            "validationStatusFindings", "Errors and warnings", FINDINGS_TIP
        )
        self.findings_button.setParent(self)
        self.findings_button.clicked.connect(self.opened)
        self.hints_button = _make_button(
            "validationStatusHints", "Hints about the current object", HINTS_TIP
        )
        self.hints_button.setParent(self)
        self.hints_button.clicked.connect(self.hints_opened)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.findings_button)
        layout.addWidget(self.hints_button)
        # The service names its listeners by identity.
        self._token = object()
        self._service: ValidationService | None = None
        self._target: object | None = None
        self._mode_subscription = hints_mode().subscribe(self._on_hints_mode)
        self._kinds_subscription = hint_kinds().subscribe(self._on_kinds)
        self.hide()

    @property
    def counts(self) -> FindingCounts:
        """The errors and warnings of the package that the widget shows now."""
        service = self._service
        if service is None:
            return FindingCounts()
        return count_findings(service.report)

    @property
    def hints_here(self) -> int:
        """How many hints the current object has, apart from the kinds that
        are turned off. Zero while hints mode is off."""
        service = self._service
        if service is None or self._target is None or not hints_mode().is_on:
            return 0
        return hint_count_here(hints_for(service.hint_report, self._target))

    def set_package(self, package: ValidatedPackage | None) -> None:
        """Shows the counts of a package, or hides the widget for None.

        Args:
            package: The current package, or None if none is open.
        """
        current = self._service
        if (
            package is not None
            and current is not None
            and current is service_for(package)
        ):
            return
        self._leave()
        if package is not None:
            self._enter(service_for(package))
        self._update()

    def set_target(self, target: object | None) -> None:
        """Shows the hints of the object that is current.

        Args:
            target: The shell, submodel, description or element that the tree
                or the focused tab shows. None, or anything else, such as a
                package, has no hints.
        """
        if target is not self._target:
            self._target = target
            self._update()

    # -- internals --------------------------------------------------------

    def _enter(self, service: ValidationService) -> None:
        self._service = service
        service.report_changed.connect(self._update)
        # No hook on `destroyed` here: Python code that runs while Qt deletes
        # the widget can be interrupted by the garbage collector, which freed
        # widgets under it and crashed the large main window test. The window
        # lives as long as the application, and a closed package is left in
        # `set_package(None)`.
        service.listen(self._token, with_hints=hints_mode().is_on)

    def _leave(self) -> None:
        service, self._service = self._service, None
        if service is not None:
            service.report_changed.disconnect(self._update)
            service.stop_listening(self._token)

    def _on_hints_mode(self, on: bool) -> None:
        try:
            service = self._service
            if service is not None:
                service.listen(self._token, with_hints=on)
            self._update()
        except RuntimeError:
            # The widget was deleted, and the subscription outlived it.
            self._mode_subscription.cancel()

    def _on_kinds(self) -> None:
        try:
            self._update()
        except RuntimeError:
            # The widget was deleted, and the subscription outlived it.
            self._kinds_subscription.cancel()

    def _update(self) -> None:
        if self._service is None:
            self.hide()
            return
        counts = self.counts
        self.findings_button.setText(findings_text(counts))
        self.findings_button.setProperty("state", findings_state(counts))
        style = self.findings_button.style()
        if style is not None:
            style.unpolish(self.findings_button)
            style.polish(self.findings_button)
        here = self.hints_here
        self.hints_button.setText(hints_here_text(here))
        self.hints_button.setToolTip(self._hints_tip())
        self.hints_button.setVisible(here > 0)
        self.show()

    def _hints_tip(self) -> str:
        off = len(hint_kinds().off)
        if not off:
            return HINTS_TIP
        return f"{HINTS_TIP} {count_text(off, 'kind')} turned off."
