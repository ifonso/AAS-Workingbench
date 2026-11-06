"""The conversion of a submodel element to another type, and what it loses."""

import datetime
import io
import json

from basyx.aas import model
from basyx.aas.adapter.json import write_aas_json_file
import dateutil.relativedelta
import pytest
from tests.factories import make_blob
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.domain.conversion import plan_conversion
from aas_editor.domain.conversion import refusal_for
from aas_editor.domain.conversion import targets_for
from aas_editor.domain.replacement import ConversionRefused

STRING = model.datatypes.String
INT = model.datatypes.Int


def _in_submodel(element: model.SubmodelElement) -> model.SubmodelElement:
    make_submodel(elements=[element])
    return element


def _lost(plan) -> list[str]:
    return [loss.what for loss in plan.losses]


def _decorated(element: model.SubmodelElement) -> model.SubmodelElement:
    """Gives an element every attribute that all elements share."""
    element.category = "PARAMETER"
    element.display_name = model.MultiLanguageNameType({"en": "Shown"})
    element.description = model.MultiLanguageTextType({"en": "Described"})
    element.semantic_id = make_external_reference("urn:example:semantic")
    element.supplemental_semantic_id.append(
        make_external_reference("urn:example:supplemental")
    )
    element.qualifier.add(model.Qualifier("quality", STRING, "good"))
    element.extension.add(model.Extension("extra", STRING, "data"))
    return element


def test_a_converted_element_keeps_what_all_elements_share() -> None:
    old = _in_submodel(_decorated(make_property("Temperature", value="20")))

    new = plan_conversion(old, model.Capability).preview

    assert (
        new.id_short,
        new.category,
        dict(new.display_name or {}),
        dict(new.description or {}),
        new.semantic_id,
        list(new.supplemental_semantic_id),
        [q.type for q in new.qualifier],
        [e.name for e in new.extension],
    ) == (
        "Temperature",
        "PARAMETER",
        {"en": "Shown"},
        {"en": "Described"},
        make_external_reference("urn:example:semantic"),
        [make_external_reference("urn:example:supplemental")],
        ["quality"],
        ["extra"],
    )


def test_the_copy_of_the_qualifiers_is_independent_of_the_original() -> None:
    old = _in_submodel(_decorated(make_property()))

    new = plan_conversion(old, model.Range).preview

    next(iter(new.qualifier)).value = "changed"
    assert next(iter(old.qualifier)).value == "good"


def test_planning_changes_nothing() -> None:
    old = _in_submodel(_decorated(make_collection(elements=[make_property()])))
    before = _json(old.parent)

    plan_conversion(old, model.SubmodelElementList)

    assert _json(old.parent) == before


def _json(submodel: object) -> str:
    buffer = io.StringIO()
    store = model.SetIdentifiableStore()
    store.add(submodel)  # type: ignore[arg-type]
    write_aas_json_file(buffer, store)
    return buffer.getvalue()


# Which conversions are offered


def test_every_type_but_itself_and_the_event_element_is_offered() -> None:
    old = _in_submodel(make_property())

    targets = targets_for(old)

    assert model.Property not in targets
    assert model.BasicEventElement not in targets
    assert len(targets) == 12


def test_an_event_element_can_be_converted_but_not_made() -> None:
    observed = model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, "urn:example:observed"),),
        model.Submodel,
    )
    event = _in_submodel(
        model.BasicEventElement(
            "Event",
            observed,
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
        )
    )

    assert model.Capability in targets_for(event)
    assert model.BasicEventElement not in targets_for(make_property())


def test_an_item_of_a_list_cannot_be_converted() -> None:
    item = model.Property(None, STRING, "a")
    make_submodel(elements=[make_list(elements=[item])])

    assert targets_for(item) == []
    assert "AASd-108" in (refusal_for(item) or "")
    with pytest.raises(ConversionRefused):
        plan_conversion(item, model.Range)


def test_an_element_outside_a_submodel_cannot_be_converted() -> None:
    loose = make_property()

    assert refusal_for(loose) is not None
    with pytest.raises(ConversionRefused):
        plan_conversion(loose, model.Range)


def test_an_annotation_can_only_become_another_data_element() -> None:
    annotation = model.Property("Note", STRING, "n")
    make_submodel(
        elements=[
            model.AnnotatedRelationshipElement(
                "Relation",
                make_external_reference("urn:a"),
                make_external_reference("urn:b"),
                annotation=[annotation],
            )
        ]
    )

    targets = targets_for(annotation)

    assert model.MultiLanguageProperty in targets
    assert model.SubmodelElementCollection not in targets
    assert model.Capability not in targets


