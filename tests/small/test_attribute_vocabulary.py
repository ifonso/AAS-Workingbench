"""The vocabulary names the attributes the way the metamodel does."""

import inspect
import re

from basyx.aas import model
import basyx.aas.model.aas
import basyx.aas.model.base
import basyx.aas.model.concept
import basyx.aas.model.submodel
import pytest

from aas_editor.domain.attribute_vocabulary import AttributeInfo
from aas_editor.domain.attribute_vocabulary import attribute_info
from aas_editor.domain.attribute_vocabulary import entries
from aas_editor.domain.attribute_vocabulary import metamodel_name
from aas_editor.domain.attribute_vocabulary import vocabulary_classes

# The names of the metamodel are lowerCamelCase.
_METAMODEL_NAME = re.compile(r"^[a-z][A-Za-z0-9]*$")
# What the SDK says in Python, and a person who knows the AAS does not.
_PYTHON_WORDS = ("Optional", "Union", "Iterable", "typing", "NoneType", "[")
# Classes of the editor, which have attributes that tabs show.
_EDITOR_CLASSES = {"Package", "StoredFile", "DictItem"}


def _type_of_value(owner: type) -> str:
    info = attribute_info(owner, "value")
    assert info is not None
    return info.type_name


def test_an_attribute_of_a_base_class_is_found_for_its_subclasses() -> None:
    info = attribute_info(model.Property, "display_name")

    assert info is not None
    assert (info.name, info.type_name) == (
        "displayName",
        "MultiLanguageNameType",
    )


def test_an_attribute_that_is_named_the_same_has_the_type_of_its_class() -> (
    None
):
    types = {
        owner.__name__: _type_of_value(owner)
        for owner in (
            model.Property,
            model.MultiLanguageProperty,
            model.File,
            model.ReferenceElement,
            model.SubmodelElementCollection,
        )
    }

    assert types == {
        "Property": "ValueDataType",
        "MultiLanguageProperty": "MultiLanguageTextType",
        "File": "xs:string",
        "ReferenceElement": "Reference",
        "SubmodelElementCollection": "list of SubmodelElement",
    }


def test_the_metamodel_names_the_attributes_in_camel_case() -> None:
    names = {
        sdk_name: metamodel_name(owner, sdk_name)
        for owner, sdk_name in (
            (model.Property, "id_short"),
            (model.Property, "value_type"),
            (model.Submodel, "supplemental_semantic_id"),
            (model.Qualifier, "value_id"),
            (model.SubmodelElementList, "type_value_list_element"),
            (model.Operation, "in_output_variable"),
        )
    }

    assert names == {
        "id_short": "idShort",
        "value_type": "valueType",
        "supplemental_semantic_id": "supplementalSemanticId",
        "value_id": "valueId",
        "type_value_list_element": "typeValueListElement",
        "in_output_variable": "inoutputVariable",
    }


def test_an_attribute_without_an_entry_keeps_its_name() -> None:
    assert attribute_info(model.Property, "no_such_attribute") is None
    assert metamodel_name(model.Property, "no_such_attribute") == (
        "no_such_attribute"
    )


def test_a_list_attribute_says_what_the_list_holds() -> None:
    info = attribute_info(model.Property, "qualifier")

    assert info is not None
    assert info.type_name == "list of Qualifier"
    assert info.is_list


@pytest.mark.parametrize(
    ("class_name", "info"),
    entries(),
    ids=lambda value: value if isinstance(value, str) else value.sdk_name,
)
def test_an_entry_is_complete(class_name: str, info: AttributeInfo) -> None:
    assert info.description.endswith(".")
    assert 20 <= len(info.description) <= 200
    assert not any(word in info.type_name for word in _PYTHON_WORDS)
    if info.in_metamodel:
        assert _METAMODEL_NAME.match(info.name), (class_name, info.name)


def test_every_entry_names_a_class_that_exists() -> None:
    sdk_classes = {
        name
        for module in (
            basyx.aas.model.aas,
            basyx.aas.model.base,
            basyx.aas.model.concept,
            basyx.aas.model.submodel,
        )
        for name, _ in inspect.getmembers(module, inspect.isclass)
    }

    unknown = set(vocabulary_classes()) - sdk_classes - _EDITOR_CLASSES

    assert unknown == set()
