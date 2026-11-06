"""Moving rows with the move actions: do, undo, redo, save, and reload."""

from pathlib import Path

from basyx.aas import model
import pytest
from PyQt6.QtCore import Qt
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_list
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.editing import edit_mode

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def moves(views):
    """A package that the move actions work on, and ways to drive them."""
    from aas_editor.package import Package
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.ui.move_actions import register_move_actions

    register_move_actions()

    class Moves:
        def __init__(self, *elements: model.SubmodelElement, extra=()):
            self.shown = views()
            self.submodel = make_submodel(elements=elements)
            self.package = self.shown.open_package(self.submodel, *extra)
            self.view = self.shown.view

        def select(self, *paths: tuple[str, ...]) -> None:
            self.shown.select(*(self.shown.index(*SUBMODEL, *p) for p in paths))

        def act(self, action_id: str) -> bool:
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            action.trigger()
            return enabled

        def enabled(self, action_id: str) -> bool:
            return self.view.registeredActions.find(action_id).isEnabled()

        def rows(self, *path: str) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(*SUBMODEL, *path)
            return [
                proxy.index(row, 0, parent).data(NAME_ROLE)
                for row in range(proxy.rowCount(parent))
            ]

        def saved(self, tmp_path: Path) -> model.Submodel:
            path = tmp_path / "moved.aasx"
            self.package.write(path)
            return Package(path).objStore.get_item(self.submodel.id)

    return Moves


def _ids(container) -> list[str]:
    return [m.id_short for m in container]


def test_the_row_moves_with_the_object_and_survives_save_and_reload(
    moves, tmp_path
) -> None:
    lab = moves(make_property("A"), make_property("B"), make_property("C"))
    lab.select(("C",))

    lab.act("structure.move_top")
    after = (lab.rows(), _ids(lab.submodel.submodel_element))
    saved = _ids(lab.saved(tmp_path).submodel_element)
    lab.view.onUndo()
    undone = (lab.rows(), _ids(lab.submodel.submodel_element))
    lab.view.onRedo()
    redone = (lab.rows(), _ids(lab.submodel.submodel_element))

    assert after == (["C", "A", "B"], ["C", "A", "B"])
    assert saved == ["C", "A", "B"]
    assert undone == (["A", "B", "C"], ["A", "B", "C"])
    assert redone == after


@pytest.mark.parametrize(
    ("action", "start", "expected"),
    [
        ("structure.move_up", "B", ["B", "A", "C"]),
        ("structure.move_down", "B", ["A", "C", "B"]),
        ("structure.move_top", "C", ["C", "A", "B"]),
        ("structure.move_end", "A", ["B", "C", "A"]),
    ],
)
def test_each_move_changes_the_saved_order(
    moves, tmp_path, action: str, start: str, expected: list[str]
) -> None:
    lab = moves(make_property("A"), make_property("B"), make_property("C"))
    lab.select((start,))

    lab.act(action)

    assert lab.rows() == expected
    assert _ids(lab.saved(tmp_path).submodel_element) == expected


def test_the_selection_stays_on_the_moved_row(moves) -> None:
    lab = moves(make_property("A"), make_property("B"), make_property("C"))
    lab.select(("B",))

    lab.act("structure.move_down")

    assert lab.view.currentIndex().data(Qt.ItemDataRole.DisplayRole) == "B"
    selected = {i.row() for i in lab.view.selectedIndexes()}
    assert selected == {2}


def test_enabled_states_follow_the_place_of_the_row(moves) -> None:
    lab = moves(make_property("A"), make_property("B"))
    lab.select(("A",))
    first = {
        "up": lab.enabled("structure.move_up"),
        "top": lab.enabled("structure.move_top"),
        "down": lab.enabled("structure.move_down"),
        "end": lab.enabled("structure.move_end"),
    }

    lab.act("structure.move_down")
    last = {
        "up": lab.enabled("structure.move_up"),
        "top": lab.enabled("structure.move_top"),
        "down": lab.enabled("structure.move_down"),
        "end": lab.enabled("structure.move_end"),
    }

    assert first == {"up": False, "top": False, "down": True, "end": True}
    assert last == {"up": True, "top": True, "down": False, "end": False}


def test_a_submodel_cannot_be_moved(moves) -> None:
    lab = moves(make_property("A"), make_property("B"))
    lab.shown.select(lab.shown.index(*SUBMODEL))

    assert not any(
        lab.enabled(f"structure.move_{kind}")
        for kind in ("up", "down", "top", "end")
    )


def test_several_rows_move_together_as_one_undo_step(moves) -> None:
    lab = moves(*(make_property(n) for n in "ABCD"))
    lab.select(("B",), ("D",))
    steps_before = lab.package.commandStack.can_undo

    lab.act("structure.move_up")
    moved = _ids(lab.submodel.submodel_element)
    lab.view.onUndo()

    assert not steps_before
    assert moved == ["B", "A", "D", "C"]
    assert _ids(lab.submodel.submodel_element) == list("ABCD")
    assert not lab.package.commandStack.can_undo


def test_a_sorted_tree_goes_back_to_the_order_of_the_package(moves) -> None:
    lab = moves(make_property("Z"), make_property("A"), make_property("M"))
    lab.view.header().sectionClicked.emit(0)  # sort ascending by name
    sorted_rows = lab.rows()
    lab.select(("M",))

    lab.act("structure.move_up")

    assert sorted_rows == ["A", "M", "Z"]
    assert lab.rows() == _ids(lab.submodel.submodel_element) == ["Z", "M", "A"]
    assert lab.view.header().sortIndicatorSection() == -1


