"""Tests for the design tokens: contrast, scales, and the two themes."""

import pytest

from aas_editor.domain.design_tokens import CONTRAST_PAIRS
from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import DEFAULT_DENSITY
from aas_editor.domain.design_tokens import DIALOG_GAP
from aas_editor.domain.design_tokens import DIALOG_PADDING
from aas_editor.domain.design_tokens import ICON_CONTRAST
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.domain.design_tokens import ROW_HEIGHTS
from aas_editor.domain.design_tokens import ROW_TEXT_PADDING
from aas_editor.domain.design_tokens import SPACING
from aas_editor.domain.design_tokens import TEXT_CONTRAST
from aas_editor.domain.design_tokens import THEMES
from aas_editor.domain.design_tokens import TYPE_RAMP
from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import Density
from aas_editor.domain.design_tokens import contrast_ratio
from aas_editor.domain.design_tokens import fitting_row_height
from aas_editor.domain.design_tokens import parse_density

PAIR_IDS = [pair.name for pair in CONTRAST_PAIRS]


@pytest.mark.parametrize("pair", CONTRAST_PAIRS, ids=PAIR_IDS)
def test_light_pair_reads_when_it_carries_text_or_an_icon(pair):
    assert pair.ratio(LIGHT) >= pair.minimum


@pytest.mark.parametrize("pair", CONTRAST_PAIRS, ids=PAIR_IDS)
def test_dark_pair_reads_when_it_carries_text_or_an_icon(pair):
    assert pair.ratio(DARK) >= pair.minimum


def test_contrast_is_21_for_black_on_white():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0)


def test_contrast_is_1_for_a_color_on_itself():
    assert contrast_ratio("#0f62b8", "#0f62b8") == pytest.approx(1.0)


def test_contrast_is_the_same_in_both_directions():
    assert contrast_ratio("#242424", "#ffffff") == contrast_ratio(
        "#ffffff", "#242424"
    )


@pytest.mark.parametrize(
    ("tokens", "foreground", "background", "expected"),
    [
        (LIGHT, "fg_primary", "bg_content", 15.52),
        (LIGHT, "link", "bg_selected", 4.78),
        (LIGHT, "status_error", "bg_error", 5.88),
        (LIGHT, "accent_on", "accent", 6.07),
        (DARK, "fg_primary", "bg_content", 14.55),
        (DARK, "link", "bg_selected", 5.73),
        (DARK, "status_warning", "bg_warning", 8.17),
        (DARK, "accent_on", "accent", 8.04),
    ],
)
def test_contrast_matches_the_table_of_the_plan(
    tokens, foreground, background, expected
):
    ratio = contrast_ratio(tokens.color(foreground), tokens.color(background))

    assert ratio == pytest.approx(expected, abs=0.01)


def test_every_text_and_icon_token_has_a_pair():
    covered = {pair.foreground for pair in CONTRAST_PAIRS}

    assert covered >= {
        "fg_primary",
        "fg_secondary",
        "fg_muted",
        "link",
        "mark_changed",
        "mark_new",
        "status_error",
        "status_warning",
        "status_success",
        "accent_on",
        "accent",
        "accent_hover",
        "stroke_strong",
        "focus",
        "focus_on_accent",
    }


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
def test_the_ring_on_the_filled_button_is_not_the_ring_on_the_page(tokens):
    # A black or white ring on the accent is heavy, and it hides the edge of
    # the button. The ring inside the button takes the color of its text.
    assert tokens.focus_on_accent == tokens.accent_on
    assert tokens.focus_on_accent != tokens.focus


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
@pytest.mark.parametrize("background", ["accent", "accent_hover"])
def test_the_ring_on_the_filled_button_can_be_seen(tokens, background):
    ratio = contrast_ratio(
        tokens.color("focus_on_accent"), tokens.color(background)
    )

    assert ratio >= ICON_CONTRAST


