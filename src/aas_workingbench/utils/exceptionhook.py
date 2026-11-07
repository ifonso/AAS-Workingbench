import sys
import logging
import traceback
from PyQt6 import QtWidgets

_on_crash_callback = None
_handling_exception = False


def set_crash_callback(cb):
    global _on_crash_callback
    _on_crash_callback = cb


def handle_exception(exc_type, exc_value, exc_traceback):
    """
    Solution from:
    https://stackoverflow.com/questions/6234405/logging-uncaught-exceptions-in-python
    - Ignore KeyboardInterrupt so a console python program can exit with Ctrl + C.

    Once the application runs, the exception is reported and the application
    keeps running, so that one failed action does not lose the open packages.
    Without an application there is nothing to report to, so the process exits.
    """
    global _handling_exception

    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    if _handling_exception:
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    _handling_exception = True
    try:
        logging.error(
            "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
        )

        if _on_crash_callback is not None:
            try:
                _on_crash_callback()
            except Exception:
                pass

        if QtWidgets.QApplication.instance() is None:
            sys.exit(1)

        box = QtWidgets.QMessageBox(None)
        box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        box.setText(f"An Exception was raised. Caught Exception: {exc_value}")
        box.setDetailedText(
            "".join(
                traceback.format_exception(exc_type, exc_value, exc_traceback)
            )
        )
        box.exec()
    finally:
        _handling_exception = False


sys.excepthook = handle_exception
