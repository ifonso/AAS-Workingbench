import json
import logging
from pathlib import Path
import shutil
from typing import Iterable


def find_recovery_files(recovery_dir: Path) -> dict:
    """Return {original_path: recovery_path} for all valid recovery entries."""
    result = {}
    if not recovery_dir.exists():
        return result
    for meta_file in recovery_dir.glob("*.meta.json"):
        try:
            with open(meta_file, encoding="utf-8") as f:
                meta = json.load(f)
            # resolve() so the key matches the resolved open-file paths restore
            # compares against; an unresolved symlink/'..' would miss the match.
            original = Path(meta["original_path"]).resolve()
            recovery = recovery_dir / meta["recovery_filename"]
            if recovery.exists():
                result[original] = recovery
        except Exception:
            # Corrupt/unreadable meta: skip it, but log so a user who lost
            # recovery has a diagnostic instead of silence.
            logging.warning(
                "Skipping unreadable recovery meta file: %s",
                meta_file,
                exc_info=True,
            )
            continue
    return result


def delete_recovery_file(recovery_path: Path) -> None:
    """Delete a recovery data file and its sidecar .meta.json."""
    recovery_path.unlink(missing_ok=True)
    (recovery_path.parent / f"{recovery_path.stem}.files.json").unlink(
        missing_ok=True
    )
    (recovery_path.parent / f"{recovery_path.stem}.meta.json").unlink(
        missing_ok=True
    )


def cleanup_recovery_dir(recovery_dir: Path, keep: Iterable[Path] = ()) -> None:
    """Delete all files in the recovery dir except `keep` (and their .meta.json).

    `keep` holds recovery files of just-restored, not-yet-saved packages; the rest
    (declined, orphaned, leftover .tmp) are swept so the dir does not grow unbounded.
    """
    if not recovery_dir.exists():
        return
    keep_names = set()
    for rec in keep:
        keep_names.add(rec.name)
        keep_names.add(f"{rec.stem}.meta.json")
        keep_names.add(f"{rec.stem}.files.json")
    for entry in recovery_dir.iterdir():
        if entry.is_file() and entry.name not in keep_names:
            entry.unlink(missing_ok=True)


# The files of one recovery entry, by the end of their name. The meta file is
# last: `find_recovery_files` offers an entry only when it has one, so an entry
# that was copied halfway is never offered.
_ENTRY_SUFFIXES = (".json", ".aasx", ".files.json", ".meta.json")


def take_over_recovery_files(old_dir: Path, new_dir: Path) -> int:
    """Moves the recovery entries of an old folder to a new one.

    A release that kept its recovery files in the source tree left an unsaved
    session there, and the update must not lose it. Each entry is copied, the
    meta file last, and removed from the old folder afterwards. An entry that
    the new folder has already, which an updated program wrote later, is kept,
    and the old one is removed. Nothing is raised: an entry that cannot be moved
    stays where it is, and the reason is logged.

    Args:
        old_dir: The folder of earlier releases, which may not exist.
        new_dir: The folder that holds recovery files now.

    Returns:
        How many entries were taken over.
    """
    try:
        if not old_dir.is_dir() or old_dir.resolve() == new_dir.resolve():
            return 0
        stems = sorted(
            meta.name.removesuffix(".meta.json")
            for meta in old_dir.glob("*.meta.json")
        )
    except OSError:
        logging.warning(
            "Recovery folder cannot be read: %s", old_dir, exc_info=True
        )
        return 0
    taken = 0
    for stem in stems:
        try:
            if _take_over_entry(old_dir, new_dir, stem):
                taken += 1
        except OSError:
            logging.warning(
                "Recovery entry %s could not be taken over from %s",
                stem,
                old_dir,
                exc_info=True,
            )
    return taken


def _take_over_entry(old_dir: Path, new_dir: Path, stem: str) -> bool:
    """Copies one entry, and removes it from the old folder."""
    names = [f"{stem}{suffix}" for suffix in _ENTRY_SUFFIXES]
    present = [name for name in names if (old_dir / name).exists()]
    copied = False
    if not (new_dir / f"{stem}.meta.json").exists():
        new_dir.mkdir(parents=True, exist_ok=True)
        for name in present:
            shutil.copy2(old_dir / name, new_dir / name)
        copied = True
    for name in present:
        (old_dir / name).unlink(missing_ok=True)
    return copied
