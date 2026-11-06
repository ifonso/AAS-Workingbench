"""Tests for creating shells and submodels, and editing asset ids (WP7)."""

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.create import CreateError
from aas_editor.application.operations.create import add_shell
from aas_editor.application.operations.create import (
    add_specific_asset_id_command,
)
from aas_editor.application.operations.create import add_submodel
from aas_editor.application.operations.create import (
    generate_global_asset_id_command,
)
from aas_editor.application.operations.create import global_asset_id_command
from aas_editor.application.operations.create import new_shell
from aas_editor.application.operations.create import new_submodel
from aas_editor.application.operations.create import (
    remove_specific_asset_id_command,
)
from aas_editor.application.operations.create import shell_of
from aas_editor.application.operations.create import unlinked_submodels
from aas_editor.application.operations.rename import DuplicateIdError
from aas_editor.domain.asset_information import build_specific_asset_id


class _Owner:
    """Stands in for a package: something that scopes an observer."""


OWNER = _Owner()


class TestNewShell:
    def test_a_shell_gets_a_generated_id_and_valid_asset_information(
        self,
    ) -> None:
        shell = new_shell([], global_asset_id="urn:asset:1")

        assert shell.id.startswith("urn:uuid:")
        assert shell.asset_information.asset_kind is model.AssetKind.INSTANCE
        assert shell.asset_information.global_asset_id == "urn:asset:1"

    def test_the_given_id_and_id_short_are_used(self) -> None:
        shell = new_shell(
            [], id_=" urn:s:1 ", id_short="Pump", global_asset_id="urn:a"
        )

        assert (shell.id, shell.id_short) == ("urn:s:1", "Pump")

    def test_without_any_asset_id_the_reason_is_explained(self) -> None:
        with pytest.raises(CreateError, match="AASd-131"):
            new_shell([])

    def test_specific_asset_id_alone_is_enough(self) -> None:
        specific = build_specific_asset_id("serial", "1")

        shell = new_shell([], specific_asset_ids=[specific])

        assert list(shell.asset_information.specific_asset_id) == [specific]

    def test_an_id_that_another_object_has_is_refused(self) -> None:
        existing = make_submodel(id_="urn:taken")

        with pytest.raises(DuplicateIdError):
            new_shell([existing], id_="urn:taken", global_asset_id="urn:a")

    def test_invalid_id_short_is_refused_with_the_rule(self) -> None:
        with pytest.raises(CreateError, match="AASd-002"):
            new_shell([], id_short="my pump", global_asset_id="urn:a")

    def test_asset_kind_is_kept(self) -> None:
        shell = new_shell(
            [], asset_kind=model.AssetKind.TYPE, global_asset_id="urn:a"
        )

        assert shell.asset_information.asset_kind is model.AssetKind.TYPE


class TestNewSubmodel:
    def test_defaults_are_a_generated_id_and_instance_kind(self) -> None:
        submodel = new_submodel([])

        assert submodel.id.startswith("urn:uuid:")
        assert submodel.kind is model.ModellingKind.INSTANCE

    def test_template_kind_is_kept(self) -> None:
        submodel = new_submodel([], kind=model.ModellingKind.TEMPLATE)

        assert submodel.kind is model.ModellingKind.TEMPLATE

    def test_duplicate_id_is_refused(self) -> None:
        with pytest.raises(DuplicateIdError):
            new_submodel([make_submodel(id_="urn:x")], id_="urn:x")


