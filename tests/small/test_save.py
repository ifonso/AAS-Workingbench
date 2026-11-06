from dataclasses import dataclass
from dataclasses import field
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pyecma376_2
import pytest
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.package_factories import make_annotated_relationship

from aas_editor.application.save import PackageFormat
from aas_editor.application.save import SaveCheck
from aas_editor.application.save import SaveOptions
from aas_editor.application.save import SaveStatus
from aas_editor.application.save import check_save
from aas_editor.application.save import package_format
from aas_editor.application.save import save
from aas_editor.domain.parts import Thumbnail

OPTIONS = SaveOptions()
DOCUMENT = "/aasx/files/document.pdf"
OTHER = "/aasx/files/other.pdf"


@dataclass
class FakeSource:
    """A package to save, with real BaSyx objects and in-memory files."""

    objects: model.SetIdentifiableStore = field(
        default_factory=model.SetIdentifiableStore
    )
    files: DictSupplementaryFileContainer = field(
        default_factory=DictSupplementaryFileContainer
    )
    thumbnail: Thumbnail | None = None
    core_properties: pyecma376_2.OPCCoreProperties | None = None
    partial: bool = False
    source_file: Path | None = None

    def store_file(self, name: str) -> None:
        self.files.add_file(name, io.BytesIO(b"content"), "application/pdf")


def _source_with_files(*paths: str, stored: tuple[str, ...] = ()) -> FakeSource:
    submodel = make_submodel(
        elements=[
            make_file_element(f"File{index}", path)
            for index, path in enumerate(paths)
        ]
    )
    source = FakeSource(objects=make_store(make_shell(), submodel))
    for name in stored:
        source.store_file(name)
    return source


# ---------------------------------------------------------------------------
# package_format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.aasx", PackageFormat.AASX),
        ("a.JSON", PackageFormat.JSON),
        ("a.xml", PackageFormat.XML),
    ],
)
def test_package_format_finds_format_when_extension_is_supported(
    name: str, expected: PackageFormat
) -> None:
    assert package_format(Path(name)) is expected


def test_package_format_raises_when_extension_is_unknown() -> None:
    with pytest.raises(TypeError):
        package_format(Path("a.txt"))


# ---------------------------------------------------------------------------
# Blockers
# ---------------------------------------------------------------------------


def test_check_save_blocks_aasx_when_file_has_no_stored_file() -> None:
    source = _source_with_files(DOCUMENT, OTHER, stored=(DOCUMENT,))

    check = check_save(source, Path("out.aasx"), OPTIONS)

    assert [issue.details for issue in check.blockers] == [
        ("File1 (/aasx/files/other.pdf)",)
    ]
    assert check.warnings == ()


def test_check_save_allows_json_when_file_has_no_stored_file() -> None:
    source = _source_with_files(OTHER)

    check = check_save(source, Path("out.json"), OPTIONS)

    assert check == SaveCheck()


def test_check_save_allows_aasx_when_file_value_is_a_url() -> None:
    source = _source_with_files(
        "https://example.com/a.pdf", "//server/a.pdf", "urn:example:a"
    )

    check = check_save(source, Path("out.aasx"), OPTIONS)

    assert check == SaveCheck()


def test_check_save_blocks_aasx_when_file_is_under_an_annotation() -> None:
    note = make_file_element("Note", DOCUMENT)
    submodel = make_submodel(
        elements=[make_annotated_relationship(annotations=(note,))]
    )
    source = FakeSource(objects=make_store(make_shell(), submodel))
    source.store_file(DOCUMENT)

    check = check_save(source, Path("out.aasx"), OPTIONS)

    assert [issue.details for issue in check.blockers] == [
        ("Annotated.Note (/aasx/files/document.pdf)",)
    ]


def test_check_save_blocks_when_partial_package_overwrites_its_source(
    tmp_path: Path,
) -> None:
    source = FakeSource(partial=True, source_file=tmp_path / "source.aasx")

    check = check_save(source, tmp_path / "source.aasx", OPTIONS)

    assert len(check.blockers) == 1
    assert "Save As" in check.blockers[0].message


def test_check_save_allows_partial_package_when_target_is_another_file(
    tmp_path: Path,
) -> None:
    source = FakeSource(partial=True, source_file=tmp_path / "source.aasx")

    check = check_save(source, tmp_path / "copy.aasx", OPTIONS)

    assert check == SaveCheck()


def test_check_save_allows_package_overwrite_when_it_is_not_partial(
    tmp_path: Path,
) -> None:
    source = FakeSource(source_file=tmp_path / "source.aasx")

    check = check_save(source, tmp_path / "source.aasx", OPTIONS)

    assert check == SaveCheck()


