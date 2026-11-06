"""The dialog that picks the target of a reference from a package (F-EDT-11).

It lists the shells, submodels, concept descriptions, and elements of a
package, filtered by the kinds of target that the field accepts, with a search.
The keys come from `domain.reference_picker.reference_to`, as an external
reference to the id, or as a model reference through the path. A target that
the chosen kind cannot point at keeps OK disabled and says why.

The dialog only shows what the domain module found. Tests drive it with
`set_filter`, `set_search`, `set_as_model`, `select`, and `reference`.
"""

from collections.abc import Sequence

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTreeWidget
from PyQt6.QtWidgets import QTreeWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.reference_picker import ANYTHING
from aas_editor.domain.reference_picker import Candidate
from aas_editor.domain.reference_picker import ReferenceRule
from aas_editor.domain.reference_picker import ReferenceTargetError
from aas_editor.domain.reference_picker import TargetClasses
from aas_editor.domain.reference_picker import TargetFilter
from aas_editor.domain.reference_picker import PickerSource
from aas_editor.domain.reference_picker import candidates_in
from aas_editor.domain.reference_picker import reference_to
from aas_editor.domain.references import describe_reference

TITLE = "Pick what the reference points to"
MODEL_TEXT = "Model reference through the path of the target"
EXTERNAL_TEXT = "External reference to the id of the target"
KIND_TIP = (
    "An element has no id, so a reference to it is a model reference "
    "through its path."
)
_CANDIDATE_ROLE = Qt.ItemDataRole.UserRole


def _default_filter(rule: ReferenceRule) -> TargetFilter | None:
    """Returns the narrowest filter that covers everything a rule accepts."""
    if rule.targets == ANYTHING:
        return None
    covering = [
        candidate
        for candidate in rule.filters()
        if candidate.classes != ANYTHING
        and all(
            issubclass(accepted, candidate.classes) for accepted in rule.targets
        )
    ]
    return covering[0] if covering else None


