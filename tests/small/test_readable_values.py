"""A cell reads names and counts, and not the repr of a Python object."""

import datetime

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest

from aas_editor.additional.classes import DictItem
from aas_editor.domain.readable_values import count_text
from aas_editor.domain.readable_values import readable_text


def _reference(*values: str) -> model.ExternalReference:
    return model.ExternalReference(
        tuple(model.Key(model.KeyTypes.GLOBAL_REFERENCE, v) for v in values)
    )


def _property() -> model.Property:
    return model.Property(
        "Speed",
        datatypes.Double,
        value=7.5,
        qualifier=[
            model.Qualifier("Cardinality", datatypes.String, "One"),
            model.Qualifier("Unit", datatypes.String),
        ],
        extension=[model.Extension("Origin", datatypes.String, "datasheet")],
    )


def test_an_extension_reads_its_name_and_value() -> None:
    extension = model.Extension("Origin", datatypes.String, "datasheet")

    assert readable_text(extension) == "Origin: datasheet"


def test_an_extension_without_a_value_reads_its_name() -> None:
    assert readable_text(model.Extension("Origin")) == "Origin"


def test_a_qualifier_reads_its_type_and_value() -> None:
    qualifier = model.Qualifier("Cardinality", datatypes.String, "One")

    assert readable_text(qualifier) == "Cardinality: One"


def test_a_set_of_qualifiers_reads_how_many_there_are() -> None:
    assert readable_text(_property().qualifier) == "2 qualifiers"


def test_a_set_of_one_extension_reads_a_singular() -> None:
    assert readable_text(_property().extension) == "1 extension"


def test_a_list_of_references_reads_a_count_whatever_kind_they_are() -> None:
    references = [
        _reference("a"),
        model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:x"),), model.Submodel
        ),
    ]

    assert readable_text(references) == "2 references"


def test_the_keys_of_a_reference_read_as_a_count() -> None:
    assert readable_text(_reference("a", "b").key) == "2 keys"


def test_a_set_of_embedded_data_specifications_is_counted_in_words() -> None:
    specification = model.EmbeddedDataSpecification(
        _reference("https://admin-shell.io/x"),
        model.DataSpecificationIEC61360(
            preferred_name=model.PreferredNameTypeIEC61360({"en": "Speed"})
        ),
    )

    assert count_text([specification, specification]) == (
        "2 embedded data specifications"
    )


@pytest.mark.parametrize(
    ("kinds", "expected"),
    [
        (["Property"], "1 property"),
        (["Property", "Property"], "2 properties"),
        (["Entity", "Entity"], "2 entities"),
        (["Property", "Range"], "2 elements"),
    ],
)
def test_elements_are_counted_by_their_class_or_as_elements(
    kinds: list[str], expected: str
) -> None:
    made = {
        "Property": lambda n: model.Property(f"p{n}", datatypes.Int),
        "Range": lambda n: model.Range(f"r{n}", datatypes.Int),
        "Entity": lambda n: model.Entity(
            f"e{n}", model.EntityType.CO_MANAGED_ENTITY
        ),
    }
    elements = [made[kind](number) for number, kind in enumerate(kinds)]

    assert count_text(elements) == expected


def test_a_mixture_is_counted_as_items() -> None:
    assert count_text([_reference("a"), "text"]) == "2 items"


def test_an_empty_container_reads_empty() -> None:
    assert readable_text([]) == "(empty)"
    assert readable_text({}) == "(empty)"
    assert readable_text(set()) == "(empty)"


def test_none_reads_as_not_set() -> None:
    assert readable_text(None) == "(not set)"


def test_a_blob_reads_its_size_and_not_its_bytes() -> None:
    assert readable_text(b"\x00\x01\x02hello") == "8 bytes"


def test_asset_information_reads_its_kind_and_global_id() -> None:
    information = model.AssetInformation(
        model.AssetKind.INSTANCE, global_asset_id="urn:motor"
    )

    assert readable_text(information) == "INSTANCE: urn:motor"


def test_asset_information_without_a_global_id_reads_its_kind() -> None:
    information = model.AssetInformation(
        model.AssetKind.TYPE,
        specific_asset_id=[model.SpecificAssetId("Serial", "1")],
    )

    assert readable_text(information) == "TYPE"


def test_a_resource_reads_its_path() -> None:
    resource = model.Resource("/aasx/files/motor.png", "image/png")

    assert readable_text(resource) == "/aasx/files/motor.png"


def test_administration_reads_what_it_has() -> None:
    administration = model.AdministrativeInformation(
        version="1", revision="2", template_id="urn:t"
    )

    assert readable_text(administration) == (
        "version 1, revision 2, template urn:t"
    )


def test_an_element_reads_its_id_short() -> None:
    assert readable_text(_property()) == "Speed"


@pytest.mark.parametrize(
    "value",
    [
        "text",
        7,
        1.5,
        True,
        datetime.date(2024, 1, 2),
        model.ModellingKind.TEMPLATE,
        model.Key(model.KeyTypes.SUBMODEL, "urn:x"),
        _reference("a"),
        DictItem("en", "Motor"),
        model.MultiLanguageNameType({"en": "Motor"}),
    ],
)
def test_what_is_shown_well_is_left_to_the_caller(value: object) -> None:
    assert readable_text(value) is None


def test_no_reader_text_looks_like_a_python_repr() -> None:
    values = [
        _property().qualifier,
        _property().extension,
        _property().qualifier.get_object_by_attribute("type", "Unit"),
        _reference("a").key,
        model.AssetInformation(global_asset_id="urn:x"),
        model.AdministrativeInformation(),
    ]

    texts = [readable_text(value) for value in values]

    assert all(
        text is not None and "(" not in text.replace("(empty)", "")
        for text in texts
    )


def test_the_generated_name_of_a_list_item_is_not_shown() -> None:
    text = readable_text("generated_submodel_list_hack_0123456789abcdef")

    assert text is not None
    assert "generated_submodel_list_hack" not in text


def test_a_duration_reads_as_an_iso_8601_duration() -> None:
    from dateutil.relativedelta import relativedelta

    assert readable_text(relativedelta(seconds=1)) == "PT1S"
    assert readable_text(relativedelta(days=2, hours=3)) == "P2DT3H"


def test_a_qualifier_with_a_duration_reads_the_duration_and_not_its_repr() -> (
    None
):
    from dateutil.relativedelta import relativedelta

    qualifier = model.Qualifier(
        "UpdateInterval", relativedelta, relativedelta(seconds=1)
    )

    assert readable_text(qualifier) == "UpdateInterval: PT1S"
