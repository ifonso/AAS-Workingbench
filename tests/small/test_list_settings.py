"""What a list fixes, and rebuilding a list with other settings."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_submodel

from aas_editor.domain.list_settings import ListSettings
from aas_editor.domain.list_settings import derive_settings
from aas_editor.domain.list_settings import detect_settings
from aas_editor.domain.list_settings import plan_list_rebuild
from aas_editor.domain.list_settings import settings_of
from aas_editor.domain.replacement import ConversionRefused

STRING = model.datatypes.String
INT = model.datatypes.Int
FIRST = make_external_reference("urn:example:first")
SECOND = make_external_reference("urn:example:second")


def _list(
    items: list[model.SubmodelElement],
    semantic_id: model.Reference | None = None,
    order_relevant: bool = True,
) -> "model.SubmodelElementList[model.Property]":
    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        items,  # type: ignore[arg-type]
        semantic_id_list_element=semantic_id,
        value_type_list_element=STRING,
        order_relevant=order_relevant,
    )
    make_submodel(elements=[item_list])
    return item_list


def _property(value: str, semantic_id: model.Reference | None = None):
    return model.Property(None, STRING, value, semantic_id=semantic_id)


def test_the_settings_of_a_list_are_read_from_it() -> None:
    item_list = _list([], FIRST, order_relevant=False)

    assert settings_of(item_list) == ListSettings(
        model.Property, STRING, FIRST, False
    )


def test_the_most_common_type_decides_the_settings_of_a_new_list() -> None:
    items: list[model.SubmodelElement] = [
        model.Property("A", INT, 1),
        make_file_element("B"),
        model.Property("C", INT, 2),
        model.Property("D", STRING, "x"),
    ]

    settings = derive_settings(items)

    assert (settings.element_type, settings.value_type) == (
        model.Property,
        INT,
    )


def test_a_tie_between_types_goes_to_the_first() -> None:
    items: list[model.SubmodelElement] = [
        make_file_element("A"),
        model.Property("B", STRING, "x"),
    ]

    assert derive_settings(items).element_type is model.File


def test_the_most_common_semantic_id_is_taken_from_the_items() -> None:
    items: list[model.SubmodelElement] = [
        model.Property("A", STRING, "1", semantic_id=SECOND),
        model.Property("B", STRING, "2", semantic_id=FIRST),
        model.Property("C", STRING, "3", semantic_id=FIRST),
    ]

    assert derive_settings(items).semantic_id == FIRST


def test_no_items_give_text_properties() -> None:
    assert derive_settings([]) == ListSettings(
        model.Property, STRING, None, True
    )


def test_detecting_finds_the_semantic_id_the_items_share() -> None:
    item_list = _list([_property("a", FIRST), _property("b")])

    detected = detect_settings(item_list)

    assert detected == ListSettings(model.Property, STRING, FIRST, True)


def test_detecting_has_nothing_to_go_by_without_items() -> None:
    assert detect_settings(_list([])) is None


def test_rebuilding_with_the_same_settings_is_refused() -> None:
    item_list = _list([_property("a")])

    with pytest.raises(ConversionRefused):
        plan_list_rebuild(item_list, settings_of(item_list))


def test_a_new_order_flag_keeps_every_item() -> None:
    item_list = _list([_property("a"), _property("b")])

    plan = plan_list_rebuild(
        item_list, ListSettings(model.Property, STRING, None, False)
    )

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert new.order_relevant is False
    assert [item.value for item in new.value] == ["a", "b"]  # type: ignore[attr-defined]
    assert plan.losses == ()
    assert plan.child_keys == {}


def test_a_new_value_type_converts_the_items_that_fit() -> None:
    item_list = _list([_property("12"), _property("abc"), _property("7")])

    plan = plan_list_rebuild(
        item_list, ListSettings(model.Property, INT, None, True)
    )

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert [item.value for item in new.value] == [12, 7]  # type: ignore[attr-defined]
    assert [loss.what for loss in plan.losses] == ["item not kept"]
    assert "abc" in plan.losses[0].detail or "xs:int" in plan.losses[0].detail
    assert plan.child_keys == {"1": None, "2": "1"}


def test_a_semantic_id_drops_the_items_that_have_another() -> None:
    item_list = _list([_property("a", FIRST), _property("b")], FIRST)

    plan = plan_list_rebuild(
        item_list, ListSettings(model.Property, STRING, SECOND, True)
    )

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert [item.value for item in new.value] == ["b"]  # type: ignore[attr-defined]
    assert "AASd-107" in plan.losses[0].detail
    assert plan.child_keys == {"0": None, "1": "0"}


def test_another_item_type_drops_all_the_items() -> None:
    item_list = _list([_property("a"), _property("b")])

    plan = plan_list_rebuild(
        item_list, ListSettings(model.File, None, None, True)
    )

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert len(new.value) == 0
    assert len(plan.losses) == 2
    assert plan.child_keys == {"0": None, "1": None}
    assert "AASd-108" in plan.losses[0].detail


def test_planning_leaves_the_list_as_it_was() -> None:
    item_list = _list([_property("a"), _property("b")])

    plan_list_rebuild(item_list, ListSettings(model.File, None, None, False))

    assert settings_of(item_list) == ListSettings(
        model.Property, STRING, None, True
    )
    assert len(item_list.value) == 2


def test_a_list_that_is_an_item_of_a_list_stays_unnamed() -> None:
    inner = model.SubmodelElementList(
        None, model.Property, value_type_list_element=STRING
    )
    outer = model.SubmodelElementList(
        "Outer", model.SubmodelElementList, [inner]
    )
    make_submodel(elements=[outer])

    plan = plan_list_rebuild(
        inner, ListSettings(model.Property, STRING, None, False)
    )

    assert plan.preview.id_short is None
