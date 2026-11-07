"""Reading and writing packages through `infrastructure.package_io`.

The module does not know the legacy `Package`. These tests use it directly,
with real files, and also guard the assumptions about the SDK that its three
workarounds rest on. When a guard fails after an SDK upgrade, the matching
workaround can go.
"""

import io
import logging
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pytest

from aas_workingbench.application.save import SaveOptions
from aas_workingbench.domain.parts import Thumbnail
from aas_workingbench.infrastructure.package_io import PackageParts
from aas_workingbench.infrastructure.package_io import read_package
from aas_workingbench.infrastructure.package_io import write_package
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx
from tests.package_factories import ANNOTATION_BYTES
from tests.package_factories import ANNOTATION_PART
from tests.package_factories import DOCUMENT_PART
from tests.package_factories import MISSING_PART
from tests.package_factories import SHARED_ID
from tests.package_factories import write_package_with_file_in_annotation
from tests.package_factories import write_package_with_same_id_in_two_parts
from tests.package_factories import write_package_with_missing_file

OPTIONS = SaveOptions()


def _parts_with(*elements: model.SubmodelElement) -> PackageParts:
    submodel = make_submodel(elements=elements)
    return PackageParts(objects=make_store(make_shell(), submodel))


# ---------------------------------------------------------------------------
# Layer rule
# ---------------------------------------------------------------------------


def test_module_does_not_import_package_or_qt_when_it_is_imported() -> None:
    code = (
        "import sys, aas_workingbench.infrastructure.package_io\n"
        "print([n for n in sys.modules if n == 'aas_workingbench.package' "
        "or n.split('.')[0] == 'PyQt6'])"
    )

    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_read_package_records_missing_file_and_keeps_value(
    tmp_path: Path,
) -> None:
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")

    parts = read_package(path)

    assert [(m.part_name, m.path) for m in parts.missing_files] == [
        ("/aasx/data.xml", MISSING_PART)
    ]
    assert sorted(parts.files) == [DOCUMENT_PART]


def test_read_package_loads_file_when_only_an_annotation_refers_to_it(
    tmp_path: Path,
) -> None:
    path = write_package_with_file_in_annotation(tmp_path / "annotation.aasx")

    parts = read_package(path)

    buffer = io.BytesIO()
    parts.files.write_file(ANNOTATION_PART, buffer)
    assert buffer.getvalue() == ANNOTATION_BYTES


def test_read_package_captures_thumbnail_name_and_content_type(
    tmp_path: Path,
) -> None:
    path = write_aasx(
        tmp_path / "thumbnail.aasx",
        make_store(make_shell()),
        thumbnail=("/docProps/thumbnail.png", b"\x89PNGsmall", "image/png"),
    )

    parts = read_package(path)

    assert parts.thumbnail == Thumbnail(
        "/docProps/thumbnail.png", "image/png", b"\x89PNGsmall"
    )


def test_read_package_has_no_thumbnail_or_properties_when_package_has_none(
    tmp_path: Path,
) -> None:
    path = write_aasx(tmp_path / "plain.aasx", make_store(make_shell()))

    parts = read_package(path)

    assert parts.thumbnail is None
    assert parts.core_properties is None


@pytest.mark.parametrize("failsafe", [False, True])
def test_read_package_marks_partial_only_when_failsafe(
    tmp_path: Path, failsafe: bool
) -> None:
    path = write_aasx(tmp_path / "plain.aasx", make_store(make_shell()))

    parts = read_package(path, failsafe=failsafe)

    assert parts.partial is failsafe
    assert parts.source_file == path


@pytest.mark.parametrize("suffix", [".json", ".xml"])
def test_read_package_reads_json_and_xml_without_package_parts(
    tmp_path: Path, suffix: str
) -> None:
    path = tmp_path / f"plain{suffix}"
    write_package(path, _parts_with(make_property("Name")), OPTIONS)

    parts = read_package(path)

    assert sorted(obj.id for obj in parts.objects) == [
        "urn:uuid:00000000-0000-4000-8000-000000000001",
        "urn:uuid:00000000-0000-4000-8000-000000000002",
    ]
    assert parts.thumbnail is None
    assert len(parts.files) == 0


