"""Builders for BaSyx objects used across the test suite.

The helpers create real BaSyx objects and import no Qt, so small tests can use
them. Every helper has defaults that give a valid object, so a test names only
the values that matter to the behavior under test.
"""

from collections.abc import Iterable
from collections.abc import Mapping
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pyecma376_2

from aas_editor.domain.ordered_store import OrderedIdentifiableStore

DEFAULT_SHELL_ID = "urn:uuid:00000000-0000-4000-8000-000000000001"
DEFAULT_SUBMODEL_ID = "urn:uuid:00000000-0000-4000-8000-000000000002"
DEFAULT_ASSET_ID = "urn:uuid:00000000-0000-4000-8000-000000000003"
DEFAULT_CONCEPT_ID = "urn:uuid:00000000-0000-4000-8000-000000000004"


def make_asset_information(
    global_asset_id: str | None = DEFAULT_ASSET_ID,
    asset_kind: model.AssetKind = model.AssetKind.INSTANCE,
    default_thumbnail: model.Resource | None = None,
) -> model.AssetInformation:
    """Builds the AssetInformation that every valid shell needs."""
    return model.AssetInformation(
        asset_kind=asset_kind,
        global_asset_id=global_asset_id,
        default_thumbnail=default_thumbnail,
    )


def make_shell(
    id_: str = DEFAULT_SHELL_ID,
    id_short: str | None = "Shell",
    submodels: Iterable[model.Submodel] = (),
    asset_information: model.AssetInformation | None = None,
) -> model.AssetAdministrationShell:
    """Builds a shell that references the given submodels."""
    if asset_information is None:
        asset_information = make_asset_information()
    return model.AssetAdministrationShell(
        asset_information=asset_information,
        id_=id_,
        id_short=id_short,
        submodel={make_reference_to(submodel) for submodel in submodels},
    )


def make_submodel(
    id_: str = DEFAULT_SUBMODEL_ID,
    id_short: str | None = "Submodel",
    elements: Iterable[model.SubmodelElement] = (),
) -> model.Submodel:
    """Builds a submodel that holds the given elements."""
    return model.Submodel(id_=id_, id_short=id_short, submodel_element=elements)


def make_property(
    id_short: str = "Property",
    value: model.datatypes.AnyXSDType | None = "text",
    value_type: type[model.datatypes.AnyXSDType] = model.datatypes.String,
) -> model.Property:
    """Builds a property. The default is a string property."""
    return model.Property(id_short=id_short, value_type=value_type, value=value)


def make_multi_language_property(
    id_short: str = "MultiLanguageProperty",
    texts: Mapping[str, str] | None = None,
) -> model.MultiLanguageProperty:
    """Builds a multi-language property from a language to text mapping."""
    if texts is None:
        texts = {"en": "text"}
    return model.MultiLanguageProperty(
        id_short=id_short, value=model.MultiLanguageTextType(dict(texts))
    )


def make_file_element(
    id_short: str = "File",
    value: str | None = "/aasx/files/document.pdf",
    content_type: str = "application/pdf",
) -> model.File:
    """Builds a File element. `value` is the path inside the package."""
    return model.File(id_short=id_short, content_type=content_type, value=value)


def make_blob(
    id_short: str = "Blob",
    value: bytes | None = b"\x00\x01binary",
    content_type: str = "application/octet-stream",
) -> model.Blob:
    """Builds a Blob element."""
    return model.Blob(id_short=id_short, content_type=content_type, value=value)


def make_collection(
    id_short: str = "Collection",
    elements: Iterable[model.SubmodelElement] = (),
) -> model.SubmodelElementCollection:
    """Builds a SubmodelElementCollection."""
    return model.SubmodelElementCollection(id_short=id_short, value=elements)


def make_list(
    id_short: str = "List",
    elements: Iterable[model.SubmodelElement] = (),
    type_value_list_element: type[model.SubmodelElement] = model.Property,
    value_type_list_element: type[model.datatypes.AnyXSDType]
    | None = model.datatypes.String,
) -> model.SubmodelElementList:
    """Builds a SubmodelElementList of properties by default."""
    return model.SubmodelElementList(
        id_short=id_short,
        type_value_list_element=type_value_list_element,
        value_type_list_element=value_type_list_element,
        value=elements,
    )


def make_concept_description(
    id_: str = DEFAULT_CONCEPT_ID, id_short: str | None = "Concept"
) -> model.ConceptDescription:
    """Builds a concept description without data specifications."""
    return model.ConceptDescription(id_=id_, id_short=id_short)


def make_reference_to(
    referable: model.Referable,
) -> model.ModelReference:
    """Builds a model reference to an object, as saving a shell would."""
    return model.ModelReference.from_referable(referable)


def make_external_reference(value: str) -> model.ExternalReference:
    """Builds a reference to a global object, such as a semantic id."""
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),)
    )


