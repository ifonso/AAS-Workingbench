"""The hints of a whole package, grouped by kind (ADR 0031).

The status bar counts only the hints of the object that is current, and the bar
above a tab lists only those of its object. This is the one place that has the
hints of the package, and the count of all of them. A group is a kind of hint,
named in words ("Missing description") with its count, and it opens to the
elements that have one. A double click or Enter on an element goes to it.

Almost every element has a few of the commonest hints, and a template leaves
them out on purpose, so each group has a check box. A kind that is unticked is
left out of the status bar and of the bar above a tab. The choice is the user's
and is kept in the settings, not in the package, so it holds for every package
and for the next session. A group that is turned off stays in the list, so that
it can be turned on again, and so does a button that turns every kind on.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QBrush
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTreeWidget
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.hints import HintGroup
from aas_workingbench.application.hints import group_hints
from aas_workingbench.application.hints import hint_kind_tip
from aas_workingbench.application.hints import hint_kinds
from aas_workingbench.application.hints import hints_mode
from aas_workingbench.application.validation import count_text
from aas_workingbench.domain.validation import Finding
from aas_workingbench.domain.validation import ValidationReport
from aas_workingbench.ui.hint_kinds_setting import save_hint_kinds
from aas_workingbench.ui.theme import current_tokens
from aas_workingbench.ui.theme import theme_manager
from aas_workingbench.ui.theme.icons import IconRole
from aas_workingbench.ui.theme.icons import tabler_icon
from aas_workingbench.ui.theme.kind_icons import kind_icon
from aas_workingbench.ui.tree_pane import add_filter_icon

COLUMNS = ("Kind", "Count")
KIND_COLUMN, COUNT_COLUMN = range(2)
HELP_TEXT = "Hints are advice, not rules. They do not stop a save."
"""The one line beside the filter that says what a hint is (proposal 5.4)."""
HELP_TIP = (
    "Tick a kind to count its hints in the status bar and show them above the "
    "tabs. Untick one that this package leaves out on purpose, such as the "
    "descriptions of a template. The choice is kept for every package."
)
FIRST_ELEMENTS = 4
"""How many elements a kind lists when it opens, before "Show N more"."""
FILTER_PLACEHOLDER = "Filter hints"
MODE_OFF_TEXT = (
    "Hints mode is off, so the status bar and the tabs show no hints. Switch "
    "it on in the View menu."
)
_GROUP_ROLE = Qt.ItemDataRole.UserRole
_FINDING_ROLE = Qt.ItemDataRole.UserRole + 1
_MORE_ROLE = Qt.ItemDataRole.UserRole + 2


class HintsView(QWidget):
    """Lists the hints of the current package by kind, with a count for each.

    Attributes:
        finding_activated: Emitted with the `Finding` of an element that the
            user opened with a double click or Enter.
        counted: Emitted with the count of hints that are shown, when it may
            have changed.
        summary_label: The count of all hints that are shown, and of the kinds.
        tree: The groups, and under each the elements that have a hint.
        turn_on_button: Turns every kind on. Hidden while none is off.
    """

    finding_activated = pyqtSignal(object)
    counted = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hintsView")
        self._groups: tuple[HintGroup, ...] = ()
        self._has_package = False
        self._filter = ""
        self.summary_label = QLabel(self)
        self.filter_field = QLineEdit(self)
        self.filter_field.setObjectName("hintsFilter")
        self.filter_field.setPlaceholderText(FILTER_PLACEHOLDER)
        self.filter_field.setClearButtonEnabled(True)
        add_filter_icon(self.filter_field)
        self.filter_field.setAccessibleName("Filter the hints")
        self.filter_field.textChanged.connect(self._on_filter)
        self.help_label = QLabel(HELP_TEXT, self)
        self.help_label.setObjectName("validationNote")
        self.help_label.setToolTip(HELP_TIP)
        self.mode_label = QLabel(MODE_OFF_TEXT, self)
        self.mode_label.setObjectName("validationNote")
        self.mode_label.setWordWrap(True)

        self.tree = QTreeWidget(self)
        self.tree.setObjectName("hintsTree")
        self.tree.setAccessibleName("Hints by kind")
        self.tree.setHeaderLabels(COLUMNS)
        # The kinds say what they are, so the columns need no header (1.2).
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        header = self.tree.header()
        if header is not None:
            header.setStretchLastSection(False)
            header.setSectionResizeMode(
                KIND_COLUMN, QHeaderView.ResizeMode.Stretch
            )
            header.setSectionResizeMode(
                COUNT_COLUMN, QHeaderView.ResizeMode.ResizeToContents
            )
        self.tree.itemExpanded.connect(self._fill)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemActivated.connect(self._on_activated)
        # "Show N more" is a link, which one click follows.
        self.tree.itemClicked.connect(self._on_clicked)

        self.kinds_label = QLabel(self)
        self.kinds_label.setObjectName("validationNote")
        self.turn_on_button = QPushButton("Turn all kinds on", self)
        self.turn_on_button.clicked.connect(self._turn_all_on)
        footer = QHBoxLayout()
        footer.addWidget(self.kinds_label, 1)
        footer.addWidget(self.turn_on_button)

        filters = QHBoxLayout()
        filters.addWidget(self.filter_field, 1)
        filters.addWidget(self.help_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary_label)
        layout.addLayout(filters)
        layout.addWidget(self.mode_label)
        layout.addWidget(self.tree, 1)
        layout.addLayout(footer)
        hint_kinds().subscribe(self._on_kinds)
        hints_mode().subscribe(self._on_mode)
        # The color of a kind that is off comes from the palette of the theme.
        theme_manager().changed.connect(self._repaint)
        self._show()

    # -- what it shows ----------------------------------------------------

    @property
    def groups(self) -> tuple[HintGroup, ...]:
        """The kinds that the report has hints of, the largest first."""
        return self._groups

    @property
    def shown_groups(self) -> tuple[HintGroup, ...]:
        """The kinds that the filter keeps, each with the hints it keeps."""
        return tuple(
            kept
            for group in self._groups
            if (kept := _filtered(group, self._filter)) is not None
        )

    @property
    def shown_count(self) -> int:
        """How many hints the kinds that are on have. The count that the
        status bar adds up over the objects, for the whole package."""
        return sum(g.count for g in self.groups if not _is_off(g))

    def set_report(self, report: ValidationReport, has_package: bool) -> None:
        """Shows the hints of a report.

        Args:
            report: A report made with hints. Errors and warnings in it are not
                listed.
            has_package: False when no package is open.
        """
        self._groups = group_hints(report)
        self._has_package = has_package
        self._show()

    def group_item(self, rule_id: str) -> QTreeWidgetItem | None:
        """Returns the row of a kind, or None if the package has no hint of it.

        Args:
            rule_id: The id of the hint rule.
        """
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item is not None and _group_of(item).rule_id == rule_id:
                return item
        return None

    def activate(self, item: QTreeWidgetItem) -> None:
        """Opens the element of a row, as a double click on it does."""
        self._on_activated(item, KIND_COLUMN)

    # -- internals --------------------------------------------------------

    def _show(self) -> None:
        expanded = {
            _group_of(item).rule_id
            for row in range(self.tree.topLevelItemCount())
            if (item := self.tree.topLevelItem(row)) is not None
            and item.isExpanded()
        }
        scroll = self.tree.verticalScrollBar()
        position = 0 if scroll is None else scroll.value()
        self.tree.blockSignals(True)
        self.tree.clear()
        for group in self.shown_groups:
            item = QTreeWidgetItem(self.tree)
            item.setData(KIND_COLUMN, _GROUP_ROLE, group)
            # A hint is advice, in the blue of information (proposal 1.5).
            item.setIcon(KIND_COLUMN, tabler_icon("info-circle", IconRole.INFO))
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setToolTip(KIND_COLUMN, hint_kind_tip(group.rule_id))
            item.setTextAlignment(
                COUNT_COLUMN,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            )
            self._paint(item)
        self.tree.blockSignals(False)
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item is not None and _group_of(item).rule_id in expanded:
                item.setExpanded(True)
            elif item is not None and self._filter:
                # A filter shows what it found without another click.
                item.setExpanded(True)
        if scroll is not None:
            scroll.setValue(position)
        self._show_texts()

    def _paint(self, item: QTreeWidgetItem) -> None:
        """Sets the words, the check box and the color of a row of a kind."""
        group = _group_of(item)
        off = _is_off(group)
        item.setText(KIND_COLUMN, group.name)
        item.setText(COUNT_COLUMN, str(group.count))
        item.setCheckState(
            KIND_COLUMN,
            Qt.CheckState.Unchecked if off else Qt.CheckState.Checked,
        )
        # A kind that is off is drawn in the quiet text color of the theme.
        quiet = self.palette().color(QPalette.ColorRole.PlaceholderText)
        brush = QBrush(quiet) if off else QBrush()
        for column in (KIND_COLUMN, COUNT_COLUMN):
            item.setForeground(column, brush)
        item.setToolTip(
            COUNT_COLUMN,
            "Turned off. Tick the kind to show it again."
            if off
            else "How many elements have a hint of this kind.",
        )

    def _show_texts(self) -> None:
        groups = self.groups
        off = hint_kinds().off
        if not self._has_package:
            summary = "No package open"
        elif not groups:
            summary = "No hints"
        else:
            on = [g for g in groups if not _is_off(g)]
            summary = (
                f"{count_text(sum(g.count for g in on), 'hint')} in "
                f"{count_text(len(on), 'kind')}"
            )
            hidden = sum(g.count for g in groups if _is_off(g))
            if hidden:
                summary += f". {count_text(hidden, 'hint')} turned off"
        self.summary_label.setText(summary)
        self.mode_label.setVisible(not hints_mode().is_on)
        self.kinds_label.setText(
            f"{count_text(len(off), 'kind')} turned off" if off else ""
        )
        self.kinds_label.setVisible(bool(off))
        self.turn_on_button.setVisible(bool(off))
        self.counted.emit(self.shown_count)

    def _fill(self, item: QTreeWidgetItem) -> None:
        """Adds the first elements of a kind when its row opens for the first
        time, and a row that shows the rest (proposal 5.3)."""
        if item.parent() is not None or item.childCount():
            return
        findings = _group_of(item).findings
        for finding in findings[:FIRST_ELEMENTS]:
            self._add_element(item, finding)
        rest = len(findings) - FIRST_ELEMENTS
        if rest > 0:
            more = QTreeWidgetItem(item)
            more.setText(KIND_COLUMN, f"Show {rest} more")
            more.setData(KIND_COLUMN, _MORE_ROLE, True)
            more.setForeground(
                KIND_COLUMN, QBrush(QColor(current_tokens().link))
            )
            more.setFirstColumnSpanned(True)

    def show_more(self, item: QTreeWidgetItem) -> None:
        """Lists the rest of the elements of a kind, in place of its "Show N
        more" row."""
        group_item = item.parent()
        if group_item is None or not item.data(KIND_COLUMN, _MORE_ROLE):
            return
        group_item.removeChild(item)
        shown = group_item.childCount()
        for finding in _group_of(group_item).findings[shown:]:
            self._add_element(group_item, finding)

    @staticmethod
    def _add_element(parent: QTreeWidgetItem, finding: Finding) -> None:
        child = QTreeWidgetItem(parent)
        child.setText(KIND_COLUMN, f"{finding.location}: {finding.message}")
        child.setToolTip(KIND_COLUMN, f"{finding.rule_id}: {finding.message}")
        child.setData(KIND_COLUMN, _FINDING_ROLE, finding)
        icon = kind_icon(finding.anchor)
        if icon is not None:
            child.setIcon(KIND_COLUMN, icon)
        child.setFirstColumnSpanned(True)

    def _on_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        if item.data(KIND_COLUMN, _MORE_ROLE):
            self.show_more(item)

    def _on_filter(self, text: str) -> None:
        self._filter = text.strip()
        self._show()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != KIND_COLUMN or item.parent() is not None:
            return
        off = item.checkState(KIND_COLUMN) == Qt.CheckState.Unchecked
        hint_kinds().set_off(_group_of(item).rule_id, off)
        save_hint_kinds()

    def _on_activated(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        if item.data(KIND_COLUMN, _MORE_ROLE):
            self.show_more(item)
            return
        finding = item.data(KIND_COLUMN, _FINDING_ROLE)
        if isinstance(finding, Finding):
            self.finding_activated.emit(finding)

    def _turn_all_on(self) -> None:
        hint_kinds().load(())
        save_hint_kinds()

    def _on_kinds(self) -> None:
        try:
            self._repaint()
        except RuntimeError:
            # The view was deleted, and the subscription outlived it.
            pass

    def _on_mode(self, on: bool) -> None:
        del on
        try:
            self._show_texts()
        except RuntimeError:
            pass

    def _repaint(self) -> None:
        self.tree.blockSignals(True)
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item is not None:
                self._paint(item)
        self.tree.blockSignals(False)
        self._show_texts()


def _group_of(item: QTreeWidgetItem) -> HintGroup:
    group = item.data(KIND_COLUMN, _GROUP_ROLE)
    assert isinstance(group, HintGroup)
    return group


def _is_off(group: HintGroup) -> bool:
    return hint_kinds().is_off(group.rule_id)


def _filtered(group: HintGroup, text: str) -> HintGroup | None:
    """Keeps the hints of a kind that a text of the filter names.

    A text that names the kind, by its words or its rule, keeps all of its
    hints. Otherwise a hint stays when its place or its message has the text.
    The match ignores case.

    Returns:
        The kind with the hints that it keeps, or None for none.
    """
    if not text:
        return group
    wanted = text.lower()
    if wanted in group.name.lower() or wanted in group.rule_id.lower():
        return group
    kept = tuple(
        f
        for f in group.findings
        if wanted in f.location.lower() or wanted in f.message.lower()
    )
    return HintGroup(group.rule_id, kept) if kept else None