def test_converting_to_a_type_that_is_not_offered_is_refused() -> None:
    old = _in_submodel(make_property())

    with pytest.raises(ConversionRefused):
        plan_conversion(old, model.BasicEventElement)


# Value elements


def test_a_property_becomes_a_range_with_its_value_as_minimum_and_maximum() -> (
    None
):
    old = _in_submodel(make_property(value=5, value_type=INT))

    plan = plan_conversion(old, model.Range)

    new = plan.preview
    assert isinstance(new, model.Range)
    assert (new.value_type, new.min, new.max) == (INT, 5, 5)
    assert plan.losses == ()


def test_a_range_becomes_a_property_with_its_minimum() -> None:
    old = _in_submodel(model.Range("Limits", INT, 3, 9))

    plan = plan_conversion(old, model.Property)

    new = plan.preview
    assert isinstance(new, model.Property)
    assert (new.value_type, new.value) == (INT, 3)
    assert [(loss.what, loss.detail) for loss in plan.losses] == [
        ("maximum", "'9'")
    ]


def test_a_range_with_equal_ends_loses_nothing() -> None:
    old = _in_submodel(model.Range("Limits", INT, 4, 4))

    assert plan_conversion(old, model.Property).losses == ()


def test_a_text_property_becomes_a_multi_language_text_in_the_given_language() -> (
    None
):
    old = _in_submodel(make_property(value="Hello"))

    plan = plan_conversion(old, model.MultiLanguageProperty, language="de")

    new = plan.preview
    assert isinstance(new, model.MultiLanguageProperty)
    assert dict(new.value or {}) == {"de": "Hello"}
    assert plan.losses == ()
    assert any("'de'" in note for note in plan.notes)


def test_a_number_loses_its_type_when_it_becomes_a_text() -> None:
    old = _in_submodel(make_property(value=42, value_type=INT))

    plan = plan_conversion(old, model.MultiLanguageProperty)

    assert _lost(plan) == ["value type"]
    assert "xs:int" in plan.losses[0].detail


def test_a_multi_language_text_names_the_texts_and_languages_it_drops() -> None:
    old = _in_submodel(
        make_multi_language_property(texts={"de": "Hallo", "en": "Hello"})
    )

    plan = plan_conversion(old, model.Property)

    new = plan.preview
    assert isinstance(new, model.Property)
    assert (new.value_type, new.value) == (STRING, "Hello")
    assert _lost(plan) == ["language of the text", "texts in other languages"]
    assert "Hallo" in plan.losses[1].detail


def test_a_file_becomes_a_blob_holding_its_path_when_no_content_is_given() -> (
    None
):
    old = _in_submodel(make_file_element(value="/aasx/files/a.pdf"))

    plan = plan_conversion(old, model.Blob)

    new = plan.preview
    assert isinstance(new, model.Blob)
    assert (new.value, new.content_type) == (
        b"/aasx/files/a.pdf",
        "application/pdf",
    )
    assert plan.losses == ()


def test_a_file_becomes_a_blob_holding_the_content_of_the_file() -> None:
    old = _in_submodel(make_file_element(value="/aasx/files/a.pdf"))

    plan = plan_conversion(old, model.Blob, file_content=b"%PDF content")

    new = plan.preview
    assert isinstance(new, model.Blob)
    assert new.value == b"%PDF content"
    assert _lost(plan) == ["path"]


def test_a_text_blob_becomes_a_property_and_keeps_its_line_breaks() -> None:
    old = _in_submodel(
        make_blob(value=b"one\r\ntwo", content_type="text/plain")
    )

    plan = plan_conversion(old, model.Property)

    new = plan.preview
    assert isinstance(new, model.Property)
    assert new.value == "one\r\ntwo"
    assert _lost(plan) == ["content type"]


def test_binary_bytes_cannot_become_text_and_are_listed_as_lost() -> None:
    old = _in_submodel(make_blob(value=b"\x00\x01\x02"))

    plan = plan_conversion(old, model.MultiLanguageProperty)

    assert "content" in _lost(plan)
    assert plan.preview.value is None  # type: ignore[attr-defined]


