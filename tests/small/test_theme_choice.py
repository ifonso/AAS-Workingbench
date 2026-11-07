"""A saved theme name, from this release or an older one, becomes a theme."""

import pytest

from aas_editor.application.theme_choice import DEFAULT_THEME
from aas_editor.application.theme_choice import THEME_DARK
from aas_editor.application.theme_choice import THEME_LABELS
from aas_editor.application.theme_choice import THEME_LIGHT
from aas_editor.application.theme_choice import THEME_NATIVE
from aas_editor.application.theme_choice import THEME_SYSTEM
from aas_editor.application.theme_choice import theme_from_saved


def test_the_list_reads_follow_system_light_dark_native() -> None:
    assert list(THEME_LABELS.values()) == [
        "Follow system",
        "Light",
        "Dark",
        "Native",
    ]
    assert list(THEME_LABELS) == [
        THEME_SYSTEM,
        THEME_LIGHT,
        THEME_DARK,
        THEME_NATIVE,
    ]


def test_the_default_is_light() -> None:
    assert DEFAULT_THEME == THEME_LIGHT


@pytest.mark.parametrize("old", ["grey", "dark"])
def test_an_old_grey_or_dark_becomes_dark(old: str) -> None:
    assert theme_from_saved(old) == THEME_DARK


@pytest.mark.parametrize("old", ["light", "default"])
def test_an_old_light_or_default_becomes_light(old: str) -> None:
    assert theme_from_saved(old) == THEME_LIGHT


@pytest.mark.parametrize(
    "name", [THEME_SYSTEM, THEME_LIGHT, THEME_DARK, THEME_NATIVE]
)
def test_a_name_of_this_release_is_kept(name: str) -> None:
    assert theme_from_saved(name) == name


@pytest.mark.parametrize(
    ("saved", "expected"),
    [
        ("fluent-light", THEME_LIGHT),
        ("fluent-dark", THEME_DARK),
        ("fluent-system", THEME_SYSTEM),
    ],
)
def test_a_name_of_the_builds_before_the_release_is_mapped(
    saved: str, expected: str
) -> None:
    assert theme_from_saved(saved) == expected


@pytest.mark.parametrize("name", ["", "blue", "Grey", "breeze"])
def test_an_unknown_name_becomes_the_default(name: str) -> None:
    assert theme_from_saved(name) == DEFAULT_THEME
