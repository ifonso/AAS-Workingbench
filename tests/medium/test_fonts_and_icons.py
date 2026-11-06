"""The bundled font and the icons that follow the theme (ADR 0027)."""

from collections.abc import Iterator
from pathlib import Path

from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QRect
from PyQt6.QtCore import QSize
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QFont
from PyQt6.QtGui import QFontDatabase
from PyQt6.QtGui import QFontInfo
from PyQt6.QtGui import QIcon
from PyQt6.QtGui import QImage
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QToolButton
import pytest
from pytestqt.qtbot import QtBot

from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import FONT_FAMILY
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.domain.design_tokens import TYPE_RAMP
from aas_editor.settings import icons
from aas_editor.ui.theme import FLUENT_DARK
from aas_editor.ui.theme import FLUENT_LIGHT
from aas_editor.ui.theme import theme_manager
from aas_editor.ui.theme.fonts import apply_application_font
from aas_editor.ui.theme.fonts import application_font
from aas_editor.ui.theme.fonts import FONT_FILES
from aas_editor.ui.theme.fonts import FONTS_FOLDER
from aas_editor.ui.theme.fonts import install_fonts
from aas_editor.ui.theme.icons import IconRole
from aas_editor.ui.theme.icons import svg_icon
from aas_editor.ui.theme.icons import tabler_icon
from aas_editor.ui.theme.icons import TABLER_FOLDER

