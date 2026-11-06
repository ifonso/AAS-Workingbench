"""The saved columns of the tabs do not hide the layout of a new release."""

from typing import Any

import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
# A width that no default has.
DRAGGED_WIDTH = 233


def _window(
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    saved: dict[str, Any],
) -> Any:
    """Opens the main window as a session that saved `saved` would."""
    from aas_editor.editorApp import EditorApp
    from aas_editor.settings.app_settings import Setting

    read_setting = Setting.value
    monkeypatch.setattr(
        Setting,
        "value",
        lambda setting: (
            saved[setting.name]
            if setting.name in saved
            else read_setting(setting)
        ),
    )
    # The session of a test does not write the settings file of the program.
    monkeypatch.setattr(Setting, "setValue", lambda setting, value: None)
    window = EditorApp(fileToOpen=(TEST_DATA_DIR / PACKAGE).as_posix())
    qtbot.addWidget(window)
    return window


def _header(window: Any) -> Any:
    return window.mainTabWidget.currentWidget().attrsTreeView.header()


def _close(window: Any) -> None:
    window._recoveryTimer.stop()
    window.close()


def _state_with_a_dragged_attribute_column(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> bytes:
    """The state that a user leaves a header in after dragging a column."""
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_HINT_COLUMN

    window = _window(qtbot, monkeypatch, {})
    header = _header(window)
    header.resizeSection(ATTRIBUTE_COLUMN, DRAGGED_WIDTH)
    header.showSection(TYPE_HINT_COLUMN)
    state = bytes(header.saveState())
    _close(window)
    return state


def test_a_state_of_an_earlier_layout_does_not_hide_the_new_default(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTR_COLUMN_WIDTH
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_HINT_COLUMN

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    window = _window(
        qtbot,
        monkeypatch,
        {"tabTreeViewHeaderState": state, "tabTreeViewHeaderLayout": 1},
    )
    header = _header(window)

    assert header.sectionSize(ATTRIBUTE_COLUMN) == ATTR_COLUMN_WIDTH
    assert header.isSectionHidden(TYPE_HINT_COLUMN)
    _close(window)


def test_a_state_that_was_saved_without_a_layout_is_not_restored_either(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTR_COLUMN_WIDTH
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    # The layout version an old session never wrote reads as its default. The
    # settings file may hold a newer one, from an earlier test.
    window = _window(
        qtbot,
        monkeypatch,
        {"tabTreeViewHeaderState": state, "tabTreeViewHeaderLayout": 0},
    )

    assert _header(window).sectionSize(ATTRIBUTE_COLUMN) == ATTR_COLUMN_WIDTH
    _close(window)


def test_what_the_user_changed_after_that_is_kept(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TAB_HEADER_LAYOUT_VERSION
    from aas_editor.settings.app_settings import TYPE_HINT_COLUMN

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    window = _window(
        qtbot,
        monkeypatch,
        {
            "tabTreeViewHeaderState": state,
            "tabTreeViewHeaderLayout": TAB_HEADER_LAYOUT_VERSION,
        },
    )
    header = _header(window)

    assert header.sectionSize(ATTRIBUTE_COLUMN) == DRAGGED_WIDTH
    assert not header.isSectionHidden(TYPE_HINT_COLUMN)
    _close(window)
