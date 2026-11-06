"""Hints about the object that a tab shows (F-EDT-06, hints mode).

The bar sits above the attributes of a tab and lists what the rules found about
the shown object: a rule of the specification that it breaks, or a hint such as
a deprecated category. It never blocks anything. The value stays in the model,
the tab stays editable, and the package can be saved. The bar reads the report
of the validation service, which runs debounced, so typing never waits for it.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.hints import hints_mode
from aas_editor.application.validation import hints_for
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Severity
from aas_editor.ui.validation_service import ValidatedPackage
from aas_editor.ui.validation_service import ValidationService
from aas_editor.ui.validation_service import service_for

# How many hints the bar lists before it summarizes the rest.
MAX_SHOWN = 5
_LABELS = {
    Severity.ERROR: "Error",
    Severity.WARNING: "Warning",
    Severity.INFO: "Hint",
}


def hint_lines(findings: tuple[Finding, ...]) -> list[str]:
    """Words the findings as the lines of the bar.

    Args:
        findings: The findings about one object, most severe first.

    Returns:
        One line for each of the first few findings, then a line that counts
        the rest. Two or more hints, which are the lowest severity, share one
        line that names their rules, so that the notices that almost every
        element has (no display name, no description) do not take the room of
        the errors. `hint_details` has the full text.
    """
    notices = [f for f in findings if f.severity is Severity.INFO]
    if len(notices) < 2:
        return _lines(findings)
    others = [f for f in findings if f.severity is not Severity.INFO]
    return [*_lines(tuple(others)), _grouped_line(notices)]


def hint_details(findings: tuple[Finding, ...]) -> str:
    """Words every finding in full, for the tooltip of the bar."""
    return "\n".join(
        f"{_LABELS[f.severity]}: {f.message} ({f.rule_id})" for f in findings
    )


def _lines(findings: tuple[Finding, ...] | list[Finding]) -> list[str]:
    lines = [
        f"{_LABELS[f.severity]}: {f.message} ({f.rule_id})"
        for f in findings[:MAX_SHOWN]
    ]
    if len(findings) > MAX_SHOWN:
        lines.append(
            f"... and {len(findings) - MAX_SHOWN} more. "
            "The Validation dock lists all of them"
        )
    return lines


def _grouped_line(notices: list[Finding]) -> str:
    rules = ", ".join(f.rule_id for f in notices)
    return f"{len(notices)} hints: {rules}"


class HintsBar(QFrame):
    """Lists the findings about the object of a tab, while hints mode is on."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("hintsBar")
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self.label)
        # The service names its listeners by identity. A token outlives the
        # bar, so that the bar can still be removed when it is destroyed.
        self._token = object()
        self._package: ValidatedPackage | None = None
        self._target: object | None = None
        self._service: ValidationService | None = None
        hints_mode().subscribe(self._on_mode)
        self.hide()

    @property
    def lines(self) -> list[str]:
        """The lines that the bar shows now. Empty when it is hidden."""
        return self.label.text().splitlines() if not self.isHidden() else []

    def set_target(
        self, package: ValidatedPackage | None, target: object | None
    ) -> None:
        """Shows the hints about an object.

        Args:
            package: The package that holds the object, or None for no object.
            target: The shell, submodel, description or element that the tab
                shows. Anything else, such as a package, has no hints.
        """
        self._target = target
        if package is not self._package:
            self._leave()
            self._package = package
        self._enter()
        self._update()

    # -- internals --------------------------------------------------------

    def _on_mode(self, on: bool) -> None:
        del on
        try:
            if hints_mode().is_on:
                self._enter()
            else:
                self._leave()
            self._update()
        except RuntimeError:
            # The tab was deleted, and the subscription outlived it.
            pass

    def _enter(self) -> None:
        if (
            self._package is None
            or not hints_mode().is_on
            or self._service is not None
        ):
            return
        service = service_for(self._package)
        self._service = service
        service.report_changed.connect(self._update)
        token = self._token
        self.destroyed.connect(lambda: service.stop_listening(token))
        service.listen(token, with_hints=True)

    def _leave(self) -> None:
        service, self._service = self._service, None
        if service is not None:
            service.report_changed.disconnect(self._update)
            service.stop_listening(self._token)

    def _update(self) -> None:
        service = self._service
        findings: tuple[Finding, ...] = ()
        if service is not None and self._target is not None:
            findings = hints_for(service.hint_report, self._target)
        if not findings:
            self.label.clear()
            self.hide()
            return
        self.label.setText("\n".join(hint_lines(findings)))
        self.setToolTip(hint_details(findings))
        self.show()
