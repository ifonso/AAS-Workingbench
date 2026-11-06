"""Order of namespace members (D19), for every container the SDK offers."""

from collections.abc import Callable
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_list
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.domain.ordering import OrderRestoreError
from aas_editor.domain.ordering import insert_at
from aas_editor.domain.ordering import move_to
from aas_editor.domain.ordering import reorder
from aas_editor.domain.ordering import replace_item
from aas_editor.domain.ordering import restore_order
from aas_editor.domain.ordering import set_id_short
from aas_editor.domain.ordering import snapshot_order

Elements = model.NamespaceSet[Any]
Builder = Callable[[], Elements]


def _props(*names: str) -> list[model.Property]:
    return [make_property(name) for name in names]


def _submodel_elements() -> Elements:
    return make_submodel(elements=_props("a", "b", "c")).submodel_element


def _collection_value() -> Elements:
    return make_collection(elements=_props("a", "b", "c")).value


def _entity_statements() -> Elements:
    return make_entity(statements=_props("a", "b", "c")).statement


def _operation_input() -> Elements:
    return make_operation(input_variables=_props("a", "b", "c")).input_variable


def _operation_output() -> Elements:
    return make_operation(
        output_variables=_props("a", "b", "c")
    ).output_variable


def _operation_in_output() -> Elements:
    return make_operation(
        in_output_variables=_props("a", "b", "c")
    ).in_output_variable


def _annotations() -> Elements:
    return make_annotated_relationship(
        annotations=_props("a", "b", "c")
    ).annotation


def _list_value() -> Elements:
    return make_list(elements=_props("a", "b", "c")).value


# Elements of a list have no idShort of their own, so these are only compared
# by identity. The other containers are also compared by name.
NAMED = {
    "submodel": _submodel_elements,
    "collection": _collection_value,
    "entity": _entity_statements,
    "operation-input": _operation_input,
    "operation-output": _operation_output,
    "operation-in-output": _operation_in_output,
    "annotations": _annotations,
}
ALL = {**NAMED, "list": _list_value}


def _ids(elements: Elements) -> list[str]:
    return [element.id_short for element in elements]


def _members(elements: Elements) -> list[Any]:
    return list(elements)


def test_sdk_moves_element_to_the_end_when_id_short_is_assigned() -> None:
    # Guards the SDK behavior that ordering.py works around.
    elements = _submodel_elements()

    _members(elements)[0].id_short = "z"

    assert _ids(elements) == ["b", "c", "z"]


@pytest.mark.parametrize("build", NAMED.values(), ids=NAMED.keys())
class TestSetIdShort:
    def test_keeps_position_when_first_element_is_renamed(
        self, build: Builder
    ) -> None:
        elements = build()

        set_id_short(_members(elements)[0], "z")

        assert _ids(elements) == ["z", "b", "c"]

    def test_keeps_position_when_middle_element_is_renamed(
        self, build: Builder
    ) -> None:
        elements = build()

        set_id_short(_members(elements)[1], "z")

        assert _ids(elements) == ["a", "z", "c"]

    def test_keeps_order_when_id_short_is_taken(self, build: Builder) -> None:
        elements = build()

        with pytest.raises(model.AASConstraintViolation):
            set_id_short(_members(elements)[0], "c")

        assert _ids(elements) == ["a", "b", "c"]

    def test_keeps_order_when_id_short_is_invalid(self, build: Builder) -> None:
        elements = build()

        with pytest.raises(model.AASConstraintViolation):
            set_id_short(_members(elements)[1], "1 invalid")

        assert _ids(elements) == ["a", "b", "c"]


@pytest.mark.parametrize("build", ALL.values(), ids=ALL.keys())
class TestChangeOrder:
    def test_reorder_orders_members_as_given(self, build: Builder) -> None:
        elements = build()
        first, second, third = _members(elements)

        reorder(elements, [third, first, second])

        assert _members(elements) == [third, first, second]

    def test_reorder_keeps_parent_of_every_member(self, build: Builder) -> None:
        elements = build()
        first, second, third = _members(elements)
        owner = first.parent

        reorder(elements, [third, second, first])

        assert [member.parent for member in elements] == [owner, owner, owner]

    def test_reorder_raises_and_keeps_order_when_a_member_is_missing(
        self, build: Builder
    ) -> None:
        elements = build()
        first, second, third = _members(elements)

        with pytest.raises(ValueError):
            reorder(elements, [third, first])

        assert _members(elements) == [first, second, third]

    def test_reorder_raises_and_keeps_order_when_a_member_is_listed_twice(
        self, build: Builder
    ) -> None:
        elements = build()
        first, second, third = _members(elements)

        with pytest.raises(ValueError):
            reorder(elements, [third, first, first])

        assert _members(elements) == [first, second, third]

    def test_insert_at_adds_object_at_the_position(
        self, build: Builder
    ) -> None:
        elements = build()
        first, second, third = _members(elements)
        new = make_property("n")

        insert_at(elements, new, 1)

        assert _members(elements) == [first, new, second, third]

    def test_move_to_puts_member_at_the_end(self, build: Builder) -> None:
        elements = build()
        first, second, third = _members(elements)

        move_to(elements, first, 2)

        assert _members(elements) == [second, third, first]

    def test_move_to_puts_member_at_the_start(self, build: Builder) -> None:
        elements = build()
        first, second, third = _members(elements)

        move_to(elements, third, 0)

        assert _members(elements) == [third, first, second]

    def test_replace_item_puts_new_object_at_the_position(
        self, build: Builder
    ) -> None:
        elements = build()
        first, second, third = _members(elements)
        new = make_property("n")

        replace_item(elements, second, new)

        assert _members(elements) == [first, new, third]
        assert second.parent is None


