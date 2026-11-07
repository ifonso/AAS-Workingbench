"""Delete, cut and copy act on the whole selection, also across parents.

F-EDT-09 AC2 and the Selection panel offer these actions for rows of several
parents. A selection that the action cannot serve is refused with a message,
and never done in part.
"""

import json
from pathlib import Path

import pytest
from PyQt6.QtCore import QItemSelection
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMessageBox
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

SUB1 = ("submodels", "Sub1")
SUB2 = ("submodels", "Sub2")
SUB3 = ("submodels", "Sub3")
SUB4 = ("submodels", "Sub4")


def _ids(container: object) -> list[str | None]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


@pytest.fixture
def crossing(views, monkeypatch: pytest.MonkeyPatch):
    """A package of three submodels and ways to act on a selection."""
    from aas_workingbench.ui import reference_dialogs
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions

    register_move_actions()
    register_paste_actions()
    problems: list[str] = []
    # The user agrees to the question that a destructive delete asks.
    monkeypatch.setattr(
        reference_dialogs, "confirm_delete", lambda plan, parent=None: True
    )
    monkeypatch.setattr(
        QMessageBox,
        "exec",
        lambda box: problems.append(box.text()) or 0,
    )
    QApplication.clipboard().clear()

    class Crossing:
        def __init__(self) -> None:
            self.problems = problems
            self.shown = views()
            self.view = self.shown.view
            self.view.treeClipboard.clear()
            self.sub1 = make_submodel(
                "urn:s1",
                "Sub1",
                [make_property("A1"), make_property("A2")],
            )
            self.sub2 = make_submodel(
                "urn:s2",
                "Sub2",
                [make_property("B1"), make_property("B2")],
            )
            self.sub3 = make_submodel("urn:s3", "Sub3", [make_property("C1")])
            self.sub4 = make_submodel(
                "urn:s4",
                "Sub4",
                [make_collection("Box", [make_property("In")])],
            )
            self.package = self.shown.open_package(
                self.sub1, self.sub2, self.sub3, self.sub4
            )
            self.stack = self.package.commandStack

        def select(self, *paths: tuple[str, ...], package: int = 0) -> None:
            self.shown.select(
                *(self.shown.index(*p, package=package) for p in paths)
            )
            self.view.updateActions(self.view.currentIndex())

        def select_rows(self, *paths: tuple[str, ...]) -> None:
            """Selects whole rows, so that every cell of a row is selected."""
            selection = self.view.selectionModel()
            selection.clear()
            model_ = self.view.model()
            for path in paths:
                index = self.shown.index(*path)
                last = index.siblingAtColumn(model_.columnCount() - 1)
                selection.select(
                    QItemSelection(index, last),
                    QItemSelectionModel.SelectionFlag.Select,
                )
            selection.setCurrentIndex(
                self.shown.index(*paths[-1]),
                QItemSelectionModel.SelectionFlag.NoUpdate,
            )
            self.view.updateActions(self.view.currentIndex())

        def clipboard_ids(self) -> list[str]:
            return [
                entry["idShort"]
                for entry in json.loads(QApplication.clipboard().text())
            ]

    return Crossing()


def test_delete_removes_the_rows_of_every_parent_in_one_undo_step(
    crossing,
) -> None:
    before = snapshot(crossing.package.objStore)
    crossing.select((*SUB1, "A1"), (*SUB2, "B2"))

    crossing.view.onDelClear()

    assert _ids(crossing.sub1.submodel_element) == ["A2"]
    assert _ids(crossing.sub2.submodel_element) == ["B1"]
    crossing.view.onUndo()
    assert snapshot(crossing.package.objStore) == before
    assert not crossing.stack.can_undo


def test_delete_of_whole_rows_removes_each_row_once(crossing) -> None:
    crossing.select_rows((*SUB1, "A1"), (*SUB2, "B1"), (*SUB2, "B2"))

    crossing.view.onDelClear()

    assert _ids(crossing.sub1.submodel_element) == ["A2"]
    assert _ids(crossing.sub2.submodel_element) == []


def test_delete_works_when_a_row_above_shifts_the_rows_below_it(
    crossing,
) -> None:
    # Deleting Sub2 moves Sub3 up, and C1 is a row of Sub3.
    crossing.select((*SUB1, "A1"), SUB2, (*SUB3, "C1"))

    crossing.view.onDelClear()

    assert _ids(crossing.sub1.submodel_element) == ["A2"]
    assert crossing.sub2 not in crossing.package.objStore
    assert crossing.sub3 in crossing.package.objStore
    assert _ids(crossing.sub3.submodel_element) == []


def test_delete_of_a_row_and_one_below_it_removes_only_the_parent(
    crossing,
) -> None:
    crossing.select((*SUB4, "Box"), (*SUB4, "Box", "In"), (*SUB2, "B1"))

    crossing.view.onDelClear()

    assert _ids(crossing.sub4.submodel_element) == []
    assert _ids(crossing.sub2.submodel_element) == ["B2"]


