"""The panel for a selection of several rows (F-EDT-09 AC1)."""

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMainWindow
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.editing import edit_mode

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def panel(views, qtbot):
    """A package of six properties, its tree view, and the panel."""
    from aas_editor.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.selection_panel import SelectionPanel

    register_move_actions()
    register_bulk_edit_actions()

    class Lab:
        def __init__(self, *elements) -> None:
            self.shown = views()
            self.submodel = make_submodel(
                elements=elements or [make_property(n) for n in "ABCDEF"]
            )
            self.package = self.shown.open_package(self.submodel)
            self.view = self.shown.view
            self.panel = SelectionPanel(self.view)
            qtbot.addWidget(self.panel)

        def select(self, *paths: tuple[str, ...]) -> None:
            self.shown.select(*(self.shown.index(*SUBMODEL, *p) for p in paths))
            self.view.updateActions(self.view.currentIndex())

        def shown_buttons(self) -> list[str]:
            return [
                text
                for text, button in self.panel.buttons.items()
                if not button.isHidden()
            ]

        def rows(self) -> list[str]:
            return [m.id_short for m in self.submodel.submodel_element]

    return Lab


def test_two_siblings_give_the_header_and_the_actions_of_a_selection(
    panel,
) -> None:
    lab = panel()

    lab.select(("B",), ("D",))

    assert lab.panel.header_label.text() == "Multiple selected elements"
    assert "2 Property" in lab.panel.detail_label.text()
    assert (
        lab.shown_buttons()
        == [
            "Move up",
            "Move down",
            "Move to top",
            "Move to end",
            "Cut",
            "Copy",
            "Delete",
            "Change attribute...",
            "Remove extensions...",
        ][: len(lab.shown_buttons())]
    )
    assert {"Move up", "Cut", "Copy", "Delete", "Change attribute..."} <= set(
        lab.shown_buttons()
    )


def test_one_row_shows_a_hint_and_no_buttons(panel) -> None:
    lab = panel()

    lab.select(("B",))

    assert lab.panel.header_label.text() == "One element selected"
    assert "Ctrl+click" in lab.panel.detail_label.text()
    assert lab.shown_buttons() == []


def test_a_button_does_what_the_menu_entry_does(panel) -> None:
    lab = panel()
    lab.select(("C",), ("E",))

    lab.panel.buttons["Move up"].click()

    assert lab.rows() == list("ACEBDF")
    lab.view.onUndo()
    assert lab.rows() == list("ABCDEF")


def test_a_move_that_cannot_change_anything_is_disabled(panel) -> None:
    lab = panel()

    lab.select(("A",), ("D",))

    assert not lab.panel.buttons["Move up"].isEnabled()
    assert lab.panel.buttons["Move to top"].isEnabled()
    assert lab.panel.buttons["Move down"].isEnabled()


def test_the_buttons_that_change_a_package_are_off_in_read_mode(panel) -> None:
    lab = panel()
    lab.select(("B",), ("D",))
    edit_mode().set_editing(False)
    lab.view.updateActions(lab.view.currentIndex())

    states = {
        text: button.isEnabled() for text, button in lab.panel.buttons.items()
    }

    assert not any(states[t] for t in ("Move up", "Cut", "Delete"))


def test_variables_of_mixed_directions_get_cut_and_copy_only(panel) -> None:
    operation = make_operation(
        input_variables=[make_property("I1")],
        output_variables=[make_property("O1")],
    )
    lab = panel(operation)

    lab.select(
        ("Operation", "input_variable", "I1"),
        ("Operation", "output_variable", "O1"),
    )

    shown = lab.shown_buttons()
    assert "Cut" in shown and "Copy" in shown
    assert not any(t.startswith("Move") or t == "Delete" for t in shown)
    assert "different directions" in lab.panel.detail_label.text()


def test_rows_of_different_parents_are_said_to_be(panel) -> None:
    from tests.factories import make_collection

    lab = panel(
        make_collection("C1", [make_property("A")]),
        make_collection("C2", [make_property("B")]),
    )

    lab.select(("C1", "A"), ("C2", "B"))

    assert "2 different parents" in lab.panel.detail_label.text()


def test_the_dock_opens_for_a_selection_until_the_user_closes_it(
    panel, qtbot
) -> None:
    from aas_editor.ui.selection_panel import SelectionDock

    lab = panel()
    window = QMainWindow()
    qtbot.addWidget(window)
    dock = SelectionDock(lab.view, window)
    window.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
    window.show()

    lab.select(("B",))
    one = dock.isVisible()
    lab.select(("B",), ("D",))
    many = dock.isVisible()
    dock.close()
    lab.select(("A",))
    lab.select(("B",), ("D",))
    after_close = dock.isVisible()

    assert (one, many, after_close) == (False, True, False)