class ReferencePickerDialog(QDialog):
    """Lists the targets of a package and derives the reference to one."""

    def __init__(
        self,
        objects: Sequence[model.Identifiable],
        rule: ReferenceRule,
        as_model: bool | None = None,
        parent: QWidget | None = None,
        others: Sequence[PickerSource] = (),
        package_name: str = "",
        initial_filter: str | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            objects: The shells, submodels, and concept descriptions of the
                package.
            rule: What the field accepts.
            as_model: Whether to start with a model reference. None starts
                with the kind the rule prefers: external for a field that
                accepts both, because Package Explorer's "Add existing"
                gives a global reference by default.
            parent: The parent widget.
            others: The other open packages, which may hold the target too
                (F-EDT-11 AC1). A reference to something there is an external
                reference to its id, or a model reference through its path.
            package_name: The name of the package that is edited, to tell it
                from the others in the list.
            initial_filter: The text of the filter to start on, such as
                `Concept descriptions` for a semantic id (F-EDT-11 AC1).
        """
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        # The text of the kinds is a sentence, and the types are long words.
        self.setMinimumSize(720, 420)
        self._objects = list(objects)
        self._others = tuple(others)
        self._package_name = package_name or "This package"
        self._rule = rule
        self._chosen: Candidate | None = None

        self.kind_box = QComboBox(self)
        self.kind_box.setToolTip(KIND_TIP)
        if rule.allows_external:
            self.kind_box.addItem(EXTERNAL_TEXT, False)
        if rule.allows_model:
            self.kind_box.addItem(MODEL_TEXT, True)
        wanted = as_model if as_model is not None else not rule.allows_external
        self.kind_box.setCurrentIndex(max(self.kind_box.findData(wanted), 0))

        self.filter_box = QComboBox(self)
        filters = rule.filters() or (TargetFilter("Anything", ANYTHING),)
        for entry in filters:
            self.filter_box.addItem(entry.name, entry)
        preferred = _default_filter(rule)
        if preferred is not None:
            self.filter_box.setCurrentIndex(
                max(self.filter_box.findData(preferred), 0)
            )
        elif initial_filter is not None:
            # A field that has no narrower filter of its own starts on the
            # one that the caller asks for, if the field offers it.
            self.filter_box.setCurrentIndex(
                max(self.filter_box.findText(initial_filter), 0)
            )

        self.search_box = QLineEdit(self)
        self.search_box.setPlaceholderText("Search by name, type, or id")
        self.search_box.setClearButtonEnabled(True)

        self.tree = QTreeWidget(self)
        labels = ["Name", "Type", "Belongs to"]
        if self._others:
            labels.append("Package")
        self.tree.setHeaderLabels(labels)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0, 240)
        header = self.tree.header()
        if header is not None:
            # The names of the types are long words, and were cut to "Annot...".
            header.setSectionResizeMode(
                1, QHeaderView.ResizeMode.ResizeToContents
            )

        self.others_box = QCheckBox("Also list the other open packages", self)
        self.others_box.setChecked(True)
        self.others_box.setVisible(bool(self._others))
        self.preview = QLabel(self)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        if self.kind_box.count() > 1:
            layout.addWidget(self.kind_box)
        else:
            # Not in the layout, so it would sit in the corner of the dialog.
            self.kind_box.hide()
        layout.addWidget(self.filter_box)
        layout.addWidget(self.search_box)
        layout.addWidget(self.others_box)
        layout.addWidget(self.tree)
        layout.addWidget(self.preview)
        layout.addWidget(self.buttons)

        self.kind_box.currentIndexChanged.connect(self._reload)
        self.filter_box.currentIndexChanged.connect(self._reload)
        self.search_box.textChanged.connect(self._reload)
        self.others_box.toggled.connect(self._reload)
        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_clicked)
        self._reload()

    # What the dialog works on

    @property
    def as_model(self) -> bool:
        """Whether the user wants a model reference where there is a choice."""
        return bool(self.kind_box.currentData())

    def _as_model_for(self, target: model.Referable) -> bool:
        """Tells which kind a target gets: an element has no id to point at."""
        if self.as_model:
            return True
        if isinstance(target, model.Identifiable):
            return False
        return self._rule.allows_model

    def _classes(self) -> TargetClasses:
        """The classes that can be chosen now: filter and rule together."""
        current: TargetFilter | None = self.filter_box.currentData()
        wanted = current.classes if current is not None else ANYTHING
        if not self._rule.allows_model:
            # Only an external reference: it points at ids.
            return (
                (model.Identifiable,)
                if wanted == ANYTHING
                else tuple(
                    cls for cls in wanted if issubclass(cls, model.Identifiable)
                )
            )
        if self._rule.targets == ANYTHING:
            return wanted
        allowed = self._rule.targets
        if wanted == ANYTHING:
            return allowed
        return tuple(
            cls
            for cls in wanted
            if any(issubclass(cls, ok) or issubclass(ok, cls) for ok in allowed)
        )

    def _reload(self) -> None:
        classes = self._classes()
        found = (
            candidates_in(self._sources(), classes, self.search_box.text())
            if classes
            else []
        )
        if self._rule.allows_model and self._rule.targets != ANYTHING:
            found = [
                entry
                for entry in found
                if isinstance(entry.target, self._rule.targets)
            ]
        self.tree.clear()
        for entry in found:
            columns = [entry.label, entry.kind, entry.owner]
            if self._others:
                columns.append(entry.package)
            item = QTreeWidgetItem(columns)
            item.setData(0, _CANDIDATE_ROLE, entry)
            self.tree.addTopLevelItem(item)
        self._chosen = None
        self._update_preview()

    def _sources(self) -> list[PickerSource]:
        """The packages that the list covers now: this one, and the others."""
        if not self._others:
            return [PickerSource("", tuple(self._objects))]
        main = PickerSource(self._package_name, tuple(self._objects))
        return [main, *(self._others if self.others_box.isChecked() else ())]

    def _on_current_changed(
        self, current: QTreeWidgetItem | None, _previous: object
    ) -> None:
        self._chosen = (
            current.data(0, _CANDIDATE_ROLE) if current is not None else None
        )
        self._update_preview()

    def _on_double_clicked(self, item: QTreeWidgetItem) -> None:
        self._chosen = item.data(0, _CANDIDATE_ROLE)
        self._update_preview()
        if self.reference() is not None:
            self.accept()

    def _update_preview(self) -> None:
        ok_button = self.ok_button
        if self._chosen is None:
            self.preview.setText("Pick a target from the list.")
            ok_button.setEnabled(False)
            return
        try:
            reference = self._derive(self._chosen.target)
        except ReferenceTargetError as error:
            self.preview.setText(str(error))
            ok_button.setEnabled(False)
            return
        text = f"{type(reference).__name__}: {describe_reference(reference)}"
        if self._others and self._chosen.package != self._package_name:
            text += (
                f"\nThe target is in the package {self._chosen.package}, "
                "not in this one."
            )
        self.preview.setText(text)
        ok_button.setEnabled(True)

    @property
    def ok_button(self) -> QPushButton:
        """The OK button, which stays disabled until a target can be used."""
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is None:
            raise RuntimeError("The dialog has no OK button")
        return button

    # For tests, and for callers that drive the dialog

    def set_filter(self, name: str) -> None:
        """Chooses a filter by its text."""
        index = self.filter_box.findText(name)
        if index < 0:
            raise LookupError(f"No filter named '{name}'")
        self.filter_box.setCurrentIndex(index)

    def filter_names(self) -> list[str]:
        """Returns the texts of the filters that are offered."""
        return [
            self.filter_box.itemText(row)
            for row in range(self.filter_box.count())
        ]

    def set_search(self, text: str) -> None:
        """Types into the search box."""
        self.search_box.setText(text)

    def set_as_model(self, as_model: bool) -> None:
        """Chooses between a model reference and an external one."""
        index = self.kind_box.findData(as_model)
        if index < 0:
            raise LookupError("The field does not accept this kind")
        self.kind_box.setCurrentIndex(index)

    def visible_labels(self) -> list[str]:
        """Returns the names in the list, in order."""
        items = (
            self.tree.topLevelItem(row)
            for row in range(self.tree.topLevelItemCount())
        )
        return [item.text(0) for item in items if item is not None]

    def select(self, target: model.Referable) -> bool:
        """Makes a target the current row, if the list shows it."""
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item is None:
                continue
            if item.data(0, _CANDIDATE_ROLE).target is target:
                self.tree.setCurrentItem(item)
                return True
        return False

    def reference(self) -> model.Reference | None:
        """Returns the reference to the chosen target, or None."""
        if self._chosen is None:
            return None
        try:
            return self._derive(self._chosen.target)
        except ReferenceTargetError:
            return None

    def _derive(self, target: model.Referable) -> model.Reference:
        return reference_to(target, self._as_model_for(target))

    def problem(self) -> str:
        """Returns the text under the list: the reference or the reason."""
        return self.preview.text()
