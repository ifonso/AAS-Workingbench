#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/
from collections.abc import Callable
from typing import Dict

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QScrollArea,
    QWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QLineEdit,
    QRadioButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from aas_workingbench.domain.default_languages import DefaultLanguagesError
from aas_workingbench.domain.default_languages import parse_default_languages
from aas_workingbench.domain.id_templates import check_id_template
from aas_workingbench.settings import AppSettings, Setting
from aas_workingbench.ui.colors import style_as_problem
from aas_workingbench.ui.dialog_layout import finish_dialog
from aas_workingbench.ui.dialog_layout import focus_first_field
from aas_workingbench.widgets.groupBoxes import OptionGroupBox


def _languages_problem(text: str) -> str | None:
    try:
        parse_default_languages(text)
    except DefaultLanguagesError as error:
        return str(error)
    return None


class TextSettingsGroupBox(OptionGroupBox):
    """Group box to type settings that are texts, one line for each.

    Each text has a check that returns what is wrong with it. The box shows
    the problem under the lines while the user types, and `problem` tells the
    dialog not to close while there is one.
    """

    def __init__(
        self,
        parent,
        title: str,
        description: str,
        settings: list[tuple[Setting, Callable[[str], str | None]]],
    ):
        super().__init__(parent)
        self.setTitle(title)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout = QVBoxLayout(self)
        if description:
            note = QLabel(description)
            note.setWordWrap(True)
            layout.addWidget(note)
        form = QFormLayout()
        layout.addLayout(form)
        self.fields: dict[str, QLineEdit] = {}
        self._settings = settings
        for setting, _ in settings:
            edit = QLineEdit(str(setting.value() or ""))
            edit.textChanged.connect(self._showProblem)
            self.fields[setting.name] = edit
            form.addRow(setting.display_name or setting.name, edit)
        self.problemLabel = QLabel()
        self.problemLabel.setWordWrap(True)
        style_as_problem(self.problemLabel)
        self.problemLabel.hide()
        layout.addWidget(self.problemLabel)
        self._showProblem()

    def problem(self) -> str | None:
        """Return what is wrong with the first text that is wrong, or None."""
        for setting, check in self._settings:
            problem = check(self.fields[setting.name].text().strip())
            if problem is not None:
                return f"{setting.display_name}: {problem}"
        return None

    def _showProblem(self) -> None:
        problem = self.problem()
        self.problemLabel.setText(problem or "")
        self.problemLabel.setVisible(problem is not None)

    def applyChosenOption(self):
        for setting, _ in self._settings:
            setting.setValue(self.fields[setting.name].text().strip())


class RadioBtnsGroupBox(OptionGroupBox):
    """Groupbox to choose default type of new file"""

    def __init__(
        self,
        parent,
        title,
        options: Dict[str, any],
        appSetting: Setting,
        description: str = None,
        **kwargs,
    ):
        super().__init__(parent, **kwargs)
        self.setTitle(title)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout = QHBoxLayout(self)
        self.setLayout(layout)

        self.appSetting = appSetting
        self.options = options

        self.description = None
        if description:
            self.description = QLabel(description)
            self.description.setWordWrap(True)
            layout.addWidget(self.description)

        self.radiobtns = []
        for optionName in self.options:
            btn = QRadioButton(optionName)
            self.radiobtns.append(btn)
            layout.addWidget(btn)
            if self.currOption() == options[optionName]:
                btn.setChecked(True)

    def find_checked_radiobutton(self):
        for btn in self.radiobtns:
            if btn.isChecked():
                return btn

    def currOption(self):
        return self.appSetting.value()

    def chosenOption(self):
        optionName = self.find_checked_radiobutton().text()
        chosenOption = self.options[optionName]
        return chosenOption

    def applyChosenOption(self):
        self.appSetting.setValue(self.chosenOption())


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")

        QBtn = (
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttonBox = QDialogButtonBox(QBtn)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.optionGroupBoxes = [
            RadioBtnsGroupBox(
                self,
                appSetting=setting,
                title=setting.display_name,
                options=setting.options,
                description=setting.description,
            )
            for setting in AppSettings.SETTINGS_TO_CHOOSE_BY_USER
        ]

        # The texts: the languages that new multi-language texts start with,
        # and the templates of generated ids (F-EDT-04 AC2, F-EDT-06 AC5).
        self.optionGroupBoxes.append(
            TextSettingsGroupBox(
                self,
                "Default languages",
                AppSettings.DEFAULT_LANGUAGES.description,
                [(AppSettings.DEFAULT_LANGUAGES, _languages_problem)],
            )
        )
        self.optionGroupBoxes.append(
            TextSettingsGroupBox(
                self,
                "Id templates",
                AppSettings.ID_TEMPLATE_DESCRIPTION,
                [
                    (setting, check_id_template)
                    for setting in (
                        AppSettings.ID_TEMPLATE_AAS,
                        AppSettings.ID_TEMPLATE_ASSET,
                        AppSettings.ID_TEMPLATE_SUBMODEL_INSTANCE,
                        AppSettings.ID_TEMPLATE_SUBMODEL_TEMPLATE,
                        AppSettings.ID_TEMPLATE_CONCEPT_DESCRIPTION,
                    )
                ],
            )
        )

        self.layout = QVBoxLayout()
        message = QLabel("App settings")
        self.layout.addWidget(message)
        # The boxes scroll, so that a small screen still reaches OK.
        body = QWidget()
        bodyLayout = QVBoxLayout(body)
        bodyLayout.setContentsMargins(0, 0, 0, 0)
        for groupbox in self.optionGroupBoxes:
            bodyLayout.addWidget(groupbox)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        self.layout.addWidget(scroll)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)
        finish_dialog(self)
        screen = QGuiApplication.primaryScreen()
        limit = (
            int(screen.availableGeometry().height() * 0.9) if screen else 700
        )
        wanted = body.sizeHint().height() + self.buttonBox.sizeHint().height()
        self.resize(
            max(body.sizeHint().width() + 40, 520), min(wanted + 60, limit)
        )

    def showEvent(self, event) -> None:
        super().showEvent(event)
        focus_first_field(self)

    def accept(self) -> None:
        # A text that cannot be used stays on screen with its reason.
        if any(
            isinstance(box, TextSettingsGroupBox) and box.problem() is not None
            for box in self.optionGroupBoxes
        ):
            return
        self.applySettings()
        super(SettingsDialog, self).accept()

    def applySettings(self) -> None:
        for optionGroupBox in self.optionGroupBoxes:
            optionGroupBox.applyChosenOption()
