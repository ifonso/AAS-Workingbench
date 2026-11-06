"""Tests for pasting a Submodel or a Submodel reference into a shell.

F-EDT-08 AC11 and AC12, and F-EDT-03 AC4: a reference that is pasted twice is
skipped, an unknown Submodel comes with its reference, and a copy has a new id.
"""

from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.paste import PasteError
from aas_editor.application.operations.paste import plan_paste_into_shell
from aas_editor.application.operations.paste import shell_paste_commands


class _Owner:
    """Stands in for a package: something that scopes an observer."""


OWNER = _Owner()


def _apply(stack: CommandStack, plan: Any) -> None:
    with stack.group(plan.description):
        for command in shell_paste_commands(observer_for(OWNER), plan):
            stack.push(command)


def _world() -> tuple[Any, Any, Any, Any]:
    """A package with two shells; the second holds a submodel."""
    first = make_submodel(id_="urn:sm:1", id_short="First")
    second = make_submodel(id_="urn:sm:2", id_short="Second")
    target = make_shell(id_="urn:shell:target", id_short="Target")
    other = make_shell(id_="urn:shell:other", submodels=[second])
    store = make_store(target, other, first, second)
    return store, target, first, second


class TestReferences:
    def test_a_reference_to_a_submodel_of_the_package_is_added(self) -> None:
        store, target, first, _ = _world()
        reference = make_reference_to(first)

        plan = plan_paste_into_shell(target, [reference], store)
        _apply(CommandStack(), plan)

        assert list(target.submodel) == [reference]
        assert plan.copies == ()
        assert plan.dangling == ()

    def test_pasting_the_same_reference_again_is_skipped(self) -> None:
        store, target, first, _ = _world()
        reference = make_reference_to(first)
        target.submodel.add(reference)

        plan = plan_paste_into_shell(target, [reference], store)

        assert plan.is_empty
        assert plan.already_linked == (reference,)

    def test_the_same_reference_twice_in_one_paste_is_added_once(self) -> None:
        store, target, first, _ = _world()
        reference = make_reference_to(first)

        plan = plan_paste_into_shell(
            target, [reference, make_reference_to(first)], store
        )

        assert len(plan.references) == 1
        assert len(plan.already_linked) == 1

    def test_a_reference_to_a_missing_submodel_is_added_and_flagged(
        self,
    ) -> None:
        store, target, *_ = _world()
        reference = model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),), model.Submodel
        )

        plan = plan_paste_into_shell(target, [reference], store)

        assert plan.references == (reference,)
        assert plan.dangling == (reference,)

    def test_a_missing_submodel_comes_along_from_the_source_package(
        self,
    ) -> None:
        store, target, *_ = _world()
        foreign = make_submodel(id_="urn:sm:foreign", id_short="Foreign")
        foreign.submodel_element.add(make_property("P"))
        source = make_store(foreign)
        reference = make_reference_to(foreign)

        plan = plan_paste_into_shell(
            target, [reference], store, source_objects=source
        )
        _apply(CommandStack(), plan)

        added = store.get_item("urn:sm:foreign")
        assert added is not foreign
        assert [e.id_short for e in added.submodel_element] == ["P"]
        assert plan.dangling == ()
        assert reference.resolve(store) is added

    def test_a_reference_to_an_element_is_refused_with_a_reason(self) -> None:
        store, target, first, _ = _world()
        first.submodel_element.add(make_property("P"))
        element_reference = make_reference_to(first.get_referable("P"))

        with pytest.raises(PasteError, match="references to Submodels"):
            plan_paste_into_shell(target, [element_reference], store)

    def test_a_reference_to_a_shell_is_refused(self) -> None:
        store, target, *_ = _world()
        other = store.get_item("urn:shell:other")

        with pytest.raises(PasteError):
            plan_paste_into_shell(target, [make_reference_to(other)], store)


class TestSubmodels:
    def test_a_copied_submodel_gets_a_new_id_and_a_reference(self) -> None:
        store, target, first, _ = _world()

        plan = plan_paste_into_shell(target, [first], store)
        _apply(CommandStack(), plan)

        (copy,) = [c.copy for c in plan.copies]
        assert copy is not first
        assert copy.id != first.id
        assert copy.id_short == "First"
        assert copy in list(store)
        assert [r.key[0].value for r in target.submodel] == [copy.id]

    def test_a_cut_submodel_keeps_its_id_when_it_is_free(self) -> None:
        store, target, first, _ = _world()
        store.remove(first)

        plan = plan_paste_into_shell(target, [first], store, keep_ids=True)

        (item,) = plan.copies
        assert item.copy.id == first.id

    def test_a_submodel_unknown_to_the_package_is_added_with_its_reference(
        self,
    ) -> None:
        store, target, *_ = _world()
        external = make_submodel(id_="urn:sm:external", id_short="External")

        plan = plan_paste_into_shell(target, [external], store)
        _apply(CommandStack(), plan)

        (copy,) = [c.copy for c in plan.copies]
        assert copy in list(store)
        assert list(target.submodel)[0].resolve(store) is copy

    def test_undo_removes_the_submodel_and_the_reference_together(self) -> None:
        store, target, first, _ = _world()
        before = snapshot(store)
        stack = CommandStack()

        plan = plan_paste_into_shell(target, [first], store)
        _apply(stack, plan)
        pasted = snapshot(store)
        stack.undo()
        undone = snapshot(store)
        stack.redo()

        assert pasted != before
        assert undone == before
        assert snapshot(store) == pasted
        assert not stack.can_redo

    def test_several_items_are_one_undo_step(self) -> None:
        store, target, first, second = _world()
        stack = CommandStack()

        plan = plan_paste_into_shell(
            target, [make_reference_to(second), first], store
        )
        _apply(stack, plan)
        stack.undo()

        assert len(target.submodel) == 0
        assert len(list(store)) == 4
        assert not stack.can_undo


class TestNothingToPaste:
    def test_an_empty_buffer_is_refused(self) -> None:
        store, target, *_ = _world()

        with pytest.raises(PasteError, match="nothing to paste"):
            plan_paste_into_shell(target, [], store)

    def test_a_property_is_refused_with_a_reason(self) -> None:
        store, target, *_ = _world()

        with pytest.raises(PasteError, match="Submodels"):
            plan_paste_into_shell(target, [make_property("P")], store)