def test_bytes_are_no_path_when_a_blob_becomes_a_file() -> None:
    old = _in_submodel(make_blob(value=b"text", content_type="text/plain"))

    plan = plan_conversion(old, model.File)

    new = plan.preview
    assert isinstance(new, model.File)
    assert (new.value, new.content_type) == (None, "text/plain")
    assert _lost(plan) == ["content"]


def test_a_property_becomes_a_file_with_the_value_as_path() -> None:
    old = _in_submodel(make_property(value="/aasx/files/sheet.pdf"))

    plan = plan_conversion(old, model.File)

    new = plan.preview
    assert isinstance(new, model.File)
    assert (new.value, new.content_type) == (
        "/aasx/files/sheet.pdf",
        "application/pdf",
    )


# Reference elements


def _relationship(cls: type[model.RelationshipElement], **kwargs: object):
    return _in_submodel(
        cls(
            "Link",
            make_external_reference("urn:first"),
            make_external_reference("urn:second"),
            **kwargs,  # type: ignore[arg-type]
        )
    )


def test_a_relationship_becomes_an_annotated_one_and_keeps_both_ends() -> None:
    old = _relationship(model.RelationshipElement)

    plan = plan_conversion(old, model.AnnotatedRelationshipElement)

    new = plan.preview
    assert isinstance(new, model.AnnotatedRelationshipElement)
    assert (new.first, new.second) == (old.first, old.second)
    assert plan.losses == ()


def test_a_relationship_that_becomes_a_reference_names_the_second_end() -> None:
    old = _relationship(model.RelationshipElement)

    plan = plan_conversion(old, model.ReferenceElement)

    new = plan.preview
    assert isinstance(new, model.ReferenceElement)
    assert new.value == old.first
    assert _lost(plan) == ["second reference"]
    assert "urn:second" in plan.losses[0].detail


def test_an_annotated_relationship_names_the_annotations_it_drops() -> None:
    old = _relationship(
        model.AnnotatedRelationshipElement,
        annotation=[model.Property("Note", STRING, "n")],
    )

    plan = plan_conversion(old, model.RelationshipElement)

    assert _lost(plan) == ["annotations"]
    assert "Note" in plan.losses[0].detail
    assert plan.child_keys == {"Note": None}


def test_a_reference_element_becomes_a_relationship_with_a_first_end() -> None:
    old = _in_submodel(
        model.ReferenceElement("Ref", make_external_reference("urn:target"))
    )

    plan = plan_conversion(old, model.RelationshipElement)

    new = plan.preview
    assert isinstance(new, model.RelationshipElement)
    assert (new.first, new.second) == (old.value, None)
    assert plan.losses == ()


# Containers


def test_a_collection_becomes_a_list_that_keeps_the_items_that_fit() -> None:
    old = _in_submodel(
        make_collection(
            elements=[
                make_property("A", "1"),
                make_property("B", "2"),
                make_file_element("C"),
            ]
        )
    )

    plan = plan_conversion(old, model.SubmodelElementList)

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert new.type_value_list_element is model.Property
    assert [item.value for item in new.value] == ["1", "2"]  # type: ignore[attr-defined]
    assert _lost(plan) == ["item not kept", "idShorts of the items"]
    assert "C (File)" in plan.losses[0].detail
    assert plan.child_keys == {"A": "0", "B": "1", "C": None}


def test_a_list_that_keeps_every_item_still_loses_their_idshorts() -> None:
    old = _in_submodel(
        make_collection(elements=[make_property("A"), make_property("B")])
    )

    plan = plan_conversion(old, model.SubmodelElementList)

    assert _lost(plan) == ["idShorts of the items"]
    assert plan.losses[0].detail.startswith("A, B")
    assert plan.child_keys == {"A": "0", "B": "1"}


def test_an_empty_collection_becomes_a_list_of_text_properties() -> None:
    old = _in_submodel(make_collection())

    plan = plan_conversion(old, model.SubmodelElementList)

    new = plan.preview
    assert isinstance(new, model.SubmodelElementList)
    assert (new.type_value_list_element, new.value_type_list_element) == (
        model.Property,
        STRING,
    )
    assert plan.losses == ()


