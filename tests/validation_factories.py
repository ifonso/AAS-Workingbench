"""Builders for the objects that the validation tests break on purpose.

The SDK refuses most invalid objects when they are made, so a test reaches an
invalid state the way a user can: by a later edit, or through an argument that
the SDK does not check. The helpers here build the valid starting point.
"""

from collections.abc import Iterable

from basyx.aas import model
from tests.factories import make_external_reference
from tests.factories import make_shell
from tests.factories import make_store
from tests.factories import make_submodel


def store_with(
    *elements: model.SubmodelElement,
    kind: model.ModellingKind = model.ModellingKind.INSTANCE,
) -> model.SetIdentifiableStore:
    """Builds a store with one shell and one submodel that holds the elements."""
    submodel = make_submodel(elements=elements)
    submodel.kind = kind
    return make_store(make_shell(submodels=[submodel]), submodel)


def template_qualifier(type_: str = "Cardinality") -> model.Qualifier:
    """Builds a qualifier of kind TemplateQualifier."""
    return model.Qualifier(
        type_,
        model.datatypes.String,
        "One",
        kind=model.QualifierKind.TEMPLATE_QUALIFIER,
    )


def model_reference_to_submodel(id_: str) -> model.ModelReference:
    """Builds a model reference to a submodel, which may not exist."""
    return model.ModelReference(
        (model.Key(model.KeyTypes.SUBMODEL, id_),), model.Submodel
    )


def concept_with_value_list(
    id_: str, values: Iterable[tuple[str, str]]
) -> model.ConceptDescription:
    """Builds a concept description with an IEC 61360 value list.

    Args:
        id_: The id of the concept description.
        values: Pairs of the text of a coded value and the global id that
            stands for it.
    """
    pairs = {
        model.ValueReferencePair(text, make_external_reference(global_id))
        for text, global_id in values
    }
    content = model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360({"en": "Color"}),
        value_list=pairs,
    )
    return model.ConceptDescription(
        id_=id_,
        embedded_data_specifications=[
            model.EmbeddedDataSpecification(
                make_external_reference(
                    "https://admin-shell.io/DataSpecificationTemplates/"
                    "DataSpecificationIec61360/3/0"
                ),
                content,
            )
        ],
    )
