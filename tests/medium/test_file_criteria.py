# ruff: noqa: F811
"""F-EDT-10 criteria that the first audit found open."""

from pathlib import Path
import zipfile

from tests.medium.test_package_files_ui import NOTE
from tests.medium.test_package_files_ui import DOC
from tests.medium.test_package_files_ui import controller  # noqa: F401
from tests.medium.test_package_files_ui import world  # noqa: F401


def _part(name: str) -> str:
    return name.lstrip("/")


def _saved_parts(package, path: Path) -> tuple[list[str], str]:
    """Save the package, and return its parts and the text of every relation."""
    package.write(path)
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        relations = "".join(
            archive.read(name).decode("utf-8")
            for name in names
            if name.endswith(".rels")
        )
    return names, relations


# -- AC3 ---------------------------------------------------------------------


def test_a_file_that_was_added_and_removed_before_a_save_is_not_written(
    world, controller, tmp_path: Path
) -> None:
    source = tmp_path / "later removed.pdf"
    source.write_bytes(b"%PDF new")
    world.answers.picked = source
    name = controller.add_from_disk()
    assert name is not None
    assert name in world.package.fileStore

    removed = controller.remove(name)
    names, relations = _saved_parts(world.package, tmp_path / "out.aasx")

    assert removed
    assert name not in world.package.fileStore
    assert _part(name) not in names
    assert "later_removed" not in relations


# -- AC4 ---------------------------------------------------------------------


def test_a_removed_file_is_gone_from_the_saved_package_with_its_relationship(
    world, controller, tmp_path: Path
) -> None:
    before_names, before_relations = _saved_parts(
        world.package, tmp_path / "before.aasx"
    )
    assert _part(DOC) in before_names
    assert "doc.pdf" in before_relations

    assert controller.remove(DOC)
    names, relations = _saved_parts(world.package, tmp_path / "after.aasx")

    assert _part(DOC) not in names
    assert "doc.pdf" not in relations
    # The other files and their relationships stay.
    assert _part(NOTE) in names
    assert "note.txt" in relations
    assert world.document.value is None
