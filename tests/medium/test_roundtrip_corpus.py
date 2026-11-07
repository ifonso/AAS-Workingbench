"""Round trip of a corpus of packages: read, save, and read again.

Each package is compared by its BaSyx objects and by its file parts: the
supplementary files, the package thumbnail, the core properties, and the zip
entries. The corpus has three sources:

* The packages in tests/data, always.
* The AASX templates in src/aas_workingbench/submodel_templates. A sample of them
  runs by default, and it always holds the templates that point to a file
  missing in the package. Set AAS_CORPUS_TEMPLATES=all to run every template:

      AAS_CORPUS_TEMPLATES=all uv run pytest tests/medium/test_roundtrip_corpus.py

* A local mode with packages outside the repository, such as
  Requester_screwing.aasx and the samples of the Package Explorer. Set
  AAS_CORPUS_ROOT to the folder that contains them, for example:

      AAS_CORPUS_ROOT=C:/Users/me/code/asset-administration-shell

  Without the variable, or when the folder has no samples, it is skipped.

A package that points to a file missing in the package cannot be written to an
AASX, so the round trip repairs it first, by clearing those File values. The
save flow refuses it before that, which test_save_is_refused_when_templates_*
checks.
"""

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import zipfile

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.json import AASToJsonEncoder
import pyecma376_2
from pyecma376_2.package_model import normalize_part_name
import pytest

from aas_workingbench.application.save import SaveOptions
from aas_workingbench.application.save import check_save
from aas_workingbench.domain.walking import walk_elements
from aas_workingbench.package import Package
from tests.factories import make_asset_information
from tests.factories import make_blob
from tests.factories import make_file_element
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.factories import write_aasx

TEST_DATA_DIR = Path(__file__).parents[1] / "data"
TEMPLATES_DIR = (
    Path(__file__).parents[2]
    / "src"
    / "aas_workingbench"
    / "submodel_templates"
)
CORPUS_ROOT_VARIABLE = "AAS_CORPUS_ROOT"
TEMPLATES_VARIABLE = "AAS_CORPUS_TEMPLATES"
SUFFIXES = (".aasx", ".json", ".xml")
# Every n-th template, in the order of the sorted paths, is in the default run.
TEMPLATE_SAMPLE_STEP = 8
THUMBNAIL_PART = "/aasx/files/asset.png"
THUMBNAIL_BYTES = b"\x89PNG\r\n\x1a\nthumbnail"
PACKAGE_THUMBNAIL_PART = "/package-thumbnail.png"
PACKAGE_THUMBNAIL_BYTES = b"\x89PNG\r\n\x1a\npackage thumbnail"
DOCUMENT_BYTES = b"%PDF-1.4 document"

# The templates whose File elements point to a part that is not in the
# package, with one such path. The SDK could not open them. They always run.
TEMPLATES_WITH_MISSING_FILES = {
    "IDTA 02027-1-0-1_Template_AIMC.aasx": (
        "/aasx/files/Siemens_Sentron_PAC4200.jpg"
    ),
    "IDTA 02027-1-0-1_Template_AIMC_forAASMetamodelV3.1.aasx": (
        "/aasx/files/Siemens_Sentron_PAC4200.jpg"
    ),
    "IDTA 02027-1-0_Template_AIMC.aasx": (
        "/aasx/files/Siemens_Sentron_PAC4200.jpg"
    ),
    "IDTA 02012-1-0_Template_DEXPI.aasx": "/aasx/C01V04-VER.EX01.xml",
    "IDTA 02004-2-0-1_Template_sample_HandoverDocumentation_forAASMetamodelV3.1.aasx": (
        "/aasx/files/datasheet_en.pdf"
    ),
    "IDTA 02004-2-0_Template_sample_HandoverDocumentation.aasx": (
        "/aasx/files/datasheet_en.pdf"
    ),
    "IDTA_02001-1-0-1_Submodel_MTPv1.0-rc2-with-documentation1_en.aasx": (
        "/aasx/Example.aml"
    ),
    "IDTA_02001-1-0-1_Submodel_MTPv1.0-rc2-with-documentation1_en_forAASMetamodelV3.1.aasx": (
        "/aasx/Example.aml"
    ),
    "IDTA 02067_Template_ProductionCalendar.aasx": (
        "/aasx/files/RFC5545-X-BREAK.txt"
    ),
    "IDTA 02067_Template_ProductionCalendar_forAASMetamodelV3.1.aasx": (
        "/aasx/files/RFC5545-X-BREAK.txt"
    ),
    "IDTA 02026-1-0-1_Template_ProvisionOf3DModels.aasx": (
        "/aasx/files/IDTA_02026-1-0_Cover_Thumbnail.png"
    ),
    "IDTA 02026-1-0-1_Template_ProvisionOf3DModels_forAASMetamodelV3.1.aasx": (
        "/aasx/files/IDTA_02026-1-0_Cover_Thumbnail.png"
    ),
    "IDTA02026-1-0_Template_ProvisionOf3DModels.aasx": (
        "/aasx/files/IDTA_02026-1-0_Cover_Thumbnail.png"
    ),
}
# The only template with a package thumbnail.
TEMPLATE_WITH_THUMBNAIL = (
    "IDTA 02029-1_Template_Sensor4.0_MeasurementValue.aasx"
)