BIG = QSize(96, 96)


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look and the font of the platform back."""
    QStandardPaths.setTestModeEnabled(True)
    font = QFont(qapp.font())
    yield
    qapp.setFont(font)
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


def action_icons() -> dict[str, QIcon]:
    """Every action icon of the editor by the name of its constant."""
    return {
        name: value
        for name, value in vars(icons).items()
        if name.endswith("_ICON") and isinstance(value, QIcon)
    }


def opaque_pixels(image: QImage) -> list[QColor]:
    """The colors of the pixels that are fully drawn."""
    return [
        QColor(image.pixelColor(x, y))
        for x in range(image.width())
        for y in range(image.height())
        if image.pixelColor(x, y).alpha() == 255
    ]


def drawn(icon: QIcon, mode: QIcon.Mode = QIcon.Mode.Normal) -> QImage:
    return icon.pixmap(BIG, 1.0, mode).toImage()


def test_there_are_the_38_action_icons_of_the_old_set() -> None:
    assert len(action_icons()) == 38


@pytest.mark.parametrize("name", sorted(action_icons()))
def test_every_action_icon_draws_something(name: str) -> None:
    image = icons.__dict__[name].pixmap(QSize(16, 16)).toImage()

    assert any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(image.width())
        for y in range(image.height())
    )


def test_an_icon_that_is_not_bundled_fails_when_it_is_made() -> None:
    with pytest.raises(FileNotFoundError):
        tabler_icon("no-such-icon")


def test_every_bundled_icon_draws_in_the_color_that_it_is_given() -> None:
    files = sorted(TABLER_FOLDER.glob("*.svg"))

    assert files
    for file in files:
        text = file.read_text(encoding="utf-8")
        assert "currentColor" in text, file.name
        assert "<script" not in text, file.name


def test_the_licenses_of_the_font_and_the_icons_are_bundled() -> None:
    assert "SIL OPEN FONT LICENSE Version 1.1" in (
        FONTS_FOLDER / "OFL.txt"
    ).read_text(encoding="utf-8")
    assert (
        (TABLER_FOLDER / "LICENSE")
        .read_text(encoding="utf-8")
        .startswith("MIT License")
    )


@pytest.mark.parametrize(
    ("choice", "tokens"), [(FLUENT_LIGHT, LIGHT), (FLUENT_DARK, DARK)]
)
def test_an_icon_is_drawn_in_the_color_of_the_theme_in_use(
    choice: str, tokens
) -> None:
    theme_manager().apply(choice)

    colors = {c.name() for c in opaque_pixels(drawn(icons.ADD_ICON))}

    assert colors == {tokens.fg_secondary}


def test_a_disabled_icon_is_drawn_in_the_disabled_color() -> None:
    theme_manager().apply(FLUENT_LIGHT)

    image = drawn(icons.ADD_ICON, QIcon.Mode.Disabled)

    assert {c.name() for c in opaque_pixels(image)} == {LIGHT.fg_disabled}


def test_an_icon_under_the_pointer_is_drawn_in_the_primary_color() -> None:
    theme_manager().apply(FLUENT_LIGHT)

    image = drawn(icons.ADD_ICON, QIcon.Mode.Active)

    assert {c.name() for c in opaque_pixels(image)} == {LIGHT.fg_primary}


def test_the_role_of_an_icon_sets_its_color() -> None:
    theme_manager().apply(FLUENT_DARK)
    error = tabler_icon("circle-x", IconRole.ERROR)

    assert {c.name() for c in opaque_pixels(drawn(error))} == {
        DARK.status_error
    }


def test_the_same_icon_follows_a_switch_of_theme_on_a_button(
    qtbot: QtBot,
) -> None:
    button = QToolButton()
    button.setIcon(icons.SAVE_ICON)
    button.setIconSize(QSize(16, 16))
    qtbot.addWidget(button)
    theme_manager().apply(FLUENT_LIGHT)
    light = button.grab().toImage()

    theme_manager().apply(FLUENT_DARK)
    dark = button.grab().toImage()

    assert light != dark


def test_an_icon_for_a_screen_of_ratio_two_has_twice_the_pixels() -> None:
    pixmap = icons.ADD_ICON.pixmap(QSize(16, 16), 2.0)

    assert pixmap.size() == QSize(32, 32)
    assert pixmap.devicePixelRatio() == 2.0


def test_an_icon_painted_on_a_screen_of_ratio_two_is_drawn_with_its_pixels() -> (
    None
):
    image = QImage(32, 32, QImage.Format.Format_ARGB32_Premultiplied)
    image.setDevicePixelRatio(2.0)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    icons.ADD_ICON.paint(painter, QRect(0, 0, 16, 16))
    painter.end()

    stretched = (
        icons.ADD_ICON.pixmap(QSize(16, 16))
        .toImage()
        .scaled(
            32,
            32,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        .convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    )
    sharp = (
        icons.ADD_ICON.pixmap(QSize(16, 16), 2.0)
        .toImage()
        .convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    )

    # The line of the icon is drawn on the pixels of the screen, not drawn
    # small and stretched, which is what made icons soft before.
    assert (
        image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        == sharp
    )
    assert sharp != stretched


def test_a_new_kind_of_icon_is_one_svg_file_and_a_role(tmp_path: Path) -> None:
    file = tmp_path / "kind.svg"
    file.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16">'
        '<rect width="16" height="16" fill="currentColor"/></svg>',
        encoding="utf-8",
    )
    theme_manager().apply(FLUENT_LIGHT)

    icon = svg_icon(file, IconRole.ACCENT)

    assert {c.name() for c in opaque_pixels(drawn(icon))} == {LIGHT.accent}


def test_the_font_is_bundled_with_its_license() -> None:
    for name in FONT_FILES:
        assert (FONTS_FOLDER / name).is_file()
    assert (FONTS_FOLDER / "OFL.txt").is_file()


def test_the_font_is_registered_and_has_the_weights_of_the_type_ramp(
    qapp: QApplication,
) -> None:
    assert install_fonts()

    assert FONT_FAMILY in QFontDatabase.families()
    for style in TYPE_RAMP.values():
        font = QFont(FONT_FAMILY)
        font.setWeight(QFont.Weight(style.weight))
        assert QFontInfo(font).family() == FONT_FAMILY
        assert QFontInfo(font).weight() == style.weight


def test_a_font_file_that_cannot_be_loaded_is_reported_not_raised(
    tmp_path: Path, qapp: QApplication, caplog: pytest.LogCaptureFixture
) -> None:
    assert not install_fonts(tmp_path)

    assert "did not load" in caplog.text


def test_the_application_font_is_the_body_of_the_type_ramp(
    qapp: QApplication,
) -> None:
    font = application_font()

    assert font.family() == FONT_FAMILY
    assert font.pixelSize() == TYPE_RAMP["body"].size
    assert font.weight() == QFont.Weight.Normal


def test_a_widget_without_a_font_of_its_own_gets_the_font_of_the_application(
    qapp: QApplication, qtbot: QtBot
) -> None:
    apply_application_font(qapp)
    button = QToolButton()
    qtbot.addWidget(button)

    assert QFontInfo(button.font()).family() == FONT_FAMILY
    assert QFontInfo(button.font()).pixelSize() == TYPE_RAMP["body"].size


def test_the_font_of_the_rows_is_regular_and_not_thin() -> None:
    # Qt 6 reads the 40 that Qt 5 meant as Normal as a weight below Thin, and
    # Inter has a Thin style, so every row would draw hairline thin.
    from aas_editor.settings.app_settings import DEFAULT_FONT

    assert DEFAULT_FONT.weight() == QFont.Weight.Normal
    assert DEFAULT_FONT.family() == FONT_FAMILY


def test_the_font_does_not_change_the_zoom_of_a_tree(
    views, qtbot: QtBot
) -> None:
    from aas_editor.models import DetailedInfoTable
    from aas_editor.settings.app_settings import DEFAULT_FONT

    zoomed = DetailedInfoTable.currFont.pointSize()
    try:
        apply_application_font(QApplication.instance())
        assert DetailedInfoTable.currFont.pointSize() == zoomed
        assert zoomed == DEFAULT_FONT.pointSize()
    finally:
        DetailedInfoTable.currFont.setPointSize(zoomed)


def test_zooming_a_tree_changes_the_size_and_keeps_the_family(
    views, qtbot: QtBot, qapp: QApplication
) -> None:
    from aas_editor.models import DetailedInfoTable
    from tests.factories import make_property
    from tests.factories import make_submodel

    apply_application_font(qapp)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("Speed")]))
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")
    before = DetailedInfoTable.currFont.pointSize()
    try:
        attrs.zoomIn()
        font = attrs.model().data(QModelIndex(), Qt.ItemDataRole.FontRole)

        assert font.pointSize() == before + 2
        assert QFontInfo(font).family() == FONT_FAMILY
    finally:
        DetailedInfoTable.currFont.setPointSize(before)


def test_the_shared_qapp_has_inter_registered_for_every_test(
    qapp: QApplication,
) -> None:
    # Run this test alone: nothing else has called `install_fonts` then.
    assert FONT_FAMILY in QFontDatabase.families()
    assert QFontInfo(QFont(FONT_FAMILY)).family() == FONT_FAMILY
