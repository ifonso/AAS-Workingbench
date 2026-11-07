"""Fix References and Sync idShort."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.reference_factories import CONCEPT_ID
from tests.reference_factories import MAIN_ID
from tests.reference_factories import OTHER_ID
from tests.reference_factories import Linked
from tests.reference_factories import make_linked
from tests.serialization import snapshot

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.operations.fix import FixReferencesPlan
from aas_workingbench.application.operations.fix import plan_fix_references
from aas_workingbench.application.operations.fix import sync_id_short_commands
from aas_workingbench.application.operations.references import (
    reference_commands,
)
from aas_workingbench.domain.references import ReferenceIndex


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


def _apply(
    observer: ModelChangeObserver, stack: CommandStack, plan: FixReferencesPlan
) -> None:
    with stack.group("Fix References"):
        for command in reference_commands(observer, plan.changes):
            stack.push(command)


def _model_reference(*keys: model.Key) -> model.ModelReference:
    return model.ModelReference(keys, model.Property)


def _keys(reference: model.Reference | None) -> list[tuple[str, str]]:
    assert reference is not None
    return [(key.type.name, key.value) for key in reference.key]


class TestFixReferences:
    def test_plan_is_empty_for_a_consistent_environment(self) -> None:
        linked = make_linked()

        plan = plan_fix_references(linked.store)

        assert plan.changes == ()
        assert plan.unfixable == ()

    def test_fix_replaces_the_idshort_in_the_first_key_by_the_id(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.pointer.value = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, "Main"),
            model.Key(model.KeyTypes.PROPERTY, "Name"),
        )
        original = snapshot(linked.store)
        stack = CommandStack()

        plan = plan_fix_references(linked.store)
        _apply(observer, stack, plan)

        assert _keys(linked.pointer.value) == [
            ("SUBMODEL", MAIN_ID),
            ("PROPERTY", "Name"),
        ]
        assert ReferenceIndex(linked.store).dangling() == []
        stack.undo()
        assert snapshot(linked.store) == original

    def test_fix_corrects_the_type_of_a_key(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.pointer.value = model.ModelReference(
            (model.Key(model.KeyTypes.CONCEPT_DESCRIPTION, MAIN_ID),),
            model.ConceptDescription,
        )
        stack = CommandStack()

        _apply(observer, stack, plan_fix_references(linked.store))

        assert _keys(linked.pointer.value) == [("SUBMODEL", MAIN_ID)]

    def test_fix_corrects_the_type_of_a_key_in_the_path(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        linked.pointer.value = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, MAIN_ID),
            model.Key(model.KeyTypes.MULTI_LANGUAGE_PROPERTY, "Name"),
        )
        stack = CommandStack()

        _apply(observer, stack, plan_fix_references(linked.store))

        assert _keys(linked.pointer.value) == [
            ("SUBMODEL", MAIN_ID),
            ("PROPERTY", "Name"),
        ]

    def test_fix_leaves_a_general_key_type_alone(self) -> None:
        linked = make_linked()
        linked.pointer.value = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, MAIN_ID),
            model.Key(model.KeyTypes.SUBMODEL_ELEMENT, "Name"),
        )

        plan = plan_fix_references(linked.store)

        assert plan.changes == ()

    def test_fix_reports_a_reference_that_points_at_nothing(self) -> None:
        linked = make_linked()
        linked.pointer.value = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, "urn:gone"),
            model.Key(model.KeyTypes.PROPERTY, "Name"),
        )

        plan = plan_fix_references(linked.store)

        assert plan.changes == ()
        assert [item.slot.owner for item in plan.unfixable] == [linked.pointer]

    def test_fix_does_not_guess_when_two_objects_have_the_idshort(
        self,
    ) -> None:
        linked = make_linked()
        linked.other.id_short = "Main"
        linked.pointer.value = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, "Main"),
            model.Key(model.KeyTypes.PROPERTY, "Name"),
        )

        plan = plan_fix_references(linked.store)

        assert plan.changes == ()
        assert len(plan.unfixable) == 1

    def test_fix_can_be_limited_to_some_objects(self) -> None:
        linked = make_linked()
        bad = _model_reference(
            model.Key(model.KeyTypes.SUBMODEL, "Main"),
            model.Key(model.KeyTypes.PROPERTY, "Name"),
        )
        linked.pointer.value = bad
        linked.link.value = bad

        only_other = plan_fix_references(linked.store, [linked.other])

        assert [c.slot.owner for c in only_other.changes] == [linked.pointer]

    def test_fix_repairs_a_reference_below_another_reference(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        element = make_property("Nested")
        element.semantic_id = model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:x"),),
            model.ModelReference(
                (model.Key(model.KeyTypes.SUBMODEL, "Main"),), model.Submodel
            ),
        )
        linked.other.submodel_element.add(element)
        stack = CommandStack()

        _apply(observer, stack, plan_fix_references(linked.store))

        assert element.semantic_id is not None
        assert element.semantic_id.key[0].value == "urn:x"
        assert _keys(element.semantic_id.referred_semantic_id) == [
            ("SUBMODEL", MAIN_ID)
        ]

    def test_fix_keeps_a_trailing_fragment_key(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        file = model.File("Doc", "text/plain")
        linked.other.submodel_element.add(file)
        linked.pointer.value = model.ModelReference(
            (
                model.Key(model.KeyTypes.SUBMODEL, "Other"),
                model.Key(model.KeyTypes.FILE, "Doc"),
                model.Key(model.KeyTypes.FRAGMENT_REFERENCE, "page=2"),
            ),
            model.File,
        )
        stack = CommandStack()

        _apply(observer, stack, plan_fix_references(linked.store))

        assert _keys(linked.pointer.value) == [
            ("SUBMODEL", OTHER_ID),
            ("FILE", "Doc"),
            ("FRAGMENT_REFERENCE", "page=2"),
        ]


def _concept_without_names() -> model.ConceptDescription:
    return model.ConceptDescription(
        CONCEPT_ID,
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                make_external_reference("urn:iec61360"),
                model.DataSpecificationIEC61360(
                    preferred_name=model.PreferredNameTypeIEC61360(
                        {"en": "Preferred"}
                    )
                ),
            )
        ],
    )


def _linked_with_unnamed_concept() -> Linked:
    linked = make_linked()
    linked.store.remove(linked.concept)
    unnamed = _concept_without_names()
    linked.store.add(unnamed)
    linked.concept = unnamed
    return linked


def _short_name(concept: model.ConceptDescription) -> dict[str, str] | None:
    content = concept.embedded_data_specifications[0].data_specification_content
    assert isinstance(content, model.DataSpecificationIEC61360)
    return None if content.short_name is None else dict(content.short_name)


class TestSync:
    def test_sync_copies_the_idshort_of_an_element_to_its_concept(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = _linked_with_unnamed_concept()
        original = snapshot(linked.store)
        stack = CommandStack()

        with stack.group("Sync"):
            for command in sync_id_short_commands(
                observer, linked.store, linked.name
            ):
                stack.push(command)

        assert linked.concept.id_short == "Name"
        assert _short_name(linked.concept) == {"en": "Name"}
        stack.undo()
        assert snapshot(linked.store) == original

    def test_sync_does_not_replace_names_that_are_set(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()
        content = model.DataSpecificationIEC61360(
            preferred_name=model.PreferredNameTypeIEC61360({"en": "P"}),
            short_name=model.ShortNameTypeIEC61360({"en": "Kept"}),
        )
        linked.concept.embedded_data_specifications.append(
            model.EmbeddedDataSpecification(
                make_external_reference("urn:iec61360"), content
            )
        )

        commands = sync_id_short_commands(observer, linked.store, linked.name)

        assert commands == []

    def test_sync_skips_a_short_name_that_is_too_long(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = _linked_with_unnamed_concept()
        long_name = make_property("AVeryLongIdShortWithManyLetters")
        long_name.semantic_id = make_external_reference(CONCEPT_ID)
        linked.other.submodel_element.add(long_name)
        stack = CommandStack()

        for command in sync_id_short_commands(
            observer, linked.store, long_name
        ):
            stack.push(command)

        assert linked.concept.id_short == "AVeryLongIdShortWithManyLetters"
        assert _short_name(linked.concept) is None

    def test_sync_of_a_concept_description_fills_its_short_name(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = _linked_with_unnamed_concept()
        linked.concept.id_short = "Voltage"
        stack = CommandStack()

        for command in sync_id_short_commands(
            observer, linked.store, linked.concept
        ):
            stack.push(command)

        assert _short_name(linked.concept) == {"en": "Voltage"}

    def test_sync_does_nothing_without_a_concept(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = make_linked()

        assert (
            sync_id_short_commands(observer, linked.store, linked.group) == []
        )

    def test_sync_uses_the_language_that_is_asked_for(
        self, observer: ModelChangeObserver
    ) -> None:
        linked = _linked_with_unnamed_concept()
        stack = CommandStack()

        for command in sync_id_short_commands(
            observer, linked.store, linked.name, language="de"
        ):
            stack.push(command)

        assert _short_name(linked.concept) == {"de": "Name"}
