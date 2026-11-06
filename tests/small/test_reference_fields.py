"""Checks that the walk over BaSyx objects finds every reference field.

`iter_slots` has no list of fields. This test reads the constructor of every
class of the SDK, and fails when a class has a reference field that the
builders below do not populate, or that the walk does not find. After an SDK
upgrade that adds a field, the test names the class to add here.
"""

from collections.abc import Callable
from collections.abc import Iterable
import inspect
import itertools
import typing
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.domain.references import chain
from aas_editor.domain.references import iter_slots

_Built = tuple[model.Identifiable, list[model.Reference]]
_Builder = Callable[[dict[str, Any]], _Built]

_counter = itertools.count()


def _mentions(annotation: object, base: type) -> bool:
    origin = typing.get_origin(annotation)
    candidate = origin or annotation
    if isinstance(candidate, type) and issubclass(candidate, base):
        return True
    if isinstance(annotation, str):
        return base.__name__ in annotation
    return any(_mentions(arg, base) for arg in typing.get_args(annotation))


def _is_collection(annotation: object) -> bool:
    candidates = [annotation, *typing.get_args(annotation)]
    for candidate in candidates:
        origin = typing.get_origin(candidate)
        if (
            isinstance(origin, type)
            and not issubclass(origin, model.Reference)
            and issubclass(origin, Iterable)
        ):
            return True
    return False


def _new_reference(annotation: object) -> model.Reference:
    number = next(_counter)
    if _mentions(annotation, model.ModelReference):
        return model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, f"urn:test:{number}"),),
            model.Submodel,
        )
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, f"urn:test:{number}"),)
    )


def _flatten(refs: dict[str, Any]) -> list[model.Reference]:
    found: list[model.Reference] = []
    for value in refs.values():
        found.extend(value if isinstance(value, (list, set)) else [value])
    return found


def _other_reference() -> model.ExternalReference:
    return model.ExternalReference(
        (
            model.Key(
                model.KeyTypes.GLOBAL_REFERENCE, f"urn:test:{next(_counter)}"
            ),
        )
    )


def _element(element: model.SubmodelElement, refs: dict[str, Any]) -> _Built:
    return make_submodel(elements=[element]), _flatten(refs)


def _embedded(
    content: model.DataSpecificationContent, refs: dict[str, Any]
) -> _Built:
    specification = _other_reference()
    concept = model.ConceptDescription(
        id_="urn:test:concept",
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(specification, content)
        ],
    )
    return concept, [specification, *_flatten(refs)]


def _iec(**kwargs: Any) -> model.DataSpecificationIEC61360:
    return model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360({"en": "name"}),
        **kwargs,
    )


def _build_property(refs: dict[str, Any]) -> _Built:
    return _element(
        model.Property("p", value_type=model.datatypes.String, **refs), refs
    )


