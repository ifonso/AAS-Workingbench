"""AASX files in the wild use the old `www.` relationship types.

The relationships of AASX first had `www.` in their namespace, and many files
still do. Such a file is a valid package, and all of its content opens.
"""

from pathlib import Path
import zipfile

import pytest
from tests.conftest import TEST_DATA_DIR

from aas_editor.application.save import SaveOptions
from aas_editor.infrastructure.package_io import read_package
from aas_editor.infrastructure.package_io import write_package

OLD = b"http://www.admin-shell.io/aasx/relationships/"
NEW = b"http://admin-shell.io/aasx/relationships/"
SOURCE = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.aasx"


def _with_old_relationships(source: Path, target: Path) -> Path:
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as changed,
    ):
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename.endswith(".rels"):
                data = data.replace(NEW, OLD)
            changed.writestr(item.filename, data)
    return target


def _relationships(path: Path) -> bytes:
    with zipfile.ZipFile(path) as package:
        return b"".join(
            package.read(name)
            for name in package.namelist()
            if name.endswith(".rels")
        )


@pytest.fixture
def old_package(tmp_path: Path) -> Path:
    path = _with_old_relationships(SOURCE, tmp_path / "old.aasx")
    assert OLD in _relationships(path)
    return path


def test_a_package_with_old_relationships_opens_strictly_with_its_content(
    old_package: Path,
) -> None:
    expected = read_package(SOURCE)

    parts = read_package(old_package)

    assert {o.id for o in parts.objects} == {o.id for o in expected.objects}
    assert len(list(parts.objects)) > 0
    assert not parts.partial
    assert not parts.load_report.issues


def test_saving_writes_the_current_relationships(
    old_package: Path, tmp_path: Path
) -> None:
    parts = read_package(old_package)
    saved = tmp_path / "saved.aasx"

    write_package(saved, parts, SaveOptions())

    written = _relationships(saved)
    assert NEW + b"aasx-origin" in written
    assert OLD not in written
    assert {o.id for o in read_package(saved).objects} == {
        o.id for o in parts.objects
    }
