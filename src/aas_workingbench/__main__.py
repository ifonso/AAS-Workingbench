#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import sys
import logging

from PyQt6 import QtWidgets
from aas_workingbench.utils import exceptionhook  # noqa: F401
from PyQt6 import QtWebEngineWidgets

logging.basicConfig(
    level=logging.INFO,
    filename="log.log",
    filemode="w",
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    app = QtWidgets.QApplication(sys.argv)

    from aas_workingbench.ui.theme.fonts import apply_application_font

    # Before the first module of the editor is imported, because some of them
    # read the font of the application when they are imported. The icons need
    # nothing here: they draw when they are shown, in the colors of the theme.
    apply_application_font(app)

    # The data folder of the user, where the recovery files go, is named by
    # these. They are the names of the recent files of the user, so that what
    # the program keeps for a user is under one name. After the font, because
    # the settings read a font when they are imported.
    from aas_workingbench.settings.app_settings import IAT
    from aas_workingbench.settings.app_settings import SETTINGS_APPLICATION_NAME

    app.setOrganizationName(IAT)
    app.setApplicationName(SETTINGS_APPLICATION_NAME)

    # Features add their actions before the first view exists.
    from aas_workingbench.ui.blob_actions import register_blob_actions

    register_blob_actions()

    from aas_workingbench.ui.file_actions import register_file_actions

    register_file_actions()

    from aas_workingbench.editorApp import EditorApp as CurrentApp
    from aas_workingbench.ui.reference_actions import register_reference_actions

    # The actions must be registered before the first tree view is created.
    register_reference_actions()

    from aas_workingbench.ui.move_actions import register_move_actions

    register_move_actions()

    from aas_workingbench.ui.paste_actions import register_paste_actions

    register_paste_actions()

    from aas_workingbench.ui.reference_jump import register_jump_actions

    register_jump_actions()

    from aas_workingbench.ui.create_actions import register_create_actions

    register_create_actions()

    from aas_workingbench.ui.shell_copy_actions import (
        register_shell_copy_actions,
    )

    register_shell_copy_actions()

    from aas_workingbench.ui.bulk_actions import register_bulk_actions

    register_bulk_actions()
    from aas_workingbench.ui.concept_actions import register_concept_actions

    register_concept_actions()

    from aas_workingbench.ui.conversion_actions import (
        register_conversion_actions,
    )

    register_conversion_actions()

    from aas_workingbench.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_workingbench.ui.preset_actions import register_preset_actions

    register_bulk_edit_actions()
    register_preset_actions()

    from aas_workingbench.ui.load_report_actions import (
        register_load_report_actions,
    )

    register_load_report_actions()

    from aas_workingbench.ui.location_actions import register_location_actions

    register_location_actions()

    # Check if a file path is provided as an argument
    fileToOpen = sys.argv[1] if len(sys.argv) > 1 else None

    window = CurrentApp(fileToOpen)

    window.show()

    # splash.setFocus()
    app.exec()


if __name__ == "__main__":
    main()
