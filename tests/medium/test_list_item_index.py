"""An item of a SubmodelElementList shows its position, not an idShort (AC13)."""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_list
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.serialization import snapshot

STRING = model.datatypes.String
_holders: list[Any] = []


@pytest.fixture
def lab(lab_class: Any) -> Any:
    items = [model.Property(None, STRING, text) for text in ("a", "b", "c")]
    return lab_class(make_list(ELEMENT_ID, items))


def _item_tab(lab: Any, position: int) -> Any:
    """Opens the attributes of the item at a position, as a tab does."""
    from aas_editor.treeviews.treeview_detailed import AttrsTreeView
    from PyQt6.QtWidgets import QWidget

    proxy = lab.shown.view.model()
    child = proxy.index(position, 0, lab.shown.index(*ELEMENT_PATH))
    holder = QWidget()
    _holders.append(holder)  # a widget without a reference is deleted
    attrs = AttrsTreeView(holder)
    attrs.newPackItem(child)
    return attrs


def _rows(attrs: Any) -> dict[str, Any]:
    proxy = attrs.model()
    return {
        proxy.index(row, 0).data(): proxy.index(row, 1)
        for row in range(proxy.rowCount())
    }


def test_an_item_shows_its_position_and_no_idshort(lab: Any) -> None:
    rows = _rows(_item_tab(lab, 1))

    assert "id_short" not in rows
    assert rows["index"].data(Qt.ItemDataRole.DisplayRole) == "1"


def test_an_element_that_is_no_item_still_shows_its_idshort(
    lab_class: Any,
) -> None:
    lab = lab_class(model.Property(ELEMENT_ID, STRING, "x"))

    rows = _rows(lab.attrs())

    assert "index" not in rows
    assert rows["id_short"].data(Qt.ItemDataRole.DisplayRole) == ELEMENT_ID


def test_the_position_cannot_be_edited(lab: Any) -> None:
    attrs = _item_tab(lab, 0)
    index = _rows(attrs)["index"]
    before = snapshot(lab.package.objStore)

    flags = attrs.model().flags(index)
    edited = attrs.model().setData(index, 2, Qt.ItemDataRole.EditRole)

    assert not flags & Qt.ItemFlag.ItemIsEditable
    assert not edited
    assert not lab.stack.can_undo
    assert snapshot(lab.package.objStore) == before


def test_the_position_follows_an_item_that_is_removed_before_it(
    lab: Any,
) -> None:
    from aas_editor.application.changes import observer_for
    from aas_editor.application.edits import RemoveMember

    attrs = _item_tab(lab, 2)
    first = list(lab.element().value)[0]

    lab.stack.push(
        RemoveMember(observer_for(lab.package), lab.element().value, first)
    )

    shown = _rows(attrs)["index"].data(Qt.ItemDataRole.DisplayRole)
    assert shown == "1"


def test_the_position_follows_an_item_that_moves(lab: Any) -> None:
    from aas_editor.domain import ordering

    attrs = _item_tab(lab, 0)
    first = list(lab.element().value)[0]

    ordering.move_to(lab.element().value, first, 2)

    shown = _rows(attrs)["index"].data(Qt.ItemDataRole.DisplayRole)
    assert shown == "2"
