"""The index of ids and references: duplicates, usages, and dangling."""

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import OTHER_ID
from tests.reference_factories import make_linked

from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.references import describe_reference
from aas_editor.domain.references import iter_slots
from aas_editor.domain.references import path_of


class TestIds:
    def test_with_id_finds_the_object(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.with_id(MAIN_ID) == (linked.main,)
        assert index.with_id("urn:missing") == ()

    def test_duplicate_ids_names_objects_that_share_an_id(self) -> None:
        first = make_submodel("urn:same", "First")
        second = make_submodel("urn:same", "Second")
        index = ReferenceIndex([first, second, make_submodel("urn:x", "Other")])

        assert index.duplicate_ids() == {"urn:same": (first, second)}

    def test_is_taken_ignores_the_object_that_gets_the_id(self) -> None:
        submodel = make_submodel("urn:a")
        index = ReferenceIndex([submodel, make_submodel("urn:b")])

        assert not index.is_taken("urn:a", ignoring=submodel)
        assert index.is_taken("urn:b", ignoring=submodel)
        assert not index.is_taken("urn:free", ignoring=submodel)

    def test_a_shell_and_a_concept_description_cannot_share_an_id(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.is_taken(CONCEPT_ID, ignoring=linked.main)


class TestSlots:
    def test_slots_cover_semantic_ids_and_references_of_the_environment(
        self,
    ) -> None:
        linked = make_linked()

        found = [
            (slot.owner, slot.attribute) for slot in iter_slots(linked.main)
        ]

        assert found == [
            (linked.name, "semantic_id"),
            (linked.inner, "semantic_id"),
            (linked.link, "value"),
            (linked.list_link, "value"),
            (linked.concept_link, "value"),
            (linked.relationship, "first"),
            (linked.relationship, "second"),
        ]

    def test_shell_references_are_members_of_the_submodel_set(self) -> None:
        linked = make_linked()

        slots = list(iter_slots(linked.shell))

        assert [slot.attribute for slot in slots] == ["submodel", "submodel"]
        assert all(slot.is_member for slot in slots)
        assert all(slot.is_removable for slot in slots)

    def test_the_first_of_a_relationship_cannot_be_removed(self) -> None:
        linked = make_linked()

        slot = next(
            slot
            for slot in iter_slots(linked.main)
            if slot.attribute == "first"
        )

        assert not slot.is_removable
        assert slot.owner is linked.relationship

    def test_optional_attributes_can_be_removed(self) -> None:
        linked = make_linked()

        slot = next(
            slot
            for slot in iter_slots(linked.main)
            if slot.attribute == "value" and slot.owner is linked.link
        )

        assert slot.is_removable

    def test_a_specific_asset_id_is_replaced_not_changed(self) -> None:
        subject = make_external_reference("urn:subject")
        shell = model.AssetAdministrationShell(
            model.AssetInformation(
                model.AssetKind.INSTANCE,
                specific_asset_id=[
                    model.SpecificAssetId("n", "v", external_subject_id=subject)
                ],
            ),
            "urn:shell",
        )

        (slot,) = iter_slots(shell)

        assert slot.is_frozen
        assert slot.owner_container is shell.asset_information.specific_asset_id

    def test_slots_are_in_document_order(self) -> None:
        linked = make_linked()

        owners = [slot.owner for slot in iter_slots(linked.main)]

        assert owners[:2] == [linked.name, linked.inner]


class TestResolve:
    def test_resolve_follows_idshorts(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.resolve(linked.link.value) is linked.inner

    def test_resolve_follows_list_positions(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.resolve(linked.list_link.value) is linked.second_item

    def test_resolve_follows_a_reference_to_an_identifiable(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.resolve(linked.concept_link.value) is linked.concept

    def test_resolve_is_none_for_a_global_reference(self) -> None:
        index = ReferenceIndex(make_linked().store)

        assert index.resolve(make_external_reference(CONCEPT_ID)) is None

    def test_resolve_ignores_a_fragment_key(self) -> None:
        linked = make_linked()
        file = model.File("Doc", "text/plain")
        linked.main.submodel_element.add(file)
        reference = model.ModelReference(
            (
                model.Key(model.KeyTypes.SUBMODEL, MAIN_ID),
                model.Key(model.KeyTypes.FILE, "Doc"),
                model.Key(model.KeyTypes.FRAGMENT_REFERENCE, "page=2"),
            ),
            model.File,
        )

        assert ReferenceIndex(linked.store).resolve(reference) is file


class TestUsages:
    def test_usages_of_a_concept_description_lists_semantic_ids(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.concept])

        assert [usage.slot.owner for usage in usages] == [
            linked.name,
            linked.inner,
            linked.concept_link,
        ]

    def test_usages_of_a_submodel_includes_references_to_its_elements(
        self,
    ) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.main])

        owners = [usage.slot.owner for usage in usages]
        assert linked.pointer in owners
        assert linked.shell in owners

    def test_usages_of_a_submodel_leave_out_references_stored_inside(
        self,
    ) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.main])

        assert linked.relationship not in [usage.slot.owner for usage in usages]
        assert linked.link not in [usage.slot.owner for usage in usages]

    def test_usages_of_an_element_include_references_to_what_is_below(
        self,
    ) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.group])

        assert [usage.slot.owner for usage in usages] == [
            linked.link,
            linked.relationship,
        ]

    def test_usages_of_a_list_item_use_its_position(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.second_item])

        assert [usage.slot.owner for usage in usages] == [linked.list_link]

    def test_usages_of_two_targets_count_a_reference_once(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.group, linked.inner])

        assert len(usages) == 2

    def test_usages_is_empty_when_nothing_refers_to_the_target(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        assert index.usages_of([linked.pointer]) == []

    def test_usages_of_a_list_include_references_to_its_items(self) -> None:
        linked = make_linked()
        index = ReferenceIndex(linked.store)

        usages = index.usages_of([linked.items])

        assert [usage.slot.owner for usage in usages] == [linked.list_link]

    def test_usages_of_a_shell_are_the_references_to_its_id(self) -> None:
        linked = make_linked()
        derived = model.AssetAdministrationShell(
            model.AssetInformation(model.AssetKind.INSTANCE, "urn:asset"),
            "urn:derived",
            derived_from=model.ModelReference.from_referable(linked.shell),
        )
        index = ReferenceIndex([*linked.store, derived])

        usages = index.usages_of([linked.shell])

        assert [usage.slot.owner for usage in usages] == [derived]
        assert usages[0].slot.attribute == "derived_from"

    def test_usages_find_a_nested_referred_semantic_id(self) -> None:
        linked = make_linked()
        outer = model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:other"),),
            make_external_reference(CONCEPT_ID),
        )
        element = make_property("Nested")
        element.semantic_id = outer
        linked.other.submodel_element.add(element)

        usages = ReferenceIndex(linked.store).usages_of([linked.concept])

        nested = [usage for usage in usages if usage.slot.owner is element]
        assert [usage.is_nested for usage in nested] == [True]

    def test_usages_match_an_id_in_any_key_of_an_external_reference(
        self,
    ) -> None:
        concept = make_concept_description("urn:cd")
        element = make_property("p")
        element.semantic_id = model.ExternalReference(
            (
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:other"),
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:cd"),
            )
        )

        usages = ReferenceIndex(
            [concept, make_submodel(elements=[element])]
        ).usages_of([concept])

        assert [usage.slot.owner for usage in usages] == [element]