def test_read_package_raises_when_extension_is_unknown(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    path.write_text("not a package")

    with pytest.raises(TypeError):
        read_package(path)


def test_read_package_releases_file_when_it_returns(tmp_path: Path) -> None:
    path = write_aasx(tmp_path / "plain.aasx", make_store(make_shell()))
    replacement = tmp_path / "replacement.aasx"
    replacement.write_bytes(b"x")
    read_package(path)

    # On Windows this raises PermissionError while a reader is open.
    os.replace(replacement, path)

    assert path.read_bytes() == b"x"


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_write_package_pretty_prints_json_when_option_is_set(
    tmp_path: Path,
) -> None:
    parts = _parts_with(make_property("Name"))
    pretty = tmp_path / "pretty.json"
    compact = tmp_path / "compact.json"

    write_package(pretty, parts, SaveOptions(pretty_json=True))
    write_package(compact, parts, SaveOptions(pretty_json=False))

    assert pretty.read_text(encoding="utf-8").count("\n") > 10
    assert compact.read_text(encoding="utf-8").count("\n") == 0


def test_write_package_writes_json_part_when_option_is_set(
    tmp_path: Path,
) -> None:
    path = tmp_path / "json_part.aasx"

    write_package(
        path,
        _parts_with(make_property("Name")),
        SaveOptions(write_json_in_aasx=True),
    )

    with zipfile.ZipFile(path) as archive:
        assert "aasx/data.json" in archive.namelist()


def test_write_package_leaves_no_temporary_file_when_it_fails(
    tmp_path: Path,
) -> None:
    parts = _parts_with(make_file_element("Document", DOCUMENT_PART))
    target = tmp_path / "out.aasx"

    with pytest.raises(KeyError):
        write_package(target, parts, OPTIONS)

    assert list(tmp_path.iterdir()) == []


def test_write_package_keeps_target_when_it_fails(tmp_path: Path) -> None:
    target = tmp_path / "out.aasx"
    target.write_bytes(b"previous content")
    parts = _parts_with(make_file_element("Document", DOCUMENT_PART))

    with pytest.raises(KeyError):
        write_package(target, parts, OPTIONS)

    assert target.read_bytes() == b"previous content"


def test_write_package_raises_before_touching_disk_when_extension_is_unknown(
    tmp_path: Path,
) -> None:
    with pytest.raises(TypeError):
        write_package(tmp_path / "out.txt", PackageParts(), OPTIONS)

    assert list(tmp_path.iterdir()) == []


def test_write_package_links_thumbnail_once_when_part_is_also_a_file(
    tmp_path: Path,
) -> None:
    part = "/aasx/files/asset.png"
    parts = PackageParts(
        objects=make_store(
            make_shell(
                asset_information=make_asset_information(
                    default_thumbnail=model.Resource(part, "image/png")
                )
            )
        ),
        thumbnail=Thumbnail(part, "image/png", b"\x89PNGdata"),
    )
    parts.files.add_file(part, io.BytesIO(b"\x89PNGdata"), "image/png")
    target = tmp_path / "out.aasx"

    write_package(target, parts, OPTIONS)

    with zipfile.ZipFile(target) as archive:
        assert archive.namelist().count("aasx/files/asset.png") == 1
    assert read_package(target).thumbnail == parts.thumbnail


# ---------------------------------------------------------------------------
# Guards: the SDK behavior that the workarounds rest on
# ---------------------------------------------------------------------------


def test_sdk_reader_raises_key_error_when_part_is_missing_even_if_failsafe(
    tmp_path: Path,
) -> None:
    # Without it, _TolerantReader is not needed for missing files.
    path = write_package_with_missing_file(tmp_path / "dangling.aasx")

    with (
        AASXReader(path.as_posix(), failsafe=True) as reader,
        pytest.raises(KeyError),
    ):
        reader.read_into(
            model.SetIdentifiableStore(), DictSupplementaryFileContainer()
        )


@pytest.mark.parametrize("failsafe", [False, True])
def test_sdk_reader_skips_an_object_of_a_second_part_without_a_log_record(
    tmp_path: Path, failsafe: bool
) -> None:
    # Without it, the tolerant reader no longer needs to find these objects
    # itself, and would report each of them twice.
    path = write_package_with_same_id_in_two_parts(tmp_path / "two.aasx")
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    logger = logging.getLogger("basyx")
    handler = Collect(level=logging.DEBUG)
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with AASXReader(path.as_posix(), failsafe=failsafe) as reader:
            store = model.SetIdentifiableStore[model.Identifiable]()
            reader.read_into(store, DictSupplementaryFileContainer())
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)

    kept = store.get(SHARED_ID)
    assert isinstance(kept, model.Submodel)
    assert kept.id_short == "First"
    assert [
        record.getMessage()
        for record in records
        if record.levelno > logging.DEBUG and SHARED_ID in record.getMessage()
    ] == []


def test_sdk_reader_skips_file_when_it_is_under_an_annotation(
    tmp_path: Path,
) -> None:
    # Without it, _TolerantReader no longer needs to read annotation files.
    path = write_package_with_file_in_annotation(tmp_path / "annotation.aasx")
    files = DictSupplementaryFileContainer()

    with AASXReader(path.as_posix(), failsafe=False) as reader:
        reader.read_into(model.SetIdentifiableStore(), files)

    assert list(files) == []


def test_sdk_writer_skips_file_when_it_is_under_an_annotation(
    tmp_path: Path,
) -> None:
    # Without it, the save no longer needs to refuse annotation files.
    path = write_package_with_file_in_annotation(tmp_path / "annotation.aasx")
    parts = read_package(path)
    assert list(parts.files) == [ANNOTATION_PART]
    target = tmp_path / "out.aasx"

    with AASXWriter(target.as_posix(), failsafe=False) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", parts.objects, parts.files
        )

    with zipfile.ZipFile(target) as archive:
        assert "aasx/files/annotation.txt" not in archive.namelist()


def test_sdk_writer_duplicates_part_when_thumbnail_is_also_a_file(
    tmp_path: Path,
) -> None:
    # Without it, _ThumbnailLinkingWriter can write the thumbnail normally.
    part = "/aasx/files/asset.png"
    store = make_store(
        make_shell(
            asset_information=make_asset_information(
                default_thumbnail=model.Resource(part, "image/png")
            )
        )
    )
    files = DictSupplementaryFileContainer()
    files.add_file(part, io.BytesIO(b"data"), "image/png")
    target = tmp_path / "out.aasx"

    with (
        pytest.warns(UserWarning, match="Duplicate name"),
        AASXWriter(target.as_posix(), failsafe=False) as writer,
    ):
        writer.write_all_aas_objects("/aasx/data.xml", store, files)
        writer.write_thumbnail(part, bytearray(b"data"), "image/png")


def test_sdk_get_thumbnail_returns_only_bytes(tmp_path: Path) -> None:
    # Without it, the part name and content type need no extra reading.
    path = write_aasx(
        tmp_path / "thumbnail.aasx",
        make_store(make_shell()),
        thumbnail=("/docProps/thumbnail.png", b"\x89PNGsmall", "image/png"),
    )

    with AASXReader(path.as_posix()) as reader:
        thumbnail = reader.get_thumbnail()

    assert isinstance(thumbnail, bytes)
