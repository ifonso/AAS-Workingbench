"""The counts of errors, warnings and hints in the status bar.

The counts say what the rules found in the current package, with the Validation
panel closed. Errors and warnings are findings of the rules of the specification,
and a click opens the panel that lists them. Hints are advice, and the panel does
not list them, so they are a separate count that a click does not open.

The widget listens to the validation service of the package for as long as the
package is current, so the counts are right whatever the state of the panel
(ADR 0029).
"""

from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget

from aas_editor.application.hints import hints_mode
from aas_editor.application.validation import FindingCounts
from aas_editor.application.validation import count_findings
from aas_editor.application.validation import count_text
from aas_editor.ui.validation_service import ValidatedPackage
from aas_editor.ui.validation_service import ValidationService
from aas_editor.ui.validation_service import service_for

FINDINGS_TIP = (
    "Errors and warnings that the package breaks in the rules of the "
    "specification. Click to list them in the Validation panel. F8 goes to the "
    "next one."
)
HINTS_TIP = (
    "Hints are advice, not rules. They show above the attributes of the object "
    "they are about, and the Validation panel does not list them."
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


class ValidationStatus(QWidget):
    """Shows the findings and the hints of the current package.

    Attributes:
        findings_button: The errors and warnings. A click emits `opened`.
        hints_label: The hints, apart from the findings. It is hidden while
            hints mode is off.
        opened: Emitted when the user asks to see the findings.
    """

    opened = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("validationStatus")
        self.findings_button = QToolButton(self)
        self.findings_button.setObjectName("validationStatusFindings")
        self.findings_button.setAutoRaise(True)
        self.findings_button.setToolTip(FINDINGS_TIP)
        self.findings_button.setAccessibleName("Errors and warnings")
        self.findings_button.setAccessibleDescription(FINDINGS_TIP)
        self.findings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.findings_button.clicked.connect(self.opened)
        self.hints_label = QLabel(self)
        self.hints_label.setObjectName("validationStatusHints")
        self.hints_label.setToolTip(HINTS_TIP)
        self.hints_label.setAccessibleName("Hints")
        self.hints_label.setAccessibleDescription(HINTS_TIP)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.findings_button)
        layout.addWidget(self.hints_label)
        # The service names its listeners by identity.
        self._token = object()
        self._service: ValidationService | None = None
        self._mode_subscription = hints_mode().subscribe(self._on_hints_mode)
        self.hide()

    @property
    def counts(self) -> FindingCounts:
        """The counts that the widget shows now."""
        service = self._service
        if service is None:
            return FindingCounts()
        report = service.hint_report if hints_mode().is_on else service.report
        return count_findings(report)

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
        self.hints_label.setText(count_text(counts.hints, "hint"))
        self.hints_label.setVisible(hints_mode().is_on)
        self.show()
