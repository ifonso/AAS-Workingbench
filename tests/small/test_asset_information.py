"""Tests for building AssetInformation that the SDK accepts (F-EDT-02)."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference

from aas_editor.domain.asset_information import ASSET_KINDS
from aas_editor.domain.asset_information import AssetInformationError
from aas_editor.domain.asset_information import build_asset_information
from aas_editor.domain.asset_information import build_specific_asset_id
from aas_editor.domain.asset_information import check_asset_ids
from aas_editor.domain.asset_information import new_global_asset_id


class TestSdkFacts:
    """What the pinned SDK does, so the messages below do not drift."""

    def test_sdk_refuses_asset_information_without_any_asset_id(self) -> None:
        with pytest.raises(model.AASConstraintViolation, match="AASd-131"):
            model.AssetInformation(model.AssetKind.INSTANCE)

    def test_sdk_has_no_batch_kind_in_v3_1(self) -> None:
        assert {kind.name for kind in ASSET_KINDS} == {
            "TYPE",
            "INSTANCE",
            "NOT_APPLICABLE",
            "ROLE",
        }


class TestBuildAssetInformation:
    def test_a_global_asset_id_is_enough(self) -> None:
        info = build_asset_information(model.AssetKind.TYPE, "urn:asset:1")

        assert info.asset_kind is model.AssetKind.TYPE
        assert info.global_asset_id == "urn:asset:1"

    def test_a_specific_asset_id_is_enough(self) -> None:
        specific = build_specific_asset_id("serial", "4711")

        info = build_asset_information(
            model.AssetKind.INSTANCE, None, [specific]
        )

        assert info.global_asset_id is None
        assert list(info.specific_asset_id) == [specific]

    def test_blank_global_asset_id_counts_as_missing(self) -> None:
        with pytest.raises(AssetInformationError, match="AASd-131"):
            build_asset_information(model.AssetKind.INSTANCE, "   ")

    def test_the_asset_type_is_kept_and_a_blank_one_is_dropped(self) -> None:
        with_type = build_asset_information(
            model.AssetKind.INSTANCE, "urn:a", asset_type=" urn:type "
        )
        blank = build_asset_information(
            model.AssetKind.INSTANCE, "urn:a", asset_type="  "
        )

        assert with_type.asset_type == "urn:type"
        assert blank.asset_type is None

    def test_too_long_global_asset_id_is_explained(self) -> None:
        with pytest.raises(AssetInformationError, match="2048"):
            build_asset_information(model.AssetKind.INSTANCE, "x" * 2049)

    def test_too_long_asset_type_is_explained(self) -> None:
        with pytest.raises(AssetInformationError, match="asset type"):
            build_asset_information(
                model.AssetKind.INSTANCE, "urn:a", asset_type="x" * 2049
            )

    def test_the_text_of_an_error_is_for_the_user_not_a_traceback(self) -> None:
        with pytest.raises(AssetInformationError) as error:
            build_asset_information(model.AssetKind.INSTANCE, None)

        assert "Traceback" not in str(error.value)
        assert "global asset id" in str(error.value)


class TestBuildSpecificAssetId:
    def test_name_and_value_are_trimmed(self) -> None:
        specific = build_specific_asset_id(" serial ", " 4711 ")

        assert (specific.name, specific.value) == ("serial", "4711")

    def test_the_external_subject_is_kept(self) -> None:
        subject = make_external_reference("urn:example:customer")

        specific = build_specific_asset_id("serial", "1", subject)

        assert specific.external_subject_id == subject

    def test_empty_name_is_refused_with_a_reason(self) -> None:
        with pytest.raises(AssetInformationError, match="needs a name"):
            build_specific_asset_id("", "1")

    def test_empty_value_is_refused_with_a_reason(self) -> None:
        with pytest.raises(AssetInformationError, match="needs a value"):
            build_specific_asset_id("serial", "")


class TestCheckAssetIds:
    def test_valid_ids_have_no_problem(self) -> None:
        assert check_asset_ids("urn:a", []) is None

    def test_no_ids_is_a_problem(self) -> None:
        assert check_asset_ids(None, []) is not None

    def test_specific_ids_alone_are_valid(self) -> None:
        assert (
            check_asset_ids(None, [build_specific_asset_id("n", "v")]) is None
        )


class TestNewGlobalAssetId:
    def test_generated_ids_are_unique_urn_uuids(self) -> None:
        first, second = new_global_asset_id(), new_global_asset_id()

        assert first.startswith("urn:uuid:")
        assert first != second