def test_a_list_becomes_a_collection_and_names_its_items() -> None:
    old = _in_submodel(
        make_list(
            elements=[model.Property(None, STRING, "a"), make_property(None)]  # type: ignore[arg-type]
        )
    )

    plan = plan_conversion(old, model.SubmodelElementCollection)

    new = plan.preview
    assert isinstance(new, model.SubmodelElementCollection)
    assert [item.id_short for item in new.value] == ["Item_0", "Item_1"]
    assert plan.child_keys == {"0": "Item_0", "1": "Item_1"}
    assert plan.losses == ()


def test_a_list_names_what_a_collection_cannot_keep() -> None:
    reference = make_external_reference("urn:example:items")
    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        [],
        semantic_id_list_element=reference,
        value_type_list_element=STRING,
        order_relevant=False,
    )
    old = _in_submodel(item_list)

    plan = plan_conversion(old, model.SubmodelElementCollection)

    assert _lost(plan) == ["semantic id of the items", "order is relevant"]


def test_an_operation_keeps_every_variable_when_it_becomes_a_collection() -> (
    None
):
    old = _in_submodel(
        make_operation(
            input_variables=[make_property("In")],
            output_variables=[make_property("Out")],
            in_output_variables=[make_property("Both")],
        )
    )

    plan = plan_conversion(old, model.SubmodelElementCollection)

    new = plan.preview
    assert isinstance(new, model.SubmodelElementCollection)
    assert [item.id_short for item in new.value] == ["In", "Out", "Both"]
    assert _lost(plan) == ["direction of the variables"]
    assert "Out: output" in plan.losses[0].detail


def test_a_collection_becomes_an_operation_with_input_variables() -> None:
    old = _in_submodel(make_collection(elements=[make_property("A")]))

    plan = plan_conversion(old, model.Operation)

    new = plan.preview
    assert isinstance(new, model.Operation)
    assert [item.id_short for item in new.input_variable] == ["A"]
    assert plan.losses == ()


def test_a_self_managed_entity_names_its_asset_when_it_becomes_a_collection() -> (
    None
):
    old = _in_submodel(make_entity(statements=[make_property("S")]))

    plan = plan_conversion(old, model.SubmodelElementCollection)

    assert [item.id_short for item in plan.preview.value] == ["S"]  # type: ignore[attr-defined]
    assert _lost(plan) == ["entity type", "global asset id"]


def test_a_collection_becomes_a_co_managed_entity_with_statements() -> None:
    old = _in_submodel(make_collection(elements=[make_property("A")]))

    plan = plan_conversion(old, model.Entity)

    new = plan.preview
    assert isinstance(new, model.Entity)
    assert new.entity_type == model.EntityType.CO_MANAGED_ENTITY
    assert [item.id_short for item in new.statement] == ["A"]
    assert plan.losses == ()


# Everything else


def test_a_container_that_becomes_a_property_lists_all_its_items() -> None:
    old = _in_submodel(
        make_collection(elements=[make_property("A"), make_property("B")])
    )

    plan = plan_conversion(old, model.Property)

    assert _lost(plan) == ["items"]
    assert plan.losses[0].detail == "A, B"
    assert plan.child_keys == {"A": None, "B": None}


def test_a_capability_becomes_anything_without_a_loss() -> None:
    old = _in_submodel(_decorated(model.Capability("Skill")))

    for target in (model.Property, model.SubmodelElementList, model.Entity):
        assert plan_conversion(old, target).losses == ()


def test_an_event_element_lists_everything_that_is_its_own() -> None:
    observed = model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, "urn:example:observed"),),
        model.Submodel,
    )
    old = _in_submodel(
        model.BasicEventElement(
            "Event",
            observed,
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
            message_topic="topic/one",
            last_update=datetime.datetime(
                2024, 1, 2, 3, 4, 5, tzinfo=datetime.UTC
            ),
            min_interval=dateutil.relativedelta.relativedelta(seconds=5),
        )
    )

    plan = plan_conversion(old, model.Capability)

    assert _lost(plan) == [
        "observed",
        "direction",
        "state",
        "message topic",
        "last update",
        "minimum interval",
    ]


# Nothing is lost without a word


