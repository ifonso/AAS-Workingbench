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
    from aas_editor.package import Package
    from aas_editor.settings import package_settings  # noqa: F401
    from aas_editor.utils.util import getAttrs4detailInfo

    shown = set(getAttrs4detailInfo(Package()))

    assert {"name", "file", "numOfShells", "numOfSubmodels"} <= shown
    assert shown & INTERNALS == set()
