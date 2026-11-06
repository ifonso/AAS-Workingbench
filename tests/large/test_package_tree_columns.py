"""On a first run, the package tree shows the names of nested elements."""

from pathlib import Path

import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
# Six levels of indentation, and a name such as "ProductCarbonFootprint".
ENOUGH_FOR_A_NESTED_NAME = 300


def test_first_run_leaves_room_for_the_names_of_nested_elements(
    qapp: object, qtbot, monkeypatch, tmp_path: Path
) -> None:
    from aas_editor.editorApp import EditorApp
    from aas_editor.settings.app_settings import Setting

    read_setting = Setting.value
    monkeypatch.setattr(
        Setting,
        "value",
        lambda setting: (
            None
            if setting.name == "packTreeViewHeaderState"
            else read_setting(setting)
        ),
    )
    window = EditorApp(fileToOpen=(TEST_DATA_DIR / PACKAGE).as_posix())
    qtbot.addWidget(window)

    width = window.mainTreeView.columnWidth(0)

    window._recoveryTimer.stop()
    window.close()
    assert width >= ENOUGH_FOR_A_NESTED_NAME
