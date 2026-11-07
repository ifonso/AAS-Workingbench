"""F-EDT-04 criteria that the first audit found open."""
# ruff: noqa: F811

from collections.abc import Callable
from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.factories import make_external_reference
from tests.medium.conftest import ELEMENT_ID
from tests.medium.forms import Form
from tests.medium.test_element_conversion import Conversions  # noqa: F401
from tests.medium.test_element_conversion import registered  # noqa: F401

TARGET = [(model.KeyTypes.GLOBAL_REFERENCE, "urn:example:target")]


def _relationship(form: Form) -> None:
    form.fill_reference("first", TARGET)
    form.fill_reference("second", TARGET)


def _event(form: Form) -> None:
    form.fill_model_reference(
        "observed",
        [(model.KeyTypes.SUBMODEL, "urn:example:submodel")],
        model.Submodel,
    )


def _nothing(form: Form) -> None:
    del form


MINIMAL: dict[type, Callable[[Form], None]] = {
    model.Property: _nothing,
    model.MultiLanguageProperty: _nothing,
    model.Range: _nothing,
    model.File: _nothing,
    model.Blob: _nothing,
    model.ReferenceElement: _nothing,
    model.RelationshipElement: _relationship,
    model.AnnotatedRelationshipElement: _relationship,
    model.SubmodelElementCollection: _nothing,
    model.SubmodelElementList: lambda form: form.choose(
        "type_value_list_element", model.Property
    ),
    model.Entity: lambda form: form.type_text("global_asset_id", "urn:asset:1"),
    model.Operation: _nothing,
    model.Capability: _nothing,
    model.BasicEventElement: _event,
}


def _made(lab: Any, element_type: type) -> Any:
    def fill(form: Form) -> None:
        form.choose_type(element_type)
        form.type_text("id_short", ELEMENT_ID)
        MINIMAL[element_type](form)

    lab.add(fill)
    return lab.element()


def test_a_property_range_file_and_blob_start_with_the_default_of_the_table(
    lab,
) -> None:
    prop = _made(lab, model.Property)
    assert prop.value_type is datatypes.String
    assert prop.value is None


def test_a_range_starts_as_a_string_range(lab) -> None:
    element = _made(lab, model.Range)
    assert element.value_type is datatypes.String
    assert (element.min, element.max) == (None, None)


@pytest.mark.parametrize("element_type", [model.File, model.Blob])
def test_a_file_and_a_blob_start_with_no_content_type_and_no_value(
    lab, element_type: type
) -> None:
    # The table says "", which V3.1 and the SDK refuse (a content type has at
    # least one character), so the content type is missing.
    element = _made(lab, element_type)
    assert element.content_type is None
    assert element.value is None


def test_a_reference_element_starts_without_a_value(lab) -> None:
    # The SDK cannot hold a reference without a key, so the "empty reference"
    # of the original is no value at all.
    element = _made(lab, model.ReferenceElement)
    assert element.value is None


def test_a_relationship_has_the_two_references_it_was_made_with(lab) -> None:
    element = _made(lab, model.AnnotatedRelationshipElement)
    assert [k.value for k in element.first.key] == ["urn:example:target"]
    assert [k.value for k in element.second.key] == ["urn:example:target"]
    assert len(element.annotation) == 0


def test_a_list_has_the_default_of_the_sdk_for_the_order(lab) -> None:
    element = _made(lab, model.SubmodelElementList)
    assert element.type_value_list_element is model.Property
    assert element.order_relevant is True
    assert len(element.value) == 0


def test_an_event_starts_as_an_input_that_is_off(lab) -> None:
    element = _made(lab, model.BasicEventElement)
    assert element.direction is model.Direction.INPUT
    assert element.state is model.StateOfEvent.OFF


def test_an_entity_starts_as_a_self_managed_entity(lab) -> None:
    element = _made(lab, model.Entity)
    assert element.entity_type is model.EntityType.SELF_MANAGED_ENTITY


@pytest.mark.parametrize(
    "element_type",
    [
        model.MultiLanguageProperty,
        model.SubmodelElementCollection,
        model.Operation,
        model.Capability,
    ],
)
def test_the_other_types_are_made_empty_and_selected(
    lab, element_type: type
) -> None:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    element = _made(lab, element_type)

    assert isinstance(element, element_type)
    assert lab.shown.view.currentIndex().data(OBJECT_ROLE) is element
    for attribute in ("value", "input_variable", "output_variable"):
        held = getattr(element, attribute, None)
        if held is not None and not isinstance(held, str):
            assert len(held) == 0


# -- AC3 ---------------------------------------------------------------------


def test_a_property_that_becomes_a_range_keeps_its_type_and_common_attributes(
    lab_class, registered, monkeypatch: pytest.MonkeyPatch
) -> None:
    prop = model.Property(
        ELEMENT_ID,
        datatypes.Int,
        5,
        category="PARAMETER",
        description=model.MultiLanguageTextType({"en": "A pump"}),
        display_name=model.MultiLanguageNameType({"en": "Pump"}),
        semantic_id=make_external_reference("urn:example:pump"),
    )
    prop.qualifier.add(model.Qualifier("Cardinality", datatypes.String, "One"))
    prop.extension.add(
        model.Extension("Origin", value_type=datatypes.String, value="x")
    )
    lab = lab_class(prop)
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.Range)

    new = lab.element()
    assert isinstance(new, model.Range)
    assert (new.value_type, new.min, new.max) == (datatypes.Int, 5, 5)
    assert new.id_short == ELEMENT_ID
    assert new.category == "PARAMETER"
    assert dict(new.description or {}) == {"en": "A pump"}
    assert dict(new.display_name or {}) == {"en": "Pump"}
    assert [k.value for k in new.semantic_id.key] == ["urn:example:pump"]
    assert [(q.type, q.value) for q in new.qualifier] == [
        ("Cardinality", "One")
    ]
    assert [(e.name, e.value) for e in new.extension] == [("Origin", "x")]
    saved = lab.save_and_reload()
    assert '"modelType": "Range"' in saved
    assert '"valueType": "xs:int"' in saved
