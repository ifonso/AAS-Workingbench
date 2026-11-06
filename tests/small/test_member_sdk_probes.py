"""What the SDK does with qualifiers, extensions and the like.

Bulk editing relies on these behaviors. When the SDK changes one of them, the
failing test names what the editor must adapt.
"""

from basyx.aas import model
import pytest
from tests.factories import make_property

STRING = model.datatypes.String


def _qualifier(type_: str) -> model.Qualifier:
    return model.Qualifier(type_, value_type=STRING, value="1")


def test_a_second_qualifier_of_a_type_is_refused_on_add_aasd_021() -> None:
    prop = make_property("P")
    prop.qualifier.add(_qualifier("A"))

    with pytest.raises(model.AASConstraintViolation, match="AASd-021"):
        prop.qualifier.add(_qualifier("A"))


def test_a_second_extension_of_a_name_is_refused_on_add_aasd_077() -> None:
    prop = make_property("P")
    prop.extension.add(model.Extension("E"))

    with pytest.raises(model.AASConstraintViolation, match="AASd-077"):
        prop.extension.add(model.Extension("E"))


def test_renaming_a_qualifier_type_to_a_taken_one_is_refused_with_a_key_error() -> (
    None
):
    prop = make_property("P")
    prop.qualifier.add(_qualifier("A"))
    prop.qualifier.add(_qualifier("B"))
    second = prop.qualifier.get_object_by_attribute("type", "B")

    with pytest.raises(KeyError):
        second.type = "A"

    assert [q.type for q in prop.qualifier] == ["A", "B"]


def test_a_qualifier_can_belong_to_one_owner_only() -> None:
    first, second = make_property("A"), make_property("B")
    qualifier = _qualifier("Q")
    first.qualifier.add(qualifier)

    with pytest.raises(ValueError, match="already a parent"):
        second.qualifier.add(qualifier)

    first.qualifier.remove(qualifier)
    second.qualifier.add(qualifier)
    assert qualifier.parent is second


def test_qualifiers_and_extensions_can_be_changed_but_a_specific_asset_id_not() -> (
    None
):
    qualifier = _qualifier("Q")
    qualifier.value = "2"
    extension = model.Extension("E", value_type=STRING, value="1")
    extension.value = "2"
    asset_id = model.SpecificAssetId("N", "V")

    with pytest.raises(AttributeError, match="immutable"):
        asset_id.value = "W"  # type: ignore[misc]


def test_a_specific_asset_id_needs_a_value_and_a_co_managed_entity_refuses_it() -> (
    None
):
    with pytest.raises(ValueError, match="empty string"):
        model.SpecificAssetId("N", "")
    entity = model.Entity("E", model.EntityType.CO_MANAGED_ENTITY)

    with pytest.raises(model.AASConstraintViolation, match="AASd-014"):
        entity.specific_asset_id.append(model.SpecificAssetId("N", "V"))


def test_the_same_specific_asset_id_can_be_added_twice() -> None:
    information = model.AssetInformation(model.AssetKind.INSTANCE, "urn:a")

    information.specific_asset_id.append(model.SpecificAssetId("N", "V"))
    information.specific_asset_id.append(model.SpecificAssetId("N", "V"))

    assert len(information.specific_asset_id) == 2


def test_a_data_specification_needs_content_and_iec_61360_is_the_only_class() -> (
    None
):
    assert [
        cls.__name__ for cls in model.DataSpecificationContent.__subclasses__()
    ] == ["DataSpecificationIEC61360"]
    with pytest.raises(ValueError, match="must not be empty"):
        model.DataSpecificationIEC61360(
            preferred_name=model.PreferredNameTypeIEC61360({})
        )


def test_a_text_of_a_language_set_is_checked_when_it_is_replaced() -> None:
    prop = make_property("P")
    prop.description = model.MultiLanguageTextType({"en": "a"})

    with pytest.raises(ValueError, match="minimum length"):
        prop.description["en"] = ""
    with pytest.raises(ValueError, match="maximum length"):
        prop.description["en"] = "x" * 1024

    prop.description["en"] = "b"
    assert prop.description["en"] == "b"