def test_the_rows_of_a_new_tree_are_in_the_order_of_the_package(moves) -> None:
    lab = moves(make_property("Zeta"), make_property("Alpha"))

    assert lab.rows() == ["Zeta", "Alpha"]


def test_objects_without_a_saved_order_are_sorted_by_name(moves) -> None:
    lab = moves(
        make_property("A"),
        extra=(
            make_submodel(id_="urn:b", id_short="Zzz"),
            make_submodel(id_="urn:c", id_short="Aaa"),
        ),
    )
    proxy = lab.view.model()
    node = lab.shown.index("submodels")

    names = [
        proxy.index(row, 0, node).data(Qt.ItemDataRole.DisplayRole)
        for row in range(proxy.rowCount(node))
    ]

    assert names == ["Aaa", "Submodel", "Zzz"]


def test_read_mode_disables_the_moves_and_refuses_them(moves) -> None:
    lab = moves(make_property("A"), make_property("B"))
    lab.select(("B",))
    edit_mode().set_editing(False)
    lab.view.updateActions(lab.view.currentIndex())

    enabled = lab.enabled("structure.move_up")

    assert not enabled
    assert _ids(lab.submodel.submodel_element) == ["A", "B"]


def test_list_items_move_and_references_to_them_follow(
    moves, tmp_path
) -> None:
    items = [make_property("a", "1"), make_property("b", "2")]
    holder = make_submodel(id_="urn:holder", id_short="Holder")
    lab = moves(make_list("List", items), extra=(holder,))
    holder.submodel_element.add(
        model.ReferenceElement(
            id_short="ToA", value=model.ModelReference.from_referable(items[0])
        )
    )
    lab.select(("List", "a"))

    lab.act("structure.move_end")

    reloaded = lab.saved(tmp_path)
    from aas_editor.package import Package

    other = Package(tmp_path / "moved.aasx").objStore.get_item(
        "urn:holder"
    )
    target = other.get_referable("ToA").value
    resolved = target.resolve(Package(tmp_path / "moved.aasx").objStore)
    assert [m.value for m in reloaded.get_referable("List").value] == [
        "2",
        "1",
    ]
    assert target.key[-1].value == "1"
    assert resolved.value == "1"
    lab.view.onUndo()
    assert (
        holder.get_referable("ToA").value.key[-1].value == "0"
    )


@pytest.mark.parametrize("kind", ["operation", "entity", "annotation"])
def test_other_ordered_members_move_and_save_in_order(
    moves, tmp_path, kind: str
) -> None:
    if kind == "operation":
        parent = make_operation(
            input_variables=[make_property("I1"), make_property("I2")]
        )
        path = ("Operation", "input_variable")
        read = lambda sm: _ids(sm.get_referable("Operation").input_variable)  # noqa: E731
    elif kind == "entity":
        parent = make_entity(statements=[make_property("S1"), make_property("S2")])
        path = ("Entity",)
        read = lambda sm: _ids(sm.get_referable("Entity").statement)  # noqa: E731
    else:
        parent = make_annotated_relationship(
            annotations=[make_property("N1"), make_property("N2")]
        )
        path = ("Relationship",)
        read = lambda sm: _ids(sm.get_referable("Relationship").annotation)  # noqa: E731
    lab = moves(parent)
    first, second = lab.rows(*path)
    lab.select((*path, second))

    lab.act("structure.move_up")

    assert read(lab.submodel) == [second, first]
    assert read(lab.saved(tmp_path)) == [second, first]
    lab.view.onUndo()
    assert read(lab.submodel) == [first, second]


def test_collection_children_move(moves, tmp_path) -> None:
    lab = moves(make_collection("Coll", [make_property("x"), make_property("y")]))
    lab.select(("Coll", "y"))

    lab.act("structure.move_top")

    assert _ids(lab.saved(tmp_path).get_referable("Coll").value) == ["y", "x"]


def test_undo_of_a_delete_puts_the_row_back_where_it_was(moves) -> None:
    lab = moves(*(make_property(n) for n in "ABC"))
    lab.select(("B",))

    lab.view.onDelClear()
    deleted = lab.rows()
    lab.view.onUndo()

    assert deleted == ["A", "C"]
    assert lab.rows() == _ids(lab.submodel.submodel_element) == list("ABC")


def test_undo_of_a_delete_from_an_unordered_set_returns_to_the_sorted_place(
    moves, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.ui import reference_dialogs

    monkeypatch.setattr(reference_dialogs, "confirm_delete", lambda *a: True)
    other = make_submodel(id_="urn:other", id_short="Zzz")
    lab = moves(make_property("A"), extra=(other, make_submodel(id_="urn:a", id_short="Aaa")))
    proxy = lab.view.model()
    node = lab.shown.index("submodels")
    target = lab.shown.index("submodels", "Submodel")
    lab.shown.select(target)

    def shown() -> list[str]:
        return [
            proxy.index(row, 0, node).data(Qt.ItemDataRole.DisplayRole)
            for row in range(proxy.rowCount(node))
        ]

    lab.view.onDelClear()
    deleted = shown()
    lab.view.onUndo()

    assert deleted == ["Aaa", "Zzz"]
    assert shown() == ["Aaa", "Submodel", "Zzz"]
