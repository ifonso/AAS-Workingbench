"""The sections that the detail of an object is read in (proposals 3.2, 3.3)."""

from basyx.aas import model
import pytest

from aas_workingbench.domain.attribute_sections import CLOSED_AT_FIRST
from aas_workingbench.domain.attribute_sections import SECTION_ORDER
from aas_workingbench.domain.attribute_sections import SECTION_TITLES
from aas_workingbench.domain.attribute_sections import Section
from aas_workingbench.domain.attribute_sections import header_text
from aas_workingbench.domain.attribute_sections import holds_nothing
from aas_workingbench.domain.attribute_sections import in_reading_order
from aas_workingbench.domain.attribute_sections import place_of
from aas_workingbench.domain.attribute_sections import section_of
from aas_workingbench.domain.attribute_sections import starts_open
from aas_workingbench.domain.attribute_vocabulary import entries

# The order in which the SDK gives the attributes of a Property.
PROPERTY_ATTRIBUTES = [
    "id_short",
    "category",
    "value",
    "value_type",
    "description",
    "display_name",
    "embedded_data_specifications",
    "extension",
    "qualifier",
    "semantic_id",
    "supplemental_semantic_id",
    "value_id",
]


@pytest.mark.parametrize(
    ("class_name", "sdk_name"),
    [(cls, info.sdk_name) for cls, info in entries()],
    ids=[f"{cls}.{info.sdk_name}" for cls, info in entries()],
)
def test_every_attribute_of_the_vocabulary_has_a_section(
    class_name: str, sdk_name: str
) -> None:
    owner = type(class_name, (), {})

    assert section_of(owner, sdk_name) is not None


def test_the_sections_are_value_identification_semantics_and_advanced() -> None:
    assert [SECTION_TITLES[s] for s in SECTION_ORDER] == [
        "Value",
        "Identification",
        "Semantics",
        "Advanced",
        "Empty attributes",
    ]


def test_the_value_of_a_property_is_read_first() -> None:
    assert section_of(model.Property, "value") is Section.VALUE
    assert section_of(model.Property, "value_type") is Section.VALUE
    assert section_of(model.Property, "id_short") is Section.IDENTIFICATION
    assert section_of(model.Property, "semantic_id") is Section.SEMANTICS
    assert section_of(model.Property, "qualifier") is Section.ADVANCED


def test_an_entry_of_a_list_has_no_section() -> None:
    assert section_of(model.Property, "Qualifier 0") is None


def test_the_position_of_a_list_item_is_part_of_its_identification() -> None:
    assert section_of(model.Property, "index") is Section.IDENTIFICATION


def test_read_mode_puts_an_empty_attribute_in_the_empty_section() -> None:
    place = place_of(model.Property, "qualifier", is_empty=True, editing=False)

    assert place is Section.EMPTY


def test_edit_mode_keeps_an_empty_attribute_in_its_section() -> None:
    place = place_of(model.Property, "value_id", is_empty=True, editing=True)

    assert place is Section.VALUE


def test_the_attributes_of_a_property_read_in_sections_in_read_mode() -> None:
    empty = {
        "embedded_data_specifications",
        "extension",
        "qualifier",
        "supplemental_semantic_id",
    }

    order = in_reading_order(
        model.Property, PROPERTY_ATTRIBUTES, empty, editing=False
    )

    assert order == [
        "value",
        "value_type",
        "value_id",
        "id_short",
        "category",
        "display_name",
        "description",
        "semantic_id",
        "embedded_data_specifications",
        "extension",
        "qualifier",
        "supplemental_semantic_id",
    ]


def test_the_description_follows_the_display_name_and_the_rest_stays() -> None:
    order = in_reading_order(
        model.Submodel,
        ["id_short", "description", "display_name", "administration", "id"],
        set(),
        editing=True,
    )

    assert order == [
        "id_short",
        "display_name",
        "description",
        "administration",
        "id",
    ]


def test_edit_mode_keeps_the_empty_ones_in_place_and_advanced_last() -> None:
    empty = {"extension", "qualifier", "supplemental_semantic_id"}

    order = in_reading_order(
        model.Property, PROPERTY_ATTRIBUTES, empty, editing=True
    )

    assert order[-3:] == [
        "embedded_data_specifications",
        "extension",
        "qualifier",
    ]
    assert order.index("supplemental_semantic_id") < order.index("qualifier")


@pytest.mark.parametrize("value", [None, "", [], set(), {}])
def test_nothing_set_and_empty_collections_hold_nothing(value: object) -> None:
    assert holds_nothing(value)


@pytest.mark.parametrize("value", [0, False, 0.0, "x", [1]])
def test_a_zero_a_false_and_a_text_hold_something(value: object) -> None:
    assert not holds_nothing(value)


def test_advanced_and_empty_can_start_closed() -> None:
    assert {Section.ADVANCED, Section.EMPTY} == CLOSED_AT_FIRST


def test_empty_attributes_start_closed() -> None:
    assert not starts_open(Section.EMPTY, has_content=False)


def test_advanced_starts_closed_while_it_holds_nothing() -> None:
    assert not starts_open(Section.ADVANCED, has_content=False)
    assert starts_open(Section.ADVANCED, has_content=True)


@pytest.mark.parametrize(
    "section", [Section.VALUE, Section.IDENTIFICATION, Section.SEMANTICS]
)
def test_the_sections_that_are_read_start_open(section: Section) -> None:
    assert starts_open(section, has_content=False)


def test_a_closed_section_that_starts_closed_names_its_attributes() -> None:
    text = header_text(Section.EMPTY, ["extension", "qualifier"], is_open=False)

    assert text == ("Empty attributes", "2", "extension, qualifier")


def test_an_open_section_reads_its_title_and_its_count() -> None:
    text = header_text(Section.VALUE, ["value", "valueType"], is_open=True)

    assert text == ("Value", "2", "")
