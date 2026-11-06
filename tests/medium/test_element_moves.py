"""Each of the 14 element types moves in a submodel, and the move survives.

The plan's exit criteria ask that every type can be created, edited, moved
where valid, undone, saved, and reloaded. `test_element_types.py` does the
first, second, fourth, fifth and sixth for each type, and this file does the
move, with the same save and reload.
"""

from pathlib import Path

from basyx.aas import model
import pytest
from tests.factories import make_annotated_relationship
from tests.factories import make_entity
from tests.factories import make_submodel

SUBMODEL = ("submodels", "Submodel")


def _every_element_type() -> list[model.SubmodelElement]:
    """One element of each of the 14 types, named after its class."""
    ref = model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, "urn:sm"),), model.Submodel
    )
    return [
        model.Property("Property", model.datatypes.String, value="x"),
        model.MultiLanguageProperty(
            "MultiLanguageProperty",
            value=model.MultiLanguageTextType({"en": "x"}),
        ),
        model.Range("Range", model.datatypes.Int, min=1, max=2),
        model.File("File", "text/plain"),
        model.Blob("Blob", "application/octet-stream", value=b"1"),
        model.ReferenceElement("ReferenceElement", value=ref),
        model.RelationshipElement("RelationshipElement", ref, ref),
        make_annotated_relationship("AnnotatedRelationshipElement"),
        make_entity("Entity"),
        model.Operation("Operation"),
        model.Capability("Capability"),
        model.BasicEventElement(
            "BasicEventElement",
            observed=ref,
            direction=model.Direction.OUTPUT,
            state=model.StateOfEvent.ON,
        ),
        model.SubmodelElementCollection("SubmodelElementCollection"),
        model.SubmodelElementList(
            "SubmodelElementList",
            model.Property,
            value_type_list_element=model.datatypes.Int,
        ),
    ]


@pytest.fixture
def moves(views):
    """A submodel with one element of each type, and the move actions."""
    from aas_editor.package import Package
    from aas_editor.ui.move_actions import register_move_actions

    register_move_actions()

    class Moves:
        def __init__(self) -> None:
            self.shown = views()
            self.elements = _every_element_type()
            self.submodel = make_submodel(elements=self.elements)
            self.package = self.shown.open_package(self.submodel)
            self.view = self.shown.view

        def move(self, name: str, action_id: str) -> None:
            self.shown.select(self.shown.index(*SUBMODEL, name))
            action = self.view.registeredActions.find(action_id)
            assert action.isEnabled()
            action.trigger()

        def order(self) -> list[str]:
            return [e.id_short for e in self.submodel.submodel_element]

        def saved_order(self, tmp_path: Path) -> list[str]:
            path = tmp_path / "moved.aasx"
            self.package.write(path)
            reloaded = Package(path).objStore.get_item(self.submodel.id)
            assert isinstance(reloaded, model.Submodel)
            return [e.id_short for e in reloaded.submodel_element]

    return Moves()


def test_there_is_a_case_for_every_element_type() -> None:
    kinds = {type(element) for element in _every_element_type()}

    assert len(kinds) == 14


@pytest.mark.parametrize(
    "name", [element.id_short for element in _every_element_type()]
)
def test_each_type_moves_and_back_through_save_and_reload(
    moves, tmp_path: Path, name: str
) -> None:
    before = moves.order()
    # The first element cannot go up and the others can, so it goes to the end.
    if name == before[0]:
        action = "structure.move_end"
        expected = [*before[1:], name]
    else:
        action = "structure.move_top"
        expected = [name, *[n for n in before if n != name]]

    moves.move(name, action)
    moved = moves.order()
    saved = moves.saved_order(tmp_path)
    moves.view.onUndo()
    undone = moves.order()
    moves.view.onRedo()
    redone = moves.order()

    assert moved == expected
    assert saved == expected
    assert undone == before
    assert redone == expected
