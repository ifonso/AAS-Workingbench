"""F-EDT-04 AC8, AC19 and AC22, through the views."""

import json

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from PyQt6.QtWidgets import QApplication
from tests.factories import make_collection
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.conftest import ELEMENT_ID
from tests.serialization import snapshot

from aas_workingbench.ui.paste_actions import register_paste_actions

# -- AC8 ---------------------------------------------------------------------


def test_a_range_refuses_a_text_that_is_no_number_and_keeps_its_limits(
    lab_class,
) -> None:
    lab = lab_class(model.Range(ELEMENT_ID, datatypes.Int, 1, 10))
    attrs = lab.attrs()

    edited = lab.set(attrs, "min", "abc")

    assert edited is False
    assert "xs:int" in lab.refusal
    assert "Traceback" not in lab.refusal
    assert (lab.element().min, lab.element().max) == (1, 10)
    assert not lab.stack.can_undo


# -- AC19 --------------------------------------------------------------------


def test_a_cut_element_pasted_into_the_input_variables_leaves_its_source(
    views,
) -> None:
    register_paste_actions()
    QApplication.clipboard().clear()
    moved = make_property("Moved")
    box = make_collection("Box", [moved])
    operation = make_operation("Op")
    submodel = make_submodel(elements=[box, operation])
    shown = views()
    package = shown.open_package(submodel)
    shown.view.treeClipboard.clear()
    before = snapshot(package.objStore)
    base = ("submodels", "Submodel")
    shown.select(shown.index(*base, "Box", "Moved"))

    shown.view.onCut()
    shown.select(shown.index(*base, "Op", "input_variable"))
    action = shown.view.registeredActions.find("structure.paste_into")
    enabled = action.isEnabled()
    action.trigger()

    assert enabled
    assert [m.id_short for m in box.value] == []
    assert [v.id_short for v in operation.input_variable] == ["Moved"]
    assert len(operation.output_variable) == 0
    assert len(operation.in_output_variable) == 0
    package.commandStack.undo()
    package.commandStack.undo()
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


# -- AC22 --------------------------------------------------------------------


def test_a_list_without_order_relevant_in_the_file_shows_the_default(
    views, tmp_path
) -> None:
    from aas_workingbench.package import Package
    from aas_workingbench.settings.app_settings import NAME_ROLE

    document = {
        "submodels": [
            {
                "modelType": "Submodel",
                "id": "urn:sm:1",
                "idShort": "Sub",
                "submodelElements": [
                    {
                        "modelType": "SubmodelElementList",
                        "idShort": "List",
                        "typeValueListElement": "Property",
                        "valueTypeListElement": "xs:string",
                    }
                ],
            }
        ]
    }
    path = tmp_path / "list.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    shown = views()
    shown.table.addItem(Package(path))

    attrs = shown.attrs_view("submodels", "Sub", "List")
    proxy = attrs.model()
    shown_values = {
        proxy.index(row, 0).data(NAME_ROLE): proxy.index(row, 1).data()
        for row in range(proxy.rowCount())
    }

    assert shown_values["order_relevant"] == "True"


_ = pytest
