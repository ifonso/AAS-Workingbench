"""The submodels that say what the arm is: nameplate, contacts, software, CO2.

All four follow a bundled IDTA template. The semantic ids come from the
template files through `like`, and only the values are written here.
"""

from decimal import Decimal

from basyx.aas import model
from basyx.aas.model import datatypes

from arm_facts import PRODUCT_NAME
from arm_helpers import LOGO_PATH
from arm_helpers import MARKING_PATH
from arm_helpers import SERIAL_NUMBER
from arm_helpers import moment
from arm_helpers import prop
from arm_templates import Template
from arm_templates import like

COMPANY = "Workingbench Example Robotics (fictional)"
PRODUCT = {
    "en": PRODUCT_NAME,
    "de": "Workingbench Beispiel-Arm PP-6",
    "pt": "Braço de exemplo Workingbench PP-6",
}


def nameplate() -> model.Submodel:
    """Builds the Digital Nameplate of the arm.

    Returns:
        The submodel, from the template Digital Nameplate 3.0.1.
    """
    t = Template("nameplate")
    contact = Template("contact").at("ContactInformation")
    address = like(
        t.at("AddressInformation"),
        children=[
            like(contact.get_referable("Street"), {"de": "Beispielweg 1"}),
            like(contact.get_referable("Zipcode"), {"de": "00000"}),
            like(contact.get_referable("CityTown"), {"de": "Musterstadt"}),
            like(contact.get_referable("StateCounty"), {"de": "Musterland"}),
            like(contact.get_referable("NationalCode"), {"de": "DE"}),
        ],
    )
    marking_t = t.at("Markings", 0)
    marking = like(
        marking_t,
        id_short=None,
        children=[
            like(
                marking_t.get_referable("MarkingName"),
                # The specification lets a marking with no entry in the
                # enumeration of ECLASS be written as plain text. This one is
                # no real marking, so it has none.
                "EXAMPLE",
            ),
            like(
                marking_t.get_referable("DesignationOfCertificateOrApproval"),
                "EXAMPLE-ONLY-0000",
            ),
            like(
                marking_t.get_referable("IssueDate"),
                datatypes.Date(2026, 3, 1),
            ),
            like(
                marking_t.get_referable("ExpiryDate"),
                datatypes.Date(2031, 3, 1),
            ),
            like(marking_t.get_referable("MarkingFile"), MARKING_PATH),
            like(
                marking_t.get_referable("MarkingAdditionalText"),
                "Fictional example: no conformity assessment took place.",
            ),
        ],
    )
    elements = [
        like(
            t.at("URIOfTheProduct"),
            f"https://example.com/products/pp-6/{SERIAL_NUMBER}",
        ),
        like(t.at("ManufacturerName"), {"en": COMPANY}),
        like(t.at("ManufacturerProductDesignation"), PRODUCT),
        address,
        like(
            t.at("ManufacturerProductRoot"),
            {
                "en": "Industrial robot",
                "de": "Industrieroboter",
                "pt": "Robô industrial",
            },
        ),
        like(
            t.at("ManufacturerProductFamily"),
            {
                "en": "Example Arm",
                "de": "Beispiel-Arm",
                "pt": "Braço de exemplo",
            },
        ),
        like(t.at("ManufacturerProductType"), "PP-6"),
        like(t.at("OrderCodeOfManufacturer"), "EX-PP6-6K-900"),
        like(t.at("ProductArticleNumberOfManufacturer"), "PP6-100-0001"),
        like(t.at("SerialNumber"), SERIAL_NUMBER),
        like(t.at("YearOfConstruction"), "2026"),
        like(t.at("DateOfManufacture"), datatypes.Date(2026, 3, 16)),
        like(t.at("HardwareVersion"), "1.2.0"),
        like(t.at("FirmwareVersion"), "4.2.1"),
        like(t.at("CountryOfOrigin"), "DE"),
        like(t.at("CompanyLogo"), LOGO_PATH),
        like(t.at("Markings"), children=[marking]),
        like(
            t.at("AssetSpecificProperties"),
            children=[
                prop("NumberOfAxes", int, 6),
                prop("RatedPayload", float, 6.0),
            ],
        ),
    ]
    return t.instance("Nameplate", elements)


