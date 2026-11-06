"""Validation in the running editor: the dock, the save gate, and the marker.

A real template is opened in the main window. An element gets a one-letter
idShort, which the SDK accepts and AASd-002 refuses. The dock shows the error,
a double click goes to the element, the save asks once, and the changed marker
follows the saved state. The modal dialogs are replaced.
"""

from pathlib import Path
import shutil
from types import SimpleNamespace

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
SUBMODEL = ("submodels", "CarbonFootprint")


@pytest.fixture
def editor(qapp: object, qtbot, tmp_path: Path, monkeypatch):
    """The main window with the template, copied so that a save is harmless."""
    from aas_editor.editorApp import EditorApp

    asked: list[object] = []
    monkeypatch.setattr(
        "aas_editor.treeviews.treeview_pack.confirm_save",
        lambda check, parent=None, extra=None: asked.append(check) or True,
    )
    source = tmp_path / PACKAGE
    shutil.copy(TEST_DATA_DIR / PACKAGE, source)
    window = EditorApp(fileToOpen=source.as_posix())
    qtbot.addWidget(window)
    window.show()
    window.mainTreeView.expandAll()

    shown = SimpleNamespace()
    shown.window = window
    shown.view = window.mainTreeView
    shown.dock = window.validationController.dock
    (shown.package,) = window.packTreeModel.openedPacks()
    shown.stack = shown.package.commandStack
    shown.asked = asked
    yield shown
    shown.stack.mark_saved()
    window._recoveryTimer.stop()
    window.close()


def _index(view, *names: str) -> QModelIndex:
    from aas_editor.settings.app_settings import NAME_ROLE

    # By the name that the editor finds a row by. The text of the tree is the
    # AAS word, such as `Submodels`.
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


def _rename_first_element(editor) -> object:
    (submodel,) = list(editor.package.submodels)
    first = next(iter(submodel.submodel_element))
    column = [
        editor.view.sourceModel().headerData(i, Qt.Orientation.Horizontal, 0)
        for i in range(editor.view.sourceModel().columnCount())
    ].index("id_short")
    index = _index(editor.view, *SUBMODEL, first.id_short)
    editor.view.model().setData(
        index.siblingAtColumn(column), "Q", Qt.ItemDataRole.EditRole
    )
    return first


def _error_findings(dock) -> list[object]:
    return [f for f in dock.report.findings if f.rule_id == "AASd-002"]


def test_dock_save_gate_and_marker_work_on_a_real_package(
    editor, qtbot
) -> None:
    from PyQt6.QtGui import QColor

    from aas_editor.domain.design_tokens import LIGHT
    from aas_editor.settings.app_settings import OBJECT_ROLE

    editor.dock.show()
    qtbot.waitUntil(editor.dock.isVisible, timeout=2000)
    assert editor.dock.package is editor.package
    assert _error_findings(editor.dock) == []
    assert not editor.window.isWindowModified()

    # An edit gives an error, which the dock shows after the debounce.
    renamed = _rename_first_element(editor)
    assert renamed.id_short == "Q"
    qtbot.waitUntil(
        lambda: len(_error_findings(editor.dock)) == 1, timeout=3000
    )
    row = _index(editor.view, *SUBMODEL, "Q")
    assert row.data(Qt.ItemDataRole.ForegroundRole) == QColor(
        LIGHT.mark_changed
    )
    assert editor.window.isWindowModified()

    # A double click on the finding selects its element in the package tree.
    editor.view.setCurrentIndex(_index(editor.view, *SUBMODEL))
    editor.view.collapseAll()
    rule_row = [f.rule_id for f in editor.dock.visible_findings()].index(
        "AASd-002"
    )
    editor.dock.activate_row(rule_row)
    assert editor.view.currentIndex().data(OBJECT_ROLE) is renamed

    # The save asks once about the error, and the marker is gone afterwards.
    assert editor.view.savePack(editor.package)
    assert len(editor.asked) == 1
    assert editor.asked[0].warnings[0].message.startswith("AASd-002")
    assert not editor.window.isWindowModified()
    assert (
        _index(editor.view, *SUBMODEL, "Q").data(Qt.ItemDataRole.ForegroundRole)
        is None
    )
    assert editor.view.savePack(editor.package)
    assert len(editor.asked) == 1

    # Undo goes back past the saved state: the error and the marker follow.
    editor.stack.undo()
    qtbot.waitUntil(lambda: _error_findings(editor.dock) == [], timeout=3000)
    assert editor.window.isWindowModified()
    assert _index(editor.view, *SUBMODEL, renamed.id_short).data(
        Qt.ItemDataRole.ForegroundRole
    ) == QColor(LIGHT.mark_changed)
    editor.stack.redo()
    assert not editor.window.isWindowModified()
    assert (
        _index(editor.view, *SUBMODEL, "Q").data(Qt.ItemDataRole.ForegroundRole)
        is None
    )


def test_closing_the_package_clears_the_dock(
    editor, qtbot, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.widgets.tab import TabWidget

    # Tab widgets of windows that earlier tests closed stay in this list.
    monkeypatch.setattr(
        TabWidget, "openedTabWidgets", [editor.window.mainTabWidget]
    )
    editor.dock.show()
    qtbot.waitUntil(editor.dock.isVisible, timeout=2000)
    _rename_first_element(editor)
    qtbot.waitUntil(
        lambda: len(_error_findings(editor.dock)) == 1, timeout=3000
    )
    editor.stack.mark_saved()

    editor.view.closeFile(_index(editor.view))

    assert editor.dock.package is None
    assert editor.dock.visible_findings() == []


def test_read_mode_hides_the_null_rows_of_a_tab_and_edit_mode_shows_them(
    editor,
) -> None:
    from aas_editor.application.editing import edit_mode

    (submodel,) = list(editor.package.submodels)
    first = next(iter(submodel.submodel_element))
    editor.window.mainTabWidget.openItemInNewTab(
        _index(editor.view, *SUBMODEL, first.id_short)
    )
    model_ = editor.window.mainTabWidget.currentWidget().attrsTreeView.model()

    def names() -> list[str]:
        return [
            model_.index(row, 0).data(Qt.ItemDataRole.DisplayRole)
            for row in range(model_.rowCount())
        ]

    in_edit_mode = names()
    edit_mode().set_editing(False)
    in_read_mode = names()
    edit_mode().set_editing(True)

    assert "idShort" in in_read_mode
    assert set(in_read_mode) < set(in_edit_mode)
    assert names() == in_edit_mode
