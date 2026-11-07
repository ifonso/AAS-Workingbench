"""Reads the IDTA submodel templates that the editor bundles, and fills them.

The semantic ids, the supplemental semantic ids, the display names and the
descriptions of the elements of a template submodel are read from the bundled
template files and are not typed here. `like` makes an element of the example
from the template element at the same place, with the value that the example
gives it.

The templates are published by the IDTA under CC BY 4.0. NOTICE says so.
"""

from collections.abc import Iterable
from collections.abc import Mapping
import copy
import functools
from pathlib import Path
from typing import Any

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer

from arm_concepts import IEC_61360_TEMPLATE
from arm_helpers import fictional
from arm_helpers import submodel_id

TEMPLATES = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "aas_workingbench"
    / "submodel_templates"
)

# The files that the example is built from, below the templates folder. Each is
# the metamodel V3.1 file of its template, except the nameplate, which the IDTA
# published only as one file.
TEMPLATE_FILES: dict[str, str] = {
    "nameplate": "Digital nameplate/3/0/1/IDTA 02006-3-0-1_Template_Digital Nameplate.aasx",
    "contact": "Contact Information/1/0/1/IDTA 02002-1-0-1_Template_ContactInformation_forAASMetamodelV3.1.aasx",
    "technical": "Technical_Data/2/0/1/IDTA 02003_2-0-1_Template_TechnicalData_forAASMetamodelV3.1.aasx",
    "handover": "Handover Documentation/2/0/1/IDTA 02004-2-0-1_Template_HandoverDocumentation__forAASMetamodelV3.1.aasx",
    "structure": "Hierarchical Structures enabling Bills of Material/1/1/1/IDTA 02011-1-1-1_Template_HSEBoM_forAASMetamodelV3.1.aasx",
    "carbon": "Carbon Footprint/1/0/1/IDTA 02023-1-0-1 _Template_CarbonFootprint_forAASMetamodelV3.1.aasx",
    "software": "Software Nameplate/1/0/1/IDTA 02007-1-0-1_Template_Software Nameplate_forAASMetamodelV3.1.aasx",
    "series": "Time Series Data/1/1/1/IDTA 02008-1-1-1_Template_TimeSeriesData_forAASMetamodelV3.1.aasx",
}

# The name and the description of the submodel that is made from each
# template, in English, German and Portuguese. The templates have none.
SUBMODEL_TEXTS: dict[str, tuple[tuple[str, str, str], tuple[str, str, str]]] = {
    "nameplate": (
        (
            "Digital nameplate",
            "Digitales Typenschild",
            "Placa de identificação digital",
        ),
        (
            "What the arm is: the manufacturer, the type, the serial number, the year and the markings.",
            "Was der Arm ist: Hersteller, Typ, Seriennummer, Baujahr und Kennzeichnungen.",
            "O que o braço é: fabricante, tipo, número de série, ano e marcações.",
        ),
    ),
    "contact": (
        (
            "Contact information",
            "Kontaktinformationen",
            "Informações de contato",
        ),
        (
            "Who to ask at the manufacturer about service and about offers.",
            "An wen man sich beim Hersteller für Service und Angebote wendet.",
            "Quem procurar no fabricante para assistência e para propostas.",
        ),
    ),
    "technical": (
        ("Technical data", "Technische Daten", "Dados técnicos"),
        (
            "The performance, the axes, the supply, the environment, the mounting and the gripper of the arm.",
            "Leistung, Achsen, Versorgung, Umgebung, Montage und Greifer des Arms.",
            "Desempenho, eixos, alimentação, ambiente, montagem e garra do braço.",
        ),
    ),
    "handover": (
        (
            "Handover documentation",
            "Übergabedokumentation",
            "Documentação de entrega",
        ),
        (
            "The documents that come with the arm, classified as VDI 2770 asks.",
            "Die Dokumente, die zum Arm gehören, klassifiziert nach VDI 2770.",
            "Os documentos que acompanham o braço, classificados conforme a VDI 2770.",
        ),
    ),
    "structure": (
        ("Bill of material", "Stückliste", "Lista de materiais"),
        (
            "The parts of the arm as a tree of entities: base, joints, wrist, gripper and controller.",
            "Die Teile des Arms als Baum von Entitäten: Basis, Gelenke, Handgelenk, Greifer und Steuerung.",
            "As peças do braço como uma árvore de entidades: base, juntas, punho, garra e controlador.",
        ),
    ),
    "carbon": (
        ("Carbon footprint", "CO2-Fußabdruck", "Pegada de carbono"),
        (
            "The made-up carbon footprint of producing one arm.",
            "Der erfundene CO2-Fußabdruck der Herstellung eines Arms.",
            "A pegada de carbono inventada da produção de um braço.",
        ),
    ),
    "software": (
        (
            "Software nameplate",
            "Software-Typenschild",
            "Placa de identificação do software",
        ),
        (
            "The firmware of the controller: its version and what is installed.",
            "Die Firmware der Steuerung: ihre Version und was installiert ist.",
            "O firmware do controlador: sua versão e o que está instalado.",
        ),
    ),
    "series": (
        (
            "Joint temperature history",
            "Verlauf der Gelenktemperaturen",
            "Histórico das temperaturas das juntas",
        ),
        (
            "A short recording of the six joint temperatures as a time series.",
            "Eine kurze Aufzeichnung der sechs Gelenktemperaturen als Zeitreihe.",
            "Um registro curto das seis temperaturas das juntas como série temporal.",
        ),
    ),
}

