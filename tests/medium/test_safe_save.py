"""Opening and saving packages without losing content.

Each test goes through the public `Package` API and real files. They cover the
defects that the safe-save work package fixes: packages that point to missing
parts, files under annotations, a failed save that damages the original, a
failed Save As that changes the target, and readers that stay open.
"""

import hashlib
import io
import os
from pathlib import Path
import zipfile

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
import pyecma376_2
import pytest

from aas_editor.package import Package
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx
from tests.package_factories import ANNOTATION_BYTES
from tests.package_factories import ANNOTATION_PART
from tests.package_factories import DOCUMENT_BYTES
from tests.package_factories import DOCUMENT_PART
from tests.package_factories import MISSING_PART
from tests.package_factories import write_aasx_tolerating_missing_files
from tests.package_factories import write_package_with_file_in_annotation
from tests.package_factories import write_package_with_missing_file


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _file_values(package: Package) -> dict[str, str | None]:
    submodel = next(iter(package.submodels))
    return {
        element.id_short: element.value
        for element in submodel.submodel_element
        if isinstance(element, model.File)
    }


@pytest.fixture(autouse=True)
def pinned_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    # The settings file of the user must not change what a save writes.
    monkeypatch.setattr(Package, "writeJsonInAasx", False)
    monkeypatch.setattr(Package, "writePrettyJson", True)
    monkeypatch.setattr(Package, "sortKeysInJson", True)


# ---------------------------------------------------------------------------
# A File element that points to a part that is not in the package
# ---------------------------------------------------------------------------


