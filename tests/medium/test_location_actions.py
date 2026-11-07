"""Push location and Pop location in the package tree (F-EDT-01 AC10, AC11)."""

import pytest
from PyQt6.QtGui import QKeySequence
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.application.locations import default_stack

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def places(views):
    """A package with a collection, and the two actions."""
    from aas_workingbench.ui.location_actions import POP_ID
    from aas_workingbench.ui.location_actions import PUSH_ID
    from aas_workingbench.ui.location_actions import register_location_actions

    register_location_actions()
    default_stack().clear()

    class Places:
        def __init__(self) -> None:
            self.shown = views()
            self.submodel = make_submodel(
                elements=[
                    make_collection("Coll", [make_property("Inner")]),
                    make_property("Other"),
                ]
            )
            self.package = self.shown.open_package(self.submodel)
            self.view = self.shown.view

        def go(self, *path: str) -> None:
            self.shown.select(self.shown.index(*SUBMODEL, *path))
            self.view.updateActions(self.view.currentIndex())

        def run(self, action_id: str) -> bool:
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            action.trigger()
            return enabled

        def current(self) -> str:
            return self.view.currentIndex().data(0)

        def push(self) -> bool:
            return self.run(PUSH_ID)

        def pop(self) -> bool:
            return self.run(POP_ID)

    yield Places()
    default_stack().clear()


def test_pop_selects_the_pushed_row_with_its_expand_state(places) -> None:
    places.go("Coll")
    places.view.expand(places.view.currentIndex())
    places.push()
    places.go("Other")
    places.view.collapse(places.shown.index(*SUBMODEL, "Coll"))

    places.pop()

    assert places.current() == "Coll"
    assert places.view.isExpanded(places.view.currentIndex())
    assert {
        i.data(0) for i in places.view.selectedIndexes() if i.column() == 0
    } == {"Coll"}


def test_a_collapsed_row_comes_back_collapsed(places) -> None:
    places.go("Coll")
    places.view.collapse(places.view.currentIndex())
    places.push()
    places.go("Other")
    places.view.expand(places.shown.index(*SUBMODEL, "Coll"))

    places.pop()

    assert not places.view.isExpanded(places.view.currentIndex())


def test_pop_goes_back_through_the_pushes_in_reverse(places) -> None:
    places.go("Coll")
    places.push()
    places.go("Other")
    places.push()
    places.go()

    places.pop()
    first = places.current()
    places.pop()

    assert (first, places.current()) == ("Other", "Coll")


def test_pop_on_an_empty_stack_changes_nothing_and_does_not_fail(
    places,
) -> None:
    places.go("Other")

    offered = places.pop()

    assert offered
    assert places.current() == "Other"


def test_a_pushed_row_that_was_deleted_is_skipped(places) -> None:
    places.go("Other")
    places.push()
    places.go("Coll")
    places.push()
    places.view.onDelClear(confirm=False)
    places.go()

    places.pop()

    assert places.current() == "Other"


def test_push_and_pop_work_in_read_mode(places) -> None:
    places.go("Coll")
    edit_mode().set_editing(False)
    places.view.updateActions(places.view.currentIndex())
    places.push()
    places.go("Other")

    places.pop()

    assert places.current() == "Coll"


def test_push_is_not_offered_for_a_row_that_names_no_object(places) -> None:
    places.shown.select(places.shown.index("submodels"))
    places.view.updateActions(places.view.currentIndex())

    offered = places.run("navigate.push_location")

    assert not offered
    assert len(default_stack()) == 0


def test_the_shortcuts_collide_with_no_other_shortcut(places) -> None:
    from aas_workingbench.settings import shortcuts
    from aas_workingbench.ui.location_actions import POP_KEY
    from aas_workingbench.ui.location_actions import PUSH_KEY

    taken: list[QKeySequence] = []
    for name in dir(shortcuts):
        value = getattr(shortcuts, name)
        if name.startswith("SC_"):
            if isinstance(value, QKeySequence.StandardKey):
                taken.extend(QKeySequence.keyBindings(value))
            else:
                taken.append(value)
    for action in places.view.actions():
        if action.text() not in ("Push location", "Pop location"):
            taken.extend(action.shortcuts())

    for key in (PUSH_KEY, POP_KEY):
        wanted = QKeySequence(key)
        assert not any(
            wanted.matches(other) != QKeySequence.SequenceMatch.NoMatch
            for other in taken
        ), key