@dataclass(frozen=True)
class Sample:
    """A package of the corpus."""

    path: Path
    label: str
    local: bool
    template: bool = False


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


def _template_samples() -> list[Sample]:
    templates = sorted(TEMPLATES_DIR.rglob("*.aasx"))
    if os.environ.get(TEMPLATES_VARIABLE) != "all":
        templates = [
            path
            for index, path in enumerate(templates)
            if index % TEMPLATE_SAMPLE_STEP == 0
            or path.name in TEMPLATES_WITH_MISSING_FILES
            or path.name == TEMPLATE_WITH_THUMBNAIL
        ]
    return [
        Sample(path, f"template:{path.name}", False, template=True)
        for path in templates
    ]


def _corpus_params() -> list:
    params = [
        pytest.param(Sample(path, path.name, False), id=path.name)
        for path in sorted(TEST_DATA_DIR.iterdir())
        if path.suffix in SUFFIXES
    ]
    params.extend(
        pytest.param(sample, id=sample.label) for sample in _template_samples()
    )
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


def _open(path: Path) -> Package:
    """Opens a package like the editor: strictly first, then failsafe."""
    try:
        return Package(path)
    except Exception:
        return Package(path, failsafe=True)


def _repair_missing_files(package: Package) -> None:
    """Clears the paths that point to a part missing in the package."""
    missing = {file.path for file in package.missingFiles}
    for shell in package.shells:
        thumbnail = shell.asset_information.default_thumbnail
        if thumbnail is not None and thumbnail.path in missing:
            shell.asset_information.default_thumbnail = None
    for submodel in package.submodels:
        for element in walk_elements(submodel):
            if isinstance(element, model.File) and element.value in missing:
                element.value = None


def _roundtrip(
    source: Path, tmp_path: Path, template: bool = False
) -> RoundTrip:
    # Pin the settings that change what a save writes, so that the result
    # does not depend on the user's settings.ini.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(Package, "writeJsonInAasx", False)
        patch.setattr(Package, "writePrettyJson", True)
        patch.setattr(Package, "sortKeysInJson", True)

        original = _open(source) if template else Package(source)
        _repair_missing_files(original)
        saved_path = tmp_path / f"saved{source.suffix}"
        original.write(str(saved_path))
        reloaded = Package(saved_path)
    return RoundTrip(original, reloaded, source, saved_path)


# Each sample is saved once and compared by several tests.
_ROUNDTRIPS: dict[Path, RoundTrip | Exception] = {}


@pytest.fixture(params=_corpus_params())
def roundtrip(
    request: pytest.FixtureRequest,
    qapp: object,
    tmp_path_factory: pytest.TempPathFactory,
) -> RoundTrip:
    sample: Sample = request.param
    if sample.path not in _ROUNDTRIPS:
        try:
            _ROUNDTRIPS[sample.path] = _roundtrip(
                sample.path,
                tmp_path_factory.mktemp("roundtrip"),
                sample.template,
            )
        except Exception as error:
            _ROUNDTRIPS[sample.path] = error
    result = _ROUNDTRIPS[sample.path]
    if isinstance(result, RoundTrip):
        return result
    if sample.local:
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
    raise result


# JSON keys whose values the SDK keeps in a set, so that their order in a file
# changes between two reads.
SET_KEYS = ("valueReferencePairs", "submodels", "isCaseOf")


def _normalized(value: object) -> object:
    """Removes differences that are not a loss of content.

    The SDK keeps some lists in a set, so their order is not stable. It also
    reads an empty value list from an XML file, and does not write it back.
    """
    if isinstance(value, dict):
        return {
            key: (
                sorted((_normalized(item) for item in items), key=json.dumps)
                if key in SET_KEYS
                else _normalized(items)
            )
            for key, items in value.items()
            if not (key == "valueList" and items == {"valueReferencePairs": []})
        }
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    return value


