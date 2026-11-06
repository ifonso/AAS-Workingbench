"""Changing one attribute of many objects with a pattern, and removing extensions."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_property
from tests.factories import make_submodel
from tests.reference_factories import Linked
from tests.reference_factories import make_linked

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.bulk_edit import BulkAttribute
from aas_editor.application.operations.bulk_edit import BulkPlan
from aas_editor.application.operations.bulk_edit import EntryStatus
from aas_editor.application.operations.bulk_edit import ExtensionKey
from aas_editor.application.operations.bulk_edit import change_commands
from aas_editor.application.operations.bulk_edit import group_extensions
from aas_editor.application.operations.bulk_edit import plan_change_attribute
from aas_editor.application.operations.bulk_edit import (
    remove_extension_commands,
)


def _apply(stack: CommandStack, owner: object, plan: BulkPlan) -> None:
    with stack.group(plan.description):
        for command in change_commands(observer_for(owner), plan):
            stack.push(command)


def _statuses(plan: BulkPlan) -> list[EntryStatus]:
    return [entry.status for entry in plan.entries]


def _ids(container: object) -> list[str]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


def _group_of(*names: str) -> tuple[model.Submodel, list[model.Property]]:
    properties = [make_property(n) for n in names]
    return make_submodel(elements=properties), properties


class TestIdShort:
    def test_a_prefix_changes_every_selected_element(self) -> None:
        submodel, props = _group_of("Foo", "Bar", "Baz")

        plan = plan_change_attribute(
            [submodel], props[:2], BulkAttribute.ID_SHORT, "ABC_{old}"
        )
        stack = CommandStack()
        _apply(stack, submodel, plan)

        assert plan.can_apply
        assert [(e.old, e.new) for e in plan.entries] == [
            ("Foo", "ABC_Foo"),
            ("Bar", "ABC_Bar"),
        ]
        assert _ids(submodel.submodel_element) == ["ABC_Foo", "ABC_Bar", "Baz"]

    def test_numbers_follow_the_order_of_the_selection(self) -> None:
        submodel, props = _group_of("A", "B", "C")

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "Item{number|pad(2)}"
        )
        _apply(CommandStack(), submodel, plan)

        assert _ids(submodel.submodel_element) == ["Item01", "Item02", "Item03"]

    def test_one_undo_gives_back_every_name_and_redo_applies_them(self) -> None:
        submodel, props = _group_of("Foo", "Bar")
        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "{old|upper}"
        )
        stack = CommandStack()

        _apply(stack, submodel, plan)
        stack.undo()
        undone = _ids(submodel.submodel_element)
        stack.redo()

        assert undone == ["Foo", "Bar"]
        assert _ids(submodel.submodel_element) == ["FOO", "BAR"]
        assert stack.undo_description == plan.description

    def test_the_elements_keep_their_places(self) -> None:
        submodel, props = _group_of("A", "B", "C")

        plan = plan_change_attribute(
            [submodel], [props[1]], BulkAttribute.ID_SHORT, "Middle"
        )
        _apply(CommandStack(), submodel, plan)

        assert _ids(submodel.submodel_element) == ["A", "Middle", "C"]

    def test_a_result_that_is_not_a_valid_id_short_is_refused(self) -> None:
        submodel, props = _group_of("Foo", "Bar")

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "{old} x"
        )

        assert _statuses(plan) == [EntryStatus.REFUSED] * 2
        assert "not a valid idShort" in plan.entries[0].reason
        assert not plan.can_apply

    def test_a_name_that_an_unselected_sibling_has_is_refused(self) -> None:
        submodel, props = _group_of("Foo", "Bar", "Taken")

        plan = plan_change_attribute(
            [submodel], props[:1], BulkAttribute.ID_SHORT, "Taken"
        )

        assert plan.entries[0].status is EntryStatus.REFUSED
        assert "sibling" in plan.entries[0].reason
        assert not plan.can_apply

    def test_two_elements_that_get_the_same_name_are_both_refused(self) -> None:
        submodel, props = _group_of("Foo", "Bar")

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "Same"
        )

        assert _statuses(plan) == [EntryStatus.REFUSED] * 2
        assert "selected" in plan.entries[0].reason

    def test_names_that_are_swapped_are_not_a_duplicate(self) -> None:
        submodel, props = _group_of("A1", "B1")
        pattern = '{old|replace("A","T")|replace("B","A")|replace("T","B")}'

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, pattern
        )
        stack = CommandStack()
        _apply(stack, submodel, plan)

        assert plan.can_apply
        assert _ids(submodel.submodel_element) == ["B1", "A1"]
        assert props[0].id_short == "B1"
        stack.undo()
        assert _ids(submodel.submodel_element) == ["A1", "B1"]

    def test_a_shift_along_a_chain_of_names_works(self) -> None:
        submodel, props = _group_of("Item1", "Item2", "Item3")
        pattern = 'Item{old|strip_prefix("Item")|add(1)}'

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, pattern
        )
        _apply(CommandStack(), submodel, plan)

        assert plan.can_apply
        assert _ids(submodel.submodel_element) == ["Item2", "Item3", "Item4"]

    def test_an_unchanged_name_is_reported_as_such(self) -> None:
        submodel, props = _group_of("Foo", "Bar")

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "{old}"
        )

        assert _statuses(plan) == [EntryStatus.UNCHANGED] * 2
        assert not plan.can_apply

    def test_an_item_of_a_list_is_skipped(self) -> None:
        item = model.Property(
            id_short=None, value_type=model.datatypes.String, value="x"
        )
        listing = make_list("List", [item])
        prop = make_property("Foo")
        submodel = make_submodel(elements=[listing, prop])

        plan = plan_change_attribute(
            [submodel], [item, prop], BulkAttribute.ID_SHORT, "X{old}"
        )

        assert _statuses(plan) == [EntryStatus.SKIPPED, EntryStatus.CHANGE]
        assert "list" in plan.entries[0].reason
        assert plan.can_apply

    def test_an_id_short_of_a_submodel_changes_without_references(self) -> None:
        submodel, _ = _group_of("Foo")

        plan = plan_change_attribute(
            [submodel], [submodel], BulkAttribute.ID_SHORT, "{old}_v2"
        )
        _apply(CommandStack(), submodel, plan)

        assert submodel.id_short == "Submodel_v2"
        assert plan.reference_count == 0

    def test_references_through_renamed_elements_follow(self) -> None:
        world = make_linked()
        objects = list(world.store)
        stack = CommandStack()

        plan = plan_change_attribute(
            objects, [world.name], BulkAttribute.ID_SHORT, "Renamed"
        )
        _apply(stack, world.main, plan)

        assert plan.reference_count >= 2
        assert [k.value for k in world.pointer.value.key] == [  # type: ignore[union-attr]
            "urn:test:main",
            "Renamed",
        ]
        stack.undo()
        assert [k.value for k in world.pointer.value.key][-1] == "Name"  # type: ignore[union-attr]

    def test_a_parent_and_its_child_are_renamed_together(self) -> None:
        world: Linked = make_linked()
        objects = list(world.store)

        plan = plan_change_attribute(
            objects,
            [world.group, world.inner],
            BulkAttribute.ID_SHORT,
            "{old|slice(0,2)}",
        )
        _apply(CommandStack(), world.main, plan)

        assert (world.group.id_short, world.inner.id_short) == ("Gr", "In")
        assert [k.value for k in world.link.value.key] == [  # type: ignore[union-attr]
            "urn:test:main",
            "Gr",
            "In",
        ]

    def test_a_wrong_pattern_gives_a_plan_that_cannot_be_applied(self) -> None:
        submodel, props = _group_of("Foo")

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.ID_SHORT, "{nope}"
        )

        assert plan.pattern_error is not None
        assert "Unknown field" in plan.pattern_error
        assert plan.entries == ()
        assert not plan.can_apply

    def test_a_filter_that_cannot_work_on_one_value_refuses_that_element(
        self,
    ) -> None:
        submodel, props = _group_of("Foo1", "Bar")

        plan = plan_change_attribute(
            [submodel],
            props,
            BulkAttribute.ID_SHORT,
            "{old|slice(3)|add(1)}",
        )

        assert plan.entries[1].status is EntryStatus.REFUSED
        assert "whole number" in plan.entries[1].reason

    def test_a_change_that_fails_while_applying_rolls_everything_back(
        self,
    ) -> None:
        submodel, props = _group_of("Foo", "Bar", "Baz")
        plan = plan_change_attribute(
            [submodel], props[:2], BulkAttribute.ID_SHORT, "N_{old}"
        )
        # The package changes between the plan and the apply.
        submodel.submodel_element.add(make_property("N_Bar"))
        stack = CommandStack()

        with pytest.raises(model.AASConstraintViolation):
            _apply(stack, submodel, plan)

        assert _ids(submodel.submodel_element) == [
            "Foo",
            "Bar",
            "Baz",
            "N_Bar",
        ]
        assert not stack.can_undo


class TestTexts:
    def _with_description(self, *texts: dict[str, str]) -> list[model.Property]:
        props = [make_property(f"P{n}") for n in range(len(texts))]
        for prop, text in zip(props, texts, strict=True):
            if text:
                prop.description = model.MultiLanguageTextType(dict(text))
        return props

    def test_the_text_of_the_chosen_language_changes(self) -> None:
        props = self._with_description(
            {"en": "alpha", "de": "eins"}, {"en": "beta"}
        )
        submodel = make_submodel(elements=props)

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.DESCRIPTION, "{old|upper}", "en"
        )
        stack = CommandStack()
        _apply(stack, submodel, plan)

        assert dict(props[0].description) == {"en": "ALPHA", "de": "eins"}
        assert dict(props[1].description) == {"en": "BETA"}
        stack.undo()
        assert dict(props[0].description) == {"en": "alpha", "de": "eins"}

    def test_an_element_without_the_language_is_skipped_and_the_rest_change(
        self,
    ) -> None:
        props = self._with_description({"en": "alpha"}, {"de": "zwei"}, {})
        submodel = make_submodel(elements=props)

        plan = plan_change_attribute(
            [submodel], props, BulkAttribute.DESCRIPTION, "X{old}", "en"
        )
        _apply(CommandStack(), submodel, plan)

        assert _statuses(plan) == [
            EntryStatus.CHANGE,
            EntryStatus.SKIPPED,
            EntryStatus.SKIPPED,
        ]
        assert "language 'en'" in plan.entries[1].reason
        assert plan.can_apply
        assert dict(props[0].description) == {"en": "Xalpha"}
        assert dict(props[1].description) == {"de": "zwei"}

    def test_a_text_that_is_too_long_or_empty_is_refused_with_the_reason(
        self,
    ) -> None:
        props = self._with_description({"en": "a"}, {"en": "b"})
        submodel = make_submodel(elements=props)

        too_long = plan_change_attribute(
            [submodel],
            props[:1],
            BulkAttribute.DESCRIPTION,
            '{old|pad(1100,"x")}',
            "en",
        )
        empty = plan_change_attribute(
            [submodel],
            props[1:],
            BulkAttribute.DESCRIPTION,
            '{old|replace("b","")}',
            "en",
        )

        assert too_long.entries[0].status is EntryStatus.REFUSED
        assert "maximum length" in too_long.entries[0].reason
        assert empty.entries[0].status is EntryStatus.REFUSED
        assert "minimum length" in empty.entries[0].reason

    def test_display_names_change_like_descriptions(self) -> None:
        prop = make_property("P")
        prop.display_name = model.MultiLanguageNameType({"en": "pump"})
        submodel = make_submodel(elements=[prop])

        plan = plan_change_attribute(
            [submodel], [prop], BulkAttribute.DISPLAY_NAME, "{old|capitalize}"
        )
        _apply(CommandStack(), submodel, plan)

        assert dict(prop.display_name) == {"en": "Pump"}

    def test_the_pattern_can_use_the_id_short_of_the_element(self) -> None:
        props = self._with_description({"en": "alpha"})
        submodel = make_submodel(elements=props)

        plan = plan_change_attribute(
            [submodel],
            props,
            BulkAttribute.DESCRIPTION,
            "{idShort}: {old}",
            "en",
        )
        _apply(CommandStack(), submodel, plan)

        assert props[0].description["en"] == "P0: alpha"


class TestValues:
    def test_the_value_of_a_property_follows_its_type(self) -> None:
        ints = make_property("Int", "7", model.datatypes.String)
        number = model.Property("Num", model.datatypes.Int, 7)
        bad = model.Property("Bad", model.datatypes.Int, 3)
        submodel = make_submodel(elements=[ints, number, bad])

        plan = plan_change_attribute(
            [submodel],
            [ints, number],
            BulkAttribute.VALUE,
            "{old|add(1)}",
        )
        _apply(CommandStack(), submodel, plan)

        assert (ints.value, number.value) == ("8", 8)
        assert isinstance(number.value, model.datatypes.Int)

    def test_a_value_that_does_not_fit_the_type_is_refused(self) -> None:
        number = model.Property("Num", model.datatypes.Int, 7)
        submodel = make_submodel(elements=[number])

        plan = plan_change_attribute(
            [submodel], [number], BulkAttribute.VALUE, "{old}x"
        )

        assert plan.entries[0].status is EntryStatus.REFUSED
        assert "7x" in plan.entries[0].reason
        assert not plan.can_apply

    def test_a_multi_language_property_changes_in_the_chosen_language(
        self,
    ) -> None:
        mlp = make_multi_language_property("M", {"en": "hello", "de": "hallo"})
        submodel = make_submodel(elements=[mlp])

        plan = plan_change_attribute(
            [submodel], [mlp], BulkAttribute.VALUE, "{old|upper}", "de"
        )
        stack = CommandStack()
        _apply(stack, submodel, plan)

        assert dict(mlp.value) == {"en": "hello", "de": "HALLO"}
        stack.undo()
        assert dict(mlp.value) == {"en": "hello", "de": "hallo"}

    def test_elements_without_a_text_value_are_skipped(self) -> None:
        collection = make_collection("C")
        prop = make_property("P", "x")
        submodel = make_submodel(elements=[collection, prop])

        plan = plan_change_attribute(
            [submodel], [collection, prop], BulkAttribute.VALUE, "{old}!"
        )

        assert _statuses(plan) == [EntryStatus.SKIPPED, EntryStatus.CHANGE]
        assert "no text value" in plan.entries[0].reason


class TestRemoveExtensions:
    def _owners(self) -> tuple[model.Submodel, list[model.Property]]:
        first, second, third = (make_property(n) for n in ("A", "B", "C"))
        for owner, name in (
            (first, "Alpha"),
            (second, "Alpha"),
            (third, "Beta"),
        ):
            owner.extension.add(
                model.Extension(
                    name,
                    value_type=model.datatypes.String,
                    value="v",
                    semantic_id=make_external_reference(f"urn:{name}"),
                )
            )
        first.extension.add(model.Extension("Beta"))
        return make_submodel(elements=[first, second, third]), [
            first,
            second,
            third,
        ]

    def test_extensions_are_grouped_by_name_with_their_counts(self) -> None:
        _, owners = self._owners()

        groups = group_extensions(owners, ExtensionKey.NAME)

        assert [(g.key, g.count) for g in groups] == [("Alpha", 2), ("Beta", 2)]
        assert groups[0].label == "Alpha (2)"

    def test_extensions_are_grouped_by_semantic_id_and_blank_ones_skipped(
        self,
    ) -> None:
        _, owners = self._owners()

        groups = group_extensions(owners, ExtensionKey.SEMANTIC_ID)

        assert [(g.key, g.count) for g in groups] == [
            ("urn:Alpha", 2),
            ("urn:Beta", 1),
        ]

    def test_the_chosen_group_is_removed_in_one_step_and_comes_back(
        self,
    ) -> None:
        submodel, owners = self._owners()
        (alpha, beta) = group_extensions(owners, ExtensionKey.NAME)
        stack = CommandStack()

        with stack.group("Remove extensions"):
            for command in remove_extension_commands(
                observer_for(submodel), alpha
            ):
                stack.push(command)
        left = [[e.name for e in owner.extension] for owner in owners]
        stack.undo()
        again = [[e.name for e in owner.extension] for owner in owners]

        assert left == [["Beta"], [], ["Beta"]]
        assert again == [["Alpha", "Beta"], ["Alpha"], ["Beta"]]
        assert beta.count == 2

    def test_no_extension_gives_no_group(self) -> None:
        assert group_extensions([make_property("A")], ExtensionKey.NAME) == []

    def test_an_owner_that_is_listed_twice_counts_once(self) -> None:
        _, owners = self._owners()

        groups = group_extensions([*owners, owners[0]], ExtensionKey.NAME)

        assert [(g.key, g.count) for g in groups] == [("Alpha", 2), ("Beta", 2)]