def make_store(
    *objects: model.Identifiable,
) -> model.SetIdentifiableStore:
    """Builds an object store that holds the given identifiables, in order."""
    store: model.SetIdentifiableStore = OrderedIdentifiableStore()
    for obj in objects:
        store.add(obj)
    return store


SAMM_V2 = "urn:samm:org.eclipse.esmf.samm"


def samm_type_urn(type_name: str, version: str = "2.1.0") -> str:
    """Returns the URN of a SAMM element type, such as `Aspect` or `Trait`."""
    meta_model = {"Aspect", "Property", "Entity", "Unit", "Characteristic"}
    space = "meta-model" if type_name in meta_model else "characteristic"
    prefix = (
        "urn:bamm:io.openmanufacturing" if version.startswith("1.") else SAMM_V2
    )
    return f"{prefix}:{space}:{version}#{type_name}"


def make_samm_concept(
    id_: str,
    type_name: str = "Property",
    value: str | None = None,
    id_short: str | None = None,
    version: str = "2.1.0",
) -> model.ConceptDescription:
    """Builds a concept description with a SAMM element in an extension.

    Package Explorer stores the element as JSON in an extension whose semantic
    id is the URN of its type. `value` is that JSON text.
    """
    extension = model.Extension(
        f"samm-{type_name.lower()}",
        value_type=model.datatypes.String,
        value=value,
        semantic_id=make_external_reference(samm_type_urn(type_name, version)),
    )
    return model.ConceptDescription(
        id_, id_short=id_short or type_name, extension=[extension]
    )


def make_valid_environment() -> model.SetIdentifiableStore:
    """Builds a small, valid environment of one shell with one submodel."""
    submodel = make_submodel(
        elements=[
            make_property("Name", "pump"),
            make_property("Count", 3, model.datatypes.Int),
        ]
    )
    concept = make_concept_description()
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            make_external_reference(
                "https://admin-shell.io/DataSpecificationTemplates/"
                "DataSpecificationIEC61360/3/1"
            ),
            model.DataSpecificationIEC61360(
                model.PreferredNameTypeIEC61360({"en": "Concept"})
            ),
        )
    )
    return make_store(
        make_shell(submodels=[submodel]),
        submodel,
        concept,
    )


def write_aasx(
    path: Path,
    objects: model.SetIdentifiableStore,
    files: Mapping[str, tuple[bytes, str]] | None = None,
    thumbnail: tuple[str, bytes, str] | None = None,
    core_properties: pyecma376_2.OPCCoreProperties | None = None,
) -> Path:
    """Writes an AASX package through the BaSyx writer.

    Args:
        path: Where to write the package.
        objects: The shells, submodels and concept descriptions to store.
        files: Supplementary files as a mapping from the part name to the
            content and the content type. A File element must reference a part
            name here for the writer to include it.
        thumbnail: The part name, content and content type of a package
            thumbnail, or None for no thumbnail.
        core_properties: The OPC core properties of the package, or None.

    Returns:
        The path that was written.
    """
    file_store = DictSupplementaryFileContainer()
    for name, (content, content_type) in (files or {}).items():
        file_store.add_file(name, io.BytesIO(content), content_type)
    with AASXWriter(path.as_posix(), failsafe=False) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", objects, file_store, write_json=False
        )
        if thumbnail is not None:
            name, content, content_type = thumbnail
            writer.write_thumbnail(name, bytearray(content), content_type)
        if core_properties is not None:
            writer.write_core_properties(core_properties)
    return path


def make_entity(
    id_short: str = "Entity",
    statements: Iterable[model.SubmodelElement] = (),
) -> model.Entity:
    """Builds a self-managed entity that holds the given statements."""
    return model.Entity(
        id_short=id_short,
        entity_type=model.EntityType.SELF_MANAGED_ENTITY,
        global_asset_id=DEFAULT_ASSET_ID,
        statement=statements,
    )


def make_operation(
    id_short: str = "Operation",
    input_variables: Iterable[model.SubmodelElement] = (),
    output_variables: Iterable[model.SubmodelElement] = (),
    in_output_variables: Iterable[model.SubmodelElement] = (),
) -> model.Operation:
    """Builds an operation with the given variables."""
    return model.Operation(
        id_short=id_short,
        input_variable=input_variables,
        output_variable=output_variables,
        in_output_variable=in_output_variables,
    )


def make_annotated_relationship(
    id_short: str = "Relationship",
    annotations: Iterable[model.DataElement] = (),
) -> model.AnnotatedRelationshipElement:
    """Builds an annotated relationship between two global references."""
    return model.AnnotatedRelationshipElement(
        id_short=id_short,
        first=make_external_reference("urn:example:first"),
        second=make_external_reference("urn:example:second"),
        annotation=annotations,
    )
