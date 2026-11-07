"""The kinds of asset that V3.1 and the SDK know (F-EDT-02 AC10, AC11).

`Batch` is a literal of the metamodel V3.2. The editor targets V3.1, and the
SDK has no such kind, so a file that holds it is not readable as a whole.
"""

import json
from pathlib import Path

from basyx.aas import model
import pytest
from tests.serialization import snapshot

from aas_workingbench.domain.asset_information import ASSET_KINDS
from aas_workingbench.domain.asset_information import DEFAULT_ASSET_KIND
from aas_workingbench.infrastructure.package_io import read_package


def _file_with_kind(path: Path, kind: str) -> Path:
    document = {
        "assetAdministrationShells": [
            {
                "modelType": "AssetAdministrationShell",
                "id": "urn:shell:1",
                "idShort": "Batched",
                "assetInformation": {
                    "assetKind": kind,
                    "globalAssetId": "urn:asset:1",
                },
            }
        ]
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_the_kinds_offered_are_those_of_the_sdk_and_have_no_batch() -> None:
    names = {kind.name for kind in ASSET_KINDS}

    assert tuple(model.AssetKind) == ASSET_KINDS
    assert names == {"TYPE", "INSTANCE", "NOT_APPLICABLE", "ROLE"}
    assert not any("BATCH" in name for name in dir(model.AssetKind))


def test_a_new_shell_is_an_instance_unless_the_user_chooses_another() -> None:
    assert DEFAULT_ASSET_KIND is model.AssetKind.INSTANCE


@pytest.mark.parametrize("kind", ["Type", "Instance", "NotApplicable", "Role"])
def test_each_kind_of_v3_1_is_read_and_written_as_it_is(
    tmp_path: Path, kind: str
) -> None:
    source = _file_with_kind(tmp_path / "kind.json", kind)

    parts = read_package(source)
    shell = parts.objects.get_item("urn:shell:1")

    assert isinstance(shell, model.AssetAdministrationShell)
    assert shell.asset_information.asset_kind.name.replace("_", "").lower() == (
        kind.lower()
    )
    written = json.loads(snapshot(parts.objects))
    assert (
        written["assetAdministrationShells"][0]["assetInformation"]["assetKind"]
        == kind
    )


def test_a_file_with_batch_is_refused_as_a_whole(tmp_path: Path) -> None:
    source = _file_with_kind(tmp_path / "batch.json", "Batch")

    with pytest.raises(KeyError, match="Batch"):
        read_package(source)


def test_in_failsafe_mode_the_shell_with_batch_is_left_out_and_the_package_partial(
    tmp_path: Path,
) -> None:
    source = _file_with_kind(tmp_path / "batch.json", "Batch")

    parts = read_package(source, failsafe=True)

    assert list(parts.objects) == []
    assert parts.partial
