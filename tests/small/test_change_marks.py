"""The marks of changed objects follow the command stack (F-EDT-01 AC3)."""

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.change_marks import ChangeMarks
from aas_editor.application.change_marks import MarkUpdate
from aas_editor.application.change_marks import is_markable
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import SetAttribute


class Package:
    """What the marks need of a package: an observer and a stack."""

    def __init__(self) -> None:
        self.observer = ModelChangeObserver()
        self.stack = CommandStack(100)
        self.marks = ChangeMarks(self.observer, self.stack)
        self.updates: list[MarkUpdate] = []
        self.subscription = self.marks.subscribe(self.updates.append)


def _setup() -> tuple[Package, model.Submodel, model.Property]:
    child = make_property("Child")
    collection = make_collection("Collection", [child])
    submodel = make_submodel(elements=[collection])
    return Package(), submodel, child


def test_an_edit_marks_the_object_and_the_objects_above_it() -> None:
    package, submodel, child = _setup()
    collection = child.parent

    package.stack.push(
        SetAttribute(package.observer, child, "category", "PARAMETER")
    )

    assert package.marks.is_changed(child)
    assert package.marks.is_changed(collection)
    assert package.marks.is_changed(submodel)


def test_an_edit_does_not_mark_a_sibling() -> None:
    package, _, child = _setup()
    sibling = make_property("Sibling")
    assert isinstance(child.parent, model.SubmodelElementCollection)
    child.parent.value.add(sibling)

    package.stack.push(
        SetAttribute(package.observer, child, "category", "PARAMETER")
    )

    assert not package.marks.is_changed(sibling)


def test_an_added_element_is_new_and_changes_the_object_above() -> None:
    package, submodel, _ = _setup()
    added = make_property("Added")

    package.stack.push(
        AddMember(package.observer, submodel.submodel_element, added)
    )

    assert package.marks.is_new(added)
    assert package.marks.is_changed(submodel)


def test_a_save_takes_all_marks_away() -> None:
    package, _, child = _setup()
    package.stack.push(
        SetAttribute(package.observer, child, "category", "PARAMETER")
    )

    package.stack.mark_saved()

    assert package.marks.is_empty
    assert not package.marks.is_changed(child)
    assert package.updates[-1].cleared


def test_undo_to_the_saved_state_takes_the_marks_away() -> None:
    package, _, child = _setup()
    package.stack.push(
        SetAttribute(package.observer, child, "category", "PARAMETER")
    )
    assert package.marks.is_changed(child)

    package.stack.undo()

    assert package.stack.is_clean
    assert package.marks.is_empty


def test_redo_marks_the_object_again() -> None:
    package, _, child = _setup()
    package.stack.push(
        SetAttribute(package.observer, child, "category", "PARAMETER")
    )
    package.stack.undo()

    package.stack.redo()

    assert package.marks.is_changed(child)


def test_undo_to_the_saved_state_after_a_save_takes_the_marks_away() -> None:
    package, _, child = _setup()
    package.stack.push(SetAttribute(package.observer, child, "category", "ONE"))
    package.stack.mark_saved()
    package.stack.push(SetAttribute(package.observer, child, "category", "TWO"))
    assert package.marks.is_changed(child)

    package.stack.undo()

    assert package.marks.is_empty


def test_undo_past_the_saved_state_marks_the_object() -> None:
    package, _, child = _setup()
    package.stack.push(SetAttribute(package.observer, child, "category", "ONE"))
    package.stack.mark_saved()

    package.stack.undo()

    assert not package.stack.is_clean
    assert package.marks.is_changed(child)


def test_marks_stay_while_the_stack_is_not_at_the_saved_state() -> None:
    package, _, child = _setup()
    other = make_property("Other")
    assert isinstance(child.parent, model.SubmodelElementCollection)
    child.parent.value.add(other)
    package.stack.push(SetAttribute(package.observer, child, "category", "ONE"))
    package.stack.push(SetAttribute(package.observer, other, "category", "TWO"))

    package.stack.undo()

    assert not package.stack.is_clean
    assert package.marks.is_changed(child)


def test_a_view_can_mark_an_object_it_knows_about() -> None:
    package = Package()
    qualifier_owner = make_property("Owner")

    package.marks.mark_changed(qualifier_owner)

    assert package.marks.is_changed(qualifier_owner)
    assert package.updates[-1].objects == (qualifier_owner,)


def test_marking_twice_tells_the_subscribers_once() -> None:
    package = Package()
    element = make_property("Element")

    package.marks.mark_changed(element)
    package.marks.mark_changed(element)

    assert len(package.updates) == 1


def test_values_that_python_shares_are_never_marked() -> None:
    package = Package()
    text = "shared"

    package.marks.mark_changed(text, 7, None, model.KeyTypes.SUBMODEL)

    assert package.marks.is_empty
    assert not package.marks.is_changed(text)


def test_is_markable_is_true_for_aas_objects() -> None:
    assert is_markable(make_property("A"))
    assert not is_markable("A")


def test_a_removed_element_is_listed_for_its_container() -> None:
    package, submodel, child = _setup()
    collection = child.parent
    assert isinstance(collection, model.SubmodelElementCollection)

    package.stack.push(RemoveMember(package.observer, collection.value, child))

    assert package.marks.removed_from(collection.value) == (child,)
    assert package.marks.is_changed(collection)
    assert package.marks.removed_from(submodel.submodel_element) == ()


def test_a_save_forgets_what_was_removed() -> None:
    package, _, child = _setup()
    collection = child.parent
    assert isinstance(collection, model.SubmodelElementCollection)
    package.stack.push(RemoveMember(package.observer, collection.value, child))

    package.stack.mark_saved()

    assert package.marks.removed_from(collection.value) == ()


def test_nothing_was_removed_from_a_container_that_was_not_touched() -> None:
    package, submodel, _ = _setup()

    assert package.marks.removed_from(submodel.submodel_element) == ()
