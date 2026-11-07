"""Deleting the last specific asset id of a shell (F-EDT-02 AC13).

The original leaves an empty list and writes none. The SDK has no null list:
an empty one is the same, and the writers leave it out. An asset needs a global
asset id or a specific asset id (AASd-131), so the last one of a shell that has
no global asset id stays.
"""

import io
import json

from basyx.aas import model
from basyx.aas.adapter.json import write_aas_json_file
from tests.factories import make_shell
from tests.serialization import snapshot


def _shell(global_asset_id: str | None) -> model.AssetAdministrationShell:
    information = model.AssetInformation(
        asset_kind=model.AssetKind.INSTANCE,
        global_asset_id=global_asset_id,
        specific_asset_id=[model.SpecificAssetId("serialNumber", "4711")],
    )
    return make_shell(id_short="Shell", asset_information=information)


def _specific_row(model_support, details):
    information = model_support.find(details, "asset_information")
    specific = model_support.find(details, "specific_asset_id", information)
    return model_support.find(details, "SpecificAssetId 0", specific)


def _written(shell: model.AssetAdministrationShell) -> dict:
    buffer = io.StringIO()
    write_aas_json_file(buffer, model.DictIdentifiableStore([shell]))
    return json.loads(buffer.getvalue())["assetAdministrationShells"][0]


def test_the_last_specific_asset_id_goes_and_the_file_has_no_list(
    model_support,
) -> None:
    from aas_workingbench.settings.app_settings import NOT_GIVEN
    from aas_workingbench.settings.app_settings import CLEAR_ROW_ROLE

    shell = _shell("urn:asset:1")
    table = model_support.pack_table(shell)
    details = model_support.detail_table(table, "shells", "Shell")
    row = _specific_row(model_support, details)
    before = snapshot(model.DictIdentifiableStore([shell]))
    written_before = _written(shell)["assetInformation"]

    cleared = details.setData(row, NOT_GIVEN, CLEAR_ROW_ROLE)
    written_after = _written(shell)["assetInformation"]

    assert cleared
    assert list(shell.asset_information.specific_asset_id) == []
    assert "specificAssetIds" in written_before
    assert "specificAssetIds" not in written_after
    assert written_after["globalAssetId"] == "urn:asset:1"
    assert snapshot(model.DictIdentifiableStore([shell])) != before


def test_the_removal_is_one_undo_step(model_support) -> None:
    from aas_workingbench.settings.app_settings import NOT_GIVEN
    from aas_workingbench.settings.app_settings import CLEAR_ROW_ROLE

    shell = _shell("urn:asset:1")
    table = model_support.pack_table(shell)
    package = model_support.package_of(table)
    details = model_support.detail_table(table, "shells", "Shell")
    package.commandStack.mark_saved()

    details.setData(
        _specific_row(model_support, details), NOT_GIVEN, CLEAR_ROW_ROLE
    )
    package.commandStack.undo()

    assert [s.name for s in shell.asset_information.specific_asset_id] == [
        "serialNumber"
    ]
    assert not package.commandStack.can_undo


def test_the_last_asset_id_of_a_shell_without_a_global_one_is_kept(
    model_support,
) -> None:
    from aas_workingbench.settings.app_settings import NOT_GIVEN
    from aas_workingbench.settings.app_settings import CLEAR_ROW_ROLE

    shell = _shell(None)
    table = model_support.pack_table(shell)
    details = model_support.detail_table(table, "shells", "Shell")
    row = _specific_row(model_support, details)

    cleared = details.setData(row, NOT_GIVEN, CLEAR_ROW_ROLE)

    assert not cleared
    assert [s.name for s in shell.asset_information.specific_asset_id] == [
        "serialNumber"
    ]
    assert "AASd-131" in details.lastErrorMsg