class TestAddAndUndo:
    def test_add_shell_is_one_step_and_undo_removes_it(self) -> None:
        store = make_store()
        stack = CommandStack()
        before = snapshot(store)

        shell = new_shell(store, id_short="S", global_asset_id="urn:a")
        add_shell(stack, observer_for(OWNER), store, shell)
        after_add = snapshot(store)
        stack.undo()
        after_undo = snapshot(store)
        stack.redo()

        assert shell in list(store)
        assert after_add != before
        assert after_undo == before
        assert snapshot(store) == after_add

    def test_add_submodel_with_a_shell_links_it_in_the_same_step(self) -> None:
        shell = make_shell()
        store = make_store(shell)
        stack = CommandStack()
        before = snapshot(store)

        submodel = new_submodel(store, id_short="Nameplate")
        add_submodel(stack, observer_for(OWNER), store, submodel, shell)
        linked = len(shell.submodel)
        stack.undo()

        assert linked == 1
        assert len(shell.submodel) == 0
        assert submodel not in list(store)
        assert snapshot(store) == before
        assert not stack.can_undo

    def test_add_submodel_without_a_shell_adds_only_the_submodel(self) -> None:
        shell = make_shell()
        store = make_store(shell)
        stack = CommandStack()

        submodel = new_submodel(store)
        add_submodel(stack, observer_for(OWNER), store, submodel)

        assert submodel in list(store)
        assert len(shell.submodel) == 0

    def test_the_link_refers_to_the_new_submodel(self) -> None:
        shell = make_shell()
        store = make_store(shell)
        submodel = new_submodel(store, id_short="N")

        add_submodel(
            CommandStack(), observer_for(OWNER), store, submodel, shell
        )

        (reference,) = shell.submodel
        assert reference.key[0].value == submodel.id
        assert reference.resolve(store) is submodel

    def test_unlinked_submodels_lists_those_the_shell_lacks(self) -> None:
        linked = make_submodel(id_="urn:l", id_short="L")
        free = make_submodel(id_="urn:f", id_short="F")
        shell = make_shell(submodels=[linked])

        assert unlinked_submodels([shell, linked, free], shell) == [free]


class TestAssetIds:
    def test_global_asset_id_command_sets_and_undoes(self) -> None:
        shell = make_shell(asset_information=make_asset_information("urn:old"))
        stack = CommandStack()

        stack.push(
            global_asset_id_command(observer_for(shell), shell, " urn:new ")
        )
        changed = shell.asset_information.global_asset_id
        stack.undo()

        assert changed == "urn:new"
        assert shell.asset_information.global_asset_id == "urn:old"

    def test_clearing_the_only_asset_id_is_refused_with_aasd_131(self) -> None:
        shell = make_shell()

        with pytest.raises(CreateError, match="AASd-131"):
            global_asset_id_command(observer_for(shell), shell, "")

    def test_clearing_is_allowed_when_a_specific_asset_id_remains(self) -> None:
        shell = make_shell(asset_information=make_asset_information("urn:old"))
        shell.asset_information.specific_asset_id.append(
            build_specific_asset_id("serial", "1")
        )
        stack = CommandStack()

        stack.push(global_asset_id_command(observer_for(shell), shell, None))

        assert shell.asset_information.global_asset_id is None

    def test_generate_gives_a_new_urn_uuid_each_time(self) -> None:
        shell = make_shell()
        stack = CommandStack()

        stack.push(generate_global_asset_id_command(observer_for(shell), shell))
        first = shell.asset_information.global_asset_id
        stack.push(generate_global_asset_id_command(observer_for(shell), shell))

        assert first is not None and first.startswith("urn:uuid:")
        assert shell.asset_information.global_asset_id != first

    def test_add_specific_asset_id_is_one_undoable_step(self) -> None:
        shell = make_shell()
        stack = CommandStack()
        specific = build_specific_asset_id("serial", "1")

        stack.push(
            add_specific_asset_id_command(observer_for(shell), shell, specific)
        )
        added = list(shell.asset_information.specific_asset_id)
        stack.undo()

        assert added == [specific]
        assert list(shell.asset_information.specific_asset_id) == []

    def test_removing_the_only_asset_id_is_refused(self) -> None:
        shell = make_shell(
            asset_information=model.AssetInformation(
                specific_asset_id=[build_specific_asset_id("serial", "1")]
            )
        )
        (only,) = shell.asset_information.specific_asset_id

        with pytest.raises(CreateError, match="AASd-131"):
            remove_specific_asset_id_command(observer_for(shell), shell, only)

    def test_removing_a_specific_asset_id_next_to_a_global_one_works(
        self,
    ) -> None:
        shell = make_shell()
        specific = build_specific_asset_id("serial", "1")
        shell.asset_information.specific_asset_id.append(specific)
        stack = CommandStack()

        stack.push(
            remove_specific_asset_id_command(
                observer_for(shell), shell, specific
            )
        )
        removed = list(shell.asset_information.specific_asset_id)
        stack.undo()

        assert removed == []
        assert list(shell.asset_information.specific_asset_id) == [specific]

    def test_shell_of_finds_the_owner_of_asset_information_and_ids(
        self,
    ) -> None:
        shell = make_shell()
        specific = build_specific_asset_id("serial", "1")
        shell.asset_information.specific_asset_id.append(specific)
        other = make_shell(id_="urn:other")

        assert shell_of(shell.asset_information, [other, shell]) is shell
        assert shell_of(specific, [other, shell]) is shell
        assert shell_of(make_submodel(), [other, shell]) is None
