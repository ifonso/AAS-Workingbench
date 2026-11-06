"""Tests for copying an AAS recursively with new Submodel ids (F-EDT-02 AC4)."""

from typing import Any

from basyx.aas import model
from tests.factories import make_asset_information
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.copy_shell import copy_shell_commands
from aas_editor.application.operations.copy_shell import plan_copy_shell


class _Owner:
    """Stands in for a package: something that scopes an observer."""


OWNER = _Owner()


def _world() -> tuple[Any, Any, Any, Any]:
    first = make_submodel(
        id_="urn:sm:1", id_short="First", elements=[make_property("P")]
    )
    second = make_submodel(id_="urn:sm:2", id_short="Second")
    shell = make_shell(
        id_="urn:shell:1",
        submodels=[first, second],
        asset_information=make_asset_information("urn:asset:1"),
    )
    return make_store(shell, first, second), shell, first, second


def _copy(store: Any, shell: Any, stack: CommandStack | None = None) -> Any:
    plan = plan_copy_shell(shell, list(store))
    stack = stack or CommandStack()
    with stack.group(plan.description):
        for command in copy_shell_commands(observer_for(OWNER), store, plan):
            stack.push(command)
    return plan


def _shells(store: Any) -> list[model.AssetAdministrationShell]:
    return [o for o in store if isinstance(o, model.AssetAdministrationShell)]


def test_the_shell_its_asset_id_and_each_submodel_get_new_ids() -> None:
    store, shell, first, second = _world()

    plan = _copy(store, shell)

    new = plan.shell
    assert new is not shell
    assert new.id not in {"urn:shell:1"}
    assert new.asset_information.global_asset_id not in (None, "urn:asset:1")
    copies = {c.id: c for _, c in plan.submodels}
    assert not ({first.id, second.id} & set(copies))
    assert sorted(c.id_short for c in copies.values()) == ["First", "Second"]
    assert sorted(r.key[0].value for r in new.submodel) == sorted(copies)


def test_the_references_of_the_new_shell_resolve_to_the_new_submodels() -> None:
    store, shell, first, second = _world()

    plan = _copy(store, shell)

    resolved = {r.resolve(store) for r in plan.shell.submodel}
    assert resolved == {c for _, c in plan.submodels}
    assert not ({first, second} & resolved)
    assert len(store) == 6


def test_the_original_is_not_changed_and_keeps_its_submodels() -> None:
    store, shell, first, second = _world()
    originals = make_store(shell, first, second)
    before = snapshot(originals)

    _copy(store, shell)

    assert shell.id == "urn:shell:1"
    assert shell.asset_information.global_asset_id == "urn:asset:1"
    assert {r.key[0].value for r in shell.submodel} == {"urn:sm:1", "urn:sm:2"}
    assert first.get_referable("P").value == "text"
    assert snapshot(originals) == before


def test_the_copy_is_one_undo_step() -> None:
    store, shell, *_ = _world()
    stack = CommandStack()

    _copy(store, shell, stack)
    stack.undo()

    assert len(store) == 3
    assert not stack.can_undo
    stack.redo()
    assert len(store) == 6


def test_a_reference_to_a_missing_submodel_is_kept_and_listed() -> None:
    store, shell, first, second = _world()
    lost = model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, "urn:sm:lost"),), model.Submodel
    )
    shell.submodel.add(lost)

    plan = _copy(store, shell)

    assert plan.unresolved == (lost,)
    assert lost in plan.shell.submodel
    assert len(plan.submodels) == 2


def test_a_reference_between_two_copied_submodels_follows_the_copy() -> None:
    target = make_submodel(
        id_="urn:sm:t", id_short="Target", elements=[make_property("Value")]
    )
    point = model.ReferenceElement(
        "Point",
        model.ModelReference.from_referable(target.get_referable("Value")),
    )
    holder = make_submodel(id_="urn:sm:h", id_short="Holder", elements=[point])
    outside = make_submodel(id_="urn:sm:o", id_short="Outside")
    point_out = model.ReferenceElement(
        "Out", make_reference_to(outside)
    )
    holder.submodel_element.add(point_out)
    shell = make_shell(id_="urn:shell:2", submodels=[target, holder])
    store = make_store(shell, target, holder, outside)

    plan = _copy(store, shell)

    copies = {o.id_short: c for o, c in plan.submodels}
    pointer = copies["Holder"].get_referable("Point")
    assert isinstance(pointer, model.ReferenceElement)
    assert pointer.value is not None
    assert pointer.value.key[0].value == copies["Target"].id
    assert pointer.value.resolve(store) is copies["Target"].get_referable(
        "Value"
    )
    # What is not copied is not redirected, and the original still points
    # into the original.
    out = copies["Holder"].get_referable("Out")
    assert isinstance(out, model.ReferenceElement)
    assert out.value is not None
    assert out.value.key[0].value == "urn:sm:o"
    assert point.value.key[0].value == "urn:sm:t"


def test_a_shell_without_submodels_is_copied_alone() -> None:
    shell = make_shell(id_="urn:shell:empty")
    store = make_store(shell)

    plan = _copy(store, shell)

    assert plan.submodels == ()
    assert len(_shells(store)) == 2
    assert plan.description == "Copy Shell with 0 Submodels"
