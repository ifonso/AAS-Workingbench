"""Files that a package declares are the user's content, and a save keeps them.

An AASX declares its supplementary files with an `aas-suppl` relationship from
the AAS part. The SDK reads only the files that a File element or the
thumbnail names, so the Technical Data template, which declares six images
and names one, lost five of them silently. These tests read and write through
`infrastructure.package_io`, with packages whose declarations are written
through the public API of the SDK writer.
"""

import io
from pathlib import Path
import zipfile

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pyecma376_2
from pyecma376_2.package_model import normalize_part_name
import pytest

from aas_workingbench.application.save import SaveOptions
from aas_workingbench.application.save import check_save
from aas_workingbench.domain.load_report import Outcome
from aas_workingbench.domain.load_report import Scope
from aas_workingbench.infrastructure.package_io import PackageParts
from aas_workingbench.infrastructure.package_io import read_package
from aas_workingbench.infrastructure.package_io import write_package
from tests.factories import make_asset_information
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.package_factories import OLD_SUPPL_RELATIONSHIP
from tests.package_factories import SUPPL_RELATIONSHIP
from tests.package_factories import write_aasx_declaring_files

OPTIONS = SaveOptions()
COVER = "/aasx/files/coverpage.png"
FIRST = "/aasx/files/first.png"
SECOND = "/aasx/files/second.png"
THIRD = "/aasx/files/third.jpg"
COVER_BYTES = b"\x89PNG cover"
FIRST_BYTES = b"\x89PNG first"
SECOND_BYTES = b"\x89PNG second"
THIRD_BYTES = b"\xff\xd8 third"
DECLARED = {
    FIRST: (FIRST_BYTES, "image/png"),
    SECOND: (SECOND_BYTES, "image/png"),
    THIRD: (THIRD_BYTES, "image/jpeg"),
}


def _technical_data(tmp_path: Path, **options: object) -> Path:
    """A package like Technical Data: one image named, three only declared."""
    submodel = make_submodel(elements=[make_file_element("Cover", COVER)])
    return write_aasx_declaring_files(
        tmp_path / "declared.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
        DECLARED,
        referenced_files={COVER: (COVER_BYTES, "image/png")},
        **options,  # pyright: ignore[reportArgumentType]
    )


def _stored(parts: PackageParts) -> dict[str, tuple[str, bytes]]:
    stored: dict[str, tuple[str, bytes]] = {}
    for name in parts.files:
        content = _read(parts, name)
        stored[name] = (parts.files.get_content_type(name), content)
    return stored


def _read(parts: PackageParts, name: str) -> bytes:
    buffer = io.BytesIO()
    parts.files.write_file(name, buffer)
    return buffer.getvalue()


def _declared_parts(path: Path) -> set[str]:
    """The parts that the AAS parts declare, read from the zip itself."""
    with pyecma376_2.ZipPackageReader(path.as_posix()) as reader:
        origin = next(
            names[0]
            for kind, names in reader.get_related_parts_by_type().items()
            if kind.endswith("/aasx-origin") and names
        )
        declared: set[str] = set()
        for kind, specs in reader.get_related_parts_by_type(origin).items():
            if not kind.endswith("/aas-spec"):
                continue
            for spec in specs:
                for suffix, names in reader.get_related_parts_by_type(
                    spec
                ).items():
                    if suffix.endswith("/aas-suppl"):
                        # OPC compares names without case, and the SDK writes
                        # the target of a relationship in lower case.
                        declared.update(normalize_part_name(n) for n in names)
        return declared


# ---------------------------------------------------------------------------
# Guards for the SDK, in the way of tests/medium/test_package_io.py
# ---------------------------------------------------------------------------


def test_the_sdk_reader_loads_only_the_files_that_a_file_element_names(
    tmp_path: Path,
) -> None:
    # When this fails after an upgrade, `read_declared_files` can go.
    path = _technical_data(tmp_path)
    store = DictSupplementaryFileContainer()

    with AASXReader(path.as_posix()) as reader:
        reader.read_into(model.DictIdentifiableStore(), store)

    assert list(store) == [COVER]


