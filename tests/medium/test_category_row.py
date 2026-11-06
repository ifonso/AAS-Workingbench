"""The category is deprecated, and stays editable, with a hint that says so."""

from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_property

from aas_editor.application.validation import hints_for
from aas_editor.application.validation import validate_package
from aas_editor.settings.app_settings import CLEAR_ROW_ROLE


@pytest.fixture
def with_category(lab_class: Any) -> Any:
    prop = make_property("Element")
    prop.category = "PARAMETER"
    return lab_class(prop)


def test_typing_over_the_category_changes_it_in_one_undo_step(
    with_category: Any,
) -> None:
    lab = with_category

    edited = lab.set(lab.attrs(), "category", "VARIABLE")
    changed = lab.element().category
    lab.stack.undo()

    assert edited
    assert changed == "VARIABLE"
    assert lab.element().category == "PARAMETER"


def test_an_element_without_a_category_can_get_one(lab_class: Any) -> None:
    lab = lab_class(make_property("Element"))

    assert lab.set(lab.attrs(), "category", "PARAMETER")

    assert lab.element().category == "PARAMETER"


def test_clearing_the_row_removes_the_category_in_one_undo_step(
    with_category: Any,
) -> None:
    lab = with_category
    attrs = lab.attrs()
    index = lab.row(attrs, "category").siblingAtColumn(0)

    cleared = attrs.model().setData(index, None, CLEAR_ROW_ROLE)
    after_clear = lab.element().category
    lab.stack.undo()

    assert cleared
    assert after_clear is None
    assert lab.element().category == "PARAMETER"


def test_the_hint_says_that_the_category_is_deprecated(
    with_category: Any,
) -> None:
    lab = with_category

    report = validate_package(lab.package.save_source(), with_hints=True)

    (finding,) = [
        f
        for f in hints_for(report, lab.element())
        if f.rule_id == "EDT-HINT-CATEGORY"
    ]
    assert "deprecated" in finding.message
    assert isinstance(lab.element(), model.Property)
