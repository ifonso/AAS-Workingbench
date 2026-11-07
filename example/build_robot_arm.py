"""Builds example/robot_arm_pick_and_place.aasx.

The package describes a fictional six-axis arm, the "Workingbench Example Arm
PP-6", that picks parts and places them. Everything in it is made up here:
the data, the pictures, the PDF files. The structure follows the IDTA
submodel templates that the editor bundles wherever one fits, and the rest is
the example's own, described by concept descriptions in the package.

Run it from the root of the repository:

    uv run python example/build_robot_arm.py

It writes the AASX file next to this script, or to the path that `--output`
gives. The model code is in the `arm_*.py` modules next to it.
"""

import argparse
from dataclasses import dataclass
import datetime
import io
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXWriter
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from pyecma376_2 import OPCCoreProperties

from arm_concepts import CONCEPTS
from arm_concepts import concept_description
from arm_files import datasheet
from arm_files import draw_arm
from arm_files import draw_envelope
from arm_files import draw_logo
from arm_files import draw_marking
from arm_files import draw_thumbnail
from arm_files import quickstart
from arm_helpers import AAS_ID
from arm_helpers import ASSET_ID
from arm_helpers import ASSET_TYPE
from arm_helpers import DATASHEET_PATH
from arm_helpers import ENVELOPE_PATH
from arm_helpers import LOGO_PATH
from arm_helpers import MANUFACTURER_ID
from arm_helpers import MARKING_PATH
from arm_helpers import PICTURE_PATH
from arm_helpers import QUICKSTART_DE_PATH
from arm_helpers import QUICKSTART_PATH
from arm_helpers import SERIAL_NUMBER
from arm_helpers import THUMBNAIL_PATH
from arm_helpers import external
from arm_helpers import fictional
from arm_helpers import names
from arm_helpers import reference_to
from arm_helpers import semantics_of
from arm_helpers import texts
from arm_identity import carbon_footprint
from arm_identity import contact_information
from arm_identity import nameplate
from arm_identity import software_nameplate
from arm_links import link_all
from arm_runtime import documentation
from arm_runtime import operational_data
from arm_runtime import temperature_history
from arm_skills import capabilities
from arm_skills import cycle_behavior
from arm_skills import pick_and_place_job
from arm_skills import station
from arm_structure import entry_node
from arm_structure import hierarchical_structure
from arm_technical import handover_documentation
from arm_technical import technical_data
from arm_templates import Template
from arm_templates import concept_named
from arm_templates import concept_of

PACKAGE_THUMBNAIL = "/docProps/thumbnail.png"
OUTPUT = Path(__file__).with_name("robot_arm_pick_and_place.aasx")


@dataclass
class Example:
    """Everything that goes into the AASX file.

    Attributes:
        objects: The shell, the submodels and the concept descriptions.
        files: The supplementary files of the package.
        thumbnail: The PNG of the package thumbnail.
    """

    objects: model.DictIdentifiableStore[model.Identifiable]
    files: DictSupplementaryFileContainer
    thumbnail: bytes


def _files() -> DictSupplementaryFileContainer:
    files = DictSupplementaryFileContainer()
    for path, data, content_type in (
        (PICTURE_PATH, draw_arm(), "image/png"),
        (ENVELOPE_PATH, draw_envelope(), "image/png"),
        (THUMBNAIL_PATH, draw_thumbnail(), "image/png"),
        (LOGO_PATH, draw_logo(), "image/png"),
        (MARKING_PATH, draw_marking(), "image/png"),
        (DATASHEET_PATH, datasheet(), "application/pdf"),
        (QUICKSTART_PATH, quickstart("en"), "application/pdf"),
        (QUICKSTART_DE_PATH, quickstart("de"), "application/pdf"),
    ):
        files.add_file(path, io.BytesIO(data), content_type)
    return files


