"""A session of an older release meets the compact trees in the main window."""

from collections.abc import Iterator
from typing import Any

import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
# The default of the releases before the compact trees, and a size of a user.
OLD_DEFAULT = 12
CHOSEN = 16


@pytest.fixture(autouse=True)
def restored_state(qapp: object) -> Iterator[None]:
    """Gives the font size of the models and the density back."""
    from aas_editor.domain.design_tokens import DEFAULT_DENSITY
    from aas_editor.models import DetailedInfoTable
    from aas_editor.models import PacksTable
    from aas_editor.ui.theme import theme_manager

    sizes = (
        PacksTable.currFont.pointSize(),
        DetailedInfoTable.currFont.pointSize(),
    )
    yield
    PacksTable.currFont.setPointSize(sizes[0])
    DetailedInfoTable.currFont.setPointSize(sizes[1])
    theme_manager().set_density(DEFAULT_DENSITY)


def _window(
    qtbot: Any, monkeypatch: pytest.MonkeyPatch, saved: dict[str, Any]
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
    written: dict[str, Any] = {}
    # The session of a test does not write the settings file of the program.
    monkeypatch.setattr(
        Setting,
        "setValue",
        lambda setting, value: written.__setitem__(setting.name, value),
    )
    window = EditorApp(fileToOpen=(TEST_DATA_DIR / PACKAGE).as_posix())
    qtbot.addWidget(window)
    window.written = written
    return window


def _close(window: Any) -> None:
    window._recoveryTimer.stop()
    window.close()


def test_the_old_default_font_size_takes_the_new_default(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.models import DetailedInfoTable
    from aas_editor.models import PacksTable
    from aas_editor.settings.app_settings import DEFAULT_FONT

    window = _window(
        qtbot,
        monkeypatch,
        {
            "fontSizeFilesView": OLD_DEFAULT,
            "fontSizeDetailedView": OLD_DEFAULT,
            "fontSizeLayout": 0,
        },
    )

    assert PacksTable.currFont.pointSize() == DEFAULT_FONT.pointSize()
    assert DetailedInfoTable.currFont.pointSize() == DEFAULT_FONT.pointSize()
    _close(window)


def test_a_font_size_that_a_user_chose_is_kept(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.models import DetailedInfoTable
    from aas_editor.models import PacksTable

    window = _window(
        qtbot,
        monkeypatch,
        {
            "fontSizeFilesView": CHOSEN,
            "fontSizeDetailedView": CHOSEN,
            "fontSizeLayout": 0,
        },
    )

    assert PacksTable.currFont.pointSize() == CHOSEN
    assert DetailedInfoTable.currFont.pointSize() == CHOSEN
    _close(window)


def test_the_old_default_chosen_again_after_the_migration_is_kept(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.application.font_sizes import FONT_SIZE_LAYOUT_VERSION
    from aas_editor.models import PacksTable

    window = _window(
        qtbot,
        monkeypatch,
        {
            "fontSizeFilesView": OLD_DEFAULT,
            "fontSizeDetailedView": OLD_DEFAULT,
            "fontSizeLayout": FONT_SIZE_LAYOUT_VERSION,
        },
    )

    assert PacksTable.currFont.pointSize() == OLD_DEFAULT
    _close(window)


def test_a_session_saves_the_version_of_the_font_size_it_ran_with(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.application.font_sizes import FONT_SIZE_LAYOUT_VERSION

    window = _window(qtbot, monkeypatch, {})

    window.writeSettings()

    assert window.written["fontSizeLayout"] == FONT_SIZE_LAYOUT_VERSION
    _close(window)


def test_the_saved_density_is_on_when_the_window_opens(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.domain.design_tokens import ROW_HEIGHTS
    from aas_editor.domain.design_tokens import Density
    from aas_editor.ui.theme import theme_manager

    window = _window(qtbot, monkeypatch, {"density": Density.DENSE.value})
    view = window.mainTreeView
    window.show()
    qtbot.waitExposed(window)

    assert theme_manager().density is Density.DENSE
    assert (
        view.visualRect(view.model().index(0, 0)).height()
        == (ROW_HEIGHTS[Density.DENSE])
    )
    _close(window)


def test_a_header_of_the_previous_release_is_not_restored(
    qapp: object, qtbot: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.settings.app_settings import PACK_TREE_HEADER_LAYOUT_VERSION
    from aas_editor.settings.app_settings import PACK_TREE_OBJECT_COLUMN_WIDTH
    from aas_editor.settings.app_settings import TAB_HEADER_LAYOUT_VERSION

    first = _window(qtbot, monkeypatch, {})
    first.mainTreeView.header().resizeSection(0, 233)
    state = bytes(first.mainTreeView.header().saveState())
    _close(first)

    window = _window(
        qtbot,
        monkeypatch,
        {
            "packTreeViewHeaderState": state,
            "packTreeViewHeaderLayout": PACK_TREE_HEADER_LAYOUT_VERSION - 1,
            "tabTreeViewHeaderLayout": TAB_HEADER_LAYOUT_VERSION - 1,
        },
    )

    assert window.mainTreeView.header().sectionSize(0) == (
        PACK_TREE_OBJECT_COLUMN_WIDTH
    )
    _close(window)
