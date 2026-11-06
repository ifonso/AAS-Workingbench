"""A generated form names its fields in the words of the metamodel."""

from basyx.aas import model
import pytest

from aas_editor.additional.classes import DictItem
from aas_editor.domain.form_labels import entry_title
from aas_editor.domain.form_labels import field_label


@pytest.mark.parametrize(
    ("owner", "param", "attribute", "name"),
    [
        (model.Qualifier, "value_type", "value_type", "valueType"),
        (model.Qualifier, "semantic_id", "semantic_id", "semanticId"),
        (model.Qualifier, "type_", "type", "type"),
        (model.Property, "id_short", "id_short", "idShort"),
        (model.Submodel, "id_", "id", "id"),
        (
            model.Property,
            "supplemental_semantic_id",
            "supplemental_semantic_id",
            "supplementalSemanticId",
        ),
    ],
)
def test_a_field_has_the_name_of_the_metamodel(
    owner: type, param: str, attribute: str, name: str
) -> None:
    label = field_label(owner, param, attribute, required=False)

    assert label.name == name
    assert label.text == name


def test_a_required_field_is_marked() -> None:
    label = field_label(model.Qualifier, "type_", "type", required=True)

    assert (label.name, label.text) == ("type", "type*")


def test_a_field_has_the_description_as_its_tooltip() -> None:
    label = field_label(model.Qualifier, "value_id", "value_id", False)

    assert label.tooltip


def test_the_attribute_is_found_when_only_the_parameter_is_known() -> None:
    label = field_label(model.Key, "type_", "type_", required=True)

    assert label.name == "type"


def test_a_field_that_nothing_names_keeps_its_python_name() -> None:
    label = field_label(
        model.Property, "no_such_param_", "no_such_param_", True
    )

    assert (label.name, label.text, label.tooltip) == (
        "no_such_param",
        "no_such_param*",
        "",
    )


def test_something_that_is_not_a_class_has_no_names() -> None:
    label = field_label(None, "value_type", "value_type", required=False)

    assert (label.text, label.tooltip) == ("value_type", "")


def test_a_language_entry_asks_for_a_language_and_a_text() -> None:
    language = field_label(DictItem, "key", "key", required=True)
    text = field_label(DictItem, "value", "value", required=True)

    assert (language.text, text.text) == ("language*", "text*")


def test_a_language_entry_keeps_the_description_of_its_attribute() -> None:
    label = field_label(DictItem, "key", "key", required=True)

    assert label.tooltip == "The language of the text, such as en."


@pytest.mark.parametrize(
    ("class_name", "position", "title"),
    [
        ("Qualifier", 1, "Qualifier 1"),
        ("DictItem", 1, "Text 1"),
        ("ModelReference", 2, "Reference 2"),
        ("ExternalReference", 3, "Reference 3"),
        ("Key", 1, "Key 1"),
    ],
)
def test_an_entry_is_titled_with_the_name_of_the_metamodel(
    class_name: str, position: int, title: str
) -> None:
    assert entry_title(class_name, position) == title
