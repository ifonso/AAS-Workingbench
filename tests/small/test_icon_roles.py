"""The colors that icons take from the theme."""

from PyQt6.QtGui import QIcon
import pytest

from aas_workingbench.domain.design_tokens import DARK
from aas_workingbench.domain.design_tokens import ICON_CONTRAST
from aas_workingbench.domain.design_tokens import LIGHT
from aas_workingbench.domain.design_tokens import contrast_ratio
from aas_workingbench.ui.theme.icons import IconRole
from aas_workingbench.ui.theme.icons import icon_color

# The surfaces that an icon of the editor is drawn on: toolbars, trees and
# forms, the strip of a dock, and a selected row.
SURFACES = ("bg_content", "bg_chrome", "bg_sunken", "bg_selected")


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
@pytest.mark.parametrize("role", list(IconRole))
def test_every_role_names_a_color_of_the_theme(tokens, role: IconRole) -> None:
    assert icon_color(tokens, role, QIcon.Mode.Normal) == tokens.color(
        role.value
    )


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
@pytest.mark.parametrize("role", list(IconRole))
@pytest.mark.parametrize("surface", SURFACES)
def test_an_icon_can_be_seen_on_every_surface(
    tokens, role: IconRole, surface: str
) -> None:
    color = icon_color(tokens, role, QIcon.Mode.Normal)

    assert contrast_ratio(color, tokens.color(surface)) >= ICON_CONTRAST


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
def test_an_icon_that_is_off_is_quiet(tokens) -> None:
    for role in IconRole:
        assert (
            icon_color(tokens, role, QIcon.Mode.Disabled) == tokens.fg_disabled
        )


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
@pytest.mark.parametrize("mode", [QIcon.Mode.Active, QIcon.Mode.Selected])
def test_a_plain_icon_darkens_under_the_pointer_and_in_a_selected_row(
    tokens, mode: QIcon.Mode
) -> None:
    assert icon_color(tokens, IconRole.DEFAULT, mode) == tokens.fg_primary


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=lambda t: t.name)
def test_an_icon_with_a_meaning_keeps_its_color_in_every_state(tokens) -> None:
    for role in (IconRole.ERROR, IconRole.WARNING, IconRole.SUCCESS):
        for mode in (QIcon.Mode.Active, QIcon.Mode.Selected):
            assert icon_color(tokens, role, mode) == tokens.color(role.value)
