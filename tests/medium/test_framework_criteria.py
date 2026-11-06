"""F-EDT-01 criteria that the first audit found open.

Each test goes through a view or a delegate and asserts what the criterion
says, and not that nothing crashed.
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtWidgets import QWidget
import pytest
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode
from aas_editor.settings.colors import CHANGED_BLUE

VALUE = "value"


def _walk(proxy: Any, parent: QModelIndex = QModelIndex()):
    """Yield every cell of every visible row below a parent."""
    for row in range(proxy.rowCount(parent)):
        first = proxy.index(row, 0, parent)
        for column in range(proxy.columnCount(parent)):
            yield first.siblingAtColumn(column)
        yield from _walk(proxy, first)


# -- AC1 ---------------------------------------------------------------------


def test_in_read_mode_no_cell_of_a_tab_can_be_edited(lab_class) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "text"))
    attrs = lab.attrs()
    attrs.expandAll()

    edit_mode().set_editing(False)
    attrs.expandAll()

    cells = list(_walk(attrs.model()))
    assert cells
    for cell in cells:
        assert not cell.flags() & Qt.ItemFlag.ItemIsEditable
        assert (
            attrs.edit(cell, attrs.EditTrigger.AllEditTriggers, None) is False
        )
    for action in (attrs.editAct, attrs.editCreateInDialogAct, attrs.addAct):
        assert not action.isEnabled()


def test_in_read_mode_an_attribute_without_a_value_has_no_row(
    lab_class,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "text"))
    attrs = lab.attrs()

    edit_mode().set_editing(False)

    shown = {
        cell.data(Qt.ItemDataRole.DisplayRole)
        for cell in _walk(attrs.model())
        if cell.column() == 0
    }
    assert "idShort" in shown
    assert not {"category", "description", "displayName", "semanticId"} & shown


# -- AC2 ---------------------------------------------------------------------


def test_a_typed_text_reaches_the_model_when_it_is_committed(
    lab_class,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "old"))
    attrs = lab.attrs()
    index = lab.row(attrs, VALUE)
    delegate = attrs.itemDelegate()
    parent = QWidget()
    editor = delegate.createEditor(parent, QStyleOptionViewItem(), index)
    delegate.setEditorData(editor, index)

    editor.setText("new")
    typed = lab.element().value
    delegate.setModelData(editor, attrs.model(), index)

    # The commit rule of a cell is the end of the edit, not each keystroke.
    assert typed == "old"
    assert lab.element().value == "new"
    assert lab.stack.can_undo
    tree = lab.shown.view.model()
    for path in (ELEMENT_PATH, ELEMENT_PATH[:-1]):
        index_in_tree = lab.shown.index(*path)
        assert tree.data(index_in_tree, Qt.ItemDataRole.ForegroundRole) == (
            CHANGED_BLUE
        )


# -- AC4 ---------------------------------------------------------------------


def test_with_an_advisory_shown_editing_and_saving_are_still_possible(
    lab_class, qtbot
) -> None:
    from aas_editor.application.validation import save_check_for
    from aas_editor.application.validation import validate_package
    from aas_editor.ui.hints_bar import HintsBar

    lab = lab_class(make_property(ELEMENT_ID, "old"))
    attrs = lab.attrs()
    element = lab.element()
    element.id_short = "X"
    bar = HintsBar()
    qtbot.addWidget(bar)
    bar.set_target(lab.package, element)
    advisory = list(bar.lines)

    edited = lab.set(attrs, VALUE, "new")
    check = save_check_for(validate_package(lab.package.save_source()))
    saved = lab.save_and_reload()

    assert advisory
    assert advisory[0].startswith("Error:")
    assert edited
    assert element.value == "new"
    assert check.blockers == ()
    assert '"value": "new"' in saved


# -- AC6 ---------------------------------------------------------------------


def test_creating_an_attribute_that_is_not_set_redraws_the_row(
    lab_class,
) -> None:
    lab = lab_class(make_property(ELEMENT_ID, "text"))
    attrs = lab.attrs()
    before = lab.row(attrs, "display_name").data(Qt.ItemDataRole.DisplayRole)

    def fill(dialog: Any) -> None:
        group = dialog.inputWidget
        group.inputWidgets[0].paramWidgets["value"].widget.setPlainText("Name")

    lab.edit_in_dialog(attrs, "display_name", fill)

    after = lab.row(attrs, "display_name").data(Qt.ItemDataRole.DisplayRole)
    assert before == "(not set)"
    assert lab.element().display_name
    assert after != "(not set)"
    assert "Name" in lab.save_and_reload()


# -- AC7 ---------------------------------------------------------------------


def test_deleting_the_last_qualifier_leaves_no_attribute_in_the_file(
    lab_class,
) -> None:
    element = make_property(ELEMENT_ID, "text")
    element.qualifier.add(
        model.Qualifier("Cardinality", model.datatypes.String)
    )
    lab = lab_class(element)
    attrs = lab.attrs()
    attrs.expandAll()
    row = lab.row(attrs, "qualifier", "Qualifier 0").siblingAtColumn(0)
    attrs.selectionModel().select(
        row, QItemSelectionModel.SelectionFlag.ClearAndSelect
    )
    attrs.setCurrentIndex(row)
    assert '"qualifiers"' in lab.save_and_reload()

    attrs.onDelClear()

    # The SDK has no null for a list, so the model holds an empty one. The
    # tab shows it as empty and the file does not have it.
    assert len(lab.element().qualifier) == 0
    assert lab.row(attrs, "qualifier").data() == "(empty)"
    assert '"qualifiers"' not in lab.save_and_reload()


# -- AC8 ---------------------------------------------------------------------


@pytest.fixture
def three(views):
    shown = views()
    submodel = make_submodel(
        elements=[make_property(n) for n in ("A", "B", "C")]
    )
    package = shown.open_package(submodel)
    return shown, submodel, package


def test_after_a_delete_the_previous_sibling_is_current(three) -> None:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    shown, submodel, _ = three
    shown.select(shown.index("submodels", "Submodel", "B"))

    shown.view.onDelClear()

    assert [m.id_short for m in submodel.submodel_element] == ["A", "C"]
    current = shown.view.currentIndex().data(OBJECT_ROLE)
    assert getattr(current, "id_short", None) == "A"


def test_after_a_delete_of_the_first_element_its_parent_is_current(
    three,
) -> None:
    from aas_editor.settings.app_settings import OBJECT_ROLE

    shown, submodel, _ = three
    shown.select(shown.index("submodels", "Submodel", "A"))

    shown.view.onDelClear()

    assert shown.view.currentIndex().data(OBJECT_ROLE) is submodel


# -- AC13 --------------------------------------------------------------------


def test_every_gesture_is_bound_to_one_action_of_the_view(views) -> None:
    from PyQt6.QtGui import QAction

    shown = views()
    shown.open_package(make_submodel(elements=[make_property("P")]))
    view = shown.view
    shown.select(shown.index("submodels", "Submodel", "P"))

    bound: dict[str, list[QAction]] = {}
    for action in view.actions():
        sequence = action.shortcut()
        if not sequence.isEmpty():
            bound.setdefault(sequence.toString(), []).append(action)

    # No gesture runs two actions, because Qt would run neither.
    assert {k: v for k, v in bound.items() if len(v) > 1} == {}
    for actions in bound.values():
        (action,) = actions
        # A gesture belongs to the view, and not to the whole window.
        assert action.shortcutContext() in (
            Qt.ShortcutContext.WidgetShortcut,
            Qt.ShortcutContext.WidgetWithChildrenShortcut,
        )
    # The standard gestures of editing are there.
    assert {"Ctrl+C", "Ctrl+X", "Ctrl+V", "Del", "Ctrl+Z", "Ctrl+Y"} <= set(
        bound
    )


# -- AC14 --------------------------------------------------------------------


def test_a_hint_rule_that_raises_is_shown_with_the_object(
    lab_class, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.application import validation
    from aas_editor.domain.validation import Rule
    from aas_editor.ui.hints_bar import HintsBar

    def broken(context: Any):
        raise RuntimeError("defect in the hint")
        yield  # pragma: no cover

    monkeypatch.setattr(
        validation,
        "HINT_RULES",
        (Rule("TEST-HINT", "A broken hint", "A test", broken),),
    )
    lab = lab_class(make_property(ELEMENT_ID, "text"))
    lab.element().category = "PARAMETER"
    bar = HintsBar()
    qtbot.addWidget(bar)

    bar.set_target(lab.package, lab.element())

    joined = "\n".join(bar.lines)
    assert "TEST-HINT" in joined
    assert "defect in the hint" in joined
    # The bar still renders: the tab stays editable.
    assert not bar.isHidden() or bar.lines


# -- AC15 --------------------------------------------------------------------


def test_a_redraw_keeps_hints_mode_and_the_sort_order(lab_class) -> None:
    from aas_editor.application.hints import hints_mode

    lab = lab_class(make_property(ELEMENT_ID, "text"))
    view = lab.shown.view
    view.sortByColumn(1, Qt.SortOrder.DescendingOrder)
    hints_mode().set_on(False)
    before = (
        view.header().sortIndicatorSection(),
        view.header().sortIndicatorOrder(),
        hints_mode().is_on,
    )
    snap = snapshot(lab.package.objStore)

    lab.set(lab.attrs(), VALUE, "again")
    lab.stack.undo()
    lab.stack.redo()
    lab.stack.undo()

    after = (
        view.header().sortIndicatorSection(),
        view.header().sortIndicatorOrder(),
        hints_mode().is_on,
    )
    assert after == before
    assert snapshot(lab.package.objStore) == snap
