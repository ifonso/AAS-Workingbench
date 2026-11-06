"""What a new child of a SubmodelElementList starts with."""

from basyx.aas import model
from basyx.aas.model import datatypes
from tests.factories import make_external_reference

from aas_editor.domain.list_children import child_defaults


def test_child_defaults_follow_the_list_of_properties() -> None:
    reference = make_external_reference("urn:example:number")
    numbers = model.SubmodelElementList(
        "Numbers",
        type_value_list_element=model.Property,
        value_type_list_element=datatypes.Int,
        semantic_id_list_element=reference,
    )

    defaults = child_defaults(numbers)

    assert defaults.element_type is model.Property
    assert defaults.value_type is datatypes.Int
    assert defaults.semantic_id == reference
    assert isinstance(defaults.template, model.Property)
    assert defaults.template.value_type is datatypes.Int
    assert defaults.template.semantic_id == reference
    assert defaults.template.id_short is None


def test_child_defaults_make_a_template_that_the_list_accepts() -> None:
    numbers = model.SubmodelElementList(
        "Numbers",
        type_value_list_element=model.Property,
        value_type_list_element=datatypes.Int,
    )
    template = child_defaults(numbers).template

    assert template is not None
    numbers.value.add(template)  # pyright: ignore[reportArgumentType]

    assert len(numbers.value) == 1


def test_child_defaults_follow_the_list_of_ranges() -> None:
    ranges = model.SubmodelElementList(
        "Ranges",
        type_value_list_element=model.Range,
        value_type_list_element=datatypes.Decimal,
    )

    template = child_defaults(ranges).template

    assert isinstance(template, model.Range)
    assert template.value_type is datatypes.Decimal


def test_child_defaults_have_no_value_type_when_the_list_fixes_none() -> None:
    files = model.SubmodelElementList(
        "Files", type_value_list_element=model.File
    )

    defaults = child_defaults(files)

    assert defaults.value_type is None
    assert defaults.semantic_id is None
    assert isinstance(defaults.template, model.File)


def test_child_defaults_make_a_blank_entity_without_a_type() -> None:
    entities = model.SubmodelElementList(
        "Entities", type_value_list_element=model.Entity
    )

    template = child_defaults(entities).template

    assert isinstance(template, model.Entity)
    assert template.entity_type is None


def test_child_defaults_have_no_template_when_the_class_needs_values() -> None:
    events = model.SubmodelElementList(
        "Events", type_value_list_element=model.BasicEventElement
    )

    defaults = child_defaults(events)

    assert defaults.element_type is model.BasicEventElement
    assert defaults.template is None


def test_child_defaults_have_no_template_for_a_list_of_lists() -> None:
    lists = model.SubmodelElementList(
        "Lists", type_value_list_element=model.SubmodelElementList
    )

    assert child_defaults(lists).template is None