_KEEP: Any = object()


class Template:
    """One bundled template, opened to read its structure."""

    def __init__(self, key: str) -> None:
        """Opens a template.

        Args:
            key: A key of `TEMPLATE_FILES`.
        """
        self.key = key
        self._store: model.DictIdentifiableStore[model.Identifiable] = (
            model.DictIdentifiableStore()
        )
        with AASXReader(str(TEMPLATES / TEMPLATE_FILES[key])) as reader:
            reader.read_into(self._store, DictSupplementaryFileContainer())
        submodels = [
            obj for obj in self._store if isinstance(obj, model.Submodel)
        ]
        assert len(submodels) == 1, key
        self.submodel: model.Submodel = submodels[0]

    @property
    def objects(self) -> list[model.Identifiable]:
        """Every shell, submodel and concept description of the template."""
        return list(self._store)

    def at(self, *path: str | int) -> Any:
        """Finds the template element at a path.

        Args:
            *path: The idShorts from the submodel down. An integer takes the
                item of a list or the child of a collection at that position.

        Returns:
            The element of the template.
        """
        current: Any = self.submodel
        for step in path:
            if isinstance(step, int):
                current = list(
                    current.statement
                    if isinstance(current, model.Entity)
                    else current.value
                )[step]
            else:
                current = current.get_referable(step)
        return current

    def concept(self, concept_id: str) -> model.ConceptDescription | None:
        """Copies a concept description of the template.

        Args:
            concept_id: The id of the description.

        Returns:
            A copy, or None if the template has no such description.
        """
        found = self._store.get(concept_id)
        if not isinstance(found, model.ConceptDescription):
            return None
        result = copy.deepcopy(found)
        # Some templates name the IEC 61360 template as it was spelled for
        # metamodel V3.0, so the key is the one of V3.1.
        records = [
            model.EmbeddedDataSpecification(
                data_specification=model.ExternalReference(
                    (
                        model.Key(
                            model.KeyTypes.GLOBAL_REFERENCE, IEC_61360_TEMPLATE
                        ),
                    )
                ),
                data_specification_content=record.data_specification_content,
            )
            for record in result.embedded_data_specifications
        ]
        result.embedded_data_specifications = records
        # A reference to a description in a dictionary that the package does not
        # hold is an external reference, and not a model reference that points
        # at nothing.
        if result.is_case_of:
            result.is_case_of = {
                model.ExternalReference(
                    tuple(
                        model.Key(model.KeyTypes.GLOBAL_REFERENCE, key.value)
                        for key in reference.key
                    )
                )
                for reference in result.is_case_of
            }
        # The names that the record holds are also the name and the description
        # of the object, so that a tree shows them.
        for record in records:
            content = record.data_specification_content
            if isinstance(content, model.DataSpecificationIEC61360):
                if content.preferred_name:
                    result.display_name = model.MultiLanguageNameType(
                        dict(content.preferred_name)
                    )
                if content.definition:
                    result.description = model.MultiLanguageTextType(
                        dict(content.definition)
                    )
        return result

    def coded_value(
        self, concept_id: str, text: str
    ) -> model.ExternalReference:
        """Reads the reference of a coded value from a concept of the template.

        Args:
            concept_id: The id of the concept description in the template.
            text: The value as the value list of the concept writes it.

        Returns:
            The reference that the value list pairs with the value.

        Raises:
            KeyError: If the template has no such value.
        """
        description = self._store.get_item(concept_id)
        assert isinstance(description, model.ConceptDescription)
        for record in description.embedded_data_specifications:
            content = record.data_specification_content
            assert isinstance(content, model.DataSpecificationIEC61360)
            for pair in content.value_list or ():
                if pair.value == text and pair.value_id is not None:
                    return model.ExternalReference(tuple(pair.value_id.key))
        raise KeyError(f"{text!r} is not a value of {concept_id}")

    def instance(
        self,
        name: str,
        elements: Iterable[model.SubmodelElement],
    ) -> model.Submodel:
        """Makes the submodel of the example from the template.

        The submodel has the id_short, the semantic id and the version of the
        template, and the kind Instance.

        Args:
            name: The short name that ends the id of the new submodel.
            elements: The elements that the example fills in.

        Returns:
            The submodel.
        """
        template = self.submodel
        admin = template.administration
        title, about = SUBMODEL_TEXTS[self.key]
        return model.Submodel(
            submodel_id(name),
            elements,
            id_short=template.id_short,
            display_name=model.MultiLanguageNameType(
                dict(zip(("en", "de", "pt"), title, strict=True))
            ),
            description=model.MultiLanguageTextType(
                dict(zip(("en", "de", "pt"), about, strict=True))
            ),
            administration=(
                model.AdministrativeInformation(admin.version, admin.revision)
                if admin is not None and admin.version
                else model.AdministrativeInformation("1", "0")
            ),
            semantic_id=_clean(template.semantic_id),
            kind=model.ModellingKind.INSTANCE,
            supplemental_semantic_id=[
                _clean(ref) for ref in template.supplemental_semantic_id
            ],
            extension=[fictional()],
        )