def test_open_records_missing_file_when_file_element_has_no_part(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")

    package = Package(path)

    assert [missing.path for missing in package.missingFiles] == [MISSING_PART]
    assert sorted(package.fileStore) == [DOCUMENT_PART]
    assert _file_values(package) == {
        "Document": DOCUMENT_PART,
        "Datasheet": MISSING_PART,
    }


def test_open_is_not_partial_when_file_element_has_no_part(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")

    package = Package(path)

    assert package.partial is False


def test_open_ignores_urls_when_file_element_points_outside_the_package(
    qapp: object, tmp_path: Path
) -> None:
    submodel = make_submodel(
        elements=[
            make_file_element("Web", "https://example.com/a.pdf"),
            make_file_element("Network", "//server/share/a.pdf"),
        ]
    )
    path = write_aasx(
        tmp_path / "urls.aasx", make_store(make_shell(), submodel)
    )

    package = Package(path)

    assert package.missingFiles == ()


def test_open_marks_package_partial_when_opened_in_failsafe_mode(
    qapp: object, aasx_file: Path
) -> None:
    package = Package(aasx_file, failsafe=True)

    assert package.partial is True


def test_open_does_not_mark_package_partial_when_opened_strictly(
    qapp: object, aasx_file: Path
) -> None:
    package = Package(aasx_file, failsafe=False)

    assert package.partial is False


def test_save_as_json_keeps_file_value_when_file_element_has_no_part(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(path)

    package.write(tmp_path / "copy.json")

    assert _file_values(Package(tmp_path / "copy.json")) == {
        "Document": DOCUMENT_PART,
        "Datasheet": MISSING_PART,
    }


# ---------------------------------------------------------------------------
# A File element under an annotation
# ---------------------------------------------------------------------------


def test_open_loads_file_when_only_an_annotation_references_it(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_file_in_annotation(tmp_path / "annotation.aasx")

    package = Package(path)

    assert sorted(package.fileStore) == [ANNOTATION_PART]
    assert package.missingFiles == ()


# ---------------------------------------------------------------------------
# A failed save leaves the original intact
# ---------------------------------------------------------------------------


def test_failed_save_keeps_original_when_writer_raises(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")
    before = _sha256(path)
    package = Package(path)

    # The SDK cannot write a File element without a stored file.
    with pytest.raises(KeyError):
        package.write()

    assert _sha256(path) == before
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [
        "dangling.aasx"
    ]


def test_failed_save_as_keeps_file_when_writer_raises(
    qapp: object, tmp_path: Path
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(path)
    original_file = package.file

    with pytest.raises(KeyError):
        package.write(tmp_path / "copy.aasx")

    assert package.file == original_file
    assert sorted(entry.name for entry in tmp_path.iterdir()) == [
        "dangling.aasx"
    ]


def test_failed_save_keeps_existing_target_when_save_as_overwrites_it(
    qapp: object, tmp_path: Path, aasx_file: Path
) -> None:
    target = tmp_path / "target.aasx"
    target.write_bytes(aasx_file.read_bytes())
    before = _sha256(target)
    source = write_package_with_missing_file(tmp_path / "dangling.aasx")
    package = Package(source)

    with pytest.raises(KeyError):
        package.write(target)

    assert _sha256(target) == before


def test_failed_save_keeps_original_when_the_replace_is_refused(
    qapp: object,
    tmp_path: Path,
    aasx_file: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The package was written completely, and then the system refused to put
    # it in place, as it does for a file that another program holds open.
    path = tmp_path / "held.aasx"
    path.write_bytes(aasx_file.read_bytes())
    before = _sha256(path)
    package = Package(path)

    def refuse(source: object, target: object) -> None:
        raise PermissionError("The file is in use")

    monkeypatch.setattr("os.replace", refuse)
    with pytest.raises(PermissionError):
        package.write()
    monkeypatch.undo()

    assert _sha256(path) == before
    assert sorted(entry.name for entry in tmp_path.iterdir()) == ["held.aasx"]


def test_failed_save_keeps_original_when_extension_is_unknown(
    qapp: object, aasx_file: Path, tmp_path: Path
) -> None:
    package = Package(aasx_file)
    original_file = package.file

    with pytest.raises(TypeError):
        package.write(tmp_path / "copy.txt")

    assert package.file == original_file
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("suffix", [".aasx", ".json", ".xml"])
def test_save_replaces_original_when_writer_succeeds(
    qapp: object, aasx_file: Path, tmp_path: Path, suffix: str
) -> None:
    package = Package(aasx_file)
    target = tmp_path / f"saved{suffix}"

    package.write(target)

    assert package.file == target.absolute()
    assert Package(target).numOfSubmodels == package.numOfSubmodels
    assert [entry.name for entry in tmp_path.iterdir()] == [target.name]


# ---------------------------------------------------------------------------
# Readers are closed, so a package can replace its own source on Windows
# ---------------------------------------------------------------------------


def test_save_overwrites_source_when_package_was_opened_from_it(
    qapp: object, tmp_path: Path, aasx_file: Path
) -> None:
    source = tmp_path / "source.aasx"
    source.write_bytes(aasx_file.read_bytes())
    package = Package(source)

    package.write()

    assert Package(source).numOfSubmodels == package.numOfSubmodels


def test_open_releases_the_file_when_package_is_loaded(
    qapp: object, tmp_path: Path, aasx_file: Path
) -> None:
    source = tmp_path / "source.aasx"
    source.write_bytes(aasx_file.read_bytes())
    replacement = tmp_path / "replacement.aasx"
    replacement.write_bytes(b"replacement")
    Package(source)

    # On Windows this raises PermissionError while a reader is still open.
    os.replace(replacement, source)

    assert source.read_bytes() == b"replacement"


# ---------------------------------------------------------------------------
# Saving no longer links submodels to the first AAS
# ---------------------------------------------------------------------------


def test_save_keeps_shell_references_when_submodel_is_not_linked(
    qapp: object, tmp_path: Path
) -> None:
    submodel = make_submodel()
    shell = make_shell()
    source = write_aasx(tmp_path / "unlinked.aasx", make_store(shell, submodel))
    package = Package(source)

    package.write(tmp_path / "saved.aasx")

    reloaded_shell = next(iter(Package(tmp_path / "saved.aasx").shells))
    assert len(reloaded_shell.submodel) == 0


# ---------------------------------------------------------------------------
# The package thumbnail, the core properties, and duplicate parts
# ---------------------------------------------------------------------------


# The source package is written with the SDK, which duplicates the part. That
# is the situation under test, and it warns.
@pytest.mark.filterwarnings("ignore:Duplicate name:UserWarning")
def test_save_does_not_duplicate_part_when_thumbnail_is_default_thumbnail(
    qapp: object, tmp_path: Path
) -> None:
    thumbnail_part = "/aasx/files/asset.png"
    shell = make_shell(
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(thumbnail_part, "image/png")
        )
    )
    source = write_aasx(
        tmp_path / "thumbnail.aasx",
        make_store(shell),
        files={thumbnail_part: (b"\x89PNGdata", "image/png")},
        thumbnail=(thumbnail_part, b"\x89PNGdata", "image/png"),
    )
    package = Package(source)

    package.write(tmp_path / "saved.aasx")

    with zipfile.ZipFile(tmp_path / "saved.aasx") as archive:
        names = archive.namelist()
    with AASXReader((tmp_path / "saved.aasx").as_posix()) as reader:
        thumbnail = reader.get_thumbnail()
    assert names.count("aasx/files/asset.png") == 1
    assert thumbnail == b"\x89PNGdata"


def test_save_keeps_package_thumbnail_when_thumbnail_is_a_separate_part(
    qapp: object, tmp_path: Path
) -> None:
    source = write_aasx(
        tmp_path / "thumbnail.aasx",
        make_store(make_shell()),
        thumbnail=("/docProps/thumbnail.png", b"\x89PNGsmall", "image/png"),
    )
    package = Package(source)

    package.write(tmp_path / "saved.aasx")

    assert package.thumbnail is not None
    assert package.thumbnail.name == "/docProps/thumbnail.png"
    assert package.thumbnail.content_type == "image/png"
    with zipfile.ZipFile(tmp_path / "saved.aasx") as archive:
        assert archive.read("docProps/thumbnail.png") == b"\x89PNGsmall"


def test_save_keeps_core_properties_when_package_has_them(
    qapp: object, tmp_path: Path
) -> None:
    properties = pyecma376_2.OPCCoreProperties()
    properties.creator = "Test Author"
    properties.title = "A title"
    source = write_aasx(
        tmp_path / "properties.aasx",
        make_store(make_shell()),
        core_properties=properties,
    )
    package = Package(source)

    package.write(tmp_path / "saved.aasx")

    with zipfile.ZipFile(tmp_path / "saved.aasx") as archive:
        core = archive.read("docProps/core.xml").decode("utf-8")
    assert "Test Author" in core
    assert "A title" in core


# ---------------------------------------------------------------------------
# Recovery keeps files that were added during the session
# ---------------------------------------------------------------------------


def test_recovery_keeps_session_files_when_package_gained_a_file(
    qapp: object, tmp_path: Path
) -> None:
    submodel = make_submodel(
        elements=[make_file_element("Document", DOCUMENT_PART)]
    )
    source = write_aasx(
        tmp_path / "source.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
        files={DOCUMENT_PART: (DOCUMENT_BYTES, "application/pdf")},
    )
    package = Package(source)
    package.fileStore.add_file(
        ANNOTATION_PART, io.BytesIO(ANNOTATION_BYTES), "text/plain"
    )
    next(iter(package.submodels)).submodel_element.add(
        make_file_element("Note", ANNOTATION_PART, "text/plain")
    )
    recovery_dir = tmp_path / "recovery"

    recovery = package.write_recovery(recovery_dir)
    restored = Package.restore_from_recovery(recovery, source)

    assert sorted(restored.fileStore) == [ANNOTATION_PART, DOCUMENT_PART]
    assert restored.file == source.absolute()


def test_recovery_keeps_thumbnail_when_package_has_one(
    qapp: object, tmp_path: Path
) -> None:
    source = write_aasx_tolerating_missing_files(
        tmp_path / "thumbnail.aasx",
        make_store(make_shell()),
        thumbnail=("/docProps/thumbnail.png", b"\x89PNGsmall", "image/png"),
    )
    package = Package(source)

    recovery = package.write_recovery(tmp_path / "recovery")
    restored = Package.restore_from_recovery(recovery, source)

    assert restored.thumbnail is not None
    assert restored.thumbnail.data == b"\x89PNGsmall"


# ---------------------------------------------------------------------------
# The object store follows edits of an id (D10)
# ---------------------------------------------------------------------------


def test_object_store_finds_submodel_by_new_id_when_id_was_edited(
    qapp: object, aasx_file: Path
) -> None:
    package = Package(aasx_file)
    submodel = next(iter(package.submodels))
    old_id = submodel.id

    submodel.id = "urn:uuid:11111111-1111-4111-8111-111111111111"

    assert (
        package.objStore.get_item(
            "urn:uuid:11111111-1111-4111-8111-111111111111"
        )
        is submodel
    )
    with pytest.raises(KeyError):
        package.objStore.get_item(old_id)


def test_object_store_refuses_second_submodel_when_id_is_taken_by_edit(
    qapp: object, aasx_file: Path
) -> None:
    package = Package(aasx_file)
    submodel = next(iter(package.submodels))
    submodel.id = "urn:uuid:11111111-1111-4111-8111-111111111111"

    with pytest.raises(KeyError):
        package.add(
            model.Submodel(id_="urn:uuid:11111111-1111-4111-8111-111111111111")
        )


def test_save_writes_new_id_when_id_was_edited(
    qapp: object, aasx_file: Path, tmp_path: Path
) -> None:
    package = Package(aasx_file)
    shell_ids = {shell.id for shell in package.shells}
    submodel = next(iter(package.submodels))
    submodel.id = "urn:uuid:11111111-1111-4111-8111-111111111111"

    package.write(tmp_path / "saved.json")

    reloaded = Package(tmp_path / "saved.json")
    assert "urn:uuid:11111111-1111-4111-8111-111111111111" in {
        obj.id for obj in reloaded.submodels
    }
    assert {shell.id for shell in reloaded.shells} == shell_ids