def test_text_pairs_ask_4_5_and_icon_pairs_ask_3():
    minimums = {pair.minimum for pair in CONTRAST_PAIRS}

    assert minimums == {TEXT_CONTRAST, ICON_CONTRAST}
    assert (TEXT_CONTRAST, ICON_CONTRAST) == (4.5, 3.0)


def test_pair_names_the_tokens_it_measures():
    assert CONTRAST_PAIRS[0].name == "fg_primary on bg_content"


def test_themes_are_light_and_dark():
    assert list(THEMES) == ["light", "dark"]
    assert (LIGHT.is_dark, DARK.is_dark) == (False, True)


def test_accent_is_the_blue_of_the_owner():
    assert (LIGHT.accent, DARK.accent) == ("#0f62b8", "#6cb0f5")


def test_light_surfaces_are_off_white_and_grey():
    assert (LIGHT.bg_content, LIGHT.bg_chrome, LIGHT.bg_sunken) == (
        "#ffffff",
        "#fafafa",
        "#f5f5f5",
    )


def test_color_reads_a_token_by_name():
    assert LIGHT.color("bg_chrome") == "#fafafa"


def test_color_refuses_an_unknown_token():
    with pytest.raises(KeyError, match="Unknown color token: 'nope'"):
        LIGHT.color("nope")


def test_color_names_leave_out_the_name_and_the_dark_flag():
    names = LIGHT.color_names()

    assert "name" not in names
    assert "is_dark" not in names
    assert names[0] == "bg_content"


def test_a_value_that_is_not_a_color_is_refused():
    values = {name: LIGHT.color(name) for name in LIGHT.color_names()}
    values["accent"] = "blue"

    with pytest.raises(ValueError, match="Not a color: 'blue' for 'accent'"):
        ColorTokens(name="bad", is_dark=False, **values)


def test_spacing_follows_the_ramp_of_fluent():
    assert SPACING == (0, 2, 4, 6, 8, 10, 12, 16, 20, 24, 32)


def test_a_dialog_has_12_pixels_of_padding_and_8_between_its_parts():
    assert (DIALOG_PADDING, DIALOG_GAP) == (12, 8)


def test_the_spacing_of_dialogs_is_on_the_ramp():
    assert {DIALOG_PADDING, DIALOG_GAP} <= set(SPACING)


def test_rows_are_28_24_and_20_pixels_high():
    assert ROW_HEIGHTS == {
        Density.COMFORTABLE: 28,
        Density.COMPACT: 24,
        Density.DENSE: 20,
    }


def test_compact_is_the_default_density():
    assert DEFAULT_DENSITY is Density.COMPACT


def test_type_ramp_has_the_roles_of_the_plan():
    assert {
        role: (style.size, style.line, style.weight)
        for role, style in TYPE_RAMP.items()
    } == {
        "caption": (12, 16, 400),
        "body": (13, 18, 400),
        "body_strong": (13, 18, 600),
        "subtitle": (14, 20, 600),
        "title": (16, 22, 600),
        "display": (20, 26, 600),
    }


def test_a_line_that_fits_leaves_the_row_at_the_height_of_its_density():
    for density, height in ROW_HEIGHTS.items():
        assert fitting_row_height(density, 16) == height


def test_a_zoomed_font_makes_the_row_taller_than_its_density():
    assert fitting_row_height(Density.COMPACT, 30) == 30 + ROW_TEXT_PADDING


def test_a_line_that_just_fits_does_not_grow_the_row():
    line = ROW_HEIGHTS[Density.DENSE] - ROW_TEXT_PADDING

    assert fitting_row_height(Density.DENSE, line) == ROW_HEIGHTS[Density.DENSE]


def test_a_density_that_was_saved_is_read_back():
    for density in Density:
        assert parse_density(density.value) is density


@pytest.mark.parametrize("text", ["", "tiny", None, 24])
def test_a_density_that_is_no_density_gives_the_default(text):
    assert parse_density(text) is DEFAULT_DENSITY