def _clean(reference: model.Reference | None) -> Any:
    """Takes the whitespace out of the keys of a reference.

    Two semantic ids of the bundled Contact Information template have a stray
    space inside the IRI. The specification and the concept descriptions of
    the template write them without, so the example does too.
    """
    if reference is None:
        return None
    keys = tuple(
        model.Key(key.type, "".join(key.value.split())) for key in reference.key
    )
    if keys == tuple(reference.key):
        return reference
    if isinstance(reference, model.ModelReference):
        return model.ModelReference(
            keys, reference.type, reference.referred_semantic_id
        )
    return model.ExternalReference(keys, reference.referred_semantic_id)


@functools.cache
def _all_templates() -> tuple[Template, ...]:
    return tuple(Template(key) for key in TEMPLATE_FILES)


def concept_named(concept_id: str) -> model.ConceptDescription | None:
    """Finds a concept description of any of the bundled templates by its id.

    Args:
        concept_id: The id of the description.

    Returns:
        A copy of the description from the first template that has it, or
        None.
    """
    for template in _all_templates():
        found = template.concept(concept_id)
        if found is not None:
            return found
    return None


def concept_of(reference: model.Reference) -> model.ConceptDescription | None:
    """Finds the concept description of a template that a reference names.

    Args:
        reference: A reference whose last key is a concept description.

    Returns:
        A copy of the concept description from the bundled template that has
        it, or None.
    """
    return concept_named(reference.key[-1].value)


def _copy_names(names: Mapping[str, str] | None) -> Any:
    return model.MultiLanguageNameType(dict(names)) if names else None


def _copy_texts(
    texts: Mapping[str, str] | None,
) -> model.MultiLanguageTextType | None:
    return model.MultiLanguageTextType(dict(texts)) if texts else None


def like(
    template: model.SubmodelElement,
    value: Any = None,
    children: Iterable[model.SubmodelElement] = (),
    id_short: str | None = _KEEP,
    value_id: model.Reference | None = None,
    **extra: Any,
) -> Any:
    """Makes an element from the template element at the same place.

    The meaning comes from the template: the semantic id, the supplemental
    semantic ids, the display name and the description. The category, which
    metamodel V3.1 deprecates, is left out. The
    template qualifiers do not, because they belong to a template and not to
    an instance.

    Args:
        template: The element of the template.
        value: The value of a data element: for a Property the value, for a
            MultiLanguageProperty a mapping of language to text, for a File
            the path, for a Range a pair of bounds, for a ReferenceElement
            the reference, and for a Relationship a pair of references.
        children: The elements of a collection, a list or an entity.
        id_short: The new idShort. None makes an item of a list. The default
            keeps the idShort of the template.
        value_id: The `valueId` of a Property.
        **extra: Arguments for the constructor, such as `global_asset_id`,
            `content_type` or `qualifier`.

    Returns:
        A new element of the same class.

    Raises:
        TypeError: If the class of the template element is not supported.
    """
    name = template.id_short if id_short is _KEEP else id_short
    common: dict[str, Any] = {
        "semantic_id": _clean(template.semantic_id),
        "supplemental_semantic_id": [
            _clean(ref) for ref in template.supplemental_semantic_id
        ],
        "display_name": _copy_names(template.display_name),
        "description": _copy_texts(template.description),
    }
    common.update(extra)
    if isinstance(template, model.Property):
        return model.Property(
            name, template.value_type, value, value_id=value_id, **common
        )
    if isinstance(template, model.MultiLanguageProperty):
        return model.MultiLanguageProperty(
            name, model.MultiLanguageTextType(dict(value)), **common
        )
    if isinstance(template, model.File):
        content_type = common.pop("content_type", template.content_type)
        return model.File(name, content_type, value, **common)
    if isinstance(template, model.Range):
        low, high = value
        return model.Range(name, template.value_type, low, high, **common)
    if isinstance(template, model.ReferenceElement):
        return model.ReferenceElement(name, value, **common)
    if isinstance(template, model.SubmodelElementCollection):
        return model.SubmodelElementCollection(name, children, **common)
    if isinstance(template, model.SubmodelElementList):
        return model.SubmodelElementList(
            name,
            template.type_value_list_element,
            children,
            semantic_id_list_element=template.semantic_id_list_element,
            value_type_list_element=template.value_type_list_element,
            order_relevant=template.order_relevant,
            **common,
        )
    if isinstance(template, model.Entity):
        return model.Entity(name, template.entity_type, children, **common)
    if isinstance(template, model.RelationshipElement):
        first, second = value
        return model.RelationshipElement(name, first, second, **common)
    raise TypeError(f"cannot copy a {type(template).__name__}")
