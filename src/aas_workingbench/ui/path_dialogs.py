"""The dialogs that ask for a path on disk: a file to open, a file to save to, a folder.

Every part of the application asks through these functions, so that all of them
use the same kind of dialog.

On Linux the dialog of Qt is used, not the one of the desktop. The desktop dialog
comes from GTK, which the AppImage carries in another version than the system, or
from the desktop portal, a separate process that the application cannot place,
raise or close. Both left the window blocked behind a dialog that did not respond
(ADR 0032). In a Flatpak or a Snap the portal is the only way to reach the files
of the user, so there the desktop dialog stays. Windows and macOS keep theirs.
"""

from collections.abc import Mapping
import os
import sys

from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QWidget


def uses_native_dialog(
    platform: str | None = None, environ: Mapping[str, str] | None = None
) -> bool:
    """Tells whether the dialog of the desktop is used.

    Args:
        platform: The value of `sys.platform`. Default: the running system.
        environ: The environment variables. Default: those of the process.

    Returns:
        False on Linux and the other Unix systems, outside a Flatpak or Snap.
        True everywhere else.
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    if platform in ("win32", "darwin"):
        return True
    return "FLATPAK_ID" in environ or "SNAP" in environ


def dialog_options() -> QFileDialog.Option:
    """Returns the options that every path dialog is opened with."""
    if uses_native_dialog():
        return QFileDialog.Option(0)
    return QFileDialog.Option.DontUseNativeDialog


def get_open_file_name(
    parent: QWidget | None,
    caption: str = "",
    directory: str = "",
    name_filter: str = "",
) -> str:
    """Asks for an existing file.

    Args:
        parent: The window that the dialog belongs to.
        caption: The title of the dialog.
        directory: The folder, or the file, that the dialog starts at.
        name_filter: The file types offered, such as `"Images (*.png)"`.

    Returns:
        The path of the chosen file, or an empty string if the user cancelled.
    """
    path, _ = QFileDialog.getOpenFileName(
        parent, caption, directory, name_filter, options=dialog_options()
    )
    return path


def get_save_file_name(
    parent: QWidget | None,
    caption: str = "",
    directory: str = "",
    name_filter: str = "",
    initial_filter: str = "",
) -> str:
    """Asks for the file to write to.

    Args:
        parent: The window that the dialog belongs to.
        caption: The title of the dialog.
        directory: The folder, or the suggested file, that the dialog starts at.
        name_filter: The file types offered.
        initial_filter: The file type selected first, one of `name_filter`.

    Returns:
        The chosen path, or an empty string if the user cancelled.
    """
    path, _ = QFileDialog.getSaveFileName(
        parent,
        caption,
        directory,
        name_filter,
        initial_filter,
        options=dialog_options(),
    )
    return path


def get_existing_directory(
    parent: QWidget | None, caption: str = "", directory: str = ""
) -> str:
    """Asks for an existing folder.

    Args:
        parent: The window that the dialog belongs to.
        caption: The title of the dialog.
        directory: The folder that the dialog starts at.

    Returns:
        The chosen folder, or an empty string if the user cancelled.
    """
    return QFileDialog.getExistingDirectory(
        parent,
        caption,
        directory,
        options=QFileDialog.Option.ShowDirsOnly | dialog_options(),
    )
