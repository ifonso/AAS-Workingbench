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
    written: dict[str, Any] | None = None,
) -> Any:
    """Opens the main window as a session that saved `saved` would.

    The window is shown, as it is for a user: the columns of a tab are fitted
    to the room when the tab is first laid out. `written` collects what the
    session writes to the settings when it closes.
    """
    from PyQt6.QtWidgets import QApplication

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
    monkeypatch.setattr(
        Setting,
        "setValue",
        lambda setting, value: (
            written.__setitem__(setting.name, value)
            if written is not None
            else None
        ),
    )
    window = EditorApp(fileToOpen=(TEST_DATA_DIR / PACKAGE).as_posix())
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    return window


def _header(window: Any) -> Any:
    return window.mainTabWidget.currentWidget().attrsTreeView.header()


def _fitting_width(window: Any) -> int:
    """The width that a new tab gives the attribute column."""
    from aas_editor.settings.app_settings import ATTR_MAX_SHARE

    view = window.mainTabWidget.currentWidget().attrsTreeView
    return min(
        view.fittingAttributeWidth(),
        int(view.viewport().width() * ATTR_MAX_SHARE),
    )


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
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_HINT_COLUMN

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    window = _window(
        qtbot,
        monkeypatch,
        {"tabTreeViewHeaderState": state, "tabTreeViewHeaderLayout": 1},
    )
    header = _header(window)

    assert header.sectionSize(ATTRIBUTE_COLUMN) == _fitting_width(window)
    assert header.isSectionHidden(TYPE_HINT_COLUMN)
    _close(window)


def test_a_state_that_was_saved_without_a_layout_is_not_restored_either(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    # The layout version an old session never wrote reads as its default. The
    # settings file may hold a newer one, from an earlier test.
    window = _window(
        qtbot,
        monkeypatch,
        {"tabTreeViewHeaderState": state, "tabTreeViewHeaderLayout": 0},
    )

    assert _header(window).sectionSize(ATTRIBUTE_COLUMN) == _fitting_width(
        window
    )
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


def test_columns_that_nobody_sized_are_fitted_again(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TAB_HEADER_LAYOUT_VERSION

    state = _state_with_a_dragged_attribute_column(qtbot, monkeypatch)

    # The session that saved the state left the columns as they were fitted.
    window = _window(
        qtbot,
        monkeypatch,
        {
            "tabTreeViewHeaderState": state,
            "tabTreeViewHeaderLayout": TAB_HEADER_LAYOUT_VERSION,
            "tabTreeViewColumnsSized": False,
        },
    )

    assert _header(window).sectionSize(ATTRIBUTE_COLUMN) == _fitting_width(
        window
    )
    _close(window)


def test_closing_writes_that_the_user_dragged_a_column(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN

    written: dict[str, Any] = {}
    window = _window(qtbot, monkeypatch, {}, written)
    _header(window).resizeSection(ATTRIBUTE_COLUMN, DRAGGED_WIDTH)

    _close(window)

    assert written["tabTreeViewColumnsSized"] is True


def test_closing_writes_that_nobody_dragged_a_column(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: dict[str, Any] = {}
    window = _window(qtbot, monkeypatch, {}, written)

    _close(window)

    assert written["tabTreeViewColumnsSized"] is False


def _pack_state_with_a_dragged_object_column(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> bytes:
    window = _window(qtbot, monkeypatch, {})
    window.mainTreeView.header().resizeSection(0, DRAGGED_WIDTH)
    state = bytes(window.mainTreeView.header().saveState())
    _close(window)
    return state


def test_the_header_of_the_package_tree_of_an_earlier_layout_is_dropped(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import PACK_TREE_OBJECT_COLUMN_WIDTH

    state = _pack_state_with_a_dragged_object_column(qtbot, monkeypatch)

    window = _window(
        qtbot,
        monkeypatch,
        {"packTreeViewHeaderState": state, "packTreeViewHeaderLayout": 0},
    )

    assert window.mainTreeView.header().sectionSize(0) == (
        PACK_TREE_OBJECT_COLUMN_WIDTH
    )
    _close(window)


def test_the_header_of_the_package_tree_of_this_layout_is_kept(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import PACK_TREE_HEADER_LAYOUT_VERSION

    state = _pack_state_with_a_dragged_object_column(qtbot, monkeypatch)

    window = _window(
        qtbot,
        monkeypatch,
        {
            "packTreeViewHeaderState": state,
            "packTreeViewHeaderLayout": PACK_TREE_HEADER_LAYOUT_VERSION,
        },
    )

    assert window.mainTreeView.header().sectionSize(0) == DRAGGED_WIDTH
    _close(window)


def _left_share(window: Any) -> float:
    from PyQt6.QtWidgets import QApplication

    window.show()
    QApplication.processEvents()
    left, right = window.splitter.sizes()
    return left / (left + right)


def test_the_zones_of_an_earlier_layout_get_the_default_widths(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtCore import QSize

    window = _window(
        qtbot,
        monkeypatch,
        {
            "leftZoneSize": QSize(100, 600),
            "rightZoneSize": QSize(900, 600),
            "zonesLayout": 0,
        },
    )

    # The saved sizes gave the tree a tenth. The default gives it a share that
    # the tab can still bear, which a small window may reduce.
    assert _left_share(window) > 0.4
    _close(window)


def test_the_zones_of_this_layout_are_restored(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtCore import QSize

    from aas_editor.settings.app_settings import ZONES_LAYOUT_VERSION

    window = _window(
        qtbot,
        monkeypatch,
        {
            "leftZoneSize": QSize(300, 600),
            "rightZoneSize": QSize(700, 600),
            "zonesLayout": ZONES_LAYOUT_VERSION,
        },
    )

    assert abs(_left_share(window) - 0.3) < 0.05
    _close(window)
