"""Loading the preset files of the app and of the user.

The app ships one file for each kind of preset in `aas_editor/presets/`. The
user keeps files with the same names in a folder of their own, which the
composition root names (the `presets` folder next to `settings.ini`). A preset
of the user with the name of a shipped one replaces it, and the others are
added. See `aas_editor.domain.presets` for the format.

Files are untrusted. A missing user file is normal. A file that cannot be read,
is too large, or is no text is reported as a problem and skipped, and the
other files still load. Nothing here raises for the content or the state of a
file.

Example:
    Loading the qualifier presets::

        loaded = load_presets(
            MemberKind.QUALIFIER, SHIPPED_PRESETS_DIR, user_dir
        )
        names = [preset.name for preset in loaded.presets]
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.presets import FILE_NAMES
from aas_editor.domain.presets import MAX_FILE_CHARS
from aas_editor.domain.presets import Preset
from aas_editor.domain.presets import Problem
from aas_editor.domain.presets import merge_presets
from aas_editor.domain.presets import parse_presets

SHIPPED_PRESETS_DIR: Final = Path(__file__).resolve().parents[1] / "presets"
"""The folder with the presets that come with the app."""

SHIPPED: Final = "shipped"
USER: Final = "user"

# Four bytes cover the longest UTF-8 character, so a file of more characters
# than the limit is always longer than this.
_MAX_FILE_BYTES: Final = MAX_FILE_CHARS * 4


@dataclass(frozen=True)
class FileProblem:
    """A problem in one preset file.

    Attributes:
        path: The file.
        source: `shipped` or `user`.
        problem: What is wrong, in the file or one of its entries.
    """

    path: Path
    source: str
    problem: Problem

    def __str__(self) -> str:
        """Returns the problem with the name of the file."""
        return f"{self.path.name} ({self.source}): {self.problem}"


@dataclass(frozen=True)
class LoadedPresets:
    """The presets of one kind, after the shipped and the user files.

    Attributes:
        presets: The presets sorted by name, the user's replacing the app's.
        problems: What was refused, from both sources.
    """

    presets: tuple[Preset, ...]
    problems: tuple[FileProblem, ...]


def read_preset_file(
    path: Path, kind: MemberKind, source: str, required: bool
) -> tuple[tuple[Preset, ...], tuple[FileProblem, ...]]:
    """Reads one preset file.

    Args:
        path: The file.
        kind: What it holds.
        source: `shipped` or `user`.
        required: Whether a missing file is a problem. A user file is
            optional.

    Returns:
        The presets and the problems. Never raises for the file.
    """

    def refused(
        message: str,
    ) -> tuple[tuple[Preset, ...], tuple[FileProblem, ...]]:
        return (), (FileProblem(path, source, Problem("File", message)),)

    try:
        if not path.is_file():
            if path.exists():
                return refused("It is not a file")
            return refused("It is missing") if required else ((), ())
        if path.stat().st_size > _MAX_FILE_BYTES:
            return refused("The file is too large")
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        return refused("The file is not UTF-8 text")
    except OSError as error:
        return refused(f"The file cannot be read: {error.strerror or error}")
    parsed = parse_presets(text, kind, source)
    return parsed.presets, tuple(
        FileProblem(path, source, problem) for problem in parsed.problems
    )


def load_presets(
    kind: MemberKind, shipped_dir: Path, user_dir: Path | None
) -> LoadedPresets:
    """Loads the presets of one kind from the app and from the user.

    Args:
        kind: What to load.
        shipped_dir: The folder with the files that come with the app.
        user_dir: The folder with the files of the user. It may be missing.

    Returns:
        The merged presets and every problem found.
    """
    name = FILE_NAMES[kind]
    shipped, shipped_problems = read_preset_file(
        shipped_dir / name, kind, SHIPPED, required=True
    )
    user: tuple[Preset, ...] = ()
    user_problems: tuple[FileProblem, ...] = ()
    if user_dir is not None:
        user, user_problems = read_preset_file(
            user_dir / name, kind, USER, required=False
        )
    return LoadedPresets(
        tuple(merge_presets(shipped, user)),
        (*shipped_problems, *user_problems),
    )


def ensure_user_dir(user_dir: Path) -> bool:
    """Creates the folder for the presets of the user, if it is missing.

    Args:
        user_dir: The folder.

    Returns:
        Whether the folder exists afterwards.
    """
    try:
        user_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return user_dir.is_dir()