def _contact(
    template: model.SubmodelElementCollection,
    number: int,
    role: str,
    department: dict[str, str],
    person: tuple[str, str],
    phone: str,
    email: str,
    link: str,
    languages: tuple[str, ...],
    note: dict[str, str],
) -> model.SubmodelElementCollection:
    def part(*path: str) -> model.SubmodelElement:
        element: model.Referable = template
        for step in path:
            element = element.get_referable(step)  # pyright: ignore[reportAttributeAccessIssue]
        return element  # pyright: ignore[reportReturnType]

    address = {"de": "Beispielweg 1"}
    return like(
        template,
        id_short=f"ContactInformation{number:02d}",
        children=[
            like(part("RoleOfContactPerson"), role),
            like(part("NationalCode"), {"de": "DE"}),
            *[
                like(part("Language"), code, id_short=f"Language{i:02d}")
                for i, code in enumerate(languages, start=1)
            ],
            like(part("TimeZone"), "+01:00"),
            like(part("CityTown"), {"de": "Musterstadt"}),
            like(part("Company"), {"en": COMPANY}),
            like(part("Department"), department),
            like(
                part("Phone"),
                children=[
                    like(part("Phone", "TelephoneNumber"), {"en": phone}),
                    like(
                        part("Phone", "TypeOfTelephone"),
                        # Office, as the template's example gives it.
                        part("Phone", "TypeOfTelephone").value,
                    ),
                    like(
                        part("Phone", "AvailableTime"),
                        {
                            "en": "Monday to Friday, 08:00 to 16:00",
                            "de": "Montag bis Freitag, 08:00 bis 16:00",
                            "pt": "Segunda a sexta-feira, 08:00 às 16:00",
                        },
                    ),
                ],
            ),
            like(
                part("Email"),
                children=[
                    like(part("Email", "EmailAddress"), email),
                    like(
                        part("Email", "TypeOfEmailAddress"),
                        part("Email", "TypeOfEmailAddress").value,
                    ),
                ],
            ),
            like(
                part("IPCommunication__00__"),
                id_short="IPCommunication01",
                children=[
                    like(
                        part(
                            "IPCommunication__00__", "AddressOfAdditionalLink"
                        ),
                        link,
                    ),
                    like(
                        part("IPCommunication__00__", "TypeOfCommunication"),
                        "Website",
                    ),
                ],
            ),
            like(part("Street"), address),
            like(part("Zipcode"), {"de": "00000"}),
            like(part("StateCounty"), {"de": "Musterland"}),
            like(part("NameOfContact"), {"en": person[1]}),
            like(part("FirstName"), {"en": person[0]}),
            like(part("FurtherDetailsOfContact"), note),
        ],
    )


def contact_information() -> model.Submodel:
    """Builds the Contact Information of the manufacturer.

    Returns:
        The submodel, from the template Contact Information 1.0.1, with a
        technical contact and a commercial one.
    """
    t = Template("contact")
    contact = t.at("ContactInformation")
    technical = (
        contact.get_referable("RoleOfContactPerson").value  # pyright: ignore[reportAttributeAccessIssue]
    )
    elements = [
        _contact(
            contact,
            1,
            technical,
            {
                "en": "Service",
                "de": "Kundendienst",
                "pt": "Assistência técnica",
            },
            ("Sam", "Example"),
            "+49 0000 000100",
            "service@example.com",
            "https://example.com/support",
            ("en", "de", "pt"),
            {
                "en": "Fictional contact for technical questions.",
                "de": "Fiktiver Ansprechpartner für technische Fragen.",
                "pt": "Contato fictício para dúvidas técnicas.",
            },
        ),
        _contact(
            contact,
            2,
            # The ECLASS value for a commercial contact, from the
            # specification of the template: 0173-1#07-AAS928#001.
            "0173-1#07-AAS928#001",
            {"en": "Sales", "de": "Vertrieb", "pt": "Vendas"},
            ("Alex", "Demo"),
            "+49 0000 000200",
            "sales@example.com",
            "https://example.com/products/pp-6",
            ("en", "de"),
            {
                "en": "Fictional contact for offers and orders.",
                "de": "Fiktiver Ansprechpartner für Angebote und Bestellungen.",
                "pt": "Contato fictício para propostas e pedidos.",
            },
        ),
    ]
    return t.instance("ContactInformations", elements)


