"""The tabs name values, null attributes, and list entries in AAS words."""

import datetime

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest

from aas_workingbench.additional.classes import DictItem
from aas_workingbench.domain.attribute_display import NOT_SET
from aas_workingbench.domain.attribute_display import entry_label
from aas_workingbench.domain.attribute_display import type_column_text
from aas_workingbench.domain.attribute_display import value_text
from aas_workingbench.domain.attribute_display import value_type_name
from aas_workingbench.domain.attribute_vocabulary import attribute_info


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (1.5, "xs:double"),
        (datatypes.Int(3), "xs:int"),
        (12, "xs:integer"),
        ("text", "xs:string"),
        (True, "xs:boolean"),
        (datetime.datetime(2024, 1, 2, 3, 4, 5), "xs:dateTime"),
        (b"\x00\x01", "xs:base64Binary"),
        (model.ModellingKind.TEMPLATE, "ModellingKind"),
        (DictItem("en", "Motor"), "LangString"),
        ([model.Key(model.KeyTypes.SUBMODEL, "x")], "list"),
        (model.Property("P", datatypes.String).qualifier, "list"),
        (model.Key(model.KeyTypes.SUBMODEL, "x"), "Key"),
        (model.Property("P", datatypes.String), "Property"),
    ],
)
def test_a_value_is_named_in_the_words_of_the_aas(
    value: object, expected: str
) -> None:
    assert value_type_name(value) == expected


def test_a_null_attribute_reads_the_type_it_would_have() -> None:
    info = attribute_info(model.Property, "semantic_id")

    text = type_column_text(info, None)

    assert text == "Reference"
    assert "None" not in text


def test_a_null_value_reads_as_not_set_and_not_as_none() -> None:
    assert value_text(None) == NOT_SET


def test_an_empty_list_does_not_read_like_python() -> None:
    assert value_text([]) == "(empty)"
    assert value_text(set()) == "(empty)"
    assert value_text({}) == "(empty)"
    assert value_text(["a"]) is None


def test_a_value_type_reads_as_an_xsd_type() -> None:
    assert value_text(datatypes.Double) == "xs:double"
    assert value_text(datatypes.Int) == "xs:int"


def test_a_value_that_follows_the_value_type_is_named_by_the_value() -> None:
    info = attribute_info(model.Property, "value")

    assert type_column_text(info, 7.5) == "xs:double"
    assert type_column_text(info, datatypes.Int(7)) == "xs:int"
    assert type_column_text(info, None) == "ValueDataType"


def test_a_reference_is_named_by_its_kind() -> None:
    info = attribute_info(model.Property, "semantic_id")
    external = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:x"),)
    )

    assert type_column_text(info, external) == "ExternalReference"


def test_a_list_attribute_is_named_by_its_declared_type() -> None:
    info = attribute_info(model.Property, "qualifier")
    qualifiers = model.Property("P", datatypes.String).qualifier

    assert type_column_text(info, qualifiers) == "list of Qualifier"


def test_an_entry_without_an_entry_in_the_vocabulary_is_named_by_its_value() -> (
    None
):
    assert type_column_text(None, DictItem("en", "x")) == "LangString"


def test_the_entry_of_a_text_is_named_by_its_language() -> None:
    assert entry_label(DictItem("de", "Motor"), 1) == "de"
    assert entry_label(DictItem("", "Motor"), 1) == "(no language)"


def test_the_entry_of_a_set_of_elements_is_named_by_its_idshort() -> None:
    element = model.Property("RatedPower", datatypes.Double)

    assert entry_label(element, 3) == "RatedPower"


def test_the_item_of_a_list_has_no_idshort_and_is_named_by_its_position() -> (
    None
):
    item = model.Property(None, datatypes.Int, 1)

    assert entry_label(item, 2) == "[2]"


def test_a_qualifier_an_extension_and_a_specific_asset_id_have_a_key() -> None:
    qualifier = model.Qualifier("Cardinality", datatypes.String)
    extension = model.Extension("Origin")
    asset_id = model.SpecificAssetId("SerialNumber", "SN-1")

    assert [
        entry_label(qualifier, 0),
        entry_label(extension, 0),
        entry_label(asset_id, 0),
    ] == ["Cardinality", "Origin", "SerialNumber"]


def test_a_key_is_named_by_its_position_and_its_type() -> None:
    key = model.Key(model.KeyTypes.SUBMODEL, "urn:x")

    assert entry_label(key, 1) == "[1] SUBMODEL"


def test_an_entry_that_has_no_key_is_named_by_its_position() -> None:
    reference = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:x"),)
    )

    assert entry_label(reference, 4) == "[4]"
