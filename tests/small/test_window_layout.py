"""The window of a first run fits the screen, and a saved size wins."""

import pytest

from aas_editor.domain.window_layout import DEFAULT_SIZE
from aas_editor.domain.window_layout import first_run_size
from aas_editor.domain.window_layout import window_size
from aas_editor.domain.window_layout import zone_widths

PREVIEW_MIN_TAB_WIDTH = 720


def test_a_large_screen_gets_a_share_of_its_room() -> None:
    assert first_run_size(1920, 1032) == (1632, 877)


def test_a_screen_that_is_not_much_larger_gets_the_default_size() -> None:
    assert first_run_size(1280, 720) == DEFAULT_SIZE


def test_a_screen_smaller_than_the_default_gets_the_screen() -> None:
    assert first_run_size(1024, 600) == (1024, 600)


@pytest.mark.parametrize(
    ("width", "height"), [(800, 600), (1366, 728), (1920, 1032), (3840, 2100)]
)
def test_the_window_never_exceeds_the_screen(width: int, height: int) -> None:
    window = first_run_size(width, height)

    assert window[0] <= width
    assert window[1] <= height


def test_a_saved_size_wins_over_the_screen() -> None:
    assert window_size((900, 500), 1920, 1032) == (900, 500)


def test_without_a_saved_size_the_screen_decides() -> None:
    assert window_size(None, 1920, 1032) == first_run_size(1920, 1032)


def test_the_tab_of_a_full_hd_first_run_has_room_for_the_preview() -> None:
    width, _ = first_run_size(1920, 1032)

    _, tabs = zone_widths(width)

    assert tabs >= PREVIEW_MIN_TAB_WIDTH


def test_the_tree_keeps_what_its_columns_need_in_a_small_window() -> None:
    left, right = zone_widths(DEFAULT_SIZE[0])

    assert left == 520
    assert left + right == DEFAULT_SIZE[0]