def software_nameplate() -> model.Submodel:
    """Builds the Software Nameplate of the controller firmware.

    Returns:
        The submodel, from the template Software Nameplate 1.0.1.
    """
    t = Template("software")
    kind = t.at("SoftwareNameplateType")
    instance = t.at("SoftwareNameplateInstance")

    def of_type(
        name: str, value: object, **extra: object
    ) -> model.SubmodelElement:
        return like(kind.get_referable(name), value, **extra)

    def of_instance(
        name: str, value: object, **extra: object
    ) -> model.SubmodelElement:
        return like(instance.get_referable(name), value, **extra)

    modules = like(
        instance.get_referable("InstalledModules"),
        children=[
            like(
                instance.get_referable("InstalledModules").get_referable(  # pyright: ignore[reportAttributeAccessIssue]
                    "InstalledModule"
                ),
                name,
                id_short=f"InstalledModule{index:02d}",
            )
            for index, name in enumerate(("motion", "gripper", "safety"), 1)
        ],
    )
    firmware = like(
        kind,
        children=[
            of_type(
                "URIOfTheProduct",
                "https://example.com/software/pp6-controller-firmware",
            ),
            of_type("ManufacturerName", {"en": COMPANY}),
            of_type(
                "ManufacturerProductDesignation",
                {
                    "en": "PP-6 controller firmware",
                    "de": "Firmware der PP-6-Steuerung",
                    "pt": "Firmware do controlador PP-6",
                },
            ),
            of_type(
                "ManufacturerProductDescription",
                {
                    "en": "Motion control, gripper control and safety functions of the PP-6 controller.",
                    "de": "Bewegungs- und Greifersteuerung und Sicherheitsfunktionen der PP-6-Steuerung.",
                    "pt": "Controle de movimento, controle da garra e funções de segurança do controlador PP-6.",
                },
            ),
            of_type(
                "ManufacturerProductFamily", {"en": "Example Arm firmware"}
            ),
            of_type("ManufacturerProductType", {"en": "CU2-FW"}),
            of_type("SoftwareType", "Firmware"),
            of_type("Version", "4.2.1"),
            of_type(
                "VersionName",
                {
                    "en": "Spring 2026",
                    "de": "Frühjahr 2026",
                    "pt": "Primavera de 2026",
                },
            ),
            of_type("ReleaseDate", datatypes.Date(2026, 3, 2)),
            of_type(
                "ReleaseNotes",
                {
                    "en": "Adds the vacuum option and the event messages.",
                    "de": "Ergänzt die Vakuumoption und die Ereignismeldungen.",
                    "pt": "Acrescenta a opção de vácuo e as mensagens de evento.",
                },
            ),
            of_type("BuildDate", datatypes.Date(2026, 2, 27)),
            of_type(
                "InstallationURI",
                "https://example.com/downloads/pp6-firmware-4.2.1.bin",
            ),
        ],
    )
    installed = like(
        instance,
        children=[
            of_instance("SerialNumber", "CU2-2026-000417"),
            of_instance("InventoryTag", "EX-ARM-0417"),
            of_instance(
                "InstanceName", f"Controller firmware of {SERIAL_NUMBER}"
            ),
            of_instance("InstalledVersion", "4.2.1"),
            of_instance("InstallationDate", datatypes.Date(2026, 3, 14)),
            of_instance("InstalledOnArchitecture", "arm64"),
            of_instance("InstalledOnOS", "Example RTOS 2.1"),
            of_instance("InstalledOnHost", "Controller CU-2"),
            modules,
        ],
    )
    return t.instance("SoftwareNameplate", [firmware, installed])


def carbon_footprint() -> model.Submodel:
    """Builds the Carbon Footprint of the arm.

    Returns:
        The submodel, from the template Carbon Footprint 1.0.1. The figure is
        made up.
    """
    t = Template("carbon")
    item = t.at("ProductCarbonFootprints", 0)

    def part(*path: str | int) -> model.SubmodelElement:
        return t.at("ProductCarbonFootprints", 0, *path)

    method_id = "0173-1#02-ABG854#003"
    unit_id = "0173-1#02-ABG856#003"
    phase_id = "0173-1#02-ABG858#003"
    phases = (
        "A1 - raw material supply (and upstream production)",
        "A2 - cradle-to-gate transport to factory",
        "A3 - production",
    )
    footprint = like(
        item,
        id_short=None,
        children=[
            like(
                part("PcfCalculationMethods"),
                children=[
                    like(
                        part("PcfCalculationMethods", 0),
                        "ISO 14067",
                        id_short=None,
                        value_id=t.coded_value(method_id, "ISO 14067"),
                    )
                ],
            ),
            like(part("PcfCO2eq"), Decimal("2150.0")),
            like(
                part("ReferenceImpactUnitForCalculation"),
                "piece",
                value_id=t.coded_value(unit_id, "piece"),
            ),
            like(part("QuantityOfMeasureForCalculation"), 1.0),
            like(
                part("LifeCyclePhases"),
                children=[
                    like(
                        part("LifeCyclePhases", 0),
                        phase,
                        id_short=None,
                        value_id=t.coded_value(phase_id, phase),
                    )
                    for phase in phases
                ],
            ),
            like(part("PublicationDate"), moment(2026, 3, 20)),
        ],
    )
    elements = [
        like(t.at("ProductCarbonFootprints"), children=[footprint]),
    ]
    return t.instance("CarbonFootprint", elements)
