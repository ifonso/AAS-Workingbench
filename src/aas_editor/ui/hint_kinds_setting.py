"""Keeps the kinds of hints that a user turned off in the user's settings.

The set lives in `application.hints`, which has no Qt. This module reads it from
the settings when a window starts, and writes it when the user changes it. The
kinds are the user's, so they are in the settings of the application and not in
the AASX file: a template leaves hints out on purpose, and the person who edits
it wants them off in every package.
"""

from aas_editor.application.hints import hint_kinds
from aas_editor.settings import app_settings
from aas_editor.settings.app_settings import AppSettings

SEPARATOR = ","


def load_hint_kinds() -> None:
    """Turns off the kinds that the settings say, and tells the views."""
    text = AppSettings.DISABLED_HINT_KINDS.value()
    saved = str(text) if text else ""
    hint_kinds().load(part for part in saved.split(SEPARATOR) if part)


def save_hint_kinds() -> None:
    """Writes the kinds that are off to the settings."""
    # The store is read from the module on each call, so that a test can point
    # it at a file of its own.
    app_settings.SETTINGS.setValue(
        AppSettings.DISABLED_HINT_KINDS.name,
        SEPARATOR.join(sorted(hint_kinds().off)),
    )
