"""The cells of a tab suggest values for the attributes that have a list."""

from basyx.aas import model
from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtWidgets import QWidget
from tests.medium.conftest import ELEMENT_ID


def _suggestions(lab, attrs, name: str) -> list[str]:
    """Return what the editor of the cell of an attribute would suggest."""
    index = lab.row(attrs, name)
    parent = QWidget()
    editor = attrs.itemDelegate().createEditor(
        parent, QStyleOptionViewItem(), index
    )
    completer = editor.completer()
    if completer is None:
        return []
    items = completer.model()
    return [items.index(row, 0).data() for row in range(items.rowCount())]


def test_the_media_type_of_a_file_suggests_media_types(lab_class) -> None:
    lab = lab_class(model.File(ELEMENT_ID, "text/plain", "/aasx/a.txt"))

    suggestions = _suggestions(lab, lab.attrs(), "content_type")

    assert "application/json" in suggestions


def test_the_category_of_a_property_suggests_the_three_categories(
    lab_class,
) -> None:
    lab = lab_class(model.Property(ELEMENT_ID, model.datatypes.String, "x"))
    lab.element().category = "CONSTANT"

    suggestions = _suggestions(lab, lab.attrs(), "category")

    assert {"CONSTANT", "PARAMETER", "VARIABLE"} <= set(suggestions)


def test_a_cell_without_a_list_suggests_nothing(lab_class) -> None:
    lab = lab_class(model.File(ELEMENT_ID, "text/plain", "/aasx/a.txt"))

    assert _suggestions(lab, lab.attrs(), "value") == []
