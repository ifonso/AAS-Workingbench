"""The rows that group a package's objects show a change only if it is theirs.

The shells, submodels, and concept descriptions of a package share one object
store. A mark on the store said that something in it changed, so after an edit
to a property all three rows showed as changed, and a person could not tell
where the change was.
"""

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import SetAttribute
from aas_editor.settings.app_settings import CHANGE_MARK_ROLE
from aas_editor.settings.app_settings import MARK_CHANGED

SHELLS = "shells"
SUBMODELS = "submodels"
CONCEPTS = "concept_descriptions"


@pytest.fixture
def world(model_support):
    """A package with a shell, a submodel with a property, and a concept."""
    pump = make_property("Pump", "on")
    submodel = make_submodel(elements=[pump])
    shell = make_shell()
    concept = make_concept_description()
    table = model_support.pack_table(shell, submodel, concept)
    package = model_support.package_of(table)

    class World:
        element = pump
        stack = package.commandStack
        observer = observer_for(package)
        store = package.objStore

        @staticmethod
        def mark_of(folder: str) -> object:
            return model_support.find_path(table, "", folder).data(
                CHANGE_MARK_ROLE
            )

        @staticmethod
        def folders_marked() -> set[str]:
            return {
                folder
                for folder in (SHELLS, SUBMODELS, CONCEPTS)
                if World.mark_of(folder) == MARK_CHANGED
            }

        @staticmethod
        def edit_value(value: str) -> None:
            package.commandStack.push(
                SetAttribute(observer_for(package), pump, "value", value)
            )

    return World


def _first(world, kind: type) -> object:
    return next(obj for obj in world.store if isinstance(obj, kind))


def test_nothing_is_marked_before_a_change(world) -> None:
    assert world.folders_marked() == set()


def test_an_edit_to_a_property_marks_only_the_row_of_the_submodels(
    world,
) -> None:
    world.edit_value("off")

    assert world.folders_marked() == {SUBMODELS}


def test_a_second_change_in_another_group_marks_that_group_too(world) -> None:
    world.edit_value("off")
    shell = _first(world, model.AssetAdministrationShell)
    world.stack.push(SetAttribute(world.observer, shell, "id_short", "Other"))

    assert world.folders_marked() == {SUBMODELS, SHELLS}


def test_removing_a_submodel_marks_the_row_it_was_in(world) -> None:
    submodel = _first(world, model.Submodel)

    world.stack.push(RemoveMember(world.observer, world.store, submodel))

    assert world.folders_marked() == {SUBMODELS}


def test_adding_a_concept_description_marks_the_row_of_the_concepts(
    world,
) -> None:
    added = make_concept_description("urn:example:added", "Added")

    world.stack.push(AddMember(world.observer, world.store, added))

    assert world.folders_marked() == {CONCEPTS}


def test_a_save_clears_the_row_that_changed(world) -> None:
    world.edit_value("off")

    world.stack.mark_saved()

    assert world.folders_marked() == set()


def test_undo_to_the_saved_state_clears_the_row_that_changed(world) -> None:
    world.edit_value("off")

    world.stack.undo()

    assert world.folders_marked() == set()
