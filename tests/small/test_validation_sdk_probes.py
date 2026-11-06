"""What the pinned SDK enforces, as the coverage table claims.

`domain.validation.coverage` says for each constraint whether the SDK refuses
a violation or accepts it. These tests are the probes behind that table. When
the SDK is upgraded, a test here that fails says which row of the table is
outdated: a refusal that went away needs a rule, and an acceptance that turned
into a refusal makes a rule dead.
"""

from collections.abc import Callable

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.validation_factories import template_qualifier

Probe = Callable[[], object]


def _key(type_: model.KeyTypes, value: str) -> model.Key:
    return model.Key(type_, value)


def _property(id_short: str | None = "P", **kwargs: object) -> model.Property:
    return model.Property(id_short, model.datatypes.String, **kwargs)  # pyright: ignore[reportArgumentType]


# ---------------------------------------------------------------------------
# The SDK refuses these: no rule is needed
# ---------------------------------------------------------------------------


def _id_short_digit_first() -> object:
    return _property("1ab")


def _id_short_hyphen_last() -> object:
    return _property("ab-")


def _revision_without_version() -> object:
    return model.AdministrativeInformation(revision="1")


def _self_managed_entity_without_asset() -> object:
    return model.Entity("E", model.EntityType.SELF_MANAGED_ENTITY)


def _entity_changed_to_self_managed() -> object:
    entity = model.Entity("E", model.EntityType.CO_MANAGED_ENTITY)
    entity.entity_type = model.EntityType.SELF_MANAGED_ENTITY
    return entity


def _duplicate_qualifier_type() -> object:
    prop = _property()
    prop.qualifier.add(model.Qualifier("T", model.datatypes.String))
    prop.qualifier.add(model.Qualifier("T", model.datatypes.String))
    return prop


def _id_short_edited_to_a_taken_one() -> object:
    submodel = model.Submodel("urn:s")
    first = _property("First")
    second = _property("Second")
    submodel.submodel_element.add(first)
    submodel.submodel_element.add(second)
    second.id_short = "First"
    return submodel


def _duplicate_extension_name() -> object:
    prop = _property()
    prop.extension.add(model.Extension("N"))
    prop.extension.add(model.Extension("N"))
    return prop


def _list_item_semantic_id_edited() -> object:
    items = model.SubmodelElementList(
        "L",
        model.Property,
        value_type_list_element=model.datatypes.String,
        semantic_id_list_element=make_external_reference("urn:a"),
    )
    item = _property(None, semantic_id=make_external_reference("urn:a"))
    items.value.add(item)
    item.semantic_id = make_external_reference("urn:other")
    return items


def _list_item_of_the_wrong_type() -> object:
    items = model.SubmodelElementList(
        "L", model.Property, value_type_list_element=model.datatypes.String
    )
    items.value.add(model.MultiLanguageProperty(None))
    return items


def _list_items_with_different_semantic_ids() -> object:
    items = model.SubmodelElementList(
        "L", model.Property, value_type_list_element=model.datatypes.String
    )
    items.value.add(
        _property(None, semantic_id=make_external_reference("urn:a"))
    )
    items.value.add(
        _property(None, semantic_id=make_external_reference("urn:b"))
    )
    return items


def _property_list_without_value_type() -> object:
    return model.SubmodelElementList("L", model.Property)


def _element_without_id_short_in_a_collection() -> object:
    collection = model.SubmodelElementCollection("C")
    collection.value.add(_property(None))
    return collection


def _semantic_id_cleared_with_supplemental() -> object:
    prop = _property(
        semantic_id=make_external_reference("urn:a"),
        supplemental_semantic_id=[make_external_reference("urn:b")],
    )
    prop.semantic_id = None
    return prop


def _supplemental_added_without_semantic() -> object:
    prop = _property()
    prop.supplemental_semantic_id.append(make_external_reference("urn:b"))
    return prop


def _external_reference_to_a_submodel_key() -> object:
    return model.ExternalReference((_key(model.KeyTypes.SUBMODEL, "x"),))


def _model_reference_to_a_global_key() -> object:
    return model.ModelReference(
        (_key(model.KeyTypes.GLOBAL_REFERENCE, "x"),), model.Submodel
    )


