"""The dialogs for creating shells and submodels, and for the asset ids of a shell.

They only collect input and show the reason when it is not valid. The rules are
in `application/operations/create.py` and `domain/asset_information.py`, and the
dialogs ask them while the user types, so OK is disabled with a reason in
place of a traceback after the click.

Tests drive them through their fields (`id_edit`, `kind_box`, and so on) and
read the result from `build`.
"""

from collections.abc import Sequence

from basyx.aas import model
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.operations.create import CreateError
from aas_editor.application.operations.create import new_shell
from aas_editor.application.operations.create import new_submodel
from aas_editor.application.operations.rename import RenameError
from aas_editor.domain.asset_information import ASSET_KINDS
from aas_editor.domain.asset_information import DEFAULT_ASSET_KIND
from aas_editor.domain.asset_information import AssetInformationError
from aas_editor.domain.asset_information import build_specific_asset_id
from aas_editor.domain.asset_information import new_global_asset_id
from aas_editor.domain.ids import new_identifier
from aas_editor.domain.references import describe_object

_PROBLEM_STYLE = "color: #b00020;"
NO_SHELL_TEXT = "(none: a Submodel that no AAS refers to)"
_KIND_TEXT = {
    model.AssetKind.TYPE: "Type",
    model.AssetKind.INSTANCE: "Instance",
    model.AssetKind.NOT_APPLICABLE: "Not applicable",
    model.AssetKind.ROLE: "Role",
}


class _ValidatedDialog(QDialog):
    """A dialog with OK and Cancel, and a line for the reason OK is off."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.form = QFormLayout()
        self.problem_label = QLabel(self)
        self.problem_label.setWordWrap(True)
        self.problem_label.setStyleSheet(_PROBLEM_STYLE)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.outer = QVBoxLayout(self)
        self.outer.addLayout(self.form)
        self.outer.addWidget(self.problem_label)
        self.outer.addWidget(self.buttons)

    @property
    def ok_button(self) -> QPushButton:
        """The OK button, off while the input is not valid."""
        button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if button is None:
            raise RuntimeError("The dialog has no OK button")
        return button

    @property
    def problem(self) -> str:
        """Why the input is not valid now, or an empty text."""
        return self.problem_label.text()

    def _show_problem(self, text: str) -> None:
        self.problem_label.setText(text)
        self.ok_button.setEnabled(not text)


class CreateShellDialog(_ValidatedDialog):
    """Asks for what a new shell needs, so that its AssetInformation is valid."""

    def __init__(
        self,
        objects: Sequence[model.Identifiable],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog with a generated id and global asset id.

        Args:
            objects: The identifiables of the package, to refuse a taken id.
            parent: The parent widget.
        """
        super().__init__("Create AAS", parent)
        self._objects = list(objects)
        self.id_edit = QLineEdit(new_identifier(), self)
        self.id_short_edit = QLineEdit(self)
        self.kind_box = QComboBox(self)
        for kind in ASSET_KINDS:
            self.kind_box.addItem(_KIND_TEXT[kind], kind)
        self.kind_box.setCurrentIndex(
            self.kind_box.findData(DEFAULT_ASSET_KIND)
        )
        self.global_id_edit = QLineEdit(new_global_asset_id(), self)
        self.generate_button = QPushButton("Generate", self)
        self.generate_button.clicked.connect(
            lambda: self.global_id_edit.setText(new_global_asset_id())
        )
        self.asset_type_edit = QLineEdit(self)
        self.specific_table = QTableWidget(0, 2, self)
        self.specific_table.setHorizontalHeaderLabels(["Name", "Value"])
        header = self.specific_table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.specific_table.setMaximumHeight(110)
        self.add_specific_button = QPushButton("Add specific asset id", self)
        self.add_specific_button.clicked.connect(self.add_specific_row)

        global_row = QHBoxLayout()
        global_row.addWidget(self.global_id_edit)
        global_row.addWidget(self.generate_button)
        self.form.addRow("id*", self.id_edit)
        self.form.addRow("idShort", self.id_short_edit)
        self.form.addRow("Asset kind*", self.kind_box)
        self.form.addRow("Global asset id", global_row)
        self.form.addRow("Asset type", self.asset_type_edit)
        self.form.addRow("Specific asset ids", self.specific_table)
        self.form.addRow("", self.add_specific_button)

        for edit in (
            self.id_edit,
            self.id_short_edit,
            self.global_id_edit,
            self.asset_type_edit,
        ):
            edit.textChanged.connect(self._validate)
        self.kind_box.currentIndexChanged.connect(self._validate)
        self.specific_table.itemChanged.connect(self._validate)
        self._validate()

    def add_specific_row(self, name: str = "", value: str = "") -> None:
        """Adds a row for a specific asset id."""
        row = self.specific_table.rowCount()
        self.specific_table.insertRow(row)
        self.specific_table.setItem(row, 0, QTableWidgetItem(name))
        self.specific_table.setItem(row, 1, QTableWidgetItem(value))

    def specific_asset_ids(self) -> list[model.SpecificAssetId]:
        """Builds the specific asset ids of the rows that are not empty.

        Raises:
            AssetInformationError: If a row has only a name or only a value.
        """
        found: list[model.SpecificAssetId] = []
        for row in range(self.specific_table.rowCount()):
            name_item = self.specific_table.item(row, 0)
            value_item = self.specific_table.item(row, 1)
            name = name_item.text() if name_item is not None else ""
            value = value_item.text() if value_item is not None else ""
            if not name.strip() and not value.strip():
                continue
            found.append(build_specific_asset_id(name, value))
        return found

    def build(self) -> model.AssetAdministrationShell:
        """Makes the shell from the fields.

        Raises:
            CreateError: If the input is not valid. The text says why.
            RenameError: If another object has the id.
        """
        try:
            specific = self.specific_asset_ids()
        except AssetInformationError as error:
            raise CreateError(str(error)) from error
        return new_shell(
            self._objects,
            id_=self.id_edit.text(),
            id_short=self.id_short_edit.text(),
            asset_kind=self.kind_box.currentData(),
            global_asset_id=self.global_id_edit.text(),
            specific_asset_ids=specific,
            asset_type=self.asset_type_edit.text(),
        )

    def _validate(self) -> None:
        try:
            self.build()
        except (CreateError, RenameError) as error:
            self._show_problem(str(error))
        else:
            self._show_problem("")


