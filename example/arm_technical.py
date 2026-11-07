"""The Technical Data and the Handover Documentation of the arm.

Both follow a bundled IDTA template. The numbers come from `arm_facts`, so the
datasheet, the nameplate and the technical data agree.
"""

from collections.abc import Sequence

from basyx.aas import model
from basyx.aas.model import datatypes

import arm_facts as facts
from arm_helpers import DATASHEET_PATH
from arm_helpers import ENVELOPE_PATH
from arm_helpers import LOGO_PATH
from arm_helpers import PICTURE_PATH
from arm_helpers import QUICKSTART_DE_PATH
from arm_helpers import QUICKSTART_PATH
from arm_helpers import collection
from arm_helpers import find
from arm_helpers import listing
from arm_helpers import mlp
from arm_helpers import names
from arm_helpers import prop
from arm_helpers import reference_to
from arm_helpers import span
from arm_helpers import texts
from arm_templates import Template
from arm_templates import like

COMPANY = "Workingbench Example Robotics (fictional)"
SHORT_NAME = "Workingbench Example"


def _area(
    template: model.SubmodelElementCollection,
    title: tuple[str, str, str],
    about: tuple[str, str, str],
    children: Sequence[model.SubmodelElement],
) -> model.SubmodelElementCollection:
    """Makes one technical property area, an item of the list of areas."""
    return like(
        template,
        id_short=None,
        children=children,
        display_name=names(*title),
        description=texts(*about),
    )


def _axes() -> model.SubmodelElementList:
    items = [
        collection(
            None,
            [
                prop("AxisNumber", int, axis.number),
                mlp("AxisName", *axis.name),
                span("RangeOfMotion", float, axis.low, axis.high),
                prop("MaximumAxisSpeed", float, axis.speed),
            ],
            concept_name="AxisDescription",
        )
        for axis in facts.AXES
    ]
    return listing(
        "Axes",
        model.SubmodelElementCollection,
        items,
        "AxisDescription",
        "AxisList",
    )


