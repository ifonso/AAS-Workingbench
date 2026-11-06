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
from aas_editor.utils import exceptionhook  # noqa: F401
from PyQt6 import QtWebEngineWidgets

logging.basicConfig(
    level=logging.INFO,
    filename="log.log",
    filemode="w",
    format="%(asctime)s | %(levelname)s | %(message)s",
)


def main():
    app = QtWidgets.QApplication(sys.argv)

    from aas_editor.settings.icons import initialize_all_icons

    # Initialize icons after QApp initialization to fix PyInstaller build errors.
    # QPixmap requires an active QApplication context; importing them earlier
    # causes the application to crash during initialization.
    initialize_all_icons()

    # Features add their actions before the first view exists.
    from aas_editor.ui.blob_actions import register_blob_actions

    register_blob_actions()

    from aas_editor.ui.file_actions import register_file_actions

    register_file_actions()

    from aas_editor.editorApp import EditorApp as CurrentApp
    from aas_editor.ui.reference_actions import register_reference_actions

    # The actions must be registered before the first tree view is created.
    register_reference_actions()

    from aas_editor.ui.move_actions import register_move_actions

    register_move_actions()

    from aas_editor.ui.paste_actions import register_paste_actions

    register_paste_actions()

    from aas_editor.ui.concept_actions import register_concept_actions

    register_concept_actions()

    from aas_editor.ui.conversion_actions import register_conversion_actions

    register_conversion_actions()

    # Check if a file path is provided as an argument
    fileToOpen = sys.argv[1] if len(sys.argv) > 1 else None

    window = CurrentApp(fileToOpen)

    window.show()

    # splash.setFocus()
    app.exec()


if __name__ == "__main__":
    main()