class CreateSubmodelDialog(_ValidatedDialog):
    """Asks for a new submodel, and for the shell that should refer to it."""

    def __init__(
        self,
        objects: Sequence[model.Identifiable],
        shells: Sequence[model.AssetAdministrationShell],
        shell: model.AssetAdministrationShell | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog with a generated id.

        Args:
            objects: The identifiables of the package, to refuse a taken id.
            shells: The shells that can refer to the submodel.
            shell: The shell to preselect, or None.
            parent: The parent widget.
        """
        super().__init__("Create Submodel", parent)
        self._objects = list(objects)
        self.id_edit = QLineEdit(new_identifier(), self)
        self.id_short_edit = QLineEdit(self)
        self.kind_box = QComboBox(self)
        self.kind_box.addItem("Instance", model.ModellingKind.INSTANCE)
        self.kind_box.addItem("Template", model.ModellingKind.TEMPLATE)
        self.shell_box = QComboBox(self)
        self.shell_box.addItem(NO_SHELL_TEXT, None)
        for candidate in shells:
            self.shell_box.addItem(describe_object(candidate), candidate)
        if shell is not None:
            self.shell_box.setCurrentIndex(
                max(self.shell_box.findData(shell), 0)
            )
        elif len(shells) == 1:
            self.shell_box.setCurrentIndex(1)
        self.form.addRow("id*", self.id_edit)
        self.form.addRow("idShort", self.id_short_edit)
        self.form.addRow("Kind*", self.kind_box)
        self.form.addRow("Refer to it from", self.shell_box)
        self.id_edit.textChanged.connect(self._validate)
        self.id_short_edit.textChanged.connect(self._validate)
        self._validate()

    def selected_shell(self) -> model.AssetAdministrationShell | None:
        """Returns the shell that will refer to the submodel, or None."""
        return self.shell_box.currentData()

    def build(self) -> model.Submodel:
        """Makes the submodel from the fields.

        Raises:
            CreateError: If the input is not valid.
            RenameError: If another object has the id.
        """
        return new_submodel(
            self._objects,
            id_=self.id_edit.text(),
            id_short=self.id_short_edit.text(),
            kind=self.kind_box.currentData(),
        )

    def _validate(self) -> None:
        try:
            self.build()
        except (CreateError, RenameError) as error:
            self._show_problem(str(error))
        else:
            self._show_problem("")


class LinkSubmodelsDialog(_ValidatedDialog):
    """Lists the submodels that a shell does not refer to, to tick some."""

    def __init__(
        self,
        shell: model.AssetAdministrationShell,
        submodels: Sequence[model.Submodel],
        parent: QWidget | None = None,
    ) -> None:
        """Builds the list.

        Args:
            shell: The shell that will refer to the chosen submodels.
            submodels: The submodels it does not refer to yet.
            parent: The parent widget.
        """
        super().__init__("Link existing Submodels", parent)
        self.setWindowTitle(f"Link Submodels to {describe_object(shell)}")
        self.list = QListWidget(self)
        for submodel in sorted(
            submodels, key=lambda item: (item.id_short or item.id).lower()
        ):
            item = QListWidgetItem(
                f"{submodel.id_short or submodel.id}  ({submodel.id})"
            )
            item.setData(Qt.ItemDataRole.UserRole, submodel)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        self.select_all_box = QCheckBox("Select all", self)
        self.select_all_box.toggled.connect(self.set_all_checked)
        self.outer.insertWidget(0, self.list)
        self.outer.insertWidget(1, self.select_all_box)
        self.list.itemChanged.connect(self._validate)
        self._validate()

    def set_all_checked(self, checked: bool) -> None:
        """Ticks or clears every submodel."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None:
                item.setCheckState(state)

    def names(self) -> list[str]:
        """Returns the texts of the rows, in order."""
        items = (self.list.item(row) for row in range(self.list.count()))
        return [item.text() for item in items if item is not None]

    def check(self, submodel: model.Submodel) -> None:
        """Ticks the row of a submodel."""
        for row in range(self.list.count()):
            item = self.list.item(row)
            if (
                item is not None
                and item.data(Qt.ItemDataRole.UserRole) is submodel
            ):
                item.setCheckState(Qt.CheckState.Checked)
                return
        raise LookupError(describe_object(submodel))

    def chosen(self) -> list[model.Submodel]:
        """Returns the ticked submodels, in the order of the list."""
        found: list[model.Submodel] = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                found.append(item.data(Qt.ItemDataRole.UserRole))
        return found

    def _validate(self) -> None:
        self._show_problem(
            "" if self.chosen() else "Tick at least one Submodel."
        )


class SpecificAssetIdDialog(_ValidatedDialog):
    """Asks for the name and the value of a specific asset id."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Builds the dialog.

        Args:
            parent: The parent widget.
        """
        super().__init__("Add specific asset id", parent)
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("for example serialNumber")
        self.value_edit = QLineEdit(self)
        self.form.addRow("name*", self.name_edit)
        self.form.addRow("value*", self.value_edit)
        self.name_edit.textChanged.connect(self._validate)
        self.value_edit.textChanged.connect(self._validate)
        self._validate()

    def build(self) -> model.SpecificAssetId:
        """Makes the specific asset id.

        Raises:
            AssetInformationError: If the name or the value is empty.
        """
        return build_specific_asset_id(
            self.name_edit.text(), self.value_edit.text()
        )

    def _validate(self) -> None:
        try:
            self.build()
        except AssetInformationError as error:
            self._show_problem(str(error))
        else:
            self._show_problem("")
