"""The columns of the attributes of an object give room to what users edit."""

from tests.factories import make_property
from tests.factories import make_submodel

# A value such as a generated id, or a short sentence.
ENOUGH_FOR_A_VALUE = 300


def test_the_value_column_is_wider_than_the_type_column(views) -> None:
    from aas_editor.settings.app_settings import TYPE_COLUMN
    from aas_editor.settings.app_settings import VALUE_COLUMN

    shown = views()
    shown.open_package(make_submodel(elements=[make_property("Speed")]))

    attrs = shown.attrs_view("submodels", "Submodel", "Speed")

    assert attrs.columnWidth(VALUE_COLUMN) >= ENOUGH_FOR_A_VALUE
    assert attrs.columnWidth(VALUE_COLUMN) > attrs.columnWidth(TYPE_COLUMN)