def _populated(
    element_type: type[model.SubmodelElement],
) -> model.SubmodelElement:
    """Makes an element in which every attribute holds a distinct marker."""
    first = make_external_reference("urn:marker:first")
    second = make_external_reference("urn:marker:second")
    child = model.Property("MarkerChild", STRING, "marker-child-value")
    other = model.Property("MarkerOther", STRING, "marker-other-value")
    makers = {
        model.Property: lambda: model.Property(
            "Subject",
            STRING,
            "marker-value",
            value_id=make_external_reference("urn:marker:value-id"),
        ),
        model.Range: lambda: model.Range(
            "Subject", STRING, "marker-minimum", "marker-maximum"
        ),
        model.MultiLanguageProperty: lambda: model.MultiLanguageProperty(
            "Subject",
            model.MultiLanguageTextType(
                {"en": "marker-english", "de": "marker-german"}
            ),
            value_id=make_external_reference("urn:marker:value-id"),
        ),
        model.File: lambda: model.File(
            "Subject", "text/marker-type", "/aasx/files/marker-path.txt"
        ),
        model.Blob: lambda: model.Blob(
            "Subject", "text/marker-type", b"marker-bytes"
        ),
        model.ReferenceElement: lambda: model.ReferenceElement(
            "Subject", first
        ),
        model.RelationshipElement: lambda: model.RelationshipElement(
            "Subject", first, second
        ),
        model.AnnotatedRelationshipElement: lambda: (
            model.AnnotatedRelationshipElement(
                "Subject", first, second, annotation=[child]
            )
        ),
        model.SubmodelElementCollection: lambda: make_collection(
            "Subject", [child, other]
        ),
        model.SubmodelElementList: lambda: model.SubmodelElementList(
            "Subject",
            model.Property,
            [child, other],
            semantic_id_list_element=first,
            value_type_list_element=STRING,
            order_relevant=False,
        ),
        model.Entity: lambda: model.Entity(
            "Subject",
            model.EntityType.SELF_MANAGED_ENTITY,
            [child],
            global_asset_id="urn:marker:asset",
        ),
        model.Operation: lambda: model.Operation("Subject", [child], [other]),
        model.Capability: lambda: model.Capability("Subject"),
        model.BasicEventElement: lambda: model.BasicEventElement(
            "Subject",
            model.ModelReference(
                (model.Key(model.KeyTypes.SUBMODEL, "urn:marker:observed"),),
                model.Submodel,
            ),
            model.Direction.OUTPUT,
            model.StateOfEvent.ON,
            message_topic="marker/topic",
        ),
    }
    return _decorated(makers[element_type]())


_SOURCES = [
    model.Property,
    model.Range,
    model.MultiLanguageProperty,
    model.File,
    model.Blob,
    model.ReferenceElement,
    model.RelationshipElement,
    model.AnnotatedRelationshipElement,
    model.SubmodelElementCollection,
    model.SubmodelElementList,
    model.Entity,
    model.Operation,
    model.Capability,
    model.BasicEventElement,
]
_MARKERS = (
    "marker-value",
    "marker-minimum",
    "marker-maximum",
    "marker-english",
    "marker-german",
    "marker-path",
    "marker-bytes",
    "urn:marker:first",
    "urn:marker:second",
    "urn:marker:value-id",
    "urn:marker:asset",
    "urn:marker:observed",
    "marker/topic",
    "MarkerChild",
    "MarkerOther",
)


@pytest.mark.parametrize("source", _SOURCES, ids=lambda cls: cls.__name__)
def test_nothing_is_lost_that_the_plan_did_not_name(
    source: type[model.SubmodelElement],
) -> None:
    for target in targets_for(_in_submodel(_populated(source))):
        old = _in_submodel(_populated(source))
        plan = plan_conversion(old, target)

        kept = _visible(make_submodel(elements=[plan.build()]))
        said = " ".join(str(loss) for loss in plan.losses)
        silent = [
            marker
            for marker in _MARKERS
            if marker in _visible(old.parent) and marker not in kept + said
        ]
        assert silent == [], f"{source.__name__} -> {target.__name__}"


def _visible(submodel: model.Submodel) -> str:
    """Returns the serialized submodel, with the bytes of Blobs as text."""
    blobs = [
        element.value.decode()
        for element in submodel.submodel_element
        if isinstance(element, model.Blob) and element.value
    ]
    return " ".join([_json(submodel), *blobs])


def test_the_json_of_a_converted_element_is_valid_to_read_again() -> None:
    old = _in_submodel(make_collection(elements=[make_property("A")]))

    document = json.loads(
        _json(
            make_submodel(elements=[plan_conversion(old, model.Entity).build()])
        )
    )

    assert document["submodels"][0]["submodelElements"][0]["entityType"] == (
        "CoManagedEntity"
    )
