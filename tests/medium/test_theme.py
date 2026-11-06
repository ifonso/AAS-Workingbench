"""Tests for the theme: the style sheet, the palette, and the manager."""

from collections.abc import Iterator
from pathlib import Path
import re

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication
import pytest
from pytestqt.qtbot import QtBot

from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.ui.colors import advisory_color
from aas_editor.ui.colors import advisory_style
from aas_editor.ui.colors import problem_border_style
from aas_editor.ui.colors import problem_color
from aas_editor.ui.colors import problem_style
from aas_editor.ui.theme import current_tokens
from aas_editor.ui.theme import FLUENT_DARK
from aas_editor.ui.theme import FLUENT_LIGHT
from aas_editor.ui.theme import FLUENT_SYSTEM
from aas_editor.ui.theme import FLUENT_THEMES
from aas_editor.ui.theme import theme_manager
from aas_editor.ui.theme import ThemeManager
from aas_editor.ui.theme.assets import images
from aas_editor.ui.theme.assets import write_images
from aas_editor.ui.theme.palette import build_palette
from aas_editor.ui.theme.stylesheet import build_stylesheet
from aas_editor.ui.theme.stylesheet import TEMPLATE_PATH

THEMES_FOLDER = Path(__file__).parents[2] / "src" / "aas_editor" / "themes"


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look of the platform back."""
    QStandardPaths.setTestModeEnabled(True)
    yield
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


def test_stylesheet_has_no_name_left_unfilled(tmp_path: Path):
    for tokens in (LIGHT, DARK):
        for density in Density:
            sheet = build_stylesheet(tokens, density, tmp_path)

            assert "$" not in sheet


def test_template_asks_only_for_names_that_have_a_value(tmp_path: Path):
    # `substitute` raises KeyError for a name without a value.
    build_stylesheet(LIGHT, Density.COMPACT, tmp_path)

    assert TEMPLATE_PATH.is_file()


def test_stylesheet_uses_the_colors_of_the_theme(tmp_path: Path):
    light = build_stylesheet(LIGHT, Density.COMPACT, tmp_path)
    dark = build_stylesheet(DARK, Density.COMPACT, tmp_path)

    assert "#0f62b8" in light
    assert "#0f62b8" not in dark
    assert "#6cb0f5" in dark


def test_stylesheet_points_at_the_folder_of_the_images(tmp_path: Path):
    sheet = build_stylesheet(LIGHT, Density.COMPACT, tmp_path)

    assert f'url("{tmp_path.as_posix()}/check.svg")' in sheet


def test_stylesheet_pads_menu_items_by_density(tmp_path: Path):
    dense = build_stylesheet(LIGHT, Density.DENSE, tmp_path)
    comfortable = build_stylesheet(LIGHT, Density.COMFORTABLE, tmp_path)

    assert "padding: 1px 28px 1px 24px;" in dense
    assert "padding: 5px 28px 5px 24px;" in comfortable


def test_every_image_that_the_stylesheet_names_is_drawn(tmp_path: Path):
    sheet = build_stylesheet(LIGHT, Density.COMPACT, tmp_path)

    named = set(re.findall(r'url\("[^"]*/([a-z-]+\.svg)"\)', sheet))

    assert named
    assert named <= set(images(LIGHT))


def test_images_are_written_to_the_cache_of_the_user():
    folder = write_images(DARK)

    assert (folder / "check.svg").read_text(encoding="utf-8").count("#141414")
    assert folder.name == "dark"


def test_images_are_colored_by_the_tokens():
    assert 'stroke="#d6d6d6"' in images(DARK)["chevron-down.svg"]
    assert 'stroke="#424242"' in images(LIGHT)["chevron-down.svg"]


def test_palette_follows_the_light_tokens():
    palette = build_palette(LIGHT)

    assert palette.color(QPalette.ColorRole.Window) == QColor("#fafafa")
    assert palette.color(QPalette.ColorRole.Base) == QColor("#ffffff")
    assert palette.color(QPalette.ColorRole.Text) == QColor("#242424")
    assert palette.color(QPalette.ColorRole.Highlight) == QColor("#d6e6f8")
    assert palette.color(QPalette.ColorRole.Accent) == QColor("#0f62b8")


def test_palette_keeps_the_selection_when_the_window_is_inactive():
    palette = build_palette(DARK)

    assert palette.color(
        QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight
    ) == QColor("#1f3f63")


def test_palette_dims_disabled_text():
    palette = build_palette(LIGHT)

    assert palette.color(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text
    ) == QColor("#bdbdbd")


@pytest.fixture
def windows_look(qapp: QApplication) -> Iterator[ThemeManager]:
    """Gives a manager that found the style `Windows` as the native one."""
    qapp.setStyle("Windows")
    manager = ThemeManager(qapp)
    yield manager
    manager.reset_to_native()
    manager.deleteLater()
    qapp.setStyle("Fusion")


def test_applying_a_new_theme_sets_fusion_the_palette_and_the_sheet(
    qapp: QApplication, windows_look: ThemeManager
):
    windows_look.apply(FLUENT_LIGHT)

    assert windows_look.base_style == "fusion"
    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor("#fafafa")
    assert "#0f62b8" in qapp.styleSheet()
    assert windows_look.tokens is LIGHT


def test_applying_dark_changes_the_palette_and_the_tokens(qapp: QApplication):
    theme_manager().apply(FLUENT_LIGHT)

    theme_manager().apply(FLUENT_DARK)

    assert qapp.palette().color(QPalette.ColorRole.Window) == QColor("#1f1f1f")
    assert "#6cb0f5" in qapp.styleSheet()
    assert current_tokens() is DARK
    assert theme_manager().choice == FLUENT_DARK


def test_applying_a_theme_tells_who_follows(qtbot: QtBot):
    with qtbot.waitSignal(theme_manager().changed, timeout=1000):
        theme_manager().apply(FLUENT_DARK)


def test_density_is_kept_until_another_is_given():
    theme_manager().apply(FLUENT_LIGHT, Density.DENSE)

    theme_manager().apply(FLUENT_DARK)

    assert theme_manager().density is Density.DENSE
    assert theme_manager().row_height == 20


def test_the_offscreen_system_has_no_dark_scheme():
    theme_manager().apply(FLUENT_SYSTEM)

    assert current_tokens() is LIGHT
    assert theme_manager().choice == FLUENT_SYSTEM


def test_an_unknown_theme_is_refused():
    with pytest.raises(ValueError, match="Unknown theme: 'blue'"):
        theme_manager().apply("blue")


def test_the_new_themes_are_light_dark_and_the_system():
    assert list(FLUENT_THEMES) == [
        "fluent-light",
        "fluent-dark",
        "fluent-system",
    ]


def test_an_old_dark_theme_puts_the_native_look_back(
    qapp: QApplication, windows_look: ThemeManager
):
    windows_look.apply(FLUENT_LIGHT)

    windows_look.apply_legacy("grey", THEMES_FOLDER / "grey.qss")

    assert windows_look.base_style == "windows"
    assert qapp.styleSheet() == (THEMES_FOLDER / "grey.qss").read_text(
        encoding="utf-8"
    )
    assert windows_look.tokens is DARK


def test_an_old_light_theme_counts_as_light():
    theme_manager().apply(FLUENT_DARK)

    theme_manager().apply_legacy("light", THEMES_FOLDER / "light.qss")

    assert current_tokens() is LIGHT


def test_resetting_gives_the_platform_look_and_no_sheet(
    qapp: QApplication, windows_look: ThemeManager
):
    windows_look.apply(FLUENT_DARK)

    windows_look.reset_to_native()

    assert windows_look.base_style == "windows"
    assert qapp.styleSheet() == ""
    assert windows_look.choice == ""


def test_problem_text_is_red_enough_on_the_light_theme():
    theme_manager().apply(FLUENT_LIGHT)

    assert problem_color() == "#b3261e"
    assert problem_style() == "color: #b3261e;"
    assert problem_border_style() == "border: 1px solid #b3261e;"


def test_problem_text_is_light_red_on_the_dark_theme():
    theme_manager().apply(FLUENT_DARK)

    assert problem_color() == "#ff8a85"
    assert problem_border_style() == "border: 1px solid #ff8a85;"


def test_advisory_text_follows_the_theme():
    theme_manager().apply(FLUENT_LIGHT)
    light = advisory_color()

    theme_manager().apply(FLUENT_DARK)

    assert (light, advisory_color()) == ("#8a5a00", "#f2c661")
    assert advisory_style() == "color: #f2c661;"


def test_text_on_an_old_dark_theme_gets_the_dark_colors():
    theme_manager().apply_legacy("grey", THEMES_FOLDER / "grey.qss")

    assert problem_color() == "#ff8a85"
    assert advisory_color() == "#f2c661"