def technical_data() -> model.Submodel:
    """Builds the Technical Data of the arm.

    Returns:
        The submodel, from the template Technical Data 2.0.1.
    """
    t = Template("technical")
    general = t.at("GeneralInformation")
    image = t.at("GeneralInformation", "ProductImages", 0)
    area = t.at("TechnicalPropertyAreas", 0)

    def info(name: str, value: object) -> model.SubmodelElement:
        return like(general.get_referable(name), value)  # pyright: ignore[reportAttributeAccessIssue]

    def picture(
        path: str, note: dict[str, str]
    ) -> model.SubmodelElementCollection:
        return like(
            image,
            id_short=None,
            children=[
                like(image.get_referable("ImageFile"), path),  # pyright: ignore[reportAttributeAccessIssue]
                like(image.get_referable("ImageNote"), note),  # pyright: ignore[reportAttributeAccessIssue]
            ],
        )

    general_information = like(
        general,
        children=[
            info("ManufacturerName", COMPANY),
            info("CompanyLogo", LOGO_PATH),
            info(
                "ManufacturerProductDesignation",
                {
                    "en": facts.PRODUCT_NAME,
                    "de": "Workingbench Beispiel-Arm PP-6",
                    "pt": "Braço de exemplo Workingbench PP-6",
                },
            ),
            info("ManufacturerArticleNumber", "PP6-100-0001"),
            info("ManufacturerOrderCode", "EX-PP6-6K-900"),
            like(
                general.get_referable("ProductImages"),  # pyright: ignore[reportAttributeAccessIssue]
                children=[
                    picture(
                        PICTURE_PATH,
                        {
                            "en": "The arm picks a part and sets it down at the place pose.",
                            "de": "Der Arm nimmt ein Teil auf und legt es an der Ablagepose ab.",
                            "pt": "O braço pega uma peça e a deposita na pose de colocação.",
                        },
                    ),
                    picture(
                        ENVELOPE_PATH,
                        {
                            "en": "Top view of the reach of 900 mm, with the pick pose and the place pose.",
                            "de": "Draufsicht auf die Reichweite von 900 mm, mit Aufnahme- und Ablagepose.",
                            "pt": "Vista de topo do alcance de 900 mm, com as poses de coleta e de colocação.",
                        },
                    ),
                ],
            ),
        ],
    )

    classification_t = t.at("ProductClassifications", 0)

    def classified(name: str, value: object) -> model.SubmodelElement:
        return like(classification_t.get_referable(name), value)  # pyright: ignore[reportAttributeAccessIssue]

    classification = like(
        classification_t,
        id_short=None,
        children=[
            classified("ClassificationSystem", "CustomerSpecific"),
            classified("ClassificationSystemVersion", "1.0"),
            classified(
                "ClassificationSystemUrl",
                "https://example.com/classification/robots",
            ),
            classified("ProductClassId", "EX-IR-6A"),
            classified("ProductClassCodedName", "EX-IR-6A"),
            classified(
                "ProductClassName",
                {
                    "en": "Six-axis industrial robot, up to 10 kg",
                    "de": "Sechsachsiger Industrieroboter, bis 10 kg",
                    "pt": "Robô industrial de seis eixos, até 10 kg",
                },
            ),
            # The reference to the area of the performance data is set when the
            # submodel is whole, in `link_areas`.
            classified("ReferenceToTechnicalPropertyArea", None),
        ],
    )
    areas = [
        _area(
            area,
            ("Performance", "Leistung", "Desempenho"),
            (
                "What the arm carries, reaches and repeats.",
                "Was der Arm trägt, erreicht und wiederholt.",
                "O que o braço carrega, alcança e repete.",
            ),
            [
                prop("NumberOfAxes", int, 6),
                prop("RatedPayload", float, facts.PAYLOAD_KG),
                prop("MaximumReach", float, facts.REACH_MM),
                prop("PoseRepeatability", float, facts.REPEATABILITY_MM),
                prop("MaximumTcpSpeed", float, facts.TCP_SPEED_M_S),
                prop("ArmMass", float, facts.ARM_MASS_KG),
                prop("PickAndPlaceCycleRate", float, facts.CYCLE_RATE),
            ],
        ),
        _area(
            area,
            ("Axes", "Achsen", "Eixos"),
            (
                "The six joints with their ranges and speeds.",
                "Die sechs Gelenke mit ihren Bereichen und Geschwindigkeiten.",
                "As seis juntas com suas faixas e velocidades.",
            ),
            [_axes()],
        ),
        _area(
            area,
            (
                "Electrical supply",
                "Elektrische Versorgung",
                "Alimentação elétrica",
            ),
            (
                "Supply of the controller and the power of the system.",
                "Versorgung der Steuerung und Leistung des Systems.",
                "Alimentação do controlador e potência do sistema.",
            ),
            [
                span("SupplyVoltage", float, *facts.SUPPLY_VOLTAGE_V),
                span("SupplyFrequency", float, *facts.SUPPLY_FREQUENCY_HZ),
                prop("NominalPowerConsumption", float, facts.NOMINAL_POWER_W),
                prop("MaximumPowerConsumption", float, facts.MAXIMUM_POWER_W),
                prop("DcBusVoltage", float, facts.DC_BUS_V),
            ],
        ),
        _area(
            area,
            ("Environment", "Umgebung", "Ambiente"),
            (
                "Where the arm may work and be stored.",
                "Wo der Arm arbeiten und gelagert werden darf.",
                "Onde o braço pode trabalhar e ser armazenado.",
            ),
            [
                prop("ArmProtectionClass", str, "IP54"),
                prop("ControllerProtectionClass", str, "IP20"),
                span(
                    "OperatingTemperature",
                    float,
                    *facts.OPERATING_TEMPERATURE_C,
                ),
                span("StorageTemperature", float, *facts.STORAGE_TEMPERATURE_C),
                span("RelativeHumidity", float, *facts.HUMIDITY_PERCENT),
                prop("NoiseLevel", float, facts.NOISE_DB_A),
            ],
        ),
        _area(
            area,
            ("Mounting", "Montage", "Montagem"),
            (
                "How the base and the tool are fixed.",
                "Wie Basis und Werkzeug befestigt werden.",
                "Como a base e a ferramenta são fixadas.",
            ),
            [
                mlp(
                    "MountingOrientation",
                    "Floor, ceiling or wall",
                    "Boden, Decke oder Wand",
                    "Piso, teto ou parede",
                ),
                prop("BaseBoltPattern", str, "4 x M8 on a 120 mm square"),
                prop("ToolFlangeStandard", str, "ISO 9409-1-50-4-M6"),
            ],
        ),
        _area(
            area,
            ("Gripper", "Greifer", "Garra"),
            (
                "The two-finger gripper and its vacuum option.",
                "Der Zweifingergreifer und seine Vakuumoption.",
                "A garra de dois dedos e sua opção de vácuo.",
            ),
            [
                mlp(
                    "GripperType",
                    "Parallel two-finger gripper with a vacuum option",
                    "Parallel-Zweifingergreifer mit Vakuumoption",
                    "Garra paralela de dois dedos com opção de vácuo",
                ),
                prop("GripStroke", float, facts.GRIP_STROKE_MM),
                span("GripForceRange", float, *facts.GRIP_FORCE_N),
                prop("MaximumVacuumLevel", float, facts.MAXIMUM_VACUUM_KPA),
            ],
        ),
    ]
    further = t.at("FurtherInformation")
    elements = [
        general_information,
        like(t.at("ProductClassifications"), children=[classification]),
        like(t.at("TechnicalPropertyAreas"), children=areas),
        like(
            further,
            children=[
                like(
                    further.get_referable("TextStatement"),  # pyright: ignore[reportAttributeAccessIssue]
                    {
                        "en": "Fictional example data. It describes no real product and may not be used to design a plant.",
                        "de": "Fiktive Beispieldaten. Sie beschreiben kein reales Produkt und dürfen nicht für die Auslegung einer Anlage genutzt werden.",
                        "pt": "Dados fictícios de exemplo. Eles não descrevem um produto real e não podem ser usados para projetar uma instalação.",
                    },
                ),
                like(
                    further.get_referable("ValidDate"),  # pyright: ignore[reportAttributeAccessIssue]
                    datatypes.Date(2026, 11, 1),
                ),
            ],
        ),
    ]
    submodel = t.instance("TechnicalData", elements)
    link_areas(submodel)
    return submodel


