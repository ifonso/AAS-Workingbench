"""The category is deprecated: a read-only row with content, and none without."""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_property
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode
from aas_editor.settings.app_settings import CLEAR_ROW_ROLE
from aas_editor.settings.app_settings import NAME_ROLE


def _rows(attrs: Any) -> list[str]:
    proxy = attrs.model()
    return [
        proxy.index(number, 0).data(NAME_ROLE)
        for number in range(proxy.rowCount())
    ]


@pytest.fixture
def with_category(lab_class):
    prop = make_property("Element")
    prop.category = "PARAMETER"
    return lab_class(prop)


def test_an_element_without_a_category_has_no_row_in_edit_or_read_mode(
    lab_class,
) -> None:
    lab = lab_class(make_property("Element"))

    in_edit = _rows(lab.attrs())
    edit_mode().set_editing(False)
    in_read = _rows(lab.attrs())

    assert "category" not in in_edit
    assert "category" not in in_read
    assert "id_short" in in_edit


def test_a_category_with_content_is_a_row_that_cannot_be_edited(
    with_category,
) -> None:
    lab = with_category
    attrs = lab.attrs()
    index = lab.row(attrs, "category")

    flags = attrs.model().flags(index)
    value = index.data(Qt.ItemDataRole.DisplayRole)

    assert not flags & Qt.ItemFlag.ItemIsEditable
    assert value == "PARAMETER"
    assert "id_short" in _rows(attrs)


def test_typing_over_the_category_is_refused_with_the_reason(
    with_category,
) -> None:
    lab = with_category
    attrs = lab.attrs()
    before = snapshot(lab.package.objStore)

    edited = lab.set(attrs, "category", "VARIABLE")

    assert not edited
    assert "deprecated" in lab.refusal
    assert lab.element().category == "PARAMETER"
    assert snapshot(lab.package.objStore) == before
    assert not lab.stack.can_undo


def test_the_row_can_be_deleted_in_one_undo_step(with_category) -> None:
    lab = with_category
    attrs = lab.attrs()
    index = lab.row(attrs, "category").siblingAtColumn(0)
    before = snapshot(lab.package.objStore)

    cleared = attrs.model().setData(index, None, CLEAR_ROW_ROLE)
    after_clear = (lab.element().category, "category" in _rows(attrs))
    lab.stack.undo()

    assert cleared
    assert after_clear == (None, False)
    assert lab.element().category == "PARAMETER"
    assert "category" in _rows(lab.attrs())
    assert snapshot(lab.package.objStore) == before


def test_the_package_tree_column_refuses_a_category_too(
    with_category,
) -> None:
    lab = with_category
    proxy = lab.shown.view.model()
    element = lab.shown.index("submodels", "Submodel", "Element")
    column = next(
        number
        for number in range(proxy.columnCount())
        if proxy.headerData(number, Qt.Orientation.Horizontal) == "category"
    )

    edited = proxy.setData(
        element.siblingAtColumn(column), "VARIABLE", Qt.ItemDataRole.EditRole
    )

    assert not edited
    assert lab.element().category == "PARAMETER"


def test_the_hint_says_why_the_category_is_deprecated(with_category) -> None:
    from aas_editor.application.validation import hints_for
    from aas_editor.application.validation import validate_package

    lab = with_category

    report = validate_package(lab.package.save_source(), with_hints=True)

    (finding,) = [
        f
        for f in hints_for(report, lab.element())
        if f.rule_id == "EDT-HINT-CATEGORY"
    ]
    assert "deprecated" in finding.message
    assert isinstance(lab.element(), model.Property)