_BUILDERS: dict[type, _Builder] = {
    model.AssetAdministrationShell: lambda refs: (
        model.AssetAdministrationShell(
            make_asset_information(), "urn:test:shell", **refs
        ),
        _flatten(refs),
    ),
    model.Submodel: lambda refs: (
        model.Submodel("urn:test:submodel", **refs),
        _flatten(refs),
    ),
    model.ConceptDescription: lambda refs: (
        model.ConceptDescription("urn:test:concept", **refs),
        _flatten(refs),
    ),
    model.AdministrativeInformation: lambda refs: (
        model.Submodel(
            "urn:test:submodel",
            administration=model.AdministrativeInformation(**refs),
        ),
        _flatten(refs),
    ),
    model.EmbeddedDataSpecification: lambda refs: (
        model.ConceptDescription(
            "urn:test:concept",
            embedded_data_specifications=[
                model.EmbeddedDataSpecification(
                    refs["data_specification"], _iec()
                )
            ],
        ),
        _flatten(refs),
    ),
    model.DataSpecificationIEC61360: lambda refs: _embedded(_iec(**refs), refs),
    model.ValueReferencePair: lambda refs: _embedded(
        _iec(value_list={model.ValueReferencePair("v", **refs)}), refs
    ),
    model.Extension: lambda refs: (
        model.Submodel(
            "urn:test:submodel", extension=[model.Extension("e", **refs)]
        ),
        _flatten(refs),
    ),
    model.Qualifier: lambda refs: (
        make_submodel(
            elements=[
                _with_qualifier(
                    model.Qualifier("q", model.datatypes.String, **refs)
                )
            ]
        ),
        _flatten(refs),
    ),
    model.SpecificAssetId: lambda refs: (
        model.AssetAdministrationShell(
            model.AssetInformation(
                model.AssetKind.INSTANCE,
                specific_asset_id=[model.SpecificAssetId("n", "v", **refs)],
            ),
            "urn:test:shell",
        ),
        _flatten(refs),
    ),
    model.Property: _build_property,
    model.MultiLanguageProperty: lambda refs: _element(
        model.MultiLanguageProperty("m", **refs), refs
    ),
    model.Range: lambda refs: _element(
        model.Range("r", model.datatypes.Int, **refs), refs
    ),
    model.Blob: lambda refs: _element(
        model.Blob("b", "text/plain", **refs), refs
    ),
    model.File: lambda refs: _element(
        model.File("f", "text/plain", **refs), refs
    ),
    model.Capability: lambda refs: _element(
        model.Capability("c", **refs), refs
    ),
    model.Operation: lambda refs: _element(model.Operation("o", **refs), refs),
    model.Entity: lambda refs: _element(
        model.Entity("e", model.EntityType.CO_MANAGED_ENTITY, **refs), refs
    ),
    model.ReferenceElement: lambda refs: _element(
        model.ReferenceElement("e", **refs), refs
    ),
    model.RelationshipElement: lambda refs: _element(
        model.RelationshipElement("r", **refs), refs
    ),
    model.AnnotatedRelationshipElement: lambda refs: _element(
        model.AnnotatedRelationshipElement("a", **refs), refs
    ),
    model.BasicEventElement: lambda refs: _element(
        model.BasicEventElement(
            "v",
            direction=model.Direction.INPUT,
            state=model.StateOfEvent.ON,
            **refs,
        ),
        refs,
    ),
    model.SubmodelElementCollection: lambda refs: _element(
        model.SubmodelElementCollection("c", **refs), refs
    ),
    model.SubmodelElementList: lambda refs: _element(
        model.SubmodelElementList(
            "l",
            type_value_list_element=model.Property,
            value_type_list_element=model.datatypes.String,
            **refs,
        ),
        refs,
    ),
}


def _with_qualifier(qualifier: model.Qualifier) -> model.Property:
    element = make_property("q")
    element.qualifier.add(qualifier)
    return element


def _classes_with_reference_fields() -> list[type]:
    classes: list[type] = []
    for cls in vars(model).values():
        if (
            not inspect.isclass(cls)
            or not cls.__module__.startswith("basyx.aas.model")
            or issubclass(cls, model.Reference)
            or inspect.isabstract(cls)
        ):
            continue
        if _reference_parameters(cls):
            classes.append(cls)
    return sorted(classes, key=lambda cls: cls.__name__)


def _reference_parameters(cls: type) -> dict[str, object]:
    return {
        name: parameter.annotation
        for name, parameter in inspect.signature(cls).parameters.items()
        if _mentions(parameter.annotation, model.Reference)
    }


def test_every_sdk_class_with_a_reference_field_has_a_builder() -> None:
    known = {cls.__name__ for cls in _BUILDERS}

    missing = [
        cls.__name__
        for cls in _classes_with_reference_fields()
        if cls.__name__ not in known
    ]

    assert missing == [], (
        "Add a builder for these SDK classes, so that the walk over "
        f"references is checked against their new fields: {missing}"
    )


@pytest.mark.parametrize(
    "cls", _classes_with_reference_fields(), ids=lambda cls: cls.__name__
)
def test_iter_slots_finds_every_reference_field_of_the_sdk(cls: type) -> None:
    fields = _reference_parameters(cls)
    refs = {
        name: (
            [_new_reference(annotation), _new_reference(annotation)]
            if _is_collection(annotation)
            else _new_reference(annotation)
        )
        for name, annotation in fields.items()
    }
    if "supplemental_semantic_id" in refs and "semantic_id" not in refs:
        raise AssertionError("A semantic id is needed for the supplemental ids")
    refs = {
        name: (
            set(value)
            if name in {"submodel", "is_case_of", "value_list"}
            else value
        )
        for name, value in refs.items()
    }

    host, expected = _BUILDERS[cls](refs)
    found = [
        reference
        for slot in iter_slots(host)
        for reference in chain(slot.reference)
    ]

    assert {id(reference) for reference in found} == {
        id(reference) for reference in expected
    }, f"{cls.__name__} has fields that iter_slots does not find: {fields}"
    assert len(found) == len(expected)


def test_iter_slots_finds_the_referred_semantic_id_of_a_reference() -> None:
    inner = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:test:inner"),)
    )
    outer = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:test:outer"),), inner
    )
    element = make_property("p")
    element.semantic_id = outer

    slots = list(iter_slots(make_submodel(elements=[element])))

    assert [slot.reference for slot in slots] == [outer]
    assert list(chain(slots[0].reference)) == [outer, inner]