# ---------------------------------------------------------------------------
# Warnings
# ---------------------------------------------------------------------------


def test_check_save_warns_when_aasx_drops_unreferenced_files() -> None:
    source = _source_with_files(DOCUMENT, stored=(DOCUMENT, OTHER))

    check = check_save(source, Path("out.aasx"), OPTIONS)

    assert check.blockers == ()
    assert [issue.details for issue in check.warnings] == [(OTHER,)]


def test_check_save_does_not_warn_when_every_file_is_referenced() -> None:
    source = _source_with_files(DOCUMENT, stored=(DOCUMENT,))

    check = check_save(source, Path("out.aasx"), OPTIONS)

    assert check == SaveCheck()


@pytest.mark.parametrize("name", ["out.json", "out.xml"])
def test_check_save_warns_when_json_or_xml_drops_all_files(name: str) -> None:
    source = _source_with_files(DOCUMENT, stored=(DOCUMENT, OTHER))

    check = check_save(source, Path(name), OPTIONS)

    assert check.blockers == ()
    assert [issue.details for issue in check.warnings] == [(DOCUMENT, OTHER)]


def test_check_save_warns_when_json_drops_thumbnail_and_properties() -> None:
    source = FakeSource(
        thumbnail=Thumbnail("/t.png", "image/png", b"png"),
        core_properties=pyecma376_2.OPCCoreProperties(),
    )

    check = check_save(source, Path("out.json"), OPTIONS)

    assert [issue.details for issue in check.warnings] == [
        ("The package thumbnail", "The package properties")
    ]


def test_check_save_keeps_thumbnail_and_properties_when_target_is_aasx() -> (
    None
):
    source = FakeSource(
        thumbnail=Thumbnail("/t.png", "image/png", b"png"),
        core_properties=pyecma376_2.OPCCoreProperties(),
    )

    assert check_save(source, Path("out.aasx"), OPTIONS) == SaveCheck()


def test_check_save_lists_ten_names_when_many_files_are_dropped() -> None:
    source = FakeSource()
    for index in range(13):
        source.store_file(f"/aasx/files/f{index:02}.pdf")

    check = check_save(source, Path("out.json"), OPTIONS)

    details = check.warnings[0].details
    assert len(details) == 11
    assert details[-1] == "... and 3 more"


def test_check_save_raises_when_extension_is_unknown() -> None:
    with pytest.raises(TypeError):
        check_save(FakeSource(), Path("out.txt"), OPTIONS)


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class RecordingWriter:
    def __init__(self) -> None:
        self.targets: list[Path] = []

    def __call__(
        self, target: Path, source: object, options: SaveOptions
    ) -> None:
        self.targets.append(target)


def test_save_writes_without_asking_when_there_are_no_issues() -> None:
    writer = RecordingWriter()
    asked: list[SaveCheck] = []

    outcome = save(
        FakeSource(),
        Path("out.aasx"),
        OPTIONS,
        writer,
        lambda check: asked.append(check) or True,
    )

    assert outcome.status is SaveStatus.SAVED
    assert writer.targets == [Path("out.aasx")]
    assert asked == []


def test_save_writes_when_user_confirms_warnings() -> None:
    writer = RecordingWriter()
    source = _source_with_files(stored=(OTHER,))

    outcome = save(source, Path("out.aasx"), OPTIONS, writer, lambda _: True)

    assert outcome.status is SaveStatus.SAVED
    assert writer.targets == [Path("out.aasx")]
    assert len(outcome.check.warnings) == 1


def test_save_cancels_without_writing_when_user_declines_warnings() -> None:
    writer = RecordingWriter()
    source = _source_with_files(stored=(OTHER,))

    outcome = save(source, Path("out.aasx"), OPTIONS, writer, lambda _: False)

    assert outcome.status is SaveStatus.CANCELLED
    assert writer.targets == []


def test_save_refuses_without_asking_when_there_is_a_blocker() -> None:
    writer = RecordingWriter()
    asked: list[SaveCheck] = []
    source = _source_with_files(OTHER)

    outcome = save(
        source,
        Path("out.aasx"),
        OPTIONS,
        writer,
        lambda check: asked.append(check) or True,
    )

    assert outcome.status is SaveStatus.REFUSED
    assert len(outcome.check.blockers) == 1
    assert writer.targets == []
    assert asked == []


def test_save_passes_options_to_writer() -> None:
    received: list[SaveOptions] = []

    def writer(target: Path, source: object, options: SaveOptions) -> None:
        received.append(options)

    options = SaveOptions(write_json_in_aasx=True, pretty_json=False)

    save(FakeSource(), Path("out.aasx"), options, writer, lambda _: True)

    assert received == [options]
