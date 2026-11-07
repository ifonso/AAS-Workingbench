"""Hints about the object that a tab shows (F-EDT-06, hints mode).

The bar sits above the attributes of a tab and lists what the rules found about
the shown object: a rule of the specification that it breaks, or a hint such as
a deprecated category. It never blocks anything. The value stays in the model,
the tab stays editable, and the package can be saved. The bar reads the report
of the validation service, which runs debounced, so typing never waits for it.

An error or a warning is a finding of the rules, and the Validation panel lists
it, so a click on the bar opens the panel at that finding. A hint is advice and
is in the Hints view of the panel, with the hints of the whole package, so a bar
that has only hints does not link anywhere. The tooltip says which is which.
A kind of hint that the user turned off in that view is left out of the bar.
"""

from PyQt6.QtCore import QEvent
from PyQt6.QtCore import QObject
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QFrame
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.hints import hint_kinds
from aas_editor.application.hints import hints_mode
from aas_editor.application.hints import hints_shown
from aas_editor.application.validation import hints_for
from aas_editor.application.validation import is_hint
from aas_editor.application.validation import is_listed
from aas_editor.domain.attribute_vocabulary import metamodel_name
from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Severity
from aas_editor.ui.validation_service import ValidatedPackage
from aas_editor.ui.validation_service import ValidationService
from aas_editor.ui.validation_service import service_for

# How many hints the bar lists before it summarizes the rest.
MAX_SHOWN = 5
KINDS_TIP = (
    "Errors and warnings break the rules of the specification, and the "
    "Validation panel lists them. Hints are advice, not rules. The Hints view "
    "of the panel lists them for the whole package, and turns a kind off."
)
_LABELS = {
    Severity.ERROR: "Error",
    Severity.WARNING: "Warning",
    Severity.INFO: "Hint",
}


def _label(finding: Finding) -> str:
    """Names the kind of a finding. A hint is a hint, whatever its severity,
    because the panel lists errors and warnings of the rules and not hints."""
    return "Hint" if is_hint(finding) else _LABELS[finding.severity]


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
    """Words every finding in full."""
    return "\n".join(
        f"{_label(f)}: {f.message} ({f.rule_id})" for f in findings
    )


def bar_tooltip(findings: tuple[Finding, ...]) -> str:
    """Words the tooltip of the bar: every finding, and what the kinds mean.

    Args:
        findings: The findings about one object, most severe first.

    Returns:
        The full text of each finding, the difference between a finding and
        a hint, and the click that opens the panel when there is something
        for it to open.
    """
    lines = [hint_details(findings), "", KINDS_TIP]
    if linked_finding(findings) is not None:
        lines.append("Click to open it in the Validation panel.")
    return "\n".join(lines)


def linked_finding(findings: tuple[Finding, ...]) -> Finding | None:
    """Picks the finding that a click on the bar opens in the panel.

    Args:
        findings: The findings about one object, most severe first.

    Returns:
        The first error or warning, or None when there are only hints,
        because a click opens the list of errors and warnings, and a hint is
        in the Hints view.
    """
    return next((f for f in findings if is_listed(f)), None)


def _lines(findings: tuple[Finding, ...] | list[Finding]) -> list[str]:
    lines = [
        f"{_label(f)}: {f.message} ({f.rule_id})" for f in findings[:MAX_SHOWN]
    ]
    if len(findings) > MAX_SHOWN:
        lines.append(
            f"... and {len(findings) - MAX_SHOWN} more. Hover to read them"
        )
    return lines


def _grouped_line(notices: list[Finding]) -> str:
    topics = ", ".join(_topic(f) for f in notices)
    return f"{len(notices)} hints about {topics}. Hover to read them"


def _topic(finding: Finding) -> str:
    if finding.attribute is None:
        return finding.rule_id
    return metamodel_name(type(finding.subject), finding.attribute)


class FindingLinks(QObject):
    """Tells the main window that a bar asked to open a finding.

    The bars live in tabs, which know nothing of the panel, so they send the
    request here. The window connects `opened` once.

    Attributes:
        opened: Emitted with the package and the `Finding` to open.
    """

    opened = pyqtSignal(object, object)


_links = FindingLinks()


def finding_links() -> FindingLinks:
    """Returns the one place where bars ask to open a finding."""
    return _links


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
        # A click on the text must reach the bar, and a drag still selects it.
        self.label.installEventFilter(self)
        self._linked: Finding | None = None
        # The service names its listeners by identity. A token outlives the
        # bar, so that the bar can still be removed when it is destroyed.
        self._token = object()
        self._package: ValidatedPackage | None = None
        self._target: object | None = None
        self._service: ValidationService | None = None
        hints_mode().subscribe(self._on_mode)
        hint_kinds().subscribe(self._on_kinds)
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

    @property
    def linked(self) -> Finding | None:
        """The finding that a click opens in the Validation panel, if any."""
        return self._linked

    def open_linked(self) -> None:
        """Asks the window to open the linked finding in the panel."""
        if self._linked is not None and self._package is not None:
            finding_links().opened.emit(self._package, self._linked)

    def mouseReleaseEvent(self, a0: QMouseEvent | None) -> None:
        """Opens the linked finding when the bar is clicked."""
        if a0 is not None and a0.button() == Qt.MouseButton.LeftButton:
            self.open_linked()
        super().mouseReleaseEvent(a0)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        """Treats a click on the text as a click on the bar.

        A release after a drag that selected text is not a click, so that the
        text can still be selected and copied.
        """
        if (
            a0 is self.label
            and a1 is not None
            and a1.type() == QEvent.Type.MouseButtonRelease
            and not self.label.hasSelectedText()
        ):
            self.open_linked()
        return super().eventFilter(a0, a1)

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

    def _on_kinds(self) -> None:
        try:
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
            findings = hints_shown(hints_for(service.hint_report, self._target))
        if not findings:
            self.label.clear()
            self._linked = None
            self.hide()
            return
        self._linked = linked_finding(findings)
        self.label.setText("\n".join(hint_lines(findings)))
        self.setToolTip(bar_tooltip(findings))
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._linked is not None
            else Qt.CursorShape.ArrowCursor
        )
        self.show()