def test_the_sdk_writer_declares_what_the_additional_relationships_name(
    tmp_path: Path,
) -> None:
    # `_write_aasx` relies on `additional_relationships` and on the public
    # `writer`. When this fails, ADR 0030 needs another way to write the files
    # that nothing refers to.
    path = _technical_data(tmp_path)

    assert _declared_parts(path) == {COVER, FIRST, SECOND, THIRD}


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def test_read_loads_files_that_only_the_package_declares(
    tmp_path: Path,
) -> None:
    parts = read_package(_technical_data(tmp_path))

    assert _stored(parts) == {
        COVER: ("image/png", COVER_BYTES),
        FIRST: ("image/png", FIRST_BYTES),
        SECOND: ("image/png", SECOND_BYTES),
        THIRD: ("image/jpeg", THIRD_BYTES),
    }
    assert not parts.load_report
    assert not parts.partial


def test_read_loads_files_declared_with_the_old_relationship_type(
    tmp_path: Path,
) -> None:
    path = _technical_data(tmp_path, relationship_type=OLD_SUPPL_RELATIONSHIP)

    parts = read_package(path)

    assert {FIRST, SECOND, THIRD} <= set(parts.files)


def test_read_keeps_the_spelling_of_the_part_when_the_target_is_lower_case(
    tmp_path: Path,
) -> None:
    # The SDK writes the target of a relationship in lower case.
    part = "/aasx/files/Photo.JPG"
    path = write_aasx_declaring_files(
        tmp_path / "case.aasx",
        make_store(make_shell(), make_submodel()),
        {part: (THIRD_BYTES, "image/jpeg")},
        declared=[part.lower()],
    )

    parts = read_package(path)

    assert list(parts.files) == [part]


def test_read_loads_a_declared_file_once_when_a_file_element_names_it_too(
    tmp_path: Path,
) -> None:
    submodel = make_submodel(elements=[make_file_element("First", FIRST)])
    path = write_aasx_declaring_files(
        tmp_path / "shared.aasx",
        make_store(make_shell(submodels=[submodel]), submodel),
        {
            FIRST: (FIRST_BYTES, "image/png"),
            SECOND: (SECOND_BYTES, "image/png"),
        },
        referenced_files={FIRST: (FIRST_BYTES, "image/png")},
        declared=[FIRST, SECOND],
    )

    parts = read_package(path)

    assert sorted(parts.files) == [FIRST, SECOND]
    stored_submodel = parts.objects.get_item(submodel.id)
    assert isinstance(stored_submodel, model.Submodel)
    element = stored_submodel.get_referable("First")
    assert isinstance(element, model.File)
    assert element.value == FIRST


def test_read_loads_a_declared_file_once_when_it_is_declared_twice(
    tmp_path: Path,
) -> None:
    path = _technical_data(tmp_path, declared=[FIRST, SECOND, FIRST, THIRD])

    parts = read_package(path)

    assert sorted(parts.files) == sorted([COVER, FIRST, SECOND, THIRD])
    assert not parts.load_report


def test_read_loads_a_declared_file_once_when_two_parts_declare_it(
    tmp_path: Path,
) -> None:
    other = make_submodel(
        id_="urn:uuid:00000000-0000-4000-8000-0000000000bb",
        id_short="Other",
        elements=[make_property("Name")],
    )
    path = write_aasx_declaring_files(
        tmp_path / "two.aasx",
        make_store(make_shell(), make_submodel()),
        {FIRST: (FIRST_BYTES, "image/png")},
        second_part=(make_store(other), [FIRST]),
    )

    parts = read_package(path)

    assert list(parts.files) == [FIRST]
    assert not parts.load_report


def test_read_reports_a_declared_file_that_is_not_in_the_package(
    tmp_path: Path,
) -> None:
    path = _technical_data(
        tmp_path, declared=[FIRST, "/aasx/files/gone.png", SECOND]
    )

    parts = read_package(path)

    assert {FIRST, SECOND} <= set(parts.files)
    (issue,) = parts.load_report.issues
    assert issue.outcome is Outcome.LEFT_OUT
    assert issue.scope is Scope.PART
    assert "/aasx/files/gone.png" in issue.describe()
    assert not parts.partial


