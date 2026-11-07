"""What the tab of a package shows, and what is the program's own business."""

INTERNALS = {
    "changeMarks",
    "objStore",
    "saveGate",
    "sortKeysInJson",
    "writeJsonInAasx",
    "writePrettyJson",
}


def test_the_tab_of_a_package_shows_its_facts_and_not_its_internals(
    qapp,
) -> None:
    from aas_workingbench.package import Package
    from aas_workingbench.settings import package_settings  # noqa: F401
    from aas_workingbench.utils.util import getAttrs4detailInfo

    shown = set(getAttrs4detailInfo(Package()))

    assert {"name", "file", "numOfShells", "numOfSubmodels"} <= shown
    assert shown & INTERNALS == set()


def test_the_core_properties_show_their_fields_and_not_the_class_tables(
    qapp,
) -> None:
    from pyecma376_2 import OPCCoreProperties

    from aas_workingbench.settings import package_settings  # noqa: F401
    from aas_workingbench.utils.util import getAttrs4detailInfo

    shown = set(getAttrs4detailInfo(OPCCoreProperties()))

    assert {"title", "creator", "created"} <= shown
    assert shown & {"ATTRIBUTES", "ATTRIBUTES_BY_TAG", "NSMAP"} == set()
