"""The validation dock: the findings of the rules for the current package.

It lists severity, rule, location and message of each finding. A bundled
template can have hundreds of findings that only say that a reference points to
a package that is not open, so the dock filters by severity and by rule, and
shows how many findings the filters hide. A double click selects the element
of the finding in the package tree.

The dock follows the current package of the tree, and clears when that package
is closed. The service in `validation_service` runs the rules, debounced, so
that typing and editing never wait for them.
"""

import weakref
from typing import override

from PyQt6.QtCore import QAbstractTableModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QObject
from PyQt6.QtCore import QSortFilterProxyModel
from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDockWidget
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QStyle
from PyQt6.QtWidgets import QTableView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.validation import Finding
from aas_editor.domain.validation import Severity
from aas_editor.domain.validation import ValidationReport
from aas_editor.ui.validation_service import ValidatedPackage
from aas_editor.ui.validation_service import ValidationService
from aas_editor.ui.validation_service import service_for

COLUMNS = ("Severity", "Rule", "Location", "Message")
SEVERITY_COLUMN, RULE_COLUMN, LOCATION_COLUMN, MESSAGE_COLUMN = range(4)
ALL_RULES_LABEL = "All rules"
SEVERITY_LABELS = {
    Severity.ERROR: "Error",
    Severity.WARNING: "Warning",
    Severity.INFO: "Info",
}
_COUNT_WORDS = {
    Severity.ERROR: ("error", "errors"),
    Severity.WARNING: ("warning", "warnings"),
    Severity.INFO: ("hint", "hints"),
}
_ICONS = {
    Severity.ERROR: QStyle.StandardPixmap.SP_MessageBoxCritical,
    Severity.WARNING: QStyle.StandardPixmap.SP_MessageBoxWarning,
    Severity.INFO: QStyle.StandardPixmap.SP_MessageBoxInformation,
}


class FindingsModel(QAbstractTableModel):
    """The findings of one report as the rows of a table."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._findings: tuple[Finding, ...] = ()

    def set_findings(self, findings: tuple[Finding, ...]) -> None:
        """Replaces the rows."""
        self.beginResetModel()
        self._findings = findings
        self.endResetModel()

    def finding_at(self, row: int) -> Finding:
        """Returns the finding of a row of the model, not of a proxy."""
        return self._findings[row]

    @override
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._findings)

    @override
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(COLUMNS)

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return COLUMNS[section]
        return None

    @override
    def data(
        self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid():
            return None
        finding = self._findings[index.row()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                SEVERITY_LABELS[finding.severity],
                finding.rule_id,
                finding.location,
                finding.message,
            )[column]
        if role == Qt.ItemDataRole.DecorationRole and column == SEVERITY_COLUMN:
            return _icon(finding.severity)
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"{finding.rule_id}: {finding.message}"
        if role == Qt.ItemDataRole.UserRole:
            return finding
        return None


def _icon(severity: Severity) -> QIcon:
    from PyQt6.QtWidgets import QApplication

    style = QApplication.style()
    return QIcon() if style is None else style.standardIcon(_ICONS[severity])


class FindingsFilter(QSortFilterProxyModel):
    """Hides the findings of severities and rules that the user filtered out."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._severities = set(Severity)
        self._rule_id: str | None = None

    def set_filters(
        self, severities: set[Severity], rule_id: str | None
    ) -> None:
        """Selects what to show.

        Args:
            severities: The severities to show.
            rule_id: The one rule to show, or None for every rule.
        """
        self._severities = set(severities)
        self._rule_id = rule_id
        self.invalidateFilter()

    @override
    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex
    ) -> bool:
        source = self.sourceModel()
        if not isinstance(source, FindingsModel):
            return True
        finding = source.finding_at(source_row)
        if finding.severity not in self._severities:
            return False
        return self._rule_id is None or finding.rule_id == self._rule_id

    @override
    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        source = self.sourceModel()
        if left.column() == SEVERITY_COLUMN and isinstance(
            source, FindingsModel
        ):
            return (
                source.finding_at(left.row()).severity.rank
                < source.finding_at(right.row()).severity.rank
            )
        return super().lessThan(left, right)


