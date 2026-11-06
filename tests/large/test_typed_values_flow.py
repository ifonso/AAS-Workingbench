"""Enter typed values in a real package, then undo, save, and read it again.

The CarbonFootprint template has Properties of the types xs:decimal, xs:double,
xs:dateTime, and xs:anyURI, and lists of Property whose semantic id the list
fixes. The values are entered through the cells of the package tree and the add
dialog of a list, as a user does, with the modal dialogs replaced.
"""

import datetime
import decimal
from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR
from tests.medium.forms import Form
from tests.medium.forms import answering
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
SUBMODEL = ("submodels", "CarbonFootprint")
PCF = (*SUBMODEL, "ProductCarbonFootprints", "SubmodelElementCollection")
METHODS = (*PCF, "PcfCalculationMethods")


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path):
    """The main window with the template, copied so that a save is harmless."""
    from aas_editor.editorApp import EditorApp

    source = tmp_path / PACKAGE
    shutil.copy(TEST_DATA_DIR / PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    shown = SimpleNamespace()
    shown.window = window
    shown.view = window.mainTreeView
    (shown.package,) = window.packTreeModel.openedPacks()
    shown.stack = shown.package.commandStack
    yield shown
    shown.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _index(view, *names: str) -> QModelIndex:
    proxy = view.model()
    index = proxy.index(0, 0)
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(Qt.ItemDataRole.DisplayRole) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def _cell(view, column: str, *names: str) -> QModelIndex:
    source = view.sourceModel()
    number = [
        source.headerData(i, Qt.Orientation.Horizontal, 0)
        for i in range(source.columnCount())
    ].index(column)
    return _index(view, *names).siblingAtColumn(number)


def _enter(view, column: str, text: object, *names: str) -> bool:
    return view.model().setData(
        _cell(view, column, *names), text, Qt.ItemDataRole.EditRole
    )


def _footprint(package) -> model.SubmodelElementCollection:
    """The one product carbon footprint in the list of the template."""
    (submodel,) = [
        s for s in package.submodels if s.id_short == "CarbonFootprint"
    ]
    footprints = submodel.get_referable("ProductCarbonFootprints")
    (footprint,) = footprints.value
    return footprint


def test_typed_values_are_entered_refused_converted_and_saved(
    editor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_editor.dialogs import EditObjDialog
    from aas_editor.package import Package

    view, package, stack = editor.view, editor.package, editor.stack
    original = snapshot(package.objStore)
    model_of_view = view.sourceModel()

    # Valid text becomes a value of the type of each Property.
    assert _enter(view, "value", "12.50", *PCF, "PcfCO2eq")
    assert _enter(
        view, "value", "1.5E3", *PCF, "QuantityOfMeasureForCalculation"
    )
    assert _enter(
        view, "value", "2024-05-31T13:45:00Z", *PCF, "PublicationDate"
    )
    assert _enter(
        view, "value", "2025-01-01T00:00:00+02:00", *PCF, "ExpirationDate"
    )
    assert _enter(
        view,
        "value",
        "https://example.com/pcf",
        *(*SUBMODEL, "ProductOrSectorSpecificCarbonFootprints"),
        "SubmodelElementCollection",
        "ExternalPcfApi",
        "PcfApiEndpoint",
    )
    footprint = _footprint(package)
    carbon = footprint.get_referable("PcfCO2eq")
    assert carbon.value == decimal.Decimal("12.50")
    assert isinstance(carbon.value, decimal.Decimal)
    quantity = footprint.get_referable("QuantityOfMeasureForCalculation")
    assert quantity.value == 1500.0
    published = footprint.get_referable("PublicationDate")
    assert published.value == datetime.datetime(
        2024, 5, 31, 13, 45, tzinfo=datetime.UTC
    )
    expires = footprint.get_referable("ExpirationDate")
    assert expires.value.utcoffset() == datetime.timedelta(hours=2)
    assert stack.can_undo

    # Text that is no value of the type is refused with the reason.
    steps_before = snapshot(package.objStore)
    assert not _enter(view, "value", "twelve", *PCF, "PcfCO2eq")
    assert model_of_view.lastErrorMsg.startswith(
        "'twelve' is not a valid xs:decimal"
    )
    assert not _enter(view, "value", "tomorrow", *PCF, "PublicationDate")
    assert "xs:dateTime" in model_of_view.lastErrorMsg
    assert not _enter(
        view, "value", "1e999", *PCF, "QuantityOfMeasureForCalculation"
    )
    assert "too large for xs:double" in model_of_view.lastErrorMsg
    assert snapshot(package.objStore) == steps_before

    # Changing the type converts the value, or is refused and changes nothing.
    assert _enter(view, "value_type", datatypes.Double, *PCF, "PcfCO2eq")
    assert carbon.value_type is datatypes.Double
    assert carbon.value == 12.5
    assert _enter(view, "value_type", datatypes.Decimal, *PCF, "PcfCO2eq")
    assert not _enter(view, "value_type", datatypes.Int, *PCF, "PcfCO2eq")
    assert "xs:int" in model_of_view.lastErrorMsg
    assert carbon.value_type is datatypes.Decimal

    # A new child of a list gets the semantic id and the type of the list.
    methods = footprint.get_referable("PcfCalculationMethods")
    list_semantic_id = methods.semantic_id_list_element
    children_before = len(methods.value)

    def fill_child(form: Form) -> None:
        keys = form.widget("semantic_id").widget.paramWidgets["key"]
        assert keys.inputWidgets[0].paramWidgets["value"].widget.text() == (
            "0173-1#02-ABG854#003"
        )
        assert not form.has("value_type")
        form.type_text("value", "GHG Protocol")

    parent = _index(view, *METHODS)
    view.setCurrentIndex(parent)
    with answering(monkeypatch, EditObjDialog, lambda d: fill_child(Form(d))):
        view.onAddAct(parent)
    assert len(methods.value) == children_before + 1
    added = list(methods.value)[-1]
    assert added.value == "GHG Protocol"
    assert added.semantic_id == list_semantic_id

    edited = snapshot(package.objStore)
    assert edited != original
    assert "generated_submodel_list_hack_" not in edited

    # The saved file holds the edits, and nothing of the hidden names.
    saved = tmp_path / "saved.aasx"
    assert view.savePack(package, saved.as_posix())
    assert snapshot(Package(saved).objStore) == edited

    # Undo gives back the package as it was read, and redo the edits again.
    while stack.can_undo:
        stack.undo()
    assert snapshot(package.objStore) == original
    while stack.can_redo:
        stack.redo()
    assert snapshot(package.objStore) == edited
