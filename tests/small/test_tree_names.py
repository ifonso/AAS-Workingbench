"""The package tree names its groups of objects in the words of the AAS."""

from basyx.aas import model
import pytest

from aas_workingbench.domain.tree_names import node_description
from aas_workingbench.domain.tree_names import node_name
from aas_workingbench.domain.tree_names import type_name
from aas_workingbench.package import Package


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("shells", "Asset Administration Shells"),
        ("submodels", "Submodels"),
        ("concept_descriptions", "Concept Descriptions"),
        ("fileStore", "Files"),
    ],
)
def test_the_groups_of_a_package_have_names_of_the_aas(
    attribute: str, expected: str
) -> None:
    assert node_name(Package, attribute) == expected


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [
        ("input_variable", "inputVariable"),
        ("output_variable", "outputVariable"),
        ("in_output_variable", "inoutputVariable"),
    ],
)
def test_the_variables_of_an_operation_are_named_by_the_metamodel(
    attribute: str, expected: str
) -> None:
    assert node_name(model.Operation, attribute) == expected


def test_a_name_that_nothing_knows_stays_as_it_is() -> None:
    assert node_name(model.Property, "no_such_attribute") == "no_such_attribute"


def test_a_group_has_a_sentence_for_the_tooltip() -> None:
    assert "concept descriptions" in node_description(
        Package, "concept_descriptions"
    )
    assert node_description(model.Operation, "input_variable")


def test_a_group_has_no_type_and_an_object_has_its_class() -> None:
    assert type_name("NamespaceSet", is_node=True) == ""
    assert type_name("Submodel", is_node=False) == "Submodel"


def test_a_class_of_the_editor_has_a_word_of_the_aas() -> None:
    assert type_name("StoredFile", is_node=False) == "SupplementaryFile"
