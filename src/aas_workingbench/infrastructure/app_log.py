"""The log file of the application.

The log goes to the data folder of the user, which the program can write when it
is installed, frozen, or started from a launcher. Earlier it went to `log.log` in
the current folder: the home folder when started from a launcher, or a folder
that cannot be written, where the program did not start at all.
"""

import logging
from pathlib import Path
import sys

LOG_FILE_NAME = "log.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(message)s"


def start_log(folder: Path) -> logging.Handler:
    """Sends the log of the application to a file in a folder.

    The file is written anew at each start. If it cannot be written, the log
    goes to the standard error stream, so that the program starts anyway. The
    handler replaces those that the root logger has.

    Args:
        folder: Where the log file goes. It is created if it is missing.

    Returns:
        The handler added to the root logger.
    """
    handler: logging.Handler
    try:
        folder.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(
            folder / LOG_FILE_NAME, mode="w", encoding="utf-8"
        )
        to_file = True
    except OSError:
        handler = logging.StreamHandler(sys.stderr)
        to_file = False
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root = logging.getLogger()
    # A record logged before this, through `logging.info` and the like, gave
    # the root logger a handler of its own that writes to the terminal.
    for earlier in list(root.handlers):
        root.removeHandler(earlier)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    if not to_file:
        logging.warning(
            "The log file cannot be written in %s, so the log goes here.",
            folder,
        )
    return handler
