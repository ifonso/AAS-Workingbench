"""Replacing an element by a new one, with its references and its place."""

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.replace import plan_reference_updates
from aas_editor.application.operations.replace import replacement_command
from aas_editor.domain.conversion import plan_conversion
from aas_editor.domain.list_settings import ListSettings
from aas_editor.domain.list_settings import plan_list_rebuild

STRING = model.datatypes.String


class _Package:
    """A submodel with a stack, as a package has."""

    def __init__(self, *elements: model.SubmodelElement) -> None:
        self.submodel = make_submodel(elements=elements)
        self.store = make_store(self.submodel)
        self.stack = CommandStack()
        self.observer = ModelChangeObserver()

    def add(self, element: model.SubmodelElement) -> None:
        self.submodel.submodel_element.add(element)

    def convert(self, element: model.SubmodelElement, target: type) -> None:
        plan = plan_conversion(element, target)
        updates = plan_reference_updates(self.store, plan)
        self.stack.push(replacement_command(self.observer, plan, updates))

    def names(self) -> list[str | None]:
        return [element.id_short for element in self.submodel.submodel_element]

    def resolves(self, reference: model.Reference) -> bool:
        try:
            reference.resolve(self.store)  # type: ignore[attr-defined]
        except (KeyError, ValueError, TypeError, model.UnexpectedTypeError):
            return False
        return True


def _referring_to(target: model.Referable) -> model.ReferenceElement:
    return model.ReferenceElement("Pointer", make_reference_to(target))


def test_the_new_element_takes_the_place_of_the_old_one() -> None:
    package = _Package(
        make_property("First"),
        make_property("Second"),
        make_property("Third"),
    )

    package.convert(package.submodel.get_referable("Second"), model.Range)

    assert package.names() == ["First", "Second", "Third"]
    assert isinstance(package.submodel.get_referable("Second"), model.Range)


def test_undo_gives_back_the_old_element_itself_and_redo_the_new_one() -> None:
    old = make_property("Subject")
    package = _Package(make_property("Before"), old)
    package.convert(old, model.Range)
    converted = package.submodel.get_referable("Subject")

    package.stack.undo()
    undone = package.submodel.get_referable("Subject")
    package.stack.redo()

    assert undone is old
    assert package.submodel.get_referable("Subject") is converted
    assert package.names() == ["Before", "Subject"]


def test_one_undo_takes_back_the_conversion_and_the_references() -> None:
    target = make_property("Subject")
    package = _Package(target)
    package.add(_referring_to(target))
    before = snapshot(package.store)

    package.convert(target, model.File)
    package.stack.undo()

    assert snapshot(package.store) == before
    assert not package.stack.can_undo


def test_a_reference_to_the_element_follows_its_new_type() -> None:
    target = make_property("Subject")
    package = _Package(target)
    pointer = _referring_to(target)
    package.add(pointer)
    assert package.resolves(pointer.value)  # type: ignore[arg-type]

    package.convert(target, model.Range)

    assert package.resolves(pointer.value)  # type: ignore[arg-type]
    assert pointer.value.key[-1].type == model.KeyTypes.RANGE  # type: ignore[union-attr]


def test_a_reference_to_the_element_stops_resolving_without_the_update() -> (
    None
):
    target = make_property("Subject")
    package = _Package(target)
    pointer = _referring_to(target)
    package.add(pointer)
    stale = pointer.value
    plan = plan_conversion(target, model.Range)

    package.stack.push(
        replacement_command(
            package.observer,
            plan,
            plan_reference_updates([], plan),  # nothing known, nothing updated
        )
    )

    assert not package.resolves(stale)  # type: ignore[arg-type]


def test_references_through_a_converted_container_keep_their_path() -> None:
    inner = make_property("Inner")
    collection = make_collection("Group", [inner])
    package = _Package(collection)
    pointer = _referring_to(inner)
    package.add(pointer)

    package.convert(collection, model.Entity)

    assert package.resolves(pointer.value)  # type: ignore[arg-type]
    assert [key.value for key in pointer.value.key] == [  # type: ignore[union-attr]
        package.submodel.id,
        "Group",
        "Inner",
    ]
    assert pointer.value.key[1].type == model.KeyTypes.ENTITY  # type: ignore[union-attr]


