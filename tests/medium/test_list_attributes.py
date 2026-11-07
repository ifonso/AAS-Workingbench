"""The attributes of a SubmodelElementList that the SDK fixes in its constructor."""

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import Qt
import pytest
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH


@pytest.fixture
def numbers() -> model.SubmodelElementList:
    return model.SubmodelElementList(
        ELEMENT_ID,
        type_value_list_element=model.Property,
        value_type_list_element=datatypes.Int,
        order_relevant=True,
    )


@pytest.mark.parametrize(
    "attribute",
    ["order_relevant", "type_value_list_element", "value_type_list_element"],
)
def test_an_attribute_that_is_fixed_when_the_list_is_made_is_refused_with_a_reason(
    lab_class, numbers: model.SubmodelElementList, attribute: str
) -> None:
    lab = lab_class(numbers)
    attrs = lab.attrs()
    value = {
        "order_relevant": False,
        "type_value_list_element": model.Range,
        "value_type_list_element": datatypes.Long,
    }[attribute]

    edited = lab.set(attrs, attribute, value)

    assert not edited
    assert lab.refusal == (
        f"'{attribute}' cannot be changed after the SubmodelElementList is "
        "made. Choose 'Change list settings...' in the context menu of the "
        "list to rebuild it"
    )
    assert not lab.stack.can_undo


def test_the_order_of_a_list_is_shown_as_true_by_default(
    lab_class, numbers: model.SubmodelElementList
) -> None:
    lab = lab_class(numbers)
    attrs = lab.attrs()

    index = lab.row(attrs, "order_relevant")

    assert index.data(Qt.ItemDataRole.EditRole) is True
    assert index.data(Qt.ItemDataRole.DisplayRole) == "True"


def test_a_list_made_without_a_choice_for_the_order_keeps_the_default(
    lab_class,
) -> None:
    lab = lab_class()

    def fill(form) -> None:
        form.choose_type(model.SubmodelElementList)
        form.type_text("id_short", ELEMENT_ID)
        form.choose("type_value_list_element", model.File)

    lab.add(fill)

    assert lab.element().order_relevant is True


@pytest.mark.parametrize(
    "child_type",
    [
        model.SubmodelElementCollection,
        model.File,
        model.MultiLanguageProperty,
        model.Capability,
    ],
)
def test_a_list_of_items_that_have_no_value_type_takes_a_child_and_fixes_none(
    lab, child_type: type
) -> None:
    def make_list(form) -> None:
        form.choose_type(model.SubmodelElementList)
        form.type_text("id_short", ELEMENT_ID)
        form.choose("type_value_list_element", child_type)

    def add_child(form) -> None:
        pass

    lab.add(make_list)
    lab.add(add_child, *ELEMENT_PATH)

    assert lab.shown.shown_errors == []
    assert lab.element().value_type_list_element is None
    assert [type(child) for child in lab.element().value] == [child_type]


def test_a_list_read_from_a_file_with_a_value_type_but_no_numbers_takes_a_child(
    lab_class,
) -> None:
    from_a_file = model.SubmodelElementList(
        ELEMENT_ID,
        type_value_list_element=model.SubmodelElementCollection,
        value_type_list_element=datatypes.String,
    )
    lab = lab_class(from_a_file)

    lab.add(lambda form: None, *ELEMENT_PATH)

    assert lab.shown.shown_errors == []
    assert [type(child) for child in from_a_file.value] == [
        model.SubmodelElementCollection
    ]
