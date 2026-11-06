"""F-EDT-05, F-EDT-06 and F-EDT-07 criteria that the first audit found open."""

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode
from aas_editor.application.hints import hints_mode
from aas_editor.settings.app_settings import OBJECT_ROLE

# -- F-EDT-05 AC1 ------------------------------------------------------------


def test_add_on_the_node_makes_a_description_with_a_generated_id(lab) -> None:
    before = snapshot(lab.package.objStore)

    lab.add(lambda form: None, "concept_descriptions")
    (concept,) = [
        o
        for o in lab.package.objStore
        if isinstance(o, model.ConceptDescription)
    ]

    assert concept.id.startswith("urn:uuid:")
    assert lab.shown.view.currentIndex().data(OBJECT_ROLE) is concept
    assert concept.id in lab.save_and_reload()
    lab.stack.undo()
    assert snapshot(lab.package.objStore) == before
    assert not lab.stack.can_undo


# -- F-EDT-06 AC11 and AC12 --------------------------------------------------


def _texts(proxy: object, parent: QModelIndex = QModelIndex()) -> list[object]:
    texts: list[object] = []
    for row in range(proxy.rowCount(parent)):  # type: ignore[attr-defined]
        first = proxy.index(row, 0, parent)  # type: ignore[attr-defined]
        for column in range(proxy.columnCount(parent)):  # type: ignore[attr-defined]
            texts.append(first.siblingAtColumn(column).data())
        texts.extend(_texts(proxy, first))
    return texts


def test_with_hints_off_no_hint_is_shown_and_the_fields_are_unchanged(
    lab_class, qtbot
) -> None:
    from aas_editor.ui.hints_bar import HintsBar

    prop = make_property(ELEMENT_ID, "text")
    prop.category = "PARAMETER"
    lab = lab_class(prop)
    attrs = lab.attrs()
    attrs.expandAll()
    bar = HintsBar()
    qtbot.addWidget(bar)
    bar.set_target(lab.package, lab.element())
    shown_with_hints = list(bar.lines)
    cells_with_hints = _texts(attrs.model())

    hints_mode().set_on(False)

    assert shown_with_hints
    assert bar.lines == []
    assert bar.isHidden()
    assert _texts(attrs.model()) == cells_with_hints
    assert lab.element().category == "PARAMETER"
    assert not lab.stack.can_undo


def test_in_read_mode_a_tab_offers_no_action_that_changes_something(
    lab_class,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "text"))
    attrs = lab.attrs()
    attrs.setCurrentIndex(lab.row(attrs, "category"))
    attrs.updateActions(attrs.currentIndex())
    assert any(act.isEnabled() for act in attrs.editingActions)

    edit_mode().set_editing(False)

    for action in attrs.editingActions:
        assert not action.isEnabled()
    for action in attrs.registeredActions.mutating_actions:
        assert not action.isEnabled()
    assert not attrs.addAct.isEnabled()


# -- F-EDT-07 AC6 ------------------------------------------------------------


@pytest.fixture
def two_qualifiers(lab_class):
    from aas_editor.ui.move_actions import register_move_actions

    register_move_actions()
    prop = make_property(ELEMENT_ID, "text")
    for name in ("First", "Second"):
        prop.qualifier.add(model.Qualifier(name, model.datatypes.String))
    lab = lab_class(prop)
    attrs = lab.attrs()
    attrs.expandAll()

    class Qualifiers:
        def select(self, number: int) -> None:
            row = lab.row(attrs, "qualifier", f"Qualifier {number}")
            index = row.siblingAtColumn(0)
            attrs.selectionModel().select(
                index, QItemSelectionModel.SelectionFlag.ClearAndSelect
            )
            attrs.setCurrentIndex(index)
            attrs.updateActions(index)

        def action(self, action_id: str):
            return attrs.registeredActions.find(action_id)

        def types(self) -> list[str]:
            return [q.type for q in lab.element().qualifier]

    qualifiers = Qualifiers()
    qualifiers.lab = lab
    return qualifiers


def test_the_last_qualifier_cannot_move_down_and_the_list_stays(
    two_qualifiers,
) -> None:
    two_qualifiers.select(1)
    before = snapshot(two_qualifiers.lab.package.objStore)

    enabled = two_qualifiers.action("structure.move_down").isEnabled()
    two_qualifiers.action("structure.move_down").trigger()

    assert not enabled
    assert two_qualifiers.types() == ["First", "Second"]
    assert snapshot(two_qualifiers.lab.package.objStore) == before
    assert not two_qualifiers.lab.stack.can_undo


def test_a_qualifier_moves_up_in_one_undo_step_and_the_file_follows(
    two_qualifiers,
) -> None:
    two_qualifiers.select(1)

    enabled = two_qualifiers.action("structure.move_up").isEnabled()
    two_qualifiers.action("structure.move_up").trigger()
    moved = two_qualifiers.types()
    saved = two_qualifiers.lab.save_and_reload()
    two_qualifiers.lab.stack.undo()

    assert enabled
    assert moved == ["Second", "First"]
    assert saved.index('"Second"') < saved.index('"First"')
    assert two_qualifiers.types() == ["First", "Second"]
    assert not two_qualifiers.lab.stack.can_undo


_ = Qt