def test_a_reference_to_an_item_gets_its_position_when_a_list_is_made() -> None:
    collection = make_collection(
        "Group", [make_property("A", "1"), make_property("B", "2")]
    )
    package = _Package(collection)
    pointer = _referring_to(collection.get_referable("B"))
    package.add(pointer)

    package.convert(collection, model.SubmodelElementList)

    assert [key.value for key in pointer.value.key][1:] == ["Group", "1"]  # type: ignore[union-attr]
    assert package.resolves(pointer.value)  # type: ignore[arg-type]
    package.stack.undo()
    assert [key.value for key in pointer.value.key][1:] == ["Group", "B"]  # type: ignore[union-attr]
    assert package.resolves(pointer.value)  # type: ignore[arg-type]


def test_references_between_the_items_follow_when_they_move() -> None:
    first = make_property("A", "1")
    second = make_property("B", "2")
    collection = make_collection("Group", [first, second])
    package = _Package(collection)
    link = model.RelationshipElement(
        "Link", make_reference_to(first), make_reference_to(second)
    )
    package.add(link)

    package.convert(collection, model.SubmodelElementList)

    assert [key.value for key in link.second.key][1:] == ["Group", "1"]  # type: ignore[union-attr]
    assert package.resolves(link.second)  # type: ignore[arg-type]


def test_a_reference_stored_inside_the_converted_element_is_updated() -> None:
    first = make_property("A")
    pointer = model.ReferenceElement("Pointer")
    collection = make_collection("Group", [first, pointer])
    package = _Package(collection)
    pointer.value = make_reference_to(first)

    package.convert(collection, model.Entity)

    statements = package.submodel.get_referable("Group").statement  # type: ignore[attr-defined]
    inside = statements.get_object_by_attribute("id_short", "Pointer")
    assert inside.value.key[1].type == model.KeyTypes.ENTITY
    assert package.resolves(inside.value)


def test_references_to_items_that_are_lost_are_reported_not_changed() -> None:
    inner = make_property("Inner")
    collection = make_collection("Group", [inner])
    package = _Package(collection)
    pointer = _referring_to(inner)
    package.add(pointer)
    plan = plan_conversion(collection, model.Capability)

    updates = plan_reference_updates(package.store, plan)

    assert [usage.slot.owner for usage in updates.orphaned] == [pointer]
    assert updates.changes == ()


def test_a_reference_to_a_lost_item_stays_as_it_was() -> None:
    inner = make_property("Inner")
    collection = make_collection("Group", [inner])
    package = _Package(collection)
    pointer = _referring_to(inner)
    package.add(pointer)
    kept = pointer.value

    package.convert(collection, model.Capability)

    assert pointer.value is kept


def test_a_reference_in_a_lost_item_is_not_reported() -> None:
    elsewhere = make_property("Elsewhere")
    inner = model.ReferenceElement("Inner")
    collection = make_collection("Group", [inner])
    package = _Package(collection, elsewhere)
    inner.value = make_reference_to(elsewhere)
    plan = plan_conversion(collection, model.Capability)

    updates = plan_reference_updates(package.store, plan)

    assert updates.orphaned == ()


def test_deleting_items_by_a_rebuild_moves_the_references_behind_them() -> None:
    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        [
            model.Property(None, STRING, "1"),
            model.Property(None, STRING, "abc"),
            model.Property(None, STRING, "3"),
        ],
        value_type_list_element=STRING,
    )
    package = _Package(item_list)
    pointer = _referring_to(list(item_list.value)[2])
    package.add(pointer)
    plan = plan_list_rebuild(
        item_list,
        ListSettings(model.Property, model.datatypes.Int, None, True),
    )
    updates = plan_reference_updates(package.store, plan)

    package.stack.push(replacement_command(package.observer, plan, updates))

    assert [key.value for key in pointer.value.key][1:] == ["Items", "1"]  # type: ignore[union-attr]
    assert package.resolves(pointer.value)  # type: ignore[arg-type]
    assert [usage.slot.owner for usage in updates.orphaned] == []


def test_the_references_to_a_dropped_list_item_are_reported() -> None:
    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        [model.Property(None, STRING, "abc")],
        value_type_list_element=STRING,
    )
    package = _Package(item_list)
    pointer = _referring_to(list(item_list.value)[0])
    package.add(pointer)
    plan = plan_list_rebuild(
        item_list,
        ListSettings(model.Property, model.datatypes.Int, None, True),
    )

    updates = plan_reference_updates(package.store, plan)

    assert len(updates.orphaned) == 1


def test_the_external_semantic_id_is_not_touched() -> None:
    reference = make_external_reference("urn:example:semantic")
    target = make_property("Subject")
    target.semantic_id = reference
    package = _Package(target)

    package.convert(target, model.Range)

    assert package.submodel.get_referable("Subject").semantic_id == reference
