"""Round trip of a corpus of packages: read, save, and read again.

The corpus always holds the packages in tests/data. A local mode adds
packages outside the repository, such as Requester_screwing.aasx and the
samples of the Package Explorer. Set the environment variable
AAS_CORPUS_ROOT to the folder that contains them, for example:

    AAS_CORPUS_ROOT=C:/Users/me/code/asset-administration-shell

Without the variable, or when the folder has no samples, the local mode is
skipped.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.json import AASToJsonEncoder
import pyecma376_2
import pytest

from aas_editor.package import Package
from tests.factories import make_blob
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_asset_information
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx

TEST_DATA_DIR = Path(__file__).parents[1] / "data"
CORPUS_ROOT_VARIABLE = "AAS_CORPUS_ROOT"
SUFFIXES = (".aasx", ".json", ".xml")
THUMBNAIL_PART = "/aasx/files/asset.png"
THUMBNAIL_BYTES = b"\x89PNG\r\n\x1a\nthumbnail"
PACKAGE_THUMBNAIL_PART = "/package-thumbnail.png"
PACKAGE_THUMBNAIL_BYTES = b"\x89PNG\r\n\x1a\npackage thumbnail"
DOCUMENT_BYTES = b"%PDF-1.4 document"


@dataclass(frozen=True)
class Sample:
    """A package of the corpus."""

    path: Path
    label: str
    local: bool


def _local_corpus_root() -> Path | None:
    root = os.environ.get(CORPUS_ROOT_VARIABLE)
    if not root or not Path(root).is_dir():
        return None
    return Path(root)


def _find_local_samples(root: Path) -> list[Sample]:
    candidates = [root / "Requester_screwing.aasx"]
    candidates.extend(
        sorted((root / "package-explorer" / "src").rglob("*.aasx"))
    )
    samples = []
    seen_digests = set()
    for path in candidates:
        if not path.is_file():
            continue
        # The Package Explorer build folders hold copies of the same sample.
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen_digests:
            continue
        seen_digests.add(digest)
        samples.append(Sample(path, path.relative_to(root).as_posix(), True))
    return samples


def _corpus_params() -> list:
    params = [
        pytest.param(Sample(path, path.name, False), id=path.name)
        for path in sorted(TEST_DATA_DIR.iterdir())
        if path.suffix in SUFFIXES
    ]
    root = _local_corpus_root()
    local_samples = _find_local_samples(root) if root else []
    if not local_samples:
        params.append(
            pytest.param(
                None,
                id="local-samples",
                marks=pytest.mark.skip(
                    reason=f"Set {CORPUS_ROOT_VARIABLE} to a folder with "
                    "Requester_screwing.aasx or package-explorer/src samples"
                ),
            )
        )
    params.extend(
        pytest.param(sample, id=f"local:{sample.label}")
        for sample in local_samples
    )
    return params


@dataclass(frozen=True)
class RoundTrip:
    """A package before and after it was saved and read again."""

    original: Package
    reloaded: Package
    original_path: Path
    saved_path: Path


def _roundtrip(
    qapp: object, source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> RoundTrip:
    # Pin the settings that change what a save writes, so that the result
    # does not depend on the user's settings.ini. Adding Submodel references to
    # the first AAS when saving is a separate defect, tracked as D8.
    monkeypatch.setattr(Package, "allSubmodelRefsToAas", False)
    monkeypatch.setattr(Package, "writeJsonInAasx", False)
    monkeypatch.setattr(Package, "writePrettyJson", True)
    monkeypatch.setattr(Package, "sortKeysInJson", True)

    original = Package(source)
    saved_path = tmp_path / f"saved{source.suffix}"
    original.write(str(saved_path))
    reloaded = Package(saved_path)
    return RoundTrip(original, reloaded, source, saved_path)


@pytest.fixture(params=_corpus_params())
def roundtrip(
    request: pytest.FixtureRequest,
    qapp: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> RoundTrip:
    sample: Sample = request.param
    try:
        return _roundtrip(qapp, sample.path, tmp_path, monkeypatch)
    except Exception as error:
        if not sample.local:
            raise
        # Only a failure to read the sample is skipped, and its reason is
        # recorded. The first read is outside the save, so a failing save of a
        # readable package still fails.
        try:
            Package(sample.path)
        except Exception as read_error:
            pytest.skip(
                f"The SDK cannot read {sample.label}: "
                f"{type(read_error).__name__}: {str(read_error)[:200]}"
            )
        raise error


def _without_set_order(value: object) -> object:
    """Sorts the lists that the SDK keeps in a set, whose order is not stable.

    The SDK stores the pairs of a value list in a set, so the order in the file
    changes between two reads. It is not a loss of content.
    """
    if isinstance(value, dict):
        return {
            key: (
                sorted(
                    (_without_set_order(item) for item in items),
                    key=json.dumps,
                )
                if key == "valueReferencePairs"
                else _without_set_order(items)
            )
            for key, items in value.items()
        }
    if isinstance(value, list):
        return [_without_set_order(item) for item in value]
    return value


def _as_json(identifiable: model.Identifiable) -> dict:
    return _without_set_order(
        json.loads(json.dumps(identifiable, cls=AASToJsonEncoder))
    )  # pyright: ignore[reportReturnType]


def _objects_by_id(package: Package) -> dict[str, dict]:
    return {obj.id: _as_json(obj) for obj in package.objStore}


def _files(package: Package) -> dict[str, tuple[str, str]]:
    return {
        name: (
            package.fileStore.get_content_type(name),
            package.fileStore.get_sha256(name).hex(),
        )
        for name in package.fileStore
    }


def _thumbnail(path: Path) -> bytes | None:
    with AASXReader(path.as_posix()) as reader:
        return reader.get_thumbnail()


def _core_properties(path: Path) -> dict:
    with AASXReader(path.as_posix()) as reader:
        return dict(vars(reader.get_core_properties()))


def test_roundtrip_keeps_objects_when_saving(roundtrip: RoundTrip) -> None:
    before = _objects_by_id(roundtrip.original)
    after = _objects_by_id(roundtrip.reloaded)

    assert after == before


def test_roundtrip_keeps_supplementary_files_when_saving(
    roundtrip: RoundTrip,
) -> None:
    before = _files(roundtrip.original)
    after = _files(roundtrip.reloaded)

    assert after == before


@pytest.mark.xfail(
    reason="WP2 (safe save) preserves the thumbnail, which Package.write drops",
    strict=False,
)
def test_roundtrip_keeps_thumbnail_when_saving(roundtrip: RoundTrip) -> None:
    if roundtrip.original_path.suffix != ".aasx":
        pytest.skip("Only an AASX has a thumbnail part")
    before = _thumbnail(roundtrip.original_path)
    after = _thumbnail(roundtrip.saved_path)

    assert after == before


@pytest.mark.xfail(
    reason="WP2 (safe save) preserves the core properties, which Package.write drops",
    strict=False,
)
def test_roundtrip_keeps_core_properties_when_saving(
    roundtrip: RoundTrip,
) -> None:
    if roundtrip.original_path.suffix != ".aasx":
        pytest.skip("Only an AASX has core properties")
    before = _core_properties(roundtrip.original_path)
    after = _core_properties(roundtrip.saved_path)

    assert after == before


def test_local_samples_are_found_once_when_copies_exist(
    tmp_path: Path,
) -> None:
    sample = TEST_DATA_DIR / "TestPackage.aasx"
    (tmp_path / "package-explorer" / "src" / "a").mkdir(parents=True)
    (tmp_path / "package-explorer" / "src" / "b").mkdir(parents=True)
    (tmp_path / "Requester_screwing.aasx").write_bytes(sample.read_bytes())
    (tmp_path / "package-explorer/src/a/one.aasx").write_bytes(
        sample.read_bytes()
    )
    (tmp_path / "package-explorer/src/b/two.aasx").write_bytes(b"other")

    found = _find_local_samples(tmp_path)

    assert [s.label for s in found] == [
        "Requester_screwing.aasx",
        "package-explorer/src/b/two.aasx",
    ]


# ---------------------------------------------------------------------------
# A package with file parts, created through BaSyx
# ---------------------------------------------------------------------------


@pytest.fixture
def generated_aasx(tmp_path: Path) -> Path:
    submodel = make_submodel(
        elements=[
            make_file_element(
                "Document", "/aasx/files/document.pdf", "application/pdf"
            ),
            make_blob("Data", b"\x00\x01\x02", "application/octet-stream"),
        ]
    )
    shell = make_shell(
        submodels=[submodel],
        asset_information=make_asset_information(
            default_thumbnail=model.Resource(THUMBNAIL_PART, "image/png")
        ),
    )
    core_properties = pyecma376_2.OPCCoreProperties()
    core_properties.creator = "Test Author"
    core_properties.title = "Generated package"
    return write_aasx(
        tmp_path / "generated.aasx",
        make_store(shell, submodel),
        files={
            "/aasx/files/document.pdf": (DOCUMENT_BYTES, "application/pdf"),
            THUMBNAIL_PART: (THUMBNAIL_BYTES, "image/png"),
        },
        thumbnail=(
            PACKAGE_THUMBNAIL_PART,
            PACKAGE_THUMBNAIL_BYTES,
            "image/png",
        ),
        core_properties=core_properties,
    )


def test_roundtrip_keeps_file_parts_when_saving_generated_package(
    qapp: object,
    generated_aasx: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roundtrip = _roundtrip(qapp, generated_aasx, tmp_path, monkeypatch)

    assert _files(roundtrip.reloaded) == {
        "/aasx/files/document.pdf": (
            "application/pdf",
            hashlib.sha256(DOCUMENT_BYTES).hexdigest(),
        ),
        THUMBNAIL_PART: (
            "image/png",
            hashlib.sha256(THUMBNAIL_BYTES).hexdigest(),
        ),
    }
    assert _objects_by_id(roundtrip.reloaded) == _objects_by_id(
        roundtrip.original
    )


@pytest.mark.xfail(
    reason="WP2 (safe save) keeps the package thumbnail; Package.write drops it",
    strict=True,
)
def test_roundtrip_keeps_package_thumbnail_when_saving_generated_package(
    qapp: object,
    generated_aasx: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roundtrip = _roundtrip(qapp, generated_aasx, tmp_path, monkeypatch)

    assert _thumbnail(roundtrip.saved_path) == PACKAGE_THUMBNAIL_BYTES


@pytest.mark.xfail(
    reason="WP2 (safe save) keeps the core properties; Package.write drops them",
    strict=True,
)
def test_roundtrip_keeps_core_properties_when_saving_generated_package(
    qapp: object,
    generated_aasx: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    roundtrip = _roundtrip(qapp, generated_aasx, tmp_path, monkeypatch)

    assert _core_properties(roundtrip.saved_path) == _core_properties(
        generated_aasx
    )