class TestDangling:
    def test_dangling_is_empty_for_a_consistent_environment(self) -> None:
        index = ReferenceIndex(make_linked().store)

        assert index.dangling() == []

    def test_dangling_finds_a_reference_to_a_missing_object(self) -> None:
        linked = make_linked()
        linked.store.remove(linked.other)
        index = ReferenceIndex(linked.store)

        dangling = index.dangling()

        assert [item.slot.owner for item in dangling] == [linked.shell]
        assert dangling[0].reason == f"No object has the id '{OTHER_ID}'"

    def test_dangling_finds_a_reference_to_a_missing_element(self) -> None:
        linked = make_linked()
        linked.group.value.remove(linked.inner)
        index = ReferenceIndex(linked.store)

        owners = [item.slot.owner for item in index.dangling()]

        assert owners == [linked.link, linked.relationship]

    def test_dangling_ignores_external_references(self) -> None:
        linked = make_linked()
        linked.store.remove(linked.concept)
        index = ReferenceIndex(linked.store)

        owners = [item.slot.owner for item in index.dangling()]

        assert linked.name not in owners
        assert owners == [linked.concept_link]

    def test_dangling_can_be_limited_to_some_objects(self) -> None:
        linked = make_linked()
        linked.store.remove(linked.other)
        index = ReferenceIndex(linked.store)

        assert index.dangling([linked.main]) == []
        assert len(index.dangling([linked.shell])) == 1


class TestPaths:
    def test_path_of_an_element_lists_ids_idshorts_and_positions(self) -> None:
        linked = make_linked()

        assert path_of(linked.inner) == (MAIN_ID, "Group", "Inner")
        assert path_of(linked.second_item) == (MAIN_ID, "Items", "1")

    def test_path_of_is_none_for_an_element_outside_an_identifiable(
        self,
    ) -> None:
        assert path_of(make_property("loose")) is None

    def test_describe_reference_names_each_key(self) -> None:
        linked = make_linked()

        assert (
            describe_reference(linked.link.value)
            == f"Submodel {MAIN_ID} > SubmodelElementCollection Group"
            " > Property Inner"
        )


def test_a_collection_without_references_has_no_slots() -> None:
    submodel = make_submodel(
        elements=[make_collection("c", [make_property("p")])]
    )

    assert list(iter_slots(submodel)) == []
