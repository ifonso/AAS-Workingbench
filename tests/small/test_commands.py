"""The undo history of a package, without Qt."""

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import Change
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack
from aas_editor.domain.ordering import insert_at


class _Append(Command):
    """Appends a text to a list, which is the object it is addressed by."""

    def __init__(self, target: list[str], text: str) -> None:
        self.description = f"Append {text}"
        self._target = target
        self._text = text

    def apply(self) -> None:
        self._target.append(self._text)

    def revert(self) -> None:
        self._target.remove(self._text)


class _Refuse(Command):
    description = "Refuse"

    def apply(self) -> None:
        raise ValueError("refused")

    def revert(self) -> None:
        raise AssertionError("A command that failed is never reverted")


class _InsertElement(Command):
    """Adds an element of a submodel at a position and reports it."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        submodel: model.Submodel,
        element: model.SubmodelElement,
        index: int,
    ) -> None:
        self.description = f"Add {element.id_short}"
        self._observer = observer
        self._elements = submodel.submodel_element
        self._element = element
        self._index = index

    def apply(self) -> None:
        insert_at(self._elements, self._element, self._index)
        self._observer.notify(
            Change.added(self._elements, self._element, self._index)
        )

    def revert(self) -> None:
        self._elements.remove(self._element)
        self._observer.notify(
            Change.removed(self._elements, self._element, self._index)
        )


def test_push_applies_the_command_and_enables_undo() -> None:
    texts: list[str] = []
    stack = CommandStack()

    stack.push(_Append(texts, "a"))

    assert texts == ["a"]
    assert stack.can_undo
    assert not stack.can_redo
    assert stack.undo_description == "Append a"


def test_undo_reverts_the_newest_step_and_enables_redo() -> None:
    texts: list[str] = []
    stack = CommandStack()
    stack.push(_Append(texts, "a"))
    stack.push(_Append(texts, "b"))

    stack.undo()

    assert texts == ["a"]
    assert stack.can_redo
    assert stack.redo_description == "Append b"


def test_redo_applies_the_step_again() -> None:
    texts: list[str] = []
    stack = CommandStack()
    stack.push(_Append(texts, "a"))
    stack.undo()

    stack.redo()

    assert texts == ["a"]
    assert not stack.can_redo


def test_push_discards_steps_that_could_be_redone() -> None:
    texts: list[str] = []
    stack = CommandStack()
    stack.push(_Append(texts, "a"))
    stack.undo()

    stack.push(_Append(texts, "b"))

    assert not stack.can_redo
    assert texts == ["b"]


def test_undo_raises_when_there_is_nothing_to_undo() -> None:
    stack = CommandStack()

    with pytest.raises(RuntimeError):
        stack.undo()


def test_redo_raises_when_there_is_nothing_to_redo() -> None:
    stack = CommandStack()

    with pytest.raises(RuntimeError):
        stack.redo()


def test_push_records_nothing_when_the_command_raises() -> None:
    stack = CommandStack()

    with pytest.raises(ValueError, match="refused"):
        stack.push(_Refuse())

    assert not stack.can_undo
    assert stack.is_clean


def test_limit_drops_the_oldest_step() -> None:
    texts: list[str] = []
    stack = CommandStack(limit=2)
    for text in ("a", "b", "c"):
        stack.push(_Append(texts, text))

    stack.undo()
    stack.undo()

    assert texts == ["a"]
    assert not stack.can_undo


def test_limit_must_be_positive() -> None:
    with pytest.raises(ValueError):
        CommandStack(limit=0)


class TestGroup:
    def test_undo_takes_back_the_whole_group_in_one_step(self) -> None:
        texts: list[str] = []
        stack = CommandStack()

        with stack.group("Add both"):
            stack.push(_Append(texts, "a"))
            stack.push(_Append(texts, "b"))
        stack.undo()

        assert texts == []
        assert not stack.can_undo

    def test_redo_applies_the_whole_group_again(self) -> None:
        texts: list[str] = []
        stack = CommandStack()
        with stack.group("Add both"):
            stack.push(_Append(texts, "a"))
            stack.push(_Append(texts, "b"))
        stack.undo()

        stack.redo()

        assert texts == ["a", "b"]

    def test_group_uses_its_own_description(self) -> None:
        stack = CommandStack()

        with stack.group("Delete with references"):
            stack.push(_Append([], "a"))

        assert stack.undo_description == "Delete with references"

    def test_commands_are_applied_while_the_group_is_open(self) -> None:
        texts: list[str] = []
        stack = CommandStack()

        with stack.group("Add both"):
            stack.push(_Append(texts, "a"))
            applied_inside = list(texts)

        assert applied_inside == ["a"]

    def test_block_that_raises_reverts_its_commands_and_records_nothing(
        self,
    ) -> None:
        texts: list[str] = []
        stack = CommandStack()

        with pytest.raises(ValueError, match="refused"), stack.group("Both"):
            stack.push(_Append(texts, "a"))
            stack.push(_Append(texts, "b"))
            stack.push(_Refuse())

        assert texts == []
        assert not stack.can_undo
        assert stack.is_clean

    def test_group_without_commands_records_nothing(self) -> None:
        stack = CommandStack()

        with stack.group("Nothing"):
            pass

        assert not stack.can_undo

    def test_inner_group_is_one_command_of_the_outer_group(self) -> None:
        texts: list[str] = []
        stack = CommandStack()

        with stack.group("Outer"):
            stack.push(_Append(texts, "a"))
            with stack.group("Inner"):
                stack.push(_Append(texts, "b"))
                stack.push(_Append(texts, "c"))
        stack.undo()

        assert texts == []
        assert not stack.can_undo

    def test_failed_inner_group_leaves_the_outer_group_usable(self) -> None:
        texts: list[str] = []
        stack = CommandStack()

        with stack.group("Outer"):
            stack.push(_Append(texts, "a"))
            with pytest.raises(ValueError, match="refused"), stack.group("In"):
                stack.push(_Append(texts, "b"))
                stack.push(_Refuse())
            applied_inside = list(texts)

        assert applied_inside == ["a"]
        assert texts == ["a"]

    def test_undo_raises_while_a_group_is_open(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))

        with stack.group("Open"), pytest.raises(RuntimeError):
            stack.undo()

    def test_mark_saved_raises_while_a_group_is_open(self) -> None:
        stack = CommandStack()

        with stack.group("Open"), pytest.raises(RuntimeError):
            stack.mark_saved()

    def test_group_is_not_clean_while_it_is_open(self) -> None:
        stack = CommandStack()

        with stack.group("Open"):
            assert not stack.is_clean


class TestSavedState:
    def test_new_stack_is_clean(self) -> None:
        assert CommandStack().is_clean

    def test_push_makes_the_stack_dirty(self) -> None:
        stack = CommandStack()

        stack.push(_Append([], "a"))

        assert not stack.is_clean

    def test_undo_to_the_saved_step_makes_the_stack_clean(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))
        stack.mark_saved()
        stack.push(_Append([], "b"))

        stack.undo()

        assert stack.is_clean

    def test_undo_past_the_saved_step_makes_the_stack_dirty(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))
        stack.mark_saved()

        stack.undo()

        assert not stack.is_clean

    def test_redo_back_to_the_saved_step_makes_the_stack_clean(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))
        stack.mark_saved()
        stack.undo()

        stack.redo()

        assert stack.is_clean

    def test_new_step_after_undo_keeps_the_stack_dirty_for_good(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))
        stack.push(_Append([], "b"))
        stack.mark_saved()
        stack.undo()

        stack.push(_Append([], "c"))

        # The stack has as many steps as when it was saved, but not the same.
        assert not stack.is_clean

    def test_dropping_the_saved_step_over_the_limit_keeps_it_dirty(
        self,
    ) -> None:
        stack = CommandStack(limit=2)
        stack.mark_saved()
        for text in ("a", "b", "c"):
            stack.push(_Append([], text))

        stack.undo()
        stack.undo()

        assert not stack.is_clean

    def test_mark_saved_makes_the_current_state_clean(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))

        stack.mark_saved()

        assert stack.is_clean

    def test_clear_keeps_a_clean_stack_clean(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))
        stack.mark_saved()

        stack.clear()

        assert stack.is_clean
        assert not stack.can_undo

    def test_clear_keeps_a_dirty_stack_dirty(self) -> None:
        stack = CommandStack()
        stack.push(_Append([], "a"))

        stack.clear()

        assert not stack.is_clean
        assert not stack.can_undo


class TestSubscription:
    def test_listener_is_called_after_push_undo_redo_and_save(self) -> None:
        stack = CommandStack()
        calls: list[str] = []
        stack.subscribe(lambda: calls.append("changed"))

        stack.push(_Append([], "a"))
        stack.undo()
        stack.redo()
        stack.mark_saved()

        assert calls == ["changed"] * 4

    def test_listener_is_not_called_when_the_command_raises(self) -> None:
        stack = CommandStack()
        calls: list[str] = []
        stack.subscribe(lambda: calls.append("changed"))

        with pytest.raises(ValueError, match="refused"):
            stack.push(_Refuse())

        assert calls == []

    def test_listener_is_called_once_for_a_group(self) -> None:
        stack = CommandStack()
        calls: list[str] = []
        stack.subscribe(lambda: calls.append("changed"))

        with stack.group("Both"):
            stack.push(_Append([], "a"))
            stack.push(_Append([], "b"))

        assert calls == ["changed"]


class TestAddressedByObjectIdentity:
    def test_undo_restores_the_position_of_the_element(self) -> None:
        observer = ModelChangeObserver()
        submodel = make_submodel(
            elements=[make_property("a"), make_property("b")]
        )
        stack = CommandStack()
        stack.push(_InsertElement(observer, submodel, make_property("n"), 1))

        stack.undo()
        stack.redo()

        assert [e.id_short for e in submodel.submodel_element] == [
            "a",
            "n",
            "b",
        ]

    def test_commands_report_to_the_observer_for_apply_and_revert(self) -> None:
        observer = ModelChangeObserver()
        received: list[Change] = []
        observer.subscribe(received.append)
        submodel = make_submodel(elements=[make_property("a")])
        element = make_property("n")
        stack = CommandStack()

        stack.push(_InsertElement(observer, submodel, element, 0))
        stack.undo()

        assert [change.kind.value for change in received] == [
            "added",
            "removed",
        ]
        assert [change.target for change in received] == [element, element]
