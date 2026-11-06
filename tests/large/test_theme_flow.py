"""The main window starts in the new light theme, and switches themes."""

from pathlib import Path

from PyQt6.QtGui import QColor
from PyQt6.QtGui import QPalette
import pytest
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"


@pytest.fixture
def open_window(qapp, qtbot, monkeypatch, tmp_path: Path):
    """Opens the main window with the theme that the settings return."""

    def open_with(saved_theme: str | None):
        from aas_editor.editorApp import EditorApp
        from aas_editor.settings.app_settings import Setting

        read_setting = Setting.value
        monkeypatch.setattr(
            Setting,
            "value",
            lambda setting: (
                (saved_theme if saved_theme else setting.default)
                if setting.name == "theme"
                else read_setting(setting)
            ),
        )
        # The theme is not saved, so that other tests start as they did.
        monkeypatch.setattr(
            Setting,
            "setValue",
            lambda setting, value: None,
        )
        window = EditorApp(fileToOpen=(TEST_DATA_DIR / PACKAGE).as_posix())
        qtbot.addWidget(window)
        windows.append(window)
        return window

    windows = []
    yield open_with
    for window in windows:
        window._recoveryTimer.stop()
        window.toggleTheme("fluent-light")
        window.close()


def window_color(app) -> QColor:
    return app.palette().color(QPalette.ColorRole.Window)


def test_first_run_uses_the_new_light_theme(qapp, open_window) -> None:
    window = open_window(None)

    assert window.currTheme == "fluent-light"
    assert window_color(qapp) == QColor("#fafafa")


def test_theme_menu_lists_the_new_themes_before_the_old_ones(
    open_window,
) -> None:
    window = open_window(None)

    ids = [action.data() for action in window.themeActs]

    assert ids[:3] == ["fluent-light", "fluent-dark", "fluent-system"]
    assert set(ids[3:]) == {"dark", "default", "grey", "light"}


def test_choosing_dark_changes_the_palette_and_the_recovery_warning(
    qapp, open_window
) -> None:
    window = open_window(None)

    window.toggleTheme("fluent-dark")

    assert window_color(qapp) == QColor("#1f1f1f")
    assert "#ff8a85" in window._recoveryStatusLabel.styleSheet()
    checked = [a.data() for a in window.themeActs if a.isChecked()]
    assert checked == ["fluent-dark"]


def test_a_saved_old_theme_stays_on(qapp, open_window) -> None:
    window = open_window("grey")

    assert window.currTheme == "grey"
    assert "#3c3f41" in qapp.styleSheet()
    assert "#fafafa" not in qapp.styleSheet()


def test_an_unknown_saved_theme_gives_the_new_light_theme(
    qapp, open_window
) -> None:
    window = open_window("sepia")

    assert window.currTheme == "fluent-light"
    assert window_color(qapp) == QColor("#fafafa")
