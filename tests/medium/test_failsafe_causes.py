"""Why 49 of the 132 bundled templates open only in failsafe mode.

D6 treats every package that is opened through the failsafe branch as partial,
because the SDK does not report what it skipped. These tests pin the causes for
the whole corpus, so the table in `docs/software/validation.md` is
reproducible, and so that a change of the SDK or of the templates shows up.

The finding behind the decision not to reduce D6: the largest cause, objects
that share an id, never leaves a package whose only loss is an equal copy.
Every package with a shared id also loses a different concept description, or
a concept description that has the id of the submodel. No reader option of the
SDK keeps both objects, because the store holds one object for each id.
"""

from pathlib import Path

import pytest
from tests.medium.failsafe_causes import DUPLICATE_ID
from tests.medium.failsafe_causes import duplicate_summary
from tests.medium.failsafe_causes import relative_name
from tests.medium.failsafe_causes import skipped_summary
from tests.medium.failsafe_causes import strict_cause
from tests.medium.failsafe_causes import templates

# The first error that a strict read raises, for each template that does not
# open strictly. The other 83 templates open strictly.
STRICT_CAUSES: dict[str, str] = {
    "Artificial Intelligence Deployment/1/0/1/IDTA 02059-1-0-1_Template_AIDeployment.aasx": "duplicate id",
    "Artificial Intelligence Deployment/1/0/1/IDTA 02059-1-0-1_Template_AIDeployment_forAASMetamodelV3.1.aasx": "duplicate id",
    "Artificial Intelligence Deployment/1/0/IDTA 02059-1-0_Template_AIDeployment.aasx": "duplicate id",
    "Artificial Intelligence Model Nameplate/1/0/1/IDTA 02060-1-0-1_Template_AIModelNameplate.aasx": "duplicate id",
    "Artificial Intelligence Model Nameplate/1/0/1/IDTA 02060-1-0-1_Template_AIModelNameplate_forAASMetamodelV3.1.aasx": "duplicate id",
    "Artificial Intelligence Model Nameplate/1/0/IDTA 02060-1-0_Template_AIModelNameplate.aasx": "duplicate id",
    "Creation and Classification of Materials/1/0/1/IDTA 02034-1-0-1 Template_BackendSpecificMaterialInformation.aasx": "duplicate id",
    "Creation and Classification of Materials/1/0/1/IDTA 02034-1-0-1 Template_BackendSpecificMaterialInformation_forAASMetamodelV3.1.aasx": "duplicate id",
    "Creation and Classification of Materials/1/0/IDTA 02034-1-0 Template_BackendSpecificMaterialInformation.aasx": "AASd-131",
    "DEXPI/1/0/IDTA 02012-1-0_Template_DEXPI.aasx": "AASd-123",
    "Handover Documentation/2/0/1/IDTA 02004-2-0-1_Template_sample_HandoverDocumentation_forAASMetamodelV3.1.aasx": "AASd-022",
    "Handover Documentation/2/0/1/IDTA 02004-2-0_Template_sample_HandoverDocumentation.aasx": "AASd-022",
    "Handover Documentation/2/0/IDTA 02004-2-0_Example_HandoverDocumentation.aasx": "AASd-109",
    "Hierarchical Structures enabling Bills of Material/1/0/IDTA 02011-1-0_Template_HierarchicalStructuresEnablingBoM.aasx": "AASd-014",
    "Hierarchical Structures enabling Bills of Material/1/1/IDTA 02011-1-1_Template_HSEBoM.aasx": "AASd-123",
    "Hierarchical Structures enabling Bills of Material/Extension based on IEC 81346/1/0/1/IDTA 02011-1-1-1 _Template_BoM_ExtensionbasedonIEC81346.aasx": "AASd-014",
    "Hierarchical Structures enabling Bills of Material/Extension based on IEC 81346/1/0/1/IDTA 02011-1-1-1 _Template_BoM_ExtensionbasedonIEC81346_forAASMetamodelV3.1.aasx": "AASd-014",
    "Hierarchical Structures enabling Bills of Material/Extension based on IEC 81346/1/0/IDTA 02011-1_Template_BoM_ExtensionbasedonIEC81346.aasx": "AASd-014",
    "Maintenance Instructions/1/0/IDTA_02018_Template_MaintenanceInstructions.aasx": "invalid enumeration text",
    "MTP/1/0/IDTA 02001-1-0_Subomdel_MTPv1.0-rc2-with-documentation.aasx": "empty text",
    "Plant Asset Management Specification Sheet/1/0/1/IDTA 02019-1-0-1_Template_PlantAssetManagement.aasx": "AASd-021",
    "Plant Asset Management Specification Sheet/1/0/IDTA 02019-1-0-1_Template_PlantAssetManagement_forAASMetamodelV3.1.aasx": "AASd-021",
    "Plant Asset Management Specification Sheet/1/0/IDTA 02019-1-0_Template_PlantAssetManagement.aasx": "AASd-021",
    "Plastic and Rubber Moulds/Part 1 Identification/1/0/IDTA 02038-1_Template_Plastic and Rubber Moulds-Identification.aasx": "duplicate id",
    "Plastic and Rubber Moulds/Part 1 Identification/1/0/IDTA 02038-1_Template_Plastic and Rubber Moulds-Identification_forAASMetamodelV3.1.aasx": "duplicate id",
    "Predictive Maintenance/1/0/IDTA 02048_Template_PredictiveMaintenance.aasx": "duplicate id",
    "Predictive Maintenance/1/0/IDTA 02048_Template_PredictiveMaintenance_forAASMetamodelV3.1.aasx": "duplicate id",
    "Process Parameters Instance/1/0/IDTA 02031-2_Template_ProcessParameters_Instance.aasx": "duplicate id",
    "Process Parameters Instance/1/0/IDTA 02031-2_Template_ProcessParameters_Instance_forAASMetamodelV3.1.aasx": "duplicate id",
    "Process Parameters Type/1/0/IDTA 02031-1_Template_ProcessParameters_Type.aasx": "duplicate id",
    "Process Parameters Type/1/0/IDTA 02031-1_Template_ProcessParameters_Type_forAASMetamodelV3.1.aasx": "duplicate id",
    "Production Calendar/1/0/IDTA 02067_Template_ProductionCalendar.aasx": "duplicate id",
    "Production Calendar/1/0/IDTA 02067_Template_ProductionCalendar_forAASMetamodelV3.1.aasx": "duplicate id",
    "Purchase Order/1/0/IDTA-02050_Template_PurchaseOrder.aasx": "duplicate id",
    "Purchase Order/1/0/IDTA-02050_Template_PurchaseOrder_forAASMetamodelV3.1.aasx": "duplicate id",
    "Quality Control for Machining/1/0/IDTA_02049_Template_QualityControlForMachining.aasx": "duplicate id",
    "sensor4.0/Part 1 Measurement Value/1/0/IDTA 02029-1_Template_Sensor4.0_MeasurementValue.aasx": "duplicate id",
    "Technical Data for Automated Guided Vehicles/1/0/1/IDTA 02047-1-0-1 Template_TechnicalDataForAGV.aasx": "duplicate id",
    "Technical Data for Automated Guided Vehicles/1/0/1/IDTA 02047-1-0-1 Template_TechnicalDataForAGV_forAASMetamodelV3.1.aasx": "duplicate id",
    "Technical Data for Automated Guided Vehicles/1/0/IDTA 02047-1-0 Template_TechnicalDataForAGV.aasx": "duplicate id",
    "Technical_Data/1/2/1/IDTA_02003-1-2-1_Template_TechnicalData.aasx": "duplicate id",
    "Technical_Data/1/2/1/IDTA_02003-1-2-1_Template_TechnicalData_forAASMetamodelV3.1.aasx": "duplicate id",
    "Technical_Data/1/2/IDTA_02003-1-2_Template_TechnicalData.aasx": "duplicate id",
    "Technical_Data/2/0/1/IDTA 02003_Sample_TechnicalData.aasx": "AASd-022",
    "Technical_Data/2/0/1/IDTA 02003_Sample_TechnicalData_forAASMetamodelV3.1.aasx": "AASd-022",
    "Technical_Data/2/0/IDTA 02003_Sample_TechnicalData.aasx": "AASd-002",
    "Technical_Data/2/0/IDTA 02003_Template_TechnicalData.aasx": "AASd-021",
    "Wireless Communication/1/0/1/IDTA 02022-1-0-1_Template_Wireless Communication.aasx": "duplicate id",
    "Wireless Communication/1/0/1/IDTA 02022-1-0-1_Template_Wireless Communication_forAASMetamodelV3.1.aasx": "duplicate id",
}  # fmt: skip

