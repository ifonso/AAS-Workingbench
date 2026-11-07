"""Renaming ids and idShorts with their references (decision D10)."""

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import make_linked
from tests.serialization import snapshot

from aas_workingbench.application.changes import Change
from aas_workingbench.application.changes import ChangeKind
from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.operations.rename import DuplicateIdError
from aas_workingbench.application.operations.rename import InvalidIdError
from aas_workingbench.application.operations.rename import InvalidIdShortError
from aas_workingbench.application.operations.rename import RenameCommand
from aas_workingbench.application.operations.rename import RenameError
from aas_workingbench.application.operations.rename import ReplaceIdentifiable
from aas_workingbench.application.operations.rename import plan_rename_id
from aas_workingbench.application.operations.rename import plan_rename_id_short
from aas_workingbench.application.operations.rename import suggest_id_short
from aas_workingbench.domain.references import ReferenceIndex


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


def _keys(reference: model.Reference | None) -> list[str]:
    assert reference is not None
    return [key.value for key in reference.key]


class TestRenameId:
    def test_rename_updates_every_reference_to_a_submodel(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()
        plan = plan_rename_id(linked.store, linked.main, "urn:test:renamed")

        stack.push(RenameCommand(observer, plan))

        assert linked.main.id == "urn:test:renamed"
        index = ReferenceIndex(linked.store)
        assert index.dangling() == []
        assert index.resolve(linked.pointer.value) is linked.name
        assert index.resolve(linked.link.value) is linked.inner
        assert _keys(linked.list_link.value)[0] == "urn:test:renamed"

    def test_rename_updates_the_references_of_the_shell(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id(linked.store, linked.main, "urn:test:renamed")

        CommandStack().push(RenameCommand(observer, plan))

        ids = sorted(_keys(reference)[0] for reference in linked.shell.submodel)
        assert ids == ["urn:test:other", "urn:test:renamed"]

    def test_rename_updates_semantic_ids_of_a_concept_description(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id(linked.store, linked.concept, "urn:test:cd2")

        CommandStack().push(RenameCommand(observer, plan))

        assert _keys(linked.name.semantic_id) == ["urn:test:cd2"]
        assert _keys(linked.inner.semantic_id) == ["urn:test:cd2"]
        assert _keys(linked.concept_link.value) == ["urn:test:cd2"]
        assert linked.name.semantic_id.key[0].type is (
            model.KeyTypes.GLOBAL_REFERENCE
        )

    def test_rename_leaves_unrelated_references_alone(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id(linked.store, linked.other, "urn:test:o2")

        assert [change.slot.owner for change in plan.changes] == [linked.shell]

    def test_undo_restores_the_serialized_state(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.main, "urn:test:renamed"),
            )
        )
        renamed = snapshot(linked.store)
        stack.undo()
        undone = snapshot(linked.store)
        stack.redo()

        assert renamed != original
        assert undone == original
        assert snapshot(linked.store) == renamed
        assert linked.main.id == "urn:test:renamed"

    def test_the_rename_is_one_step(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.concept, "urn:test:cd2"),
            )
        )
        stack.undo()

        assert not stack.can_undo
        assert stack.redo_description == "Rename Concept"

    def test_rename_reports_each_changed_object(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        reported: list[Change] = []
        observer.subscribe(reported.append)

        CommandStack().push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.concept, "urn:test:cd2"),
            )
        )

        targets = [change.target for change in reported]
        assert linked.concept in targets
        assert linked.name in targets
        assert all(change.kind is ChangeKind.CHANGED for change in reported)

    def test_rename_refuses_an_id_that_belongs_to_another_object(self) -> None:
        linked = make_linked()

        with pytest.raises(DuplicateIdError) as error:
            plan_rename_id(linked.store, linked.main, CONCEPT_ID)

        assert error.value.other is linked.concept
        assert CONCEPT_ID in str(error.value)

    def test_rename_to_the_same_id_is_a_noop(self) -> None:
        linked = make_linked()

        plan = plan_rename_id(linked.store, linked.main, MAIN_ID)

        assert plan.is_noop
        assert plan.changes == ()

    @pytest.mark.parametrize("text", ["", "   "])
    def test_rename_refuses_an_empty_id(self, text: str) -> None:
        linked = make_linked()

        with pytest.raises(InvalidIdError):
            plan_rename_id(linked.store, linked.main, text)

    def test_rename_refuses_an_id_that_is_too_long(self) -> None:
        linked = make_linked()

        with pytest.raises(InvalidIdError):
            plan_rename_id(linked.store, linked.main, "u" * 2049)

    def test_rename_drops_spaces_around_the_id(self) -> None:
        linked = make_linked()

        plan = plan_rename_id(linked.store, linked.main, "  urn:test:x  ")

        assert plan.new == "urn:test:x"

    def test_rename_updates_a_reference_below_a_reference_that_is_replaced(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        outer = model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:elsewhere"),),
            make_external_reference(CONCEPT_ID),
        )
        element = make_property("Nested")
        element.semantic_id = outer
        linked.other.submodel_element.add(element)
        original = snapshot(linked.store)
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.concept, "urn:test:cd2"),
            )
        )

        assert element.semantic_id is not None
        assert _keys(element.semantic_id) == ["urn:elsewhere"]
        assert _keys(element.semantic_id.referred_semantic_id) == [
            "urn:test:cd2"
        ]
        stack.undo()
        assert snapshot(linked.store) == original

    def test_rename_replaces_a_supplemental_semantic_id_in_place(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.name.supplemental_semantic_id.extend(
            [
                make_external_reference("urn:before"),
                make_external_reference(CONCEPT_ID),
                make_external_reference("urn:after"),
            ]
        )
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.concept, "urn:test:cd2"),
            )
        )

        assert [
            _keys(reference)[0]
            for reference in linked.name.supplemental_semantic_id
        ] == ["urn:before", "urn:test:cd2", "urn:after"]
        stack.undo()
        assert [
            _keys(reference)[0]
            for reference in linked.name.supplemental_semantic_id
        ] == ["urn:before", CONCEPT_ID, "urn:after"]

    def test_rename_updates_the_semantic_ids_of_all_items_of_a_list_at_once(
        self, observer: ModelChangeObserver
    ) -> None:
        # AASd-114 wants equal semantic ids in a list, so one item cannot be
        # changed alone. The list also names its semantic id (AASd-107).
        concept = make_concept_description("urn:cd", "Cd")
        items = model.SubmodelElementList(
            "Items",
            type_value_list_element=model.Property,
            value_type_list_element=model.datatypes.String,
            semantic_id_list_element=make_external_reference("urn:cd"),
            value=[
                model.Property(
                    None,
                    model.datatypes.String,
                    value=text,
                    semantic_id=make_external_reference("urn:cd"),
                )
                for text in ("a", "b", "c")
            ],
        )
        store = make_store(make_submodel("urn:sm", "Sm", [items]), concept)
        original = snapshot(store)
        stack = CommandStack()

        stack.push(
            RenameCommand(observer, plan_rename_id(store, concept, "urn:cd2"))
        )

        assert _keys(items.semantic_id_list_element) == ["urn:cd2"]
        assert [_keys(item.semantic_id) for item in items.value] == [
            ["urn:cd2"]
        ] * 3
        assert [item.value for item in items.value] == ["a", "b", "c"]
        stack.undo()
        assert snapshot(store) == original

    def test_rename_replaces_a_specific_asset_id_that_cannot_change(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.shell.asset_information.specific_asset_id.append(
            model.SpecificAssetId(
                "serial",
                "42",
                external_subject_id=make_external_reference(MAIN_ID),
                semantic_id=make_external_reference(CONCEPT_ID),
            )
        )
        original = snapshot(linked.store)
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.concept, "urn:test:cd2"),
            )
        )

        (specific,) = linked.shell.asset_information.specific_asset_id
        assert _keys(specific.semantic_id) == ["urn:test:cd2"]
        assert _keys(specific.external_subject_id) == [MAIN_ID]
        assert specific.name == "serial"
        stack.undo()
        assert snapshot(linked.store) == original

    def test_rename_updates_the_references_of_a_shell_to_a_shell(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        derived = model.AssetAdministrationShell(
            model.AssetInformation(model.AssetKind.INSTANCE, "urn:asset"),
            "urn:derived",
            derived_from=model.ModelReference.from_referable(linked.shell),
        )
        linked.store.add(derived)

        CommandStack().push(
            RenameCommand(
                observer,
                plan_rename_id(linked.store, linked.shell, "urn:shell2"),
            )
        )

        assert _keys(derived.derived_from) == ["urn:shell2"]


class TestRenameIdShort:
    def test_rename_updates_the_references_through_a_collection(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        stack = CommandStack()
        plan = plan_rename_id_short(linked.store, linked.group, "Cluster")

        stack.push(RenameCommand(observer, plan))

        assert _keys(linked.link.value) == [MAIN_ID, "Cluster", "Inner"]
        assert _keys(linked.relationship.second) == [
            MAIN_ID,
            "Cluster",
            "Inner",
        ]
        assert _keys(linked.relationship.first) == [MAIN_ID, "Name"]
        index = ReferenceIndex(linked.store)
        assert index.dangling() == []
        assert index.resolve(linked.link.value) is linked.inner

    def test_rename_of_a_list_keeps_the_positions_in_its_references(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()

        CommandStack().push(
            RenameCommand(
                observer,
                plan_rename_id_short(linked.store, linked.items, "Entries"),
            )
        )

        assert _keys(linked.list_link.value) == [MAIN_ID, "Entries", "1"]
        index = ReferenceIndex(linked.store)
        assert index.resolve(linked.list_link.value) is linked.second_item

    def test_rename_of_a_property_updates_the_references_in_other_submodels(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()

        CommandStack().push(
            RenameCommand(
                observer,
                plan_rename_id_short(linked.store, linked.name, "Title"),
            )
        )

        assert _keys(linked.pointer.value) == [MAIN_ID, "Title"]
        assert ReferenceIndex(linked.store).dangling() == []

    def test_rename_keeps_the_position_of_the_element(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()

        CommandStack().push(
            RenameCommand(
                observer,
                plan_rename_id_short(linked.store, linked.name, "Title"),
            )
        )

        names = [element.id_short for element in linked.main.submodel_element]
        assert names[:3] == ["Title", "Group", "Items"]

    def test_undo_restores_the_serialized_state(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        stack = CommandStack()

        stack.push(
            RenameCommand(
                observer,
                plan_rename_id_short(linked.store, linked.group, "Cluster"),
            )
        )
        renamed = snapshot(linked.store)
        stack.undo()
        undone = snapshot(linked.store)
        stack.redo()

        assert renamed != original
        assert undone == original
        assert snapshot(linked.store) == renamed

    def test_rename_of_an_identifiable_leaves_references_alone(self) -> None:
        linked = make_linked()

        plan = plan_rename_id_short(linked.store, linked.main, "Primary")

        assert plan.changes == ()

    def test_rename_refuses_text_that_is_no_idshort_and_suggests_one(
        self,
    ) -> None:
        linked = make_linked()

        with pytest.raises(InvalidIdShortError) as error:
            plan_rename_id_short(linked.store, linked.name, "my motor!")

        assert error.value.suggestion == "My_motor"
        assert error.value.text == "my motor!"

    def test_rename_refuses_the_idshort_of_a_sibling_and_suggests_a_number(
        self,
    ) -> None:
        linked = make_linked()

        with pytest.raises(InvalidIdShortError) as error:
            plan_rename_id_short(linked.store, linked.name, "Group")

        assert error.value.suggestion == "Group_1"

    def test_a_rename_the_sdk_refuses_changes_nothing(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        plan = plan_rename_id_short(linked.store, linked.name, "Fresh")
        # A sibling takes the name between the plan and the command.
        linked.group.id_short = "Fresh"
        original = snapshot(linked.store)
        stack = CommandStack()

        with pytest.raises(model.AASConstraintViolation):
            stack.push(RenameCommand(observer, plan))

        assert snapshot(linked.store) == original
        assert not stack.can_undo

    def test_rename_refuses_an_item_of_a_list(self) -> None:
        linked = make_linked()

        with pytest.raises(RenameError):
            plan_rename_id_short(linked.store, linked.second_item, "Second")

    def test_suggest_returns_a_valid_free_idshort(self) -> None:
        linked = make_linked()

        assert suggest_id_short(linked.name, "Name") == "Name"
        assert suggest_id_short(linked.name, "Group") == "Group_1"
        assert suggest_id_short(linked.name, "my motor!") == "My_motor"


class TestReplaceIdentifiable:
    def test_replace_updates_the_references_to_the_old_id(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        original = snapshot(linked.store)
        replacement = model.ConceptDescription(
            id_="urn:test:cd2", id_short="Concept"
        )
        stack = CommandStack()

        stack.push(
            ReplaceIdentifiable(
                observer,
                linked.store,
                linked.store,
                linked.concept,
                replacement,
            )
        )

        assert _keys(linked.name.semantic_id) == ["urn:test:cd2"]
        assert replacement in linked.store
        assert linked.concept not in linked.store
        stack.undo()
        assert snapshot(linked.store) == original

    def test_replace_refuses_an_id_of_another_object(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        replacement = model.ConceptDescription(id_=MAIN_ID, id_short="Concept")

        with pytest.raises(DuplicateIdError):
            ReplaceIdentifiable(
                observer,
                linked.store,
                linked.store,
                linked.concept,
                replacement,
            )