def test_cut_takes_the_rows_of_every_parent_and_paste_brings_them_back(
    crossing,
) -> None:
    crossing.select((*SUB1, "A1"), (*SUB2, "B2"))

    crossing.view.onCut()

    assert _ids(crossing.sub1.submodel_element) == ["A2"]
    assert _ids(crossing.sub2.submodel_element) == ["B1"]
    assert crossing.clipboard_ids() == ["A1", "B2"]
    crossing.select((*SUB3, "C1"))
    crossing.view.registeredActions.find("structure.paste_below").trigger()
    assert _ids(crossing.sub3.submodel_element) == ["C1", "A1", "B2"]


def test_copy_takes_the_rows_of_every_parent_in_the_order_of_the_tree(
    crossing,
) -> None:
    # The user clicked B2 first. The tree shows A1 above it.
    crossing.select((*SUB2, "B2"), (*SUB1, "A1"), (*SUB3, "C1"))

    crossing.view.onCopy()

    assert crossing.clipboard_ids() == ["A1", "B2", "C1"]
    crossing.select((*SUB3, "C1"))
    crossing.view.registeredActions.find("structure.paste_below").trigger()
    # A name that the target already has is numbered, the others are kept.
    assert _ids(crossing.sub3.submodel_element) == [
        "C1",
        "A1",
        "B2",
        "C1_1",
    ]
    assert _ids(crossing.sub1.submodel_element) == ["A1", "A2"]


def test_copy_of_whole_rows_holds_each_row_once(crossing) -> None:
    crossing.select_rows((*SUB1, "A1"), (*SUB2, "B1"))

    crossing.view.onCopy()

    assert crossing.clipboard_ids() == ["A1", "B1"]


def _two_packages(crossing):
    other = make_submodel("urn:o", "Other", [make_property("O1")])
    crossing.shown.open_package(other)
    return other


@pytest.mark.parametrize("act", ["delete", "cut", "copy"])
def test_rows_of_two_packages_are_refused_with_a_message_and_nothing_changes(
    crossing, act: str
) -> None:
    other = _two_packages(crossing)
    before = snapshot(crossing.package.objStore)
    crossing.select((*SUB2, "B1"))
    crossing.view.onCopy()
    buffered = QApplication.clipboard().text()
    crossing.select((*SUB1, "A1"))
    selection = crossing.view.selectionModel()
    selection.select(
        crossing.shown.index("submodels", "Other", "O1", package=1),
        QItemSelectionModel.SelectionFlag.Select,
    )

    {
        "delete": crossing.view.onDelClear,
        "cut": crossing.view.onCut,
        "copy": crossing.view.onCopy,
    }[act]()

    assert len(crossing.problems) == 1
    assert snapshot(crossing.package.objStore) == before
    assert _ids(other.submodel_element) == ["O1"]
    assert not crossing.stack.can_undo
    assert QApplication.clipboard().text() == buffered


def test_a_selection_in_one_package_is_not_refused_when_another_is_open(
    crossing,
) -> None:
    _two_packages(crossing)
    crossing.select((*SUB1, "A1"), (*SUB2, "B1"))

    crossing.view.onCopy()

    assert crossing.problems == []
    assert crossing.clipboard_ids() == ["A1", "B1"]


def test_a_saved_package_has_none_of_the_deleted_rows(
    crossing, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package

    crossing.select((*SUB1, "A1"), (*SUB2, "B2"))
    crossing.view.onDelClear()
    path = tmp_path / "out.aasx"
    crossing.package.write(path)

    saved = Package(path).objStore
    assert _ids(saved.get_item("urn:s1").submodel_element) == ["A2"]
    assert _ids(saved.get_item("urn:s2").submodel_element) == ["B1"]


def test_the_buttons_of_the_selection_panel_act_on_every_parent(
    crossing, qtbot
) -> None:
    from aas_workingbench.ui.selection_panel import SelectionPanel

    panel = SelectionPanel(crossing.view)
    qtbot.addWidget(panel)
    crossing.select((*SUB1, "A1"), (*SUB2, "B2"))

    panel.buttons["Delete"].click()

    assert _ids(crossing.sub1.submodel_element) == ["A2"]
    assert _ids(crossing.sub2.submodel_element) == ["B1"]
    assert crossing.problems == []


def test_rows_of_two_packages_are_not_moved(crossing) -> None:
    other = make_submodel(
        "urn:o", "Other", [make_property("O1"), make_property("O2")]
    )
    crossing.shown.open_package(other)
    crossing.select((*SUB1, "A2"))
    crossing.view.selectionModel().select(
        crossing.shown.index("submodels", "Other", "O2", package=1),
        QItemSelectionModel.SelectionFlag.Select,
    )
    crossing.view.updateActions(crossing.view.currentIndex())
    action = crossing.view.registeredActions.find("structure.move_up")

    enabled = action.isEnabled()
    action.trigger()

    assert not enabled
    assert _ids(crossing.sub1.submodel_element) == ["A1", "A2"]
    assert _ids(other.submodel_element) == ["O1", "O2"]
    assert not crossing.stack.can_undo