def _external_reference_ending_in_a_property() -> object:
    return model.ExternalReference(
        (
            _key(model.KeyTypes.GLOBAL_REFERENCE, "x"),
            _key(model.KeyTypes.PROPERTY, "p"),
        )
    )


def _model_reference_with_a_second_identifiable() -> object:
    return model.ModelReference(
        (
            _key(model.KeyTypes.SUBMODEL, "x"),
            _key(model.KeyTypes.SUBMODEL, "y"),
        ),
        model.Submodel,
    )


def _fragment_key_in_the_middle() -> object:
    return model.ModelReference(
        (
            _key(model.KeyTypes.SUBMODEL, "x"),
            _key(model.KeyTypes.FRAGMENT_REFERENCE, "f"),
            _key(model.KeyTypes.PROPERTY, "y"),
        ),
        model.Property,
    )


def _fragment_key_after_a_property() -> object:
    return model.ModelReference(
        (
            _key(model.KeyTypes.SUBMODEL, "x"),
            _key(model.KeyTypes.PROPERTY, "p"),
            _key(model.KeyTypes.FRAGMENT_REFERENCE, "f"),
        ),
        model.Property,
    )


def _list_position_that_is_no_number() -> object:
    return model.ModelReference(
        (
            _key(model.KeyTypes.SUBMODEL, "x"),
            _key(model.KeyTypes.SUBMODEL_ELEMENT_LIST, "l"),
            _key(model.KeyTypes.PROPERTY, "abc"),
        ),
        model.Property,
    )


def _asset_information_without_asset_id() -> object:
    return model.AssetInformation(model.AssetKind.INSTANCE)


def _global_asset_id_cleared() -> object:
    information = model.AssetInformation(
        model.AssetKind.INSTANCE, global_asset_id="urn:a"
    )
    information.global_asset_id = None
    return information


def _operation_variables_with_one_id_short() -> object:
    return model.Operation(
        "Op", input_variable=[_property("A")], output_variable=[_property("A")]
    )


@pytest.mark.parametrize(
    "probe",
    [
        pytest.param(_id_short_digit_first, id="AASd-002 digit first"),
        pytest.param(_id_short_hyphen_last, id="AASd-002 hyphen last"),
        pytest.param(_revision_without_version, id="AASd-005 on make"),
        pytest.param(_self_managed_entity_without_asset, id="AASd-014 on make"),
        pytest.param(_entity_changed_to_self_managed, id="AASd-014 on edit"),
        pytest.param(_duplicate_qualifier_type, id="AASd-021"),
        pytest.param(_id_short_edited_to_a_taken_one, id="AASd-022 on edit"),
        pytest.param(_duplicate_extension_name, id="AASd-077"),
        pytest.param(_list_item_semantic_id_edited, id="AASd-107 on edit"),
        pytest.param(_list_item_of_the_wrong_type, id="AASd-108"),
        pytest.param(_property_list_without_value_type, id="AASd-109 on make"),
        pytest.param(_list_items_with_different_semantic_ids, id="AASd-114"),
        pytest.param(_element_without_id_short_in_a_collection, id="AASd-117"),
        pytest.param(
            _semantic_id_cleared_with_supplemental, id="AASd-118 on clear"
        ),
        pytest.param(
            _supplemental_added_without_semantic, id="AASd-118 on add"
        ),
        pytest.param(_external_reference_to_a_submodel_key, id="AASd-122"),
        pytest.param(_model_reference_to_a_global_key, id="AASd-123"),
        pytest.param(_external_reference_ending_in_a_property, id="AASd-124"),
        pytest.param(
            _model_reference_with_a_second_identifiable, id="AASd-125"
        ),
        pytest.param(_fragment_key_in_the_middle, id="AASd-126"),
        pytest.param(_fragment_key_after_a_property, id="AASd-127"),
        pytest.param(_list_position_that_is_no_number, id="AASd-128"),
        pytest.param(
            _asset_information_without_asset_id, id="AASd-131 on make"
        ),
        pytest.param(_global_asset_id_cleared, id="AASd-131 on edit"),
        pytest.param(_operation_variables_with_one_id_short, id="AASd-134"),
    ],
)
def test_sdk_refuses_when_the_constraint_is_one_it_enforces(
    probe: Probe,
) -> None:
    with pytest.raises((model.AASConstraintViolation, ValueError, KeyError)):
        probe()


