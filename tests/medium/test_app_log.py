"""The log file goes to a folder that the program can write."""

from collections.abc import Iterator
import logging
from pathlib import Path

import pytest


@pytest.fixture
def started() -> Iterator[list[logging.Handler]]:
    """Removes the handlers that a test adds to the root logger."""
    root = logging.getLogger()
    handlers: list[logging.Handler] = []
    earlier = list(root.handlers)
    level = root.level
    yield handlers
    for handler in handlers:
        root.removeHandler(handler)
        handler.close()
    for handler in earlier:
        root.addHandler(handler)
    root.setLevel(level)


def test_the_log_is_written_to_the_given_folder(
    tmp_path: Path, started: list[logging.Handler]
) -> None:
    from aas_workingbench.infrastructure.app_log import start_log

    folder = tmp_path / "data" / "AAS Manager"
    started.append(start_log(folder))
    logging.getLogger("aas_workingbench").info("opened a package")
    started[0].flush()

    assert "opened a package" in (folder / "log.log").read_text("utf-8")


def test_the_program_starts_when_the_log_folder_cannot_be_written(
    tmp_path: Path, started: list[logging.Handler]
) -> None:
    from aas_workingbench.infrastructure.app_log import start_log

    blocked = tmp_path / "a file"
    blocked.write_text("")

    started.append(start_log(blocked / "folder"))

    assert not isinstance(started[0], logging.FileHandler)


def test_the_log_is_not_also_written_to_the_terminal(
    tmp_path: Path, started: list[logging.Handler]
) -> None:
    from aas_workingbench.infrastructure.app_log import start_log

    terminal = logging.StreamHandler()
    logging.getLogger().addHandler(terminal)

    started.append(start_log(tmp_path))

    assert logging.getLogger().handlers == started
