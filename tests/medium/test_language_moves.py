"""Moving language entries in a tab (F-EDT-06 AC15)."""

from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode


@pytest.fixture
def moving(lab_class):
    """A property with a description in three languages, shown in a tab."""
    from aas_editor.ui.move_actions import register_move_actions

    register_move_actions()
    prop = make_property("Element")
    prop.description = model.MultiLanguageTextType(
        {"en": "Pump", "de": "Pumpe", "fr": "Pompe"}
    )
    lab = lab_class(prop)

    class Moving:
        attrs = lab.attrs()
        prop = lab.element()

        @staticmethod
        def select(*numbers: int) -> None:
            from PyQt6.QtCore import QItemSelectionModel

            indexes = [
                lab.row(
                    Moving.attrs, "description", f"DictItem {number}"
                ).siblingAtColumn(0)
                for number in numbers
            ]
            selection = Moving.attrs.selectionModel()
            selection.clear()
            for index in indexes:
                selection.select(
                    index, QItemSelectionModel.SelectionFlag.Select
                )

        @staticmethod
        def action(action_id: str) -> Any:
            return Moving.attrs.registeredActions.find(action_id)

        @staticmethod
        def languages() -> list[str]:
            return list(Moving.prop.description or {})

        stack = lab.stack
        package = lab.package
        lab_ = lab

    return Moving


def test_move_down_changes_the_order_and_the_rows_follow(moving) -> None:
    moving.select(0)

    enabled = moving.action("structure.move_down").isEnabled()
    moving.action("structure.move_down").trigger()

    assert enabled
    assert moving.languages() == ["de", "en", "fr"]
    rows = [
        moving.lab_.row(moving.attrs, "description", f"DictItem {n}")
        .siblingAtColumn(1)
        .data()
        for n in range(3)
    ]
    assert [str(row) for row in rows] == ["de: Pumpe", "en: Pump", "fr: Pompe"]


def test_the_move_is_one_undo_step_and_is_saved(moving) -> None:
    before = snapshot(moving.package.objStore)
    moving.select(2)

    moving.action("structure.move_top").trigger()
    moved = moving.languages()
    saved = moving.lab_.save_and_reload()
    moving.stack.undo()

    assert moved == ["fr", "en", "de"]
    assert saved.index('"language": "fr"') < saved.index('"language": "en"')
    assert moving.languages() == ["en", "de", "fr"]
    assert snapshot(moving.package.objStore) == before
    assert not moving.stack.can_undo


def test_the_first_cannot_move_up_and_the_last_cannot_move_down(moving) -> None:
    moving.select(0)
    first = (
        moving.action("structure.move_up").isEnabled(),
        moving.action("structure.move_top").isEnabled(),
    )
    moving.select(2)
    last = (
        moving.action("structure.move_down").isEnabled(),
        moving.action("structure.move_end").isEnabled(),
    )

    assert first == (False, False)
    assert last == (False, False)


def test_two_rows_move_together(moving) -> None:
    moving.select(1, 2)

    moving.action("structure.move_up").trigger()

    assert moving.languages() == ["de", "fr", "en"]


def test_nothing_moves_in_read_mode(moving) -> None:
    moving.select(0)
    edit_mode().set_editing(False)
    moving.select(0)

    assert not moving.action("structure.move_down").isEnabled()
    assert moving.languages() == ["en", "de", "fr"]


def test_clicking_two_rows_keeps_both_selected_for_the_move(moving) -> None:
    # The user selects with the mouse, which makes the clicked row current and
    # refreshes the actions. A refresh that selects the current row alone
    # would leave the move with one row.
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest

    attrs = moving.attrs
    attrs.resize(600, 400)
    attrs.expandAll()
    cells = [
        moving.lab_.row(attrs, "description", f"DictItem {n}").siblingAtColumn(
            0
        )
        for n in (1, 2)
    ]

    QTest.mouseClick(
        attrs.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        attrs.visualRect(cells[0]).center(),
    )
    QTest.mouseClick(
        attrs.viewport(),
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ControlModifier,
        attrs.visualRect(cells[1]).center(),
    )

    selected = {i.row() for i in attrs.selectionModel().selectedRows()}
    assert selected == {1, 2}
    moving.action("structure.move_up").trigger()
    assert moving.languages() == ["de", "fr", "en"]