# ---------------------------------------------------------------------------
# The SDK accepts these: a rule of the editor finds them
# ---------------------------------------------------------------------------


def test_sdk_accepts_when_the_id_short_has_one_letter() -> None:
    assert _property("X").id_short == "X"


def test_sdk_accepts_when_the_version_is_cleared_after_the_revision() -> None:
    administration = model.AdministrativeInformation(version="1", revision="2")

    administration.version = None

    assert administration.revision == "2"


def test_sdk_accepts_when_the_value_type_of_a_property_changes() -> None:
    prop = model.Property("P", model.datatypes.Int, 3)

    prop.value_type = model.datatypes.Date

    assert prop.value == 3


def test_sdk_accepts_when_the_value_type_of_a_qualifier_changes() -> None:
    qualifier = model.Qualifier("Q", model.datatypes.Int, 3)

    qualifier.value_type = model.datatypes.Date

    assert qualifier.value == 3


def test_sdk_accepts_when_the_value_type_of_a_list_item_changes() -> None:
    items = model.SubmodelElementList(
        "L", model.Property, value_type_list_element=model.datatypes.String
    )
    item = _property(None)
    items.value.add(item)

    item.value_type = model.datatypes.Int

    assert item.value_type is model.datatypes.Int


def test_sdk_accepts_when_a_property_has_a_value_and_a_value_id() -> None:
    prop = _property(value="a", value_id=make_external_reference("urn:v"))

    assert prop.value == "a"


def test_sdk_accepts_when_a_multi_language_property_has_a_value_id() -> None:
    prop = model.MultiLanguageProperty(
        "M",
        model.MultiLanguageTextType({"en": "a"}),
        value_id=make_external_reference("urn:v"),
    )

    assert prop.value_id is not None


def test_sdk_accepts_when_a_specific_asset_id_is_named_global_asset_id() -> (
    None
):
    assert model.SpecificAssetId("globalAssetId", "x").name == "globalAssetId"


def test_sdk_accepts_when_the_external_subject_is_a_model_reference() -> None:
    reference = model.ModelReference(
        (_key(model.KeyTypes.SUBMODEL, "x"),), model.Submodel
    )

    asset_id = model.SpecificAssetId(
        "n",
        "v",
        external_subject_id=reference,  # pyright: ignore[reportArgumentType]
    )

    assert asset_id.external_subject_id is reference


def test_sdk_accepts_when_a_property_is_made_with_supplemental_but_no_semantic_id() -> (
    None
):
    prop = _property(
        supplemental_semantic_id=[make_external_reference("urn:b")]
    )

    assert prop.semantic_id is None


def test_sdk_accepts_when_a_template_qualifier_is_in_an_instance() -> None:
    prop = _property()
    prop.qualifier.add(template_qualifier())
    submodel = model.Submodel("urn:s", kind=model.ModellingKind.INSTANCE)

    submodel.submodel_element.add(prop)
    submodel.qualifier.add(template_qualifier("Other"))

    assert prop.get_identifiable_root() is submodel


def test_sdk_accepts_when_a_property_value_has_a_control_character() -> None:
    prop = _property(value="a\x00b")

    assert prop.value == "a\x00b"


def test_sdk_accepts_when_two_objects_get_one_id_by_an_edit() -> None:
    store: model.SetIdentifiableStore[model.Identifiable] = (
        model.SetIdentifiableStore()
    )
    first = model.Submodel("urn:a")
    second = model.Submodel("urn:b")
    store.add(first)
    store.add(second)

    second.id = "urn:a"

    assert len(store) == 2


def test_sdk_accepts_when_two_language_tags_differ_only_in_case() -> None:
    texts = model.MultiLanguageTextType({"en": "a", "EN": "b"})

    assert len(texts) == 2


def test_sdk_refuses_when_a_language_tag_is_malformed() -> None:
    with pytest.raises(ValueError, match="BCP 47"):
        model.MultiLanguageTextType({"en_US": "a"})