class ValidationDock(QDockWidget):
    """Lists the findings of the current package, with filters and counts.

    Attributes:
        finding_activated: Emitted with the `Finding` when the user opens one
            with a double click or Enter. The window selects its anchor.
        findings_table: The table of findings.
        counts_label: The sentence with the counts.
        rule_box: The filter for one rule.
        severity_boxes: The check boxes of the severity filter.
        filter: The proxy model that applies the filters.
    """

    finding_activated = pyqtSignal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Validation", parent)
        self.setObjectName("validationDock")
        self._package: weakref.ReferenceType[ValidatedPackage] | None = None
        self._service: ValidationService | None = None
        self._active = True
        self._report = ValidationReport()

        self.counts_label = QLabel(self)
        self.severity_boxes: dict[Severity, QCheckBox] = {}
        severity_row = QHBoxLayout()
        for severity in Severity:
            box = QCheckBox(self)
            box.setChecked(True)
            box.toggled.connect(self._apply_filters)
            self.severity_boxes[severity] = box
            severity_row.addWidget(box)
        self.rule_box = QComboBox(self)
        self.rule_box.currentIndexChanged.connect(self._apply_filters)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh)
        severity_row.addWidget(self.rule_box, 1)
        severity_row.addWidget(self.refresh_button)

        self._model = FindingsModel(self)
        self.filter = FindingsFilter(self)
        self.filter.setSourceModel(self._model)
        self.findings_table = QTableView(self)
        self.findings_table.setModel(self.filter)
        self.findings_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.findings_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.findings_table.setSortingEnabled(True)
        vertical = self.findings_table.verticalHeader()
        header = self.findings_table.horizontalHeader()
        if vertical is not None:
            vertical.hide()
        if header is not None:
            for column in (SEVERITY_COLUMN, RULE_COLUMN, LOCATION_COLUMN):
                header.setSectionResizeMode(
                    column, QHeaderView.ResizeMode.ResizeToContents
                )
            header.setSectionResizeMode(
                MESSAGE_COLUMN, QHeaderView.ResizeMode.Stretch
            )
        self.findings_table.doubleClicked.connect(self._open_row)
        self.findings_table.activated.connect(self._open_row)

        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.addWidget(self.counts_label)
        layout.addLayout(severity_row)
        layout.addWidget(self.findings_table)
        self.setWidget(body)
        self.filter.sort(SEVERITY_COLUMN, Qt.SortOrder.AscendingOrder)
        self._show_report()

    # -- the package ------------------------------------------------------

    @property
    def package(self) -> ValidatedPackage | None:
        """The package that the dock shows, or None."""
        return None if self._package is None else self._package()

    def set_package(self, package: ValidatedPackage | None) -> None:
        """Shows the findings of a package, or clears the dock for None.

        Args:
            package: The current package, or None if none is open.
        """
        if package is self.package and (package is None or self._service):
            return
        self._detach()
        self._package = None if package is None else weakref.ref(package)
        self._report = ValidationReport()
        if package is not None:
            self._service = service_for(package)
            self._service.report_changed.connect(self._on_report)
        if self._service is not None and self._active:
            self._attach()
        else:
            self._show_report()

    def set_active(self, active: bool) -> None:
        """Tells the dock whether it is visible and should keep up to date.

        A hidden dock stops the rules from running. When it shows again, the
        report is made if the package changed meanwhile.

        Args:
            active: True if the user can see the dock.
        """
        if active == self._active:
            return
        self._active = active
        if active:
            self._attach()
        elif self._service is not None:
            self._service.stop_listening(self)

    def refresh(self) -> None:
        """Runs the rules now."""
        if self._service is not None:
            self._service.listen(self)
            self._service.refresh()

    @property
    def report(self) -> ValidationReport:
        """The findings that the dock lists before its filters."""
        return self._report

    def visible_findings(self) -> list[Finding]:
        """Returns the findings that pass the filters, in the order shown."""
        return [
            self.filter.index(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.filter.rowCount())
        ]

    def activate_row(self, row: int) -> None:
        """Opens the finding of a row of the table, as a double click does."""
        self._open_row(self.filter.index(row, 0))

    # -- internals --------------------------------------------------------

    def _attach(self) -> None:
        if self._service is not None and self._active:
            self._service.listen(self)
            if self._report is not self._service.report:
                self._on_report()

    def _detach(self) -> None:
        if self._service is not None:
            self._service.stop_listening(self)
            self._service.report_changed.disconnect(self._on_report)
        self._service = None

    def _on_report(self) -> None:
        if self._service is not None:
            self._report = self._service.report
        self._show_report()

    def _show_report(self) -> None:
        report = self._report
        # Index the rule box by the rule it showed, so a refresh keeps it.
        chosen = self.rule_box.currentData()
        counts = report.counts_by_rule()
        self.rule_box.blockSignals(True)
        self.rule_box.clear()
        self.rule_box.addItem(ALL_RULES_LABEL, None)
        for rule_id, count in sorted(counts.items()):
            self.rule_box.addItem(f"{rule_id} ({count})", rule_id)
        index = self.rule_box.findData(chosen)
        self.rule_box.setCurrentIndex(max(index, 0))
        self.rule_box.blockSignals(False)
        for severity, box in self.severity_boxes.items():
            found = len(report.with_severity(severity))
            box.setText(f"{SEVERITY_LABELS[severity]} ({found})")
        self._model.set_findings(report.findings)
        self._apply_filters()

    def _apply_filters(self) -> None:
        severities = {
            severity
            for severity, box in self.severity_boxes.items()
            if box.isChecked()
        }
        self.filter.set_filters(severities, self.rule_box.currentData())
        self.counts_label.setText(self._summary())

    def _summary(self) -> str:
        if self.package is None:
            return "No package open"
        report = self._report
        if report.is_clean:
            return "No findings"
        parts = [
            f"{len(found)} {_COUNT_WORDS[severity][len(found) != 1]}"
            for severity in Severity
            if (found := report.with_severity(severity))
        ]
        shown = self.filter.rowCount()
        total = len(report.findings)
        text = ", ".join(parts)
        return text if shown == total else f"{text}. Showing {shown} of {total}"

    def _open_row(self, index: QModelIndex) -> None:
        first = self.filter.index(index.row(), 0)
        finding: object = first.data(Qt.ItemDataRole.UserRole)
        if isinstance(finding, Finding):
            self.finding_activated.emit(finding)
