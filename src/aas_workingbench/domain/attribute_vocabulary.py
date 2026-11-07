"""The names of the attributes of AAS objects, as the metamodel says them.

The tabs read the attributes of BaSyx objects. The SDK spells them in Python
(`display_name`, `value_type`), and a person who knows the AAS but no Python
looks for `displayName` and `valueType`. This module is the data that tells
the two apart: for each attribute of each class, the name of the metamodel,
the name of its type, and a short description.

The names and types follow "Details of the Asset Administration Shell, Part 1:
The exchange of information between partners in the value chain of Industrie
4.0" (IDTA-01001), version 3.1.2. The descriptions are shortened from the
explanation column of its attribute tables, not quoted. Three groups have no
definition there, so their descriptions are short statements of what the
attribute holds, and `in_metamodel` is False for the attributes that the
metamodel does not have:

* The IEC 61360 data specification content. It is defined by IDTA-01003-a.
* The classes of the editor: `Package`, `StoredFile`, and `DictItem`.
* The attributes that only the SDK has, such as the type of a ModelReference
  and the position of an item in a list.

The vocabulary is keyed by the name of a class and looked up along the base
classes of the object, so `Referable` names `idShort` once for every element.
The lookup does not change what the editor does: it edits the attribute of the
SDK, and the name here is only what is shown.

Example:
    >>> from basyx.aas import model
    >>> info = attribute_info(model.Property, "display_name")
    >>> info.name, info.type_name
    ('displayName', 'MultiLanguageNameType')
"""

from dataclasses import dataclass
import functools

LIST_OF = "list of "
VALUE_DATA_TYPE = "ValueDataType"
"""The type of a value that follows the value type of its owner."""
DATA_TYPE_DEF_XSD = "DataTypeDefXsd"
"""The type of the attribute that names the value type of its owner."""

_STRING = "xs:string"
_REFERENCE = "Reference"
_LANG_NAME = "MultiLanguageNameType"
_LANG_TEXT = "MultiLanguageTextType"


@dataclass(frozen=True)
class AttributeInfo:
    """What the vocabulary knows about one attribute of one class.

    Attributes:
        sdk_name: The name of the attribute in the SDK, such as `id_short`.
        name: The name in the metamodel, such as `idShort`.
        type_name: The type of the attribute as the AAS names it: a class,
            `xs:string`, `list of Qualifier`, or `ValueDataType` for a value
            that follows the value type of its owner.
        description: One or two sentences about the attribute.
        in_metamodel: False when Part 1 does not define the attribute.
    """

    sdk_name: str
    name: str
    type_name: str
    description: str
    in_metamodel: bool = True

    @property
    def is_list(self) -> bool:
        """Tells whether the attribute holds a list of values."""
        return self.type_name.startswith(LIST_OF)


def _a(
    sdk_name: str,
    name: str,
    type_name: str,
    description: str,
    *,
    in_metamodel: bool = True,
) -> AttributeInfo:
    return AttributeInfo(sdk_name, name, type_name, description, in_metamodel)


def _same(
    sdk_name: str,
    type_name: str,
    description: str,
    *,
    in_metamodel: bool = False,
) -> AttributeInfo:
    """An attribute of the editor, which has one name in both worlds."""
    return AttributeInfo(
        sdk_name, sdk_name, type_name, description, in_metamodel
    )


_SEMANTIC_ID = _a(
    "semantic_id",
    "semanticId",
    _REFERENCE,
    "Identifier of the semantic definition of the element, also called its "
    "main semantic id.",
)
_SUPPLEMENTAL = _a(
    "supplemental_semantic_id",
    "supplementalSemanticId",
    LIST_OF + _REFERENCE,
    "Identifiers of further semantic definitions of the element.",
)
_VALUE_ID = _a(
    "value_id",
    "valueId",
    _REFERENCE,
    "Reference to the globally unique id of a coded value.",
)
_VALUE_TYPE = _a(
    "value_type",
    "valueType",
    DATA_TYPE_DEF_XSD,
    "The XSD data type of the value.",
)
_CONTENT_TYPE = _a(
    "content_type",
    "contentType",
    _STRING,
    "The content type (MIME type) of the content, such as application/pdf.",
)
_PATH = _a(
    "path",
    "path",
    _STRING,
    "Path and name of the file, with its extension. It can be absolute or "
    "relative.",
)