def link_areas(submodel: model.Submodel) -> None:
    """Points the classification at the area of the performance data.

    Args:
        submodel: The technical data, whole.
    """
    classifications = find(submodel, "ProductClassifications")
    areas = find(submodel, "TechnicalPropertyAreas")
    target = list(areas.value)[0]  # pyright: ignore[reportAttributeAccessIssue]
    for item in classifications.value:  # pyright: ignore[reportAttributeAccessIssue]
        reference = item.get_referable("ReferenceToTechnicalPropertyArea")
        reference.value = reference_to(target)


def handover_documentation(
    entry_node: model.Entity | None = None,
) -> model.Submodel:
    """Builds the Handover Documentation of the arm.

    Args:
        entry_node: The root entity of the bill of material, which the
            documents are about. It can be set later with `link_documents`.

    Returns:
        The submodel, from the template Handover Documentation 2.0.1, with a
        datasheet and a quick start guide.
    """
    t = Template("handover")
    version = t.at("Documents", 0, "DocumentVersions", 0)

    def doc(*path: str | int) -> model.SubmodelElement:
        return t.at("Documents", 0, *path)

    def ver(*path: str | int) -> model.SubmodelElement:
        return t.at("Documents", 0, "DocumentVersions", 0, *path)

    def ids(identifier: str) -> model.SubmodelElementList:
        return like(
            doc("DocumentIds"),
            children=[
                like(
                    doc("DocumentIds", 0),
                    id_short=None,
                    children=[
                        like(
                            doc("DocumentIds", 0, "DocumentDomainId"),
                            "https://example.com/ids/documents",
                        ),
                        like(
                            doc("DocumentIds", 0, "DocumentIdentifier"),
                            identifier,
                        ),
                        like(doc("DocumentIds", 0, "DocumentIsPrimary"), True),
                    ],
                )
            ],
        )

    def classes(
        class_id: str, name: dict[str, str]
    ) -> model.SubmodelElementList:
        return like(
            doc("DocumentClassifications"),
            children=[
                like(
                    doc("DocumentClassifications", 0),
                    id_short=None,
                    children=[
                        like(
                            doc("DocumentClassifications", 0, "ClassId"),
                            class_id,
                        ),
                        like(
                            doc("DocumentClassifications", 0, "ClassName"), name
                        ),
                        like(
                            doc(
                                "DocumentClassifications",
                                0,
                                "ClassificationSystem",
                            ),
                            "VDI2770:2020",
                        ),
                    ],
                )
            ],
        )

    def versions(
        languages: Sequence[str],
        title: dict[str, str],
        summary: dict[str, str],
        keywords: dict[str, str],
        files: Sequence[tuple[str, str]],
        preview: str | None,
    ) -> model.SubmodelElementList:
        children: list[model.SubmodelElement] = [
            like(
                ver("Language"),
                children=[
                    like(ver("Language", 0), code, id_short=None)
                    for code in languages
                ],
            ),
            like(ver("Version"), "1.0"),
            like(ver("Title"), title),
            like(ver("Description"), summary),
            like(ver("KeyWords"), keywords),
            like(ver("StatusSetDate"), datatypes.Date(2026, 3, 18)),
            like(ver("StatusValue"), "Released"),
            like(ver("OrganizationShortName"), SHORT_NAME),
            like(ver("OrganizationOfficialName"), COMPANY),
            like(
                ver("DigitalFiles"),
                children=[
                    like(
                        ver("DigitalFiles", 0),
                        path,
                        id_short=None,
                        content_type=content_type,
                    )
                    for path, content_type in files
                ],
            ),
        ]
        if preview is not None:
            children.append(
                like(ver("PreviewFile"), preview, content_type="image/png")
            )
        return like(
            t.at("Documents", 0, "DocumentVersions"),
            children=[like(version, id_short=None, children=children)],
        )

    def documented() -> model.SubmodelElementList:
        # What the document is about. The reference is set by
        # `link_documents`, when the bill of material exists.
        return like(
            doc("DocumentedEntities"),
            children=[like(doc("DocumentedEntities", 0), None, id_short=None)],
        )

    datasheet = like(
        doc(),
        id_short=None,
        children=[
            ids("PP6-DS-001"),
            classes(
                "02-01",
                {
                    "en": "Technical specification",
                    "de": "Technische Spezifikation",
                    "pt": "Especificação técnica",
                },
            ),
            versions(
                ["en"],
                {
                    "en": "Datasheet of the Workingbench Example Arm PP-6",
                    "de": "Datenblatt des Workingbench Beispiel-Arms PP-6",
                    "pt": "Folha de dados do braço de exemplo Workingbench PP-6",
                },
                {
                    "en": "The main data of the fictional arm on one page.",
                    "de": "Die wichtigsten Daten des fiktiven Arms auf einer Seite.",
                    "pt": "Os dados principais do braço fictício em uma página.",
                },
                {"en": "datasheet, robot, pick and place"},
                [(DATASHEET_PATH, "application/pdf")],
                PICTURE_PATH,
            ),
            documented(),
        ],
    )
    quickstart = like(
        doc(),
        id_short=None,
        children=[
            ids("PP6-QS-001"),
            classes(
                "03-02",
                {
                    "en": "Operation",
                    "de": "Bedienung",
                    "pt": "Operação",
                },
            ),
            versions(
                ["en", "de"],
                {
                    "en": "Quick start of the Workingbench Example Arm PP-6",
                    "de": "Kurzanleitung des Workingbench Beispiel-Arms PP-6",
                    "pt": "Guia rápido do braço de exemplo Workingbench PP-6",
                },
                {
                    "en": "Six steps from the bolted base to the first cycle.",
                    "de": "Sechs Schritte von der verschraubten Basis bis zum ersten Zyklus.",
                    "pt": "Seis passos da base parafusada até o primeiro ciclo.",
                },
                {"en": "quick start, operation"},
                [
                    (QUICKSTART_PATH, "application/pdf"),
                    (QUICKSTART_DE_PATH, "application/pdf"),
                ],
                None,
            ),
            documented(),
        ],
    )
    submodel = t.instance(
        "HandoverDocumentation",
        [like(t.at("Documents"), children=[datasheet, quickstart])],
    )
    if entry_node is not None:
        link_documents(submodel, entry_node)
    return submodel


def link_documents(submodel: model.Submodel, entry_node: model.Entity) -> None:
    """Points every document at the entity that it documents.

    Args:
        submodel: The handover documentation.
        entry_node: The root entity of the bill of material.
    """
    documents = find(submodel, "Documents")
    for document in documents.value:  # pyright: ignore[reportAttributeAccessIssue]
        for entity in document.get_referable("DocumentedEntities").value:
            entity.value = reference_to(entry_node)