# What failsafe mode logs while it reads those 49 packages, by cause:
# (packages with the cause, objects or parts dropped for it).
SKIPPED: dict[str, tuple[int, int]] = {
    "duplicate id": (30, 83),
    "AASd-022": (5, 5),
    "AASd-109": (4, 9),
    "AASd-014": (4, 4),
    "AASd-021": (4, 4),
    "empty text": (3, 16),
    "AASd-118": (3, 3),
    "AASd-123": (2, 17),
    "reference without keys": (2, 2),
    "AASd-131": (1, 1),
    "AASd-127": (1, 43),
    "invalid enumeration text": (1, 1),
    "short name over 18 characters": (1, 2),
    "missing mandatory child": (1, 2),
    "value not parseable for its type": (1, 2),
    "AASd-002": (1, 6),
}


@pytest.mark.parametrize("path", templates(), ids=relative_name)
def test_strict_reading_fails_with_the_documented_cause_when_a_template_is_read(
    path: Path,
) -> None:
    assert strict_cause(path) == STRICT_CAUSES.get(relative_name(path))


def test_forty_nine_templates_need_the_failsafe_branch() -> None:
    assert len(STRICT_CAUSES) == 49


def test_failsafe_reading_drops_what_the_documentation_lists() -> None:
    assert skipped_summary(list(STRICT_CAUSES)) == SKIPPED


def test_no_package_loses_only_equal_copies_when_objects_share_an_id() -> None:
    names = [n for n, cause in STRICT_CAUSES.items() if cause == DUPLICATE_ID]

    totals = duplicate_summary(names)

    assert totals.packages == 30
    assert totals.identical == 32
    assert totals.different == 24
    assert totals.submodel_and_concept == 25
    assert totals.only_equal_packages == 0
