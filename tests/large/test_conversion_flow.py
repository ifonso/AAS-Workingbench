"""Convert an element and rebuild a list in a real package, then undo and save.

The CarbonFootprint template has a Property of the type xs:dateTime and a list
of Property whose semantic id the list fixes. Both are changed through the
context menu actions of the package tree, with the modal dialogs replaced.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR
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
    from aas_workingbench.editorApp import EditorApp
    from aas_workingbench.ui.conversion_actions import (
        register_conversion_actions,
    )

    register_conversion_actions()
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
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = view.model()
    index = proxy.index(0, 0)
    for name in names:
        for row in range(proxy.rowCount(index)):
            child = proxy.index(row, 0, index)
            if child.data(NAME_ROLE) == name:
                index = child
                break
        else:
            raise LookupError(f"{name} below {index.data()}")
    return index


def _enter(view, column: str, text: str, *names: str) -> bool:
    source = view.sourceModel()
    number = [
        source.headerData(i, Qt.Orientation.Horizontal, 0)
        for i in range(source.columnCount())
    ].index(column)
    cell = _index(view, *names).siblingAtColumn(number)
    return view.model().setData(cell, text, Qt.ItemDataRole.EditRole)


def _trigger(view, action_id: str, *names: str) -> None:
    index = _index(view, *names)
    view.setCurrentIndex(index)
    view.updateActions(index)
    view.registeredActions.find(action_id).trigger()


def _footprint(package) -> model.SubmodelElementCollection:
    (submodel,) = [
        s for s in package.submodels if s.id_short == "CarbonFootprint"
    ]
    (footprint,) = submodel.get_referable("ProductCarbonFootprints").value
    return footprint


def test_an_element_is_converted_and_a_list_rebuilt_then_undone_and_saved(
    editor, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from aas_workingbench.domain.list_settings import ListSettings
    from aas_workingbench.domain.list_settings import settings_of
    from aas_workingbench.package import Package
    from aas_workingbench.ui import replacement_dialogs

    view, package, stack = editor.view, editor.package, editor.stack
    asked: list[list[str]] = []

    monkeypatch.setattr(
        replacement_dialogs,
        "choose_target",
        lambda element, targets, parent=None: model.MultiLanguageProperty,
    )

    def confirm(title, intro, plan, updates, accept_text, parent=None) -> bool:
        asked.append([loss.what for loss in plan.losses])
        return True

    monkeypatch.setattr(replacement_dialogs, "confirm_replacement", confirm)
    assert _enter(
        view, "value", "2024-05-31T13:45:00Z", *PCF, "PublicationDate"
    )
    original = snapshot(package.objStore)
    footprint = _footprint(package)
    date = footprint.get_referable("PublicationDate")
    position = list(footprint.value).index(date)

    _trigger(view, "conversion.convert", *PCF, "PublicationDate")

    converted = footprint.get_referable("PublicationDate")
    assert isinstance(converted, model.MultiLanguageProperty)
    assert list(footprint.value).index(converted) == position
    assert dict(converted.value) == {"en": "2024-05-31T13:45:00+00:00"}
    assert asked == [["value type"]]

    methods = footprint.get_referable("PcfCalculationMethods")
    before_settings = settings_of(methods)
    monkeypatch.setattr(
        replacement_dialogs,
        "ask_list_settings",
        lambda item_list, parent=None: ListSettings(
            before_settings.element_type,
            before_settings.value_type,
            before_settings.semantic_id,
            not before_settings.order_relevant,
        ),
    )

    _trigger(view, "conversion.list_settings", *METHODS)

    rebuilt = footprint.get_referable("PcfCalculationMethods")
    assert rebuilt.order_relevant is (not before_settings.order_relevant)
    assert len(rebuilt.value) == len(methods.value)
    after_both = snapshot(package.objStore)

    stack.undo()
    stack.undo()
    assert snapshot(package.objStore) == original
    stack.redo()
    stack.redo()
    assert snapshot(package.objStore) == after_both

    target = tmp_path / "converted.aasx"
    assert view.savePack(package, target.as_posix())
    assert snapshot(Package(target).objStore) == after_both
