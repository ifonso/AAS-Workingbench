"""The concept description in the tab of the object that refers to it.

F-EDT-03 AC15 and F-EDT-05 AC14: below the attributes of a submodel or an
element with a semantic id, the tab shows the concept description that the
semantic id names. The display is read-only. It is collapsed to one line by
default, because the original's embedded editor made the panel very long
(F-EDT-05 section 6.6), and a button opens the description in the tab, where
it can be edited. A semantic id that names no description of the package shows
the notice of the original instead.

The panel is a widget of its own. A tab builds one, calls `set_target` with
the object it shows, and puts it in its layout. `aas_editor.domain.concept_summary`
decides what is shown.
"""

from collections.abc import Callable
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QFrame
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.changes import Change
from aas_editor.application.changes import observer_for
from aas_editor.domain.concept_summary import NOT_FOUND
from aas_editor.domain.concept_summary import ConceptSummary
from aas_editor.domain.concept_summary import SummaryRow
from aas_editor.domain.concept_summary import concept_named_by
from aas_editor.domain.concept_summary import summarize
from aas_editor.domain.references import describe_reference
from aas_editor.ui.colors import advisory_style
from aas_editor.ui.reference_jump import find_row

OPEN_TEXT = "Open concept description"
_HEADLINE_LENGTH = 90


def _short(text: str) -> str:
    return (
        text
        if len(text) <= _HEADLINE_LENGTH
        else text[:_HEADLINE_LENGTH] + "..."
    )


