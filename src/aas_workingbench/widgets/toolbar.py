#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

from typing import Optional

from PyQt6.QtCore import QSize
from PyQt6.QtWidgets import QToolBar, QWidget

from aas_workingbench.domain.design_tokens import ICON_SIZE
from aas_workingbench.settings.app_settings import TOOLBARS_HEIGHT


class ToolBar(QToolBar):
    def __init__(self, parent: Optional[QWidget] = ...):
        super(ToolBar, self).__init__(parent)
        self.setFixedHeight(TOOLBARS_HEIGHT)
        # 16 pixel icons in the button of a toolbar, as the plan sets.
        self.setIconSize(QSize(ICON_SIZE, ICON_SIZE))

    def toggleViewAction(self):
        action = super().toggleViewAction()
        action.setText("Command bar")
        action.setStatusTip("Show/hide the command bar")
        return action
