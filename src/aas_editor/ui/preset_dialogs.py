"""The dialog that picks a preset to add to the selection.

It shows what `aas_editor.infrastructure.preset_files` loaded: a filtered list
of the names, the JSON of the chosen preset, a field for the value of a preset
that has none, and the problems found in the preset files. A file with a
problem never stops the dialog from opening.
"""

import json
from pathlib import Path

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFormLayout
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.presets import FILE_NAMES
from aas_editor.domain.presets import Preset
from aas_editor.infrastructure.preset_files import USER
from aas_editor.infrastructure.preset_files import LoadedPresets
from aas_editor.infrastructure.preset_files import ensure_user_dir
from aas_editor.ui.dialog_layout import finish_dialog


class PresetDialog(QDialog):
    """Lists the presets of one kind and picks one."""

    def __init__(
        self,
        kind: MemberKind,
        loaded: LoadedPresets,
        user_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        """Creates the dialog.

        Args:
            kind: What the presets make.
            loaded: The presets and the problems of their files.
            user_dir: The folder with the files of the user.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._kind = kind
        self._loaded = loaded
        self._user_dir = user_dir
        self._shown: list[Preset] = []
        self.setWindowTitle(f"Add {kind.label} from a preset")
        self.resize(560, 520)

        self.filterEdit = QLineEdit(self)
        self.filterEdit.setPlaceholderText("Filter by name")
        self.filterEdit.setClearButtonEnabled(True)
        self.list = QListWidget(self)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.valueEdit = QLineEdit(self)
        self.valueLabel = QLabel("&Value:", self)
        self.valueLabel.setBuddy(self.valueEdit)
        self.problemLabel = QLabel(self)
        self.problemButton = QPushButton("Details...", self)
        self.folderButton = QPushButton("Open presets folder", self)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.addButton = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if self.addButton is not None:
            self.addButton.setText("Add")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        problems = QHBoxLayout()
        problems.addWidget(self.problemLabel, 1)
        problems.addWidget(self.problemButton)
        value = QFormLayout()
        value.addRow(self.valueLabel, self.valueEdit)
        layout = QVBoxLayout(self)
        layout.addWidget(self.filterEdit)
        layout.addWidget(self.list, 2)
        layout.addWidget(self.preview, 1)
        layout.addLayout(value)
        layout.addLayout(problems)
        layout.addWidget(self.folderButton)
        layout.addWidget(self.buttons)
        finish_dialog(self)

        self.filterEdit.textChanged.connect(self._fill)
        self.list.currentRowChanged.connect(self._row_changed)
        self.valueEdit.textChanged.connect(self._update_buttons)
        self.problemButton.clicked.connect(self._show_problems)
        self.folderButton.clicked.connect(self._open_folder)
        count = len(loaded.problems)
        self.problemLabel.setText(
            f"{count} problem{'s' if count != 1 else ''} in the preset files"
            if count
            else ""
        )
        self.problemLabel.setVisible(bool(count))
        self.problemButton.setVisible(bool(count))
        self._fill()

    @property
    def chosen(self) -> Preset | None:
        """The selected preset, or None."""
        row = self.list.currentRow()
        return self._shown[row] if 0 <= row < len(self._shown) else None

    @property
    def value(self) -> str | None:
        """The value typed for a preset that has none, or None."""
        chosen = self.chosen
        if chosen is None or not chosen.value_required:
            return None
        return self.valueEdit.text()

    def choose(self, name: str) -> None:
        """Selects the preset with a name."""
        self.filterEdit.clear()
        for row, preset in enumerate(self._shown):
            if preset.name == name:
                self.list.setCurrentRow(row)
                return
        raise LookupError(name)

    def _fill(self, *_: object) -> None:
        wanted = self.filterEdit.text().strip().casefold()
        self._shown = [
            preset
            for preset in self._loaded.presets
            if wanted in preset.name.casefold()
        ]
        self.list.clear()
        for preset in self._shown:
            label = preset.name + ("  (yours)" if preset.source == USER else "")
            QListWidgetItem(label, self.list)
        if self._shown:
            self.list.setCurrentRow(0)
        self._row_changed()

    def _row_changed(self, *_: object) -> None:
        chosen = self.chosen
        self.preview.setPlainText(
            "" if chosen is None else json.dumps(chosen.data, indent=2)
        )
        needs_value = chosen is not None and chosen.value_required
        self.valueEdit.setVisible(needs_value)
        self.valueLabel.setVisible(needs_value)
        self._update_buttons()

    def _update_buttons(self, *_: object) -> None:
        chosen = self.chosen
        ready = chosen is not None and (
            not chosen.value_required or bool(self.valueEdit.text().strip())
        )
        if self.addButton is not None:
            self.addButton.setEnabled(ready)

    def _show_problems(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Preset files")
        box.setText(
            "These entries were not used. The others work. Fix the file "
            f"{FILE_NAMES[self._kind]} in the presets folder of the user."
        )
        box.setDetailedText("\n".join(str(p) for p in self._loaded.problems))
        box.exec()

    def _open_folder(self) -> None:
        if ensure_user_dir(self._user_dir):
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._user_dir)))


def ask_preset(
    kind: MemberKind,
    loaded: LoadedPresets,
    user_dir: Path,
    parent: QWidget | None = None,
) -> tuple[Preset, str | None] | None:
    """Opens the dialog and returns the preset and its value, or None."""
    dialog = PresetDialog(kind, loaded, user_dir, parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    chosen = dialog.chosen
    return None if chosen is None else (chosen, dialog.value)
