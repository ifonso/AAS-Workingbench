"""Creating, assigning, detecting and deleting concept descriptions."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.commands import ReadOnlyError
from aas_workingbench.application.operations.concepts import CreatePlan
from aas_workingbench.application.operations.concepts import assign_commands
from aas_workingbench.application.operations.concepts import create_commands
from aas_workingbench.application.operations.concepts import from_pairs_commands
from aas_workingbench.application.operations.concepts import plan_assign
from aas_workingbench.application.operations.concepts import plan_create
from aas_workingbench.application.operations.concepts import plan_detect
from aas_workingbench.application.operations.concepts import plan_from_pairs
from aas_workingbench.application.operations.concepts import plan_invalid
from aas_workingbench.application.operations.concepts import value_pairs_of
from aas_workingbench.domain.concepts import holders_of
from aas_workingbench.domain.data_specifications import iec_content_of


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


def _prop(id_short: str, semantic: str | None = None) -> model.Property:
    prop = make_property(id_short)
    if semantic is not None:
        prop.semantic_id = make_external_reference(semantic)
    return prop


def _ids(store: model.SetIdentifiableStore) -> list[str]:
    return sorted(
        o.id for o in store if isinstance(o, model.ConceptDescription)
    )


def _apply(stack: CommandStack, description: str, commands: list) -> None:
    with stack.group(description):
        for command in commands:
            stack.push(command)


class TestCreate:
    def test_the_plan_adds_one_description_for_each_unknown_semantic_id(
        self,
    ) -> None:
        submodel = make_submodel(
            elements=[
                _prop("A", "urn:cd:a"),
                make_collection("C", [_prop("B", "urn:cd:b")]),
                _prop("NoSemantics"),
            ]
        )
        store = make_store(submodel)

        plan = plan_create(store, [submodel], adaptive=False)

        assert sorted(c.id for c in plan.new) == ["urn:cd:a", "urn:cd:b"]
        assert plan.without_semantic_id == 3  # the submodel, C and one more
        assert plan.existing == ()
        assert plan.conflicts == ()

    def test_two_elements_with_one_semantic_id_make_one_description(
        self,
    ) -> None:
        submodel = make_submodel(
            elements=[_prop("A", "urn:cd:x"), _prop("B", "urn:cd:x")]
        )

        plan = plan_create(make_store(submodel), [submodel], adaptive=False)

        assert [c.id for c in plan.new] == ["urn:cd:x"]
        assert [s.owner.id_short for s in plan.sources] == ["A"]

    def test_an_existing_description_is_reported_and_not_created_again(
        self,
    ) -> None:
        submodel = make_submodel(elements=[_prop("A", "urn:cd:a")])
        store = make_store(submodel, model.ConceptDescription("urn:cd:a"))

        plan = plan_create(store, [submodel], adaptive=False)

        assert plan.new == ()
        assert [(h.owner.id_short, c.id) for h, c in plan.existing] == [
            ("A", "urn:cd:a")
        ]

    def test_an_id_that_another_kind_of_object_has_is_a_conflict(self) -> None:
        other = make_submodel("urn:cd:clash", "Other")
        submodel = make_submodel(elements=[_prop("A", "urn:cd:clash")])
        store = make_store(submodel, other)

        plan = plan_create(store, [submodel], adaptive=False)

        assert plan.new == ()
        ((holder, obj),) = plan.conflicts
        assert holder.owner.id_short == "A"
        assert obj is other

    def test_the_summary_names_what_is_added_and_what_is_skipped(self) -> None:
        submodel = make_submodel(elements=[_prop("A", "urn:cd:a")])
        store = make_store(submodel, model.ConceptDescription("urn:cd:a"))

        plan = plan_create(store, [submodel], adaptive=False)

        assert plan.summary == (
            "0 concept descriptions will be added, 1 already exist, "
            "1 have no semantic id."
        )

    def test_a_single_element_without_looking_below(self) -> None:
        inner = _prop("Inner", "urn:cd:inner")
        outer = make_collection("Outer", [inner])
        outer.semantic_id = make_external_reference("urn:cd:outer")
        submodel = make_submodel(elements=[outer])

        plan = plan_create(
            make_store(submodel), [outer], adaptive=False, below=False
        )

        assert [c.id for c in plan.new] == ["urn:cd:outer"]

    def test_creating_is_one_step_that_undo_and_redo_restore(
        self, observer: ModelChangeObserver
    ) -> None:
        submodel = make_submodel(
            elements=[_prop("A", "urn:cd:a"), _prop("B", "urn:cd:b")]
        )
        store = make_store(submodel)
        stack = CommandStack()
        before = snapshot(store)
        plan: CreatePlan = plan_create(store, [submodel], adaptive=True)

        _apply(stack, "Create", create_commands(observer, store, plan))
        after = snapshot(store)
        stack.undo()
        undone = snapshot(store)
        stack.redo()

        assert _ids(store) == ["urn:cd:a", "urn:cd:b"]
        assert undone == before
        assert snapshot(store) == after
        assert after != before

    def test_read_mode_refuses_the_commands(
        self, observer: ModelChangeObserver
    ) -> None:
        submodel = make_submodel(elements=[_prop("A", "urn:cd:a")])
        store = make_store(submodel)
        stack = CommandStack(is_editing=lambda: False)
        plan = plan_create(store, [submodel], adaptive=False)

        with pytest.raises(ReadOnlyError):
            _apply(stack, "Create", create_commands(observer, store, plan))

        assert _ids(store) == []


class TestAssign:
    def test_a_description_becomes_the_semantic_id(
        self, observer: ModelChangeObserver
    ) -> None:
        prop = _prop("A")
        submodel = make_submodel(elements=[prop])
        concept = model.ConceptDescription("urn:cd:a")
        store = make_store(submodel, concept)
        (holder,) = holders_of([prop], below=False)
        stack = CommandStack()
        before = snapshot(store)

        plan = plan_assign(holder, concept)
        _apply(stack, "Assign", assign_commands(observer, [plan]))

        assert not plan.replaces
        assert prop.semantic_id == make_external_reference("urn:cd:a")
        stack.undo()
        assert prop.semantic_id is None
        assert snapshot(store) == before

    def test_an_existing_semantic_id_is_reported_as_replaced(self) -> None:
        prop = _prop("A", "urn:cd:old")
        make_submodel(elements=[prop])
        concept = model.ConceptDescription("urn:cd:new")
        (holder,) = holders_of([prop], below=False)

        plan = plan_assign(holder, concept)

        assert plan.replaces
        assert plan.previous == make_external_reference("urn:cd:old")

    def test_assigning_the_same_description_changes_nothing(
        self, observer: ModelChangeObserver
    ) -> None:
        prop = _prop("A", "urn:cd:a")
        make_submodel(elements=[prop])
        concept = model.ConceptDescription("urn:cd:a")
        (holder,) = holders_of([prop], below=False)

        plan = plan_assign(holder, concept)

        assert plan.is_noop
        assert assign_commands(observer, [plan]) == []

    def test_the_element_keeps_its_place(
        self, observer: ModelChangeObserver
    ) -> None:
        first, second = _prop("First"), _prop("Second")
        submodel = make_submodel(elements=[first, second])
        concept = model.ConceptDescription("urn:cd:a")
        (holder,) = holders_of([first], below=False)
        stack = CommandStack()

        _apply(
            stack,
            "Assign",
            assign_commands(observer, [plan_assign(holder, concept)]),
        )

        assert [e.id_short for e in submodel.submodel_element] == [
            "First",
            "Second",
        ]


class TestDetect:
    def _concepts(self) -> list[model.ConceptDescription]:
        return [
            model.ConceptDescription("urn:cd:speed", id_short="Speed"),
            model.ConceptDescription("urn:cd:weight", id_short="Weight"),
            model.ConceptDescription("urn:cd:dup1", id_short="Twice"),
            model.ConceptDescription("urn:cd:dup2", id_short="Twice"),
        ]

    def test_an_element_takes_the_description_with_its_idshort(self) -> None:
        submodel = make_submodel(elements=[_prop("Speed")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        ((assignment,),) = [plan.assign]
        assert assignment.holder.owner.id_short == "Speed"
        assert assignment.concept.id == "urn:cd:speed"
        assert not assignment.replaces

    def test_the_match_may_differ_in_case_if_nothing_is_exact(self) -> None:
        submodel = make_submodel(elements=[_prop("speed")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert [p.concept.id for p in plan.assign] == ["urn:cd:speed"]

    def test_several_matches_are_reported_and_nothing_is_assigned(self) -> None:
        submodel = make_submodel(elements=[_prop("Twice")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert plan.assign == ()
        ((holder, candidates),) = plan.ambiguous
        assert holder.owner.id_short == "Twice"
        assert sorted(c.id for c in candidates) == [
            "urn:cd:dup1",
            "urn:cd:dup2",
        ]

    def test_an_element_with_no_match_is_reported(self) -> None:
        submodel = make_submodel(elements=[_prop("Colour")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert [h.owner.id_short for h in plan.unmatched] == [
            "Submodel",
            "Colour",
        ]

    def test_a_semantic_id_that_names_a_description_counts_as_linked(
        self,
    ) -> None:
        submodel = make_submodel(elements=[_prop("Whatever", "urn:cd:weight")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert [h.owner.id_short for h in plan.linked] == ["Whatever"]
        assert plan.assign == ()

    def test_a_semantic_id_is_never_replaced_even_when_the_idshort_matches(
        self,
    ) -> None:
        submodel = make_submodel(elements=[_prop("Speed", "urn:other:thing")])
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert plan.assign == ()
        assert [h.owner.id_short for h in plan.unresolved] == ["Speed"]

    def test_an_item_of_a_list_has_no_idshort_to_match(self) -> None:
        item = model.Property(None, model.datatypes.String)
        make_submodel(elements=[make_list("Speed", [item])])
        store = make_store(*self._concepts())

        plan = plan_detect(store, [item], below=False)

        assert plan.assign == ()
        assert len(plan.unmatched) == 1

    def test_the_summary_counts_each_outcome(self) -> None:
        submodel = make_submodel(
            elements=[_prop("Speed"), _prop("Twice"), _prop("Colour")]
        )
        store = make_store(submodel, *self._concepts())

        plan = plan_detect(store, [submodel])

        assert plan.summary == (
            "1 element will get a concept, 1 match several (skipped), "
            "2 match none."
        )

    def test_detecting_is_one_undoable_step(
        self, observer: ModelChangeObserver
    ) -> None:
        submodel = make_submodel(elements=[_prop("Speed"), _prop("Weight")])
        store = make_store(submodel, *self._concepts())
        stack = CommandStack()
        before = snapshot(store)
        plan = plan_detect(store, [submodel])

        _apply(stack, "Detect", assign_commands(observer, plan.assign))
        done = snapshot(store)
        stack.undo()

        assert done != before
        assert snapshot(store) == before
        stack.redo()
        assert snapshot(store) == done


def _pair(value: str, id_: str | None) -> model.ValueReferencePair:
    return model.ValueReferencePair(
        value, None if id_ is None else make_external_reference(id_)
    )


def _holder(*pairs: model.ValueReferencePair) -> model.ConceptDescription:
    return model.ConceptDescription(
        "urn:cd:colours",
        id_short="Colours",
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                make_external_reference("k"),
                model.DataSpecificationIEC61360(
                    model.PreferredNameTypeIEC61360({"en": "Colours"}),
                    value_list=set(pairs),
                ),
            )
        ],
    )


class TestFromPairs:
    def test_each_pair_with_a_value_id_becomes_a_description(self) -> None:
        concept = _holder(_pair("Red", "urn:red"), _pair("Blue", "urn:blue"))
        store = make_store(concept)

        plan = plan_from_pairs(store, concept)

        assert [c.id for _, c in plan.new] == ["urn:blue", "urn:red"]
        assert plan.existing == ()
        assert plan.skipped == ()

    def test_the_new_descriptions_follow_the_spec(self) -> None:
        concept = _holder(_pair("Red", "urn:red"))
        plan = plan_from_pairs(make_store(concept), concept)

        ((_, created),) = plan.new
        content = iec_content_of(created.embedded_data_specifications[0])
        assert content is not None
        assert content.data_type is model.DataTypeIEC61360.STRING_TRANSLATABLE
        assert dict(content.preferred_name) == {"en": "Red"}
        assert created.id_short == "Red"

    def test_the_list_of_the_source_is_unchanged(self) -> None:
        concept = _holder(_pair("Red", "urn:red"))
        store = make_store(concept)
        before = snapshot(store)

        plan_from_pairs(store, concept)

        assert snapshot(store) == before

    def test_a_pair_without_a_value_id_is_skipped_with_the_reason(self) -> None:
        concept = _holder(_pair("Lonely", None))

        plan = plan_from_pairs(make_store(concept), concept)

        assert plan.new == ()
        ((pair, reason),) = plan.skipped
        assert pair.value == "Lonely"
        assert reason == "it has no value id"

    def test_a_pair_whose_id_exists_is_reported(self) -> None:
        concept = _holder(_pair("Red", "urn:red"))
        red = model.ConceptDescription("urn:red")
        store = make_store(concept, red)

        plan = plan_from_pairs(store, concept)

        assert plan.new == ()
        ((_, found),) = plan.existing
        assert found is red

    def test_two_pairs_with_one_id_make_one_description(self) -> None:
        concept = _holder(_pair("Red", "urn:x"), _pair("Rot", "urn:x"))

        plan = plan_from_pairs(make_store(concept), concept)

        assert len(plan.new) == 1
        assert len(plan.skipped) == 1
        assert "urn:x" in plan.skipped[0][1]

    def test_the_pairs_come_sorted_so_every_run_lists_alike(self) -> None:
        concept = _holder(
            _pair("b", "urn:2"), _pair("a", "urn:3"), _pair("a", "urn:1")
        )

        assert [
            (p.value, p.value_id.key[0].value) for p in value_pairs_of(concept)
        ] == [  # type: ignore[union-attr]
            ("a", "urn:1"),
            ("a", "urn:3"),
            ("b", "urn:2"),
        ]

    def test_creating_is_one_undoable_step(
        self, observer: ModelChangeObserver
    ) -> None:
        concept = _holder(_pair("Red", "urn:red"), _pair("Blue", "urn:blue"))
        store = make_store(concept)
        stack = CommandStack()
        before = snapshot(store)
        plan = plan_from_pairs(store, concept)

        _apply(stack, "Create", from_pairs_commands(observer, store, plan))
        done = snapshot(store)
        added = _ids(store)
        stack.undo()

        assert added == ["urn:blue", "urn:cd:colours", "urn:red"]
        assert _ids(store) == ["urn:cd:colours"]
        assert snapshot(store) == before
        stack.redo()
        assert snapshot(store) == done


class TestInvalid:
    def test_empty_descriptions_are_listed_with_their_usages(self) -> None:
        empty = model.ConceptDescription("urn:cd:empty", id_short="Empty")
        full = _holder(_pair("Red", "urn:red"))
        used = _prop("Used", "urn:cd:empty")
        store = make_store(empty, full, make_submodel(elements=[used]))

        (invalid,) = plan_invalid(store)

        assert invalid.concept is empty
        assert invalid.usages == 1

    def test_a_package_without_empty_descriptions_has_none(self) -> None:
        full = _holder(_pair("Red", "urn:red"))

        assert plan_invalid(make_store(full)) == ()