def _as_json(identifiable: model.Identifiable) -> dict:
    return _normalized(
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


def _zip_entries(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        return archive.namelist()


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


def _declared_parts(path: Path) -> set[str]:
    """The files that the AAS parts declare with `aas-suppl`, from the zip.

    Read with the OPC reader and not with the SDK reader, which loads only the
    files that a File element or the thumbnail names. A declaration of a part
    that is not in the package is left out, because no save can keep it. Names
    are compared as OPC does, without case, because the SDK writes the target
    of a relationship in lower case.
    """
    with pyecma376_2.ZipPackageReader(path.as_posix()) as reader:
        origin = next(
            names[0]
            for kind, names in reader.get_related_parts_by_type().items()
            if kind.endswith("/aasx-origin") and names
        )
        present = {normalize_part_name(name) for name in reader.list_items()}
        declared: set[str] = set()
        for kind, specs in reader.get_related_parts_by_type(origin).items():
            if not kind.endswith("/aas-spec"):
                continue
            for spec in specs:
                related = reader.get_related_parts_by_type(spec)
                for related_kind, names in related.items():
                    if related_kind.endswith("/aas-suppl"):
                        declared.update(
                            normalize_part_name(name)
                            for name in names
                            if normalize_part_name(name) in present
                        )
    return declared


def test_roundtrip_keeps_declared_supplementary_parts_when_saving(
    roundtrip: RoundTrip,
) -> None:
    if roundtrip.original_path.suffix != ".aasx":
        pytest.skip("Only an AASX declares supplementary parts")
    before = _declared_parts(roundtrip.original_path)
    after = _declared_parts(roundtrip.saved_path)

    # A save may declare more: the SDK declares a file that a File element or
    # a shell thumbnail names, also when the original did not.
    assert before <= after


def test_roundtrip_keeps_thumbnail_when_saving(roundtrip: RoundTrip) -> None:
    if roundtrip.original_path.suffix != ".aasx":
        pytest.skip("Only an AASX has a thumbnail part")
    before = _thumbnail(roundtrip.original_path)
    after = _thumbnail(roundtrip.saved_path)

    assert after == before


def test_roundtrip_keeps_core_properties_when_saving(
    roundtrip: RoundTrip,
) -> None:
    if roundtrip.original_path.suffix != ".aasx":
        pytest.skip("Only an AASX has core properties")
    before = _core_properties(roundtrip.original_path)
    after = _core_properties(roundtrip.saved_path)

    assert after == before


def test_roundtrip_writes_each_part_once_when_saving(
    roundtrip: RoundTrip,
) -> None:
    if roundtrip.saved_path.suffix != ".aasx":
        pytest.skip("Only an AASX is a zip")
    entries = _zip_entries(roundtrip.saved_path)

    assert len(entries) == len(set(entries))


def test_roundtrip_leaves_nothing_missing_when_package_was_repaired(
    roundtrip: RoundTrip,
) -> None:
    if roundtrip.saved_path.suffix != ".aasx":
        pytest.skip("Only an AASX has supplementary files")

    assert roundtrip.reloaded.missingFiles == ()


# ---------------------------------------------------------------------------
# The templates that point to a file missing in the package
# ---------------------------------------------------------------------------


def _template(name: str) -> Path:
    (path,) = TEMPLATES_DIR.rglob(name)
    return path


@pytest.mark.parametrize(
    ("name", "missing_path"), sorted(TEMPLATES_WITH_MISSING_FILES.items())
)
def test_template_opens_and_records_missing_file_when_part_is_missing(
    qapp: object, name: str, missing_path: str
) -> None:
    package = _open(_template(name))

    assert missing_path in {file.path for file in package.missingFiles}
    assert package.numOfSubmodels > 0


@pytest.mark.parametrize("name", sorted(TEMPLATES_WITH_MISSING_FILES))
def test_save_is_refused_when_templates_file_has_no_part(
    qapp: object, name: str
) -> None:
    package = _open(_template(name))

    check = check_save(package.save_source(), Path("out.aasx"), SaveOptions())

    assert len(check.blockers) == 1


def test_all_listed_templates_exist_in_the_templates_folder() -> None:
    # Guards the list above against a renamed or removed template.
    names = {path.name for path in TEMPLATES_DIR.rglob("*.aasx")}

    assert set(TEMPLATES_WITH_MISSING_FILES) <= names
    assert TEMPLATE_WITH_THUMBNAIL in names


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
    qapp: object, generated_aasx: Path, tmp_path: Path
) -> None:
    roundtrip = _roundtrip(generated_aasx, tmp_path)

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


def test_roundtrip_keeps_package_thumbnail_when_saving_generated_package(
    qapp: object, generated_aasx: Path, tmp_path: Path
) -> None:
    roundtrip = _roundtrip(generated_aasx, tmp_path)

    assert _thumbnail(roundtrip.saved_path) == PACKAGE_THUMBNAIL_BYTES


def test_roundtrip_keeps_core_properties_when_saving_generated_package(
    qapp: object, generated_aasx: Path, tmp_path: Path
) -> None:
    roundtrip = _roundtrip(generated_aasx, tmp_path)

    assert _core_properties(roundtrip.saved_path) == _core_properties(
        generated_aasx
    )
