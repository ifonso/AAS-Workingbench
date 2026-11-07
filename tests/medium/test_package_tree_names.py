"""The package tree reads in the words of the AAS, and is found by the SDK's names.

The nodes that group objects (`shells`, `concept_descriptions`, `fileStore`,
`input_variable`) are found by the name of the attribute of the SDK, and that
name is the lookup key. What a person reads is a separate display text.
"""

from typing import Any

from PyQt6.QtCore import Qt
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_concept_description
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

TYPE_COLUMN = 2
FILE = "/aasx/files/data.txt"


@pytest.fixture
def shown(views: Any) -> Any:
    package_views = views()
    package_views.open_package(
        make_shell(),
        make_submodel(
            elements=[
                make_property("Speed"),
                make_operation(
                    "Start",
                    input_variables=[make_property("In1")],
                    output_variables=[make_property("Out1")],
                ),
            ]
        ),
        make_concept_description(),
        files={FILE: (b"data", "text/plain")},
    )
    return package_views


def _children(shown: Any, role: int, *names: str) -> list[Any]:
    proxy = shown.view.model()
    parent = shown.index(*names)
    return [
        proxy.index(row, 0, parent).data(role)
        for row in range(proxy.rowCount(parent))
    ]


def _type_of(shown: Any, *names: str) -> Any:
    return shown.index(*names).siblingAtColumn(TYPE_COLUMN).data()


def test_the_groups_of_a_package_read_in_words_of_the_aas(shown: Any) -> None:
    shown.view.expandAll()

    texts = _children(shown, Qt.ItemDataRole.DisplayRole)

    assert texts == [
        "Asset Administration Shells",
        "Submodels",
        "Concept Descriptions",
        "Files",
    ]


def test_the_groups_are_still_found_by_the_name_of_the_sdk(shown: Any) -> None:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    names = _children(shown, NAME_ROLE)

    assert names == ["shells", "submodels", "concept_descriptions", "fileStore"]


def test_a_group_has_no_type_and_an_object_has_its_aas_class(
    shown: Any,
) -> None:
    assert _type_of(shown, "shells") == ""
    assert _type_of(shown, "submodels") == ""
    assert _type_of(shown, "submodels", "Submodel") == "Submodel"
    assert _type_of(shown, "submodels", "Submodel", "Speed") == "Property"
    assert shown.index().siblingAtColumn(TYPE_COLUMN).data() == "Package"


def test_the_python_class_of_a_group_is_not_in_any_type_cell(
    shown: Any,
) -> None:
    shown.view.expandAll()
    proxy = shown.view.model()
    package = proxy.index(0, 0)

    texts = [
        proxy.index(row, TYPE_COLUMN, package).data()
        for row in range(proxy.rowCount(package))
    ]

    assert not [text for text in texts if "Set" in text or "Dict" in text], (
        texts
    )


def test_a_file_is_a_supplementary_file(shown: Any) -> None:
    assert _type_of(shown, "fileStore", FILE) == "SupplementaryFile"


def test_the_variables_of_an_operation_read_as_the_metamodel_names_them(
    shown: Any,
) -> None:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    path = ("submodels", "Submodel", "Start")

    texts = _children(shown, Qt.ItemDataRole.DisplayRole, *path)
    names = _children(shown, NAME_ROLE, *path)

    assert texts == ["inputVariable", "outputVariable", "inoutputVariable"]
    assert names == ["input_variable", "output_variable", "in_output_variable"]


def test_a_group_tells_what_it_holds_in_a_tooltip(shown: Any) -> None:
    index = shown.index("concept_descriptions")

    tip = index.data(Qt.ItemDataRole.ToolTipRole)

    assert tip.startswith("Concept Descriptions")
    assert "concept descriptions" in tip


def test_a_group_counts_its_objects_in_the_value_column(shown: Any) -> None:
    index = shown.index("submodels")

    assert index.siblingAtColumn(1).data() == "1 submodel"


def test_an_object_that_is_not_a_group_reads_its_id_short(shown: Any) -> None:
    assert shown.index("submodels", "Submodel", "Speed").data() == "Speed"


def test_the_tab_of_a_group_is_titled_as_the_tree_names_it(
    shown: Any, qtbot: QtBot
) -> None:
    from aas_workingbench.widgets.tab import TabWidget

    tab_widget = TabWidget(unclosable=True)
    qtbot.addWidget(tab_widget)
    tab_widget.addTab(tab_widget.tabCls(parent=tab_widget), "Welcome")

    tab_widget.openItemInNewTab(shown.index("concept_descriptions"))

    assert tab_widget.tabText(tab_widget.count() - 1) == "Concept Descriptions"