# Keyed by the name of the class that declares the attribute. The classes of
# the SDK are keyed by their own names, which the metamodel uses as well.
_ATTRIBUTES: dict[str, tuple[AttributeInfo, ...]] = {
    # --- Common attributes (Part 1, "Common" and "Core") ---
    "Referable": (
        _a(
            "id_short",
            "idShort",
            _STRING,
            "Short name of the element. For an element that is not "
            "identifiable, it identifies the element within its parent.",
        ),
        _a(
            "category",
            "category",
            _STRING,
            "Further meta information about the class of the element. "
            "Deprecated in V3.",
        ),
        _a(
            "display_name",
            "displayName",
            _LANG_NAME,
            "Name for display, which can be given in several languages.",
        ),
        _a(
            "description",
            "description",
            _LANG_TEXT,
            "Description or comments on the element, which can be given in "
            "several languages.",
        ),
    ),
    "HasExtension": (
        _a(
            "extension",
            "extension",
            LIST_OF + "Extension",
            "Extensions of the element, which add information that the "
            "metamodel has no attribute for.",
        ),
    ),
    "Identifiable": (
        _a(
            "id",
            "id",
            _STRING,
            "The globally unique identification of the element.",
        ),
        _a(
            "administration",
            "administration",
            "AdministrativeInformation",
            "Administrative information of the element, such as its version.",
        ),
    ),
    "HasSemantics": (_SEMANTIC_ID, _SUPPLEMENTAL),
    "Qualifiable": (
        _a(
            "qualifier",
            "qualifier",
            LIST_OF + "Qualifier",
            "Additional qualifications of the element.",
        ),
    ),
    "HasDataSpecification": (
        _a(
            "embedded_data_specifications",
            "embeddedDataSpecifications",
            LIST_OF + "EmbeddedDataSpecification",
            "Data specification templates, with their content, that the "
            "element uses.",
        ),
    ),
    "HasKind": (
        _a(
            "kind",
            "kind",
            "ModellingKind",
            "Whether the element is a template or an instance. Instance if "
            "not given.",
        ),
    ),
    "AdministrativeInformation": (
        _a(
            "version",
            "version",
            _STRING,
            "Version of the element. A revision needs a version.",
        ),
        _a("revision", "revision", _STRING, "Revision of the element."),
        _a(
            "creator",
            "creator",
            _REFERENCE,
            "The subject that is responsible for making the element.",
        ),
        _a(
            "template_id",
            "templateId",
            _STRING,
            "Identifier of the template that guided the creation of the "
            "element.",
        ),
    ),
    "Extension": (
        _a("name", "name", _STRING, "Name of the extension."),
        _a(
            "value_type",
            "valueType",
            DATA_TYPE_DEF_XSD,
            "The XSD data type of the value of the extension. xs:string if "
            "not given.",
        ),
        _a("value", "value", VALUE_DATA_TYPE, "Value of the extension."),
        _a(
            "refers_to",
            "refersTo",
            LIST_OF + "ModelReference<Referable>",
            "Elements that the extension refers to.",
        ),
    ),
    "Qualifier": (
        _a(
            "kind",
            "kind",
            "QualifierKind",
            "The kind of qualifier: a value, concept, or template "
            "qualifier. A concept qualifier if not given.",
        ),
        _a("type", "type", _STRING, "The type of the qualifier."),
        _VALUE_TYPE,
        _a("value", "value", VALUE_DATA_TYPE, "The value of the qualifier."),
        _VALUE_ID,
    ),
    "Reference": (
        _a(
            "key",
            "key",
            LIST_OF + "Key",
            "The keys that lead to the referenced element, from the first "
            "to the last.",
        ),
        _a(
            "referred_semantic_id",
            "referredSemanticId",
            _REFERENCE,
            "The expected semantic id of the referenced element.",
        ),
    ),
    "ModelReference": (
        _a(
            "type",
            "type",
            "type of element",
            "The type of the element that the reference points to. The "
            "SDK keeps it beside the keys.",
            in_metamodel=False,
        ),
    ),
    "Key": (
        _a(
            "type",
            "type",
            "KeyTypes",
            "What kind of entity the key points to, such as Submodel or "
            "GlobalReference.",
        ),
        _a(
            "value",
            "value",
            _STRING,
            "The key value: an id, an idShort, or a fragment.",
        ),
    ),
    "EmbeddedDataSpecification": (
        _a(
            "data_specification",
            "dataSpecification",
            _REFERENCE,
            "Reference to the data specification template, which is an "
            "external reference.",
        ),
        _a(
            "data_specification_content",
            "dataSpecificationContent",
            "DataSpecificationContent",
            "The content of the data specification template.",
        ),
    ),
    # --- Asset Administration Shell ---
    "AssetAdministrationShell": (
        _a(
            "derived_from",
            "derivedFrom",
            "ModelReference<AssetAdministrationShell>",
            "The shell that this shell was derived from.",
        ),
        _a(
            "asset_information",
            "assetInformation",
            "AssetInformation",
            "Meta information about the asset that the shell represents.",
        ),
        _a(
            "submodel",
            "submodel",
            LIST_OF + "ModelReference<Submodel>",
            "References to the submodels of the shell. Each describes an "
            "aspect of the asset.",
        ),
    ),
    "AssetInformation": (
        _a(
            "asset_kind",
            "assetKind",
            "AssetKind",
            "Whether the asset is a type, an instance, a role, or none of "
            "these.",
        ),
        _a(
            "global_asset_id",
            "globalAssetId",
            _STRING,
            "Identifier of the asset that the shell represents.",
        ),
        _a(
            "specific_asset_id",
            "specificAssetId",
            LIST_OF + "SpecificAssetId",
            "Further identifiers of the asset, such as a serial number.",
        ),
        _a(
            "asset_type",
            "assetType",
            _STRING,
            "The id of the type asset, when the asset itself is an instance.",
        ),
        _a(
            "default_thumbnail",
            "defaultThumbnail",
            "Resource",
            "The thumbnail of the asset, used by default.",
        ),
    ),
    "Resource": (_PATH, _CONTENT_TYPE),
    "SpecificAssetId": (
        _a("name", "name", _STRING, "Name of the asset identifier."),
        _a(
            "value",
            "value",
            _STRING,
            "The value of the identifier with this name.",
        ),
        _a(
            "external_subject_id",
            "externalSubjectId",
            _REFERENCE,
            "The external subject that the identifier belongs to or has "
            "meaning to.",
        ),
    ),
    # --- Submodel elements ---
    "Submodel": (
        _a(
            "submodel_element",
            "submodelElement",
            LIST_OF + "SubmodelElement",
            "The elements of the submodel.",
        ),
    ),
    "Property": (
        _VALUE_TYPE,
        _a("value", "value", VALUE_DATA_TYPE, "The value of the property."),
        _VALUE_ID,
    ),
    "MultiLanguageProperty": (
        _a(
            "value",
            "value",
            _LANG_TEXT,
            "The value of the property, which can be given in several "
            "languages.",
        ),
        _VALUE_ID,
    ),
    "Range": (
        _VALUE_TYPE,
        _a(
            "min",
            "min",
            VALUE_DATA_TYPE,
            "The minimum of the range. Without it, the range has no lower "
            "bound.",
        ),
        _a(
            "max",
            "max",
            VALUE_DATA_TYPE,
            "The maximum of the range. Without it, the range has no upper "
            "bound.",
        ),
    ),
    "Blob": (
        _a(
            "value",
            "value",
            "xs:base64Binary",
            "The content of the blob, stored in the element itself.",
        ),
        _CONTENT_TYPE,
    ),
    "File": (
        _a(
            "value",
            "value",
            _STRING,
            "Path and name of the file, with its extension. It can be "
            "absolute or relative.",
        ),
        _CONTENT_TYPE,
    ),
    "ReferenceElement": (
        _a(
            "value",
            "value",
            _REFERENCE,
            "The reference: an external one, or a model reference to "
            "another element.",
        ),
    ),
    "RelationshipElement": (
        _a(
            "first",
            "first",
            _REFERENCE,
            "The first element of the relationship, which has the role of "
            "the subject.",
        ),
        _a(
            "second",
            "second",
            _REFERENCE,
            "The second element of the relationship, which has the role "
            "of the object.",
        ),
    ),
    "AnnotatedRelationshipElement": (
        _a(
            "annotation",
            "annotation",
            LIST_OF + "DataElement",
            "Data elements that annotate the relationship.",
        ),
    ),
    "SubmodelElementCollection": (
        _a(
            "value",
            "value",
            LIST_OF + "SubmodelElement",
            "The elements of the collection.",
        ),
    ),
    "SubmodelElementList": (
        _a(
            "order_relevant",
            "orderRelevant",
            "xs:boolean",
            "Whether the order of the items matters. If not, the list is a "
            "set or a bag. True if not given.",
        ),
        _a(
            "value",
            "value",
            LIST_OF + "SubmodelElement",
            "The items of the list.",
        ),
        _a(
            "semantic_id_list_element",
            "semanticIdListElement",
            _REFERENCE,
            "The semantic id that every item of the list has.",
        ),
        _a(
            "type_value_list_element",
            "typeValueListElement",
            "AasSubmodelElements",
            "The type of element that the items of the list have.",
        ),
        _a(
            "value_type_list_element",
            "valueTypeListElement",
            DATA_TYPE_DEF_XSD,
            "The value type of the items of the list, for items that have one.",
        ),
    ),
    "Entity": (
        _a(
            "statement",
            "statement",
            LIST_OF + "SubmodelElement",
            "Statements about the entity, each described by an element.",
        ),
        _a(
            "entity_type",
            "entityType",
            "EntityType",
            "Whether the entity is co-managed or self-managed.",
        ),
        _a(
            "global_asset_id",
            "globalAssetId",
            _STRING,
            "Identifier of the asset that the entity represents.",
        ),
        _a(
            "specific_asset_id",
            "specificAssetId",
            LIST_OF + "SpecificAssetId",
            "Further identifiers of the asset that the entity represents.",
        ),
    ),
    "Operation": (
        _a(
            "input_variable",
            "inputVariable",
            LIST_OF + "OperationVariable",
            "The input parameters of the operation.",
        ),
        _a(
            "output_variable",
            "outputVariable",
            LIST_OF + "OperationVariable",
            "The output parameters of the operation.",
        ),
        _a(
            "in_output_variable",
            "inoutputVariable",
            LIST_OF + "OperationVariable",
            "Parameters that are input and output of the operation.",
        ),
    ),
    "BasicEventElement": (
        _a(
            "observed",
            "observed",
            "ModelReference<Referable>",
            "The element that is observed, such as a data element or a "
            "submodel.",
        ),
        _a(
            "direction",
            "direction",
            "Direction",
            "Whether the element receives events (input) or sends them "
            "(output).",
        ),
        _a("state", "state", "StateOfEvent", "Whether the event is on or off."),
        _a(
            "message_topic",
            "messageTopic",
            _STRING,
            "Information for the message infrastructure to schedule the "
            "event on its channel.",
        ),
        _a(
            "message_broker",
            "messageBroker",
            "ModelReference<Referable>",
            "The element that describes the message infrastructure that "
            "handles the messages.",
        ),
        _a(
            "last_update",
            "lastUpdate",
            "xs:dateTime",
            "When the last event was received or sent, in UTC.",
        ),
        _a(
            "min_interval",
            "minInterval",
            "xs:duration",
            "The shortest interval between events that is handled "
            "(input) or sent (output).",
        ),
        _a(
            "max_interval",
            "maxInterval",
            "xs:duration",
            "For output, the longest time before a status update is sent "
            "even if no event happened.",
        ),
    ),
    # --- Concept descriptions ---
    "ConceptDescription": (
        _a(
            "is_case_of",
            "isCaseOf",
            LIST_OF + _REFERENCE,
            "References to external definitions that the concept is "
            "compatible with or derived from.",
        ),
    ),
    # --- IEC 61360 content (IDTA-01003-a, not Part 1) ---
    "DataSpecificationIEC61360": (
        _a(
            "preferred_name",
            "preferredName",
            "PreferredNameTypeIEC61360",
            "The preferred name of the concept, in several languages.",
        ),
        _a(
            "short_name",
            "shortName",
            "ShortNameTypeIEC61360",
            "A short name of the concept, in several languages.",
        ),
        _a("unit", "unit", _STRING, "The unit of the concept."),
        _a(
            "unit_id",
            "unitId",
            _REFERENCE,
            "Reference to the unit of the concept.",
        ),
        _a(
            "source_of_definition",
            "sourceOfDefinition",
            _STRING,
            "Where the definition comes from.",
        ),
        _a("symbol", "symbol", _STRING, "The symbol of the unit."),
        _a(
            "data_type",
            "dataType",
            "DataTypeIEC61360",
            "The data type of the concept's values.",
        ),
        _a(
            "definition",
            "definition",
            "DefinitionTypeIEC61360",
            "The definition of the concept, in several languages.",
        ),
        _a(
            "value_format",
            "valueFormat",
            _STRING,
            "The format of the concept's values.",
        ),
        _a(
            "value_list",
            "valueList",
            LIST_OF + "ValueReferencePair",
            "The values that the concept allows, each with a reference.",
        ),
        _a("value", "value", _STRING, "A value of the concept."),
        _a(
            "level_types",
            "levelType",
            "set of IEC61360LevelType",
            "The levels that the values of the concept have: minimum, "
            "nominal, typical, or maximum.",
        ),
    ),
    "ValueReferencePair": (
        _a("value", "value", _STRING, "A value of the concept."),
        _a(
            "value_id",
            "valueId",
            _REFERENCE,
            "The globally unique id of the value.",
        ),
    ),
    # --- Only the SDK or the editor has these ---
    "DictItem": (
        _same("key", _STRING, "The language of the text, such as en."),
        _same("value", _STRING, "The text in that language."),
    ),
    "Package": (
        _same("name", _STRING, "The name of the opened package."),
        _same("file", _STRING, "The file that the package was opened from."),
        _same(
            "changed",
            "xs:boolean",
            "Whether the package has changes that are not saved.",
        ),
        _same(
            "partial",
            "xs:boolean",
            "Whether the package was opened with parts missing.",
        ),
        _same(
            "numOfShells",
            "xs:integer",
            "How many Asset Administration Shells the package has.",
        ),
        _same(
            "numOfSubmodels",
            "xs:integer",
            "How many submodels the package has.",
        ),
        _same(
            "numOfConceptDescriptions",
            "xs:integer",
            "How many concept descriptions the package has.",
        ),
        _same(
            "files",
            "list of StoredFile",
            "The files that are stored in the package.",
        ),
        _same(
            "missingFiles",
            "list of xs:string",
            "Paths that elements use for a file that the package does not "
            "have.",
        ),
        _same("thumbnail", "StoredFile", "The thumbnail of the package."),
        _same(
            "coreProperties",
            "OPC core properties",
            "The title, creator and other properties of the AASX file.",
        ),
    ),
    "StoredFile": (
        _same("name", _STRING, "The path of the file in the package."),
        _a(
            "mime_type",
            "mimeType",
            _STRING,
            "The media type of the file.",
            in_metamodel=False,
        ),
        _same("value", "xs:base64Binary", "The content of the file."),
    ),
}