def _shell() -> model.AssetAdministrationShell:
    nameplate_template = Template("nameplate")
    manufacturer = external(MANUFACTURER_ID)
    information = model.AssetInformation(
        asset_kind=model.AssetKind.INSTANCE,
        global_asset_id=ASSET_ID,
        specific_asset_id=[
            model.SpecificAssetId(
                "SerialNumber",
                SERIAL_NUMBER,
                external_subject_id=manufacturer,
                semantic_id=nameplate_template.at("SerialNumber").semantic_id,
            ),
            model.SpecificAssetId(
                "ManufacturerPartId",
                "PP6-100-0001",
                external_subject_id=manufacturer,
                semantic_id=nameplate_template.at(
                    "ProductArticleNumberOfManufacturer"
                ).semantic_id,
            ),
            model.SpecificAssetId(
                "ControllerSerialNumber",
                "CU2-2026-000417",
                external_subject_id=manufacturer,
            ),
        ],
        asset_type=ASSET_TYPE,
        default_thumbnail=model.Resource(THUMBNAIL_PATH, "image/png"),
    )
    return model.AssetAdministrationShell(
        information,
        AAS_ID,
        id_short="PP6RoboticArm",
        display_name=names(
            "Workingbench Example Arm PP-6, serial PP6-2026-000417",
            "Workingbench Beispiel-Arm PP-6, Seriennummer PP6-2026-000417",
            "Braço de exemplo Workingbench PP-6, série PP6-2026-000417",
        ),
        description=texts(
            "Fictional six-axis robot arm for pick and place. The data is made up for an example.",
            "Fiktiver sechsachsiger Roboterarm für Pick-and-Place. Die Daten sind für ein Beispiel erfunden.",
            "Braço robótico fictício de seis eixos para pegar e colocar. Os dados são inventados para um exemplo.",
        ),
        administration=model.AdministrativeInformation(
            version="1", revision="0", creator=manufacturer
        ),
        extension=[fictional()],
    )


def build() -> Example:
    """Builds the package in memory.

    Returns:
        The objects, the files and the thumbnail of the package.
    """
    bill = hierarchical_structure()
    handover = handover_documentation(entry_node(bill))
    submodels = [
        nameplate(),
        contact_information(),
        technical_data(),
        handover,
        bill,
        capabilities(),
        cycle_behavior(),
        pick_and_place_job(),
        station(),
        operational_data(),
        temperature_history(),
        software_nameplate(),
        carbon_footprint(),
        documentation(),
    ]
    by_name = {submodel.id_short: submodel for submodel in submodels}
    link_all(by_name)
    shell = _shell()
    for submodel in submodels:
        shell.submodel.add(reference_to(submodel))
    objects: model.DictIdentifiableStore[model.Identifiable] = (
        model.DictIdentifiableStore()
    )
    objects.add(shell)
    for submodel in submodels:
        objects.add(submodel)
    for submodel in submodels:
        # The semantic id of a template submodel names a concept description of
        # the template, so the description comes along.
        reference = submodel.semantic_id
        if isinstance(reference, model.ModelReference):
            imported = concept_of(reference)
            if imported is None:
                # Three templates name a description that they do not carry.
                # The value stays, as a reference to a global thing.
                submodel.semantic_id = external(reference.key[-1].value)
            else:
                # Some templates give the key the type Submodel, but the
                # object is a concept description, so the key is retyped.
                submodel.semantic_id = model.ModelReference(
                    (
                        model.Key(
                            model.KeyTypes.CONCEPT_DESCRIPTION, imported.id
                        ),
                    ),
                    model.ConceptDescription,
                )
                if imported.id not in objects:
                    objects.add(imported)
    # The semantic ids that the templates define come with the descriptions
    # that the templates carry for them, so that a reader finds the meaning
    # in the package.
    for submodel in submodels:
        for reference in semantics_of(submodel):
            wanted = "".join(reference.key[-1].value.split())
            if any(wanted == obj.id for obj in objects):
                continue
            imported = concept_named(wanted)
            if imported is not None:
                objects.add(imported)
    for entry in CONCEPTS.values():
        objects.add(concept_description(entry))
    return Example(objects, _files(), draw_thumbnail())


def write(example: Example, target: Path) -> None:
    """Writes the package as an AASX file.

    Args:
        example: The package.
        target: The file to write.
    """
    properties = OPCCoreProperties()
    properties.title = "Workingbench Example Arm PP-6 (fictional example)"
    properties.creator = "AAS Workingbench example"
    properties.description = (
        "A fictional six-axis arm for pick and place, built by "
        "example/build_robot_arm.py."
    )
    properties.created = datetime.datetime(2026, 11, 6, tzinfo=datetime.UTC)
    with AASXWriter(str(target)) as writer:
        writer.write_all_aas_objects(
            "/aasx/data.xml", example.objects, example.files, write_json=False
        )
        writer.write_thumbnail(
            PACKAGE_THUMBNAIL, bytearray(example.thumbnail), "image/png"
        )
        writer.write_core_properties(properties)


def main() -> None:
    """Builds the package and writes it."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    write(build(), arguments.output)
    print(f"Wrote {arguments.output}")


if __name__ == "__main__":
    main()