class EmbeddedConceptPanel(QFrame):
    """Shows the concept description of the semantic id of an object.

    Attributes:
        toggle: The header. It names the description and folds the details.
        details: The widget with the attributes of the description.
        notice: The notice for a semantic id that names no description.
        open_button: Opens the description in the tab.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        open_concept: Callable[[ConceptDescription], None] | None = None,
    ) -> None:
        """Builds the panel, hidden until `set_target` finds something.

        Args:
            parent: The parent widget.
            open_concept: Called with the description when the user presses
                the open button.
        """
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("embeddedConcept")
        self._open_concept = open_concept
        self._package: Any = None
        self._target: object | None = None
        self._concept: ConceptDescription | None = None
        self._subscription: Any = None
        self._refresh_pending = False

        self.toggle = QToolButton(self)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(False)
        self.toggle.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle.setStyleSheet(
            "QToolButton { border: none; text-align: left; }"
        )
        self.toggle.toggled.connect(self._on_toggled)

        self.details = QWidget(self)
        rows = QWidget(self.details)
        self._form = QFormLayout(rows)
        self._form.setContentsMargins(18, 0, 0, 0)
        self._form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.open_button = QPushButton(OPEN_TEXT, self.details)
        self.open_button.clicked.connect(self._on_open)
        details_layout = QVBoxLayout(self.details)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.addWidget(rows)
        details_layout.addWidget(
            self.open_button, 0, Qt.AlignmentFlag.AlignLeft
        )

        self.notice = QLabel(self)
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet(advisory_style())
        self.notice.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.addWidget(self.toggle)
        layout.addWidget(self.details)
        layout.addWidget(self.notice)
        self.details.hide()
        self.notice.hide()
        self.hide()

    # -- what the panel shows ---------------------------------------------

    @property
    def concept(self) -> ConceptDescription | None:
        """The description that is shown, or None."""
        return self._concept

    @property
    def is_expanded(self) -> bool:
        """Whether the attributes are shown and not only the header."""
        return self.toggle.isChecked()

    @property
    def header(self) -> str:
        """The text of the header, empty when the panel shows nothing."""
        return self.toggle.text() if self._concept is not None else ""

    @property
    def shown_rows(self) -> list[tuple[str, str]]:
        """The attributes that the expanded panel lists, as label and text."""
        rows: list[tuple[str, str]] = []
        for number in range(self._form.rowCount()):
            label = self._form.itemAt(number, QFormLayout.ItemRole.LabelRole)
            field = self._form.itemAt(number, QFormLayout.ItemRole.FieldRole)
            if (
                label is not None
                and field is not None
                and isinstance(label.widget(), QLabel)
                and isinstance(field.widget(), QLabel)
            ):
                rows.append(
                    (
                        cast("QLabel", label.widget()).text(),
                        cast("QLabel", field.widget()).text(),
                    )
                )
        return rows

    @property
    def notice_text(self) -> str:
        """The notice for a semantic id that names nothing, or empty."""
        return self.notice.text() if not self.notice.isHidden() else ""

    def set_target(self, package: Any, target: object | None) -> None:
        """Shows the description of the semantic id of an object.

        Args:
            package: The package that holds the object, or None.
            target: The object that the tab shows. Only a submodel or an
                element with a semantic id shows anything.
        """
        self._target = target
        if package is not self._package:
            self._leave()
            self._package = package
            if package is not None:
                self._subscription = observer_for(package).subscribe(
                    self._on_change
                )
        self.refresh()

    def refresh(self) -> None:
        """Reads the description again, and shows it."""
        self._refresh_pending = False
        reference = self._semantic_id()
        self._concept = None
        self.notice.hide()
        if reference is None or self._package is None:
            self._clear()
            self.hide()
            return
        concept = concept_named_by(self._package.objStore, reference)
        if concept is None:
            self._clear()
            self.toggle.hide()
            self.notice.setText(
                f"{NOT_FOUND}\nThe semantic id is {describe_reference(reference)}."
            )
            self.notice.show()
            self.show()
            return
        self._concept = concept
        self._fill(summarize(concept))
        self.toggle.show()
        self.details.setVisible(self.is_expanded)
        self.show()

    # -- internals ---------------------------------------------------------

    def _semantic_id(self) -> model.Reference | None:
        target = self._target
        if not isinstance(target, (model.Submodel, model.SubmodelElement)):
            return None
        reference = target.semantic_id
        return reference if reference is not None and reference.key else None

    def _clear(self) -> None:
        while self._form.rowCount():
            self._form.removeRow(0)
        self.toggle.setText("")

    def _fill(self, summary: ConceptSummary) -> None:
        self._clear()
        headline = f" - {_short(summary.headline)}" if summary.headline else ""
        self.toggle.setText(f"Concept description {summary.title}{headline}")
        self.toggle.setToolTip(summary.concept_id)
        for row in (SummaryRow("Id", summary.concept_id), *summary.rows):
            label = QLabel(f"{row.label}:", self.details)
            text = QLabel(row.text, self.details)
            text.setWordWrap(True)
            text.setTextFormat(Qt.TextFormat.PlainText)
            text.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self._form.addRow(label, text)
        self.open_button.setVisible(self._open_concept is not None)

    def _on_toggled(self, expanded: bool) -> None:
        self.toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self.details.setVisible(expanded and self._concept is not None)

    def _on_open(self) -> None:
        if self._concept is not None and self._open_concept is not None:
            self._open_concept(self._concept)

    def _on_change(self, change: Change) -> None:
        del change
        if self._refresh_pending:
            return
        self._refresh_pending = True
        try:
            QTimer.singleShot(0, self._deferred_refresh)
        except RuntimeError:
            self._refresh_pending = False

    def _deferred_refresh(self) -> None:
        try:
            self.refresh()
        except RuntimeError:
            # The tab was deleted, and the subscription outlived it.
            pass

    def _leave(self) -> None:
        subscription, self._subscription = self._subscription, None
        if subscription is not None:
            subscription.cancel()


def open_in_tab(tab: Any, concept: ConceptDescription) -> bool:
    """Opens a description in a tab, so that the tab's Back returns.

    Args:
        tab: A `TabWithTreeView`, which has the item of its object in
            `packItem` and `openItem`.
        concept: The description to open.

    Returns:
        False if no row of the package tree shows the description.
    """
    index = QModelIndex(tab.packItem)
    shown = index.model()
    if shown is None:
        return False
    found = find_row(shown, concept)
    if found is None:
        return False
    tab.openItem(found)
    return True