LIST_INDEX = _same(
    "index",
    "xs:integer",
    "The position of the item in its list, counted from 0.",
)
"""The row of an item of a list that shows its position."""

_INDEX: dict[str, dict[str, AttributeInfo]] = {
    class_name: {info.sdk_name: info for info in infos}
    for class_name, infos in _ATTRIBUTES.items()
}


def vocabulary_classes() -> tuple[str, ...]:
    """Returns the names of the classes that the vocabulary has entries for."""
    return tuple(_INDEX)


def entries() -> tuple[tuple[str, AttributeInfo], ...]:
    """Returns every entry with the name of the class that declares it."""
    return tuple(
        (class_name, info)
        for class_name, infos in _ATTRIBUTES.items()
        for info in infos
    )


@functools.cache
def attribute_info(owner: type, sdk_name: str) -> AttributeInfo | None:
    """Returns what the vocabulary knows about an attribute of a class.

    The class and then its base classes are searched, so an attribute of
    `Referable` is found for a Property too.

    Args:
        owner: The class of the object that has the attribute.
        sdk_name: The name of the attribute in the SDK, such as `id_short`.

    Returns:
        The entry, or None if the vocabulary has none.
    """
    for cls in owner.__mro__:
        entry = _INDEX.get(cls.__name__, {}).get(sdk_name)
        if entry is not None:
            return entry
    return None


def metamodel_name(owner: type, sdk_name: str) -> str:
    """Returns the name that the metamodel gives to an attribute.

    Args:
        owner: The class of the object that has the attribute.
        sdk_name: The name of the attribute in the SDK.

    Returns:
        The metamodel name, or `sdk_name` when the vocabulary has no entry.
    """
    info = attribute_info(owner, sdk_name)
    return sdk_name if info is None else info.name