def test_restore_order_puts_members_back_after_they_were_reordered() -> None:
    elements = _submodel_elements()
    first, second, third = _members(elements)
    snapshot = snapshot_order(elements)
    reorder(elements, [third, second, first])

    restore_order(snapshot)

    assert _members(elements) == [first, second, third]


def test_restore_order_skips_removed_and_appends_joined_members() -> None:
    elements = _submodel_elements()
    first, second, third = _members(elements)
    snapshot = snapshot_order(elements)
    elements.remove(second)
    new = make_property("n")
    elements.add(new)

    restore_order(snapshot)

    assert _members(elements) == [first, third, new]


def test_insert_at_appends_when_index_is_beyond_the_end() -> None:
    elements = _submodel_elements()

    insert_at(elements, make_property("n"), 99)

    assert _ids(elements) == ["a", "b", "c", "n"]


def test_insert_at_adds_nothing_when_id_short_is_taken() -> None:
    elements = _submodel_elements()

    with pytest.raises(model.AASConstraintViolation):
        insert_at(elements, make_property("b"), 0)

    assert _ids(elements) == ["a", "b", "c"]


def test_move_to_raises_when_object_is_not_a_member() -> None:
    elements = _submodel_elements()

    with pytest.raises(KeyError):
        move_to(elements, make_property("n"), 0)

    assert _ids(elements) == ["a", "b", "c"]


def test_replace_item_keeps_old_member_when_new_one_is_refused() -> None:
    elements = _submodel_elements()
    second = _members(elements)[1]

    with pytest.raises(model.AASConstraintViolation):
        replace_item(elements, second, make_property("c"))

    assert _ids(elements) == ["a", "b", "c"]
    assert second.parent is not None


def test_replace_item_raises_when_old_object_is_not_a_member() -> None:
    elements = _submodel_elements()

    with pytest.raises(KeyError):
        replace_item(elements, make_property("n"), make_property("m"))

    assert _ids(elements) == ["a", "b", "c"]


class _Refusal:
    """An add hook of a real NamespaceSet that refuses chosen objects.

    Attributes:
        always: IdShorts that are refused every time.
        once: IdShorts that are refused the next time only.
    """

    def __init__(self) -> None:
        self.always: set[str] = set()
        self.once: set[str] = set()

    def __call__(self, element: model.Referable, _present: object) -> None:
        if element.id_short in self.once:
            self.once.discard(element.id_short)
            raise ValueError(f"Refused: {element.id_short}")
        if element.id_short in self.always:
            raise ValueError(f"Refused: {element.id_short}")


def _guarded_set() -> tuple[Elements, _Refusal]:
    refusal = _Refusal()
    owner = make_submodel(id_short="Owner")
    guarded: Elements = model.NamespaceSet(
        owner, [("id_short", True)], _props("a", "b", "c"), refusal
    )
    return guarded, refusal


def test_reorder_restores_previous_order_when_an_object_is_refused() -> None:
    elements, refusal = _guarded_set()
    first, second, third = _members(elements)
    refusal.once.add("a")

    with pytest.raises(ValueError, match="Refused: a"):
        reorder(elements, [third, second, first])

    assert _members(elements) == [first, second, third]
    assert [member.parent for member in elements] == [first.parent] * 3


def test_reorder_raises_restore_error_when_previous_order_fails_too() -> None:
    elements, refusal = _guarded_set()
    first, second, third = _members(elements)
    refusal.always.update({"a", "b"})

    with pytest.raises(OrderRestoreError):
        reorder(elements, [third, second, first])


def test_insert_at_removes_the_object_when_the_new_order_is_refused() -> None:
    elements, refusal = _guarded_set()
    first, second, third = _members(elements)
    new = make_property("n")
    refusal.once.add("b")

    with pytest.raises(ValueError, match="Refused: b"):
        insert_at(elements, new, 0)

    assert _members(elements) == [first, second, third]
    assert new.parent is None