def test_read_reports_a_declared_file_whose_name_the_package_cannot_write(
    tmp_path: Path,
) -> None:
    source = _technical_data(tmp_path)
    path = tmp_path / "umlaut.aasx"
    name = "/aasx/files/bär.png"
    with (
        zipfile.ZipFile(source) as original,
        zipfile.ZipFile(path, "w") as changed,
    ):
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "aasx/_rels/data.xml.rels":
                data = data.replace(
                    b"</Relationships>",
                    b'<Relationship Id="x" Type="'
                    + SUPPL_RELATIONSHIP.encode()
                    + b'" Target="'
                    + name.encode("utf-8")
                    + b'"/></Relationships>',
                )
            changed.writestr(item.filename, data)
        changed.writestr(name.lstrip("/"), b"data")

    parts = read_package(path)

    assert name not in parts.files
    assert {FIRST, SECOND, THIRD} <= set(parts.files)
    assert any(name in issue.describe() for issue in parts.load_report.issues)


# ---------------------------------------------------------------------------
# The Technical Data template, which declares six images
# ---------------------------------------------------------------------------

TECHNICAL_DATA = (
    Path(__file__).parents[2]
    / "src"
    / "aas_workingbench"
    / "submodel_templates"
    / "Technical_Data"
    / "2"
    / "0"
    / "1"
    / "IDTA 02003_2-0-1_Template_TechnicalData.aasx"
)


def test_the_technical_data_template_lists_and_keeps_its_six_images(
    qapp: object, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package

    declared = _declared_parts(TECHNICAL_DATA)
    assert len(declared) == 6
    package = Package(TECHNICAL_DATA)
    saved = tmp_path / "technical_data.aasx"

    package.write(str(saved))

    assert len(list(package.fileStore)) == 6
    assert len(list(Package(saved).fileStore)) == 6
    assert _declared_parts(saved) == declared


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------


def test_save_keeps_every_declared_file_when_nothing_changed(
    tmp_path: Path,
) -> None:
    source = _technical_data(tmp_path)
    saved = tmp_path / "saved.aasx"

    write_package(saved, read_package(source), OPTIONS)

    assert _stored(read_package(saved)) == _stored(read_package(source))
    assert _declared_parts(saved) == {COVER, FIRST, SECOND, THIRD}


def test_save_keeps_a_file_that_nothing_refers_to_after_the_element_was_removed(
    tmp_path: Path,
) -> None:
    parts = read_package(_technical_data(tmp_path))
    submodel = next(o for o in parts.objects if isinstance(o, model.Submodel))
    submodel.submodel_element.remove(submodel.get_referable("Cover"))
    saved = tmp_path / "saved.aasx"

    write_package(saved, parts, OPTIONS)

    assert set(read_package(saved).files) == {COVER, FIRST, SECOND, THIRD}


def test_save_writes_each_part_once_when_a_declared_file_is_the_thumbnail(
    tmp_path: Path,
) -> None:
    from aas_workingbench.domain.parts import Thumbnail

    parts = read_package(_technical_data(tmp_path))
    parts.thumbnail = Thumbnail(FIRST, "image/png", FIRST_BYTES)
    saved = tmp_path / "saved.aasx"

    write_package(saved, parts, OPTIONS)

    with zipfile.ZipFile(saved) as archive:
        names = archive.namelist()
    assert len(names) == len(set(names))
    assert read_package(saved).thumbnail == parts.thumbnail
    assert FIRST in read_package(saved).files


def test_save_to_aasx_does_not_warn_about_files_that_nothing_refers_to(
    tmp_path: Path,
) -> None:
    parts = read_package(_technical_data(tmp_path))

    check = check_save(parts, tmp_path / "out.aasx", OPTIONS)

    assert check.warnings == ()
    assert check.blockers == ()


@pytest.mark.parametrize("name", ["out.json", "out.xml"])
def test_save_to_json_or_xml_warns_that_the_files_are_not_written(
    tmp_path: Path, name: str
) -> None:
    parts = read_package(_technical_data(tmp_path))

    check = check_save(parts, tmp_path / name, OPTIONS)

    (warning,) = [w for w in check.warnings if "supplementary" in w.message]
    assert set(warning.details) == {COVER, FIRST, SECOND, THIRD}


def test_save_keeps_declared_files_next_to_a_default_thumbnail(
    tmp_path: Path,
) -> None:
    shell = make_shell(
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(COVER, "image/png")
        )
    )
    source = write_aasx_declaring_files(
        tmp_path / "shell.aasx",
        make_store(shell),
        DECLARED,
        referenced_files={COVER: (COVER_BYTES, "image/png")},
    )
    saved = tmp_path / "saved.aasx"

    write_package(saved, read_package(source), OPTIONS)

    assert _declared_parts(saved) == {COVER, FIRST, SECOND, THIRD}
