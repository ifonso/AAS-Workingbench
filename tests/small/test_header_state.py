"""A saved header state is restored only for the layout it was made for."""

from aas_editor.application.header_state import NO_VERSION
from aas_editor.application.header_state import restorable_state

STATE = b"columns the user dragged"


def test_a_state_of_the_current_layout_is_restored() -> None:
    assert restorable_state(STATE, 2, 2) == STATE


def test_a_state_that_was_saved_before_versions_existed_is_not_restored() -> (
    None
):
    assert restorable_state(STATE, NO_VERSION, 2) is None


def test_a_state_of_an_older_layout_is_not_restored() -> None:
    assert restorable_state(STATE, 1, 2) is None


def test_no_state_is_nothing_to_restore() -> None:
    assert restorable_state(None, 2, 2) is None
    assert restorable_state(b"", 2, 2) is None


def test_the_new_default_wins_once_and_a_later_change_is_kept() -> None:
    current = 2
    saved: tuple[bytes | None, int] = (STATE, 1)  # saved by an earlier release

    first_session = restorable_state(*saved, current)
    saved = (b"the user changed a width", current)  # saved when it ended
    second_session = restorable_state(*saved, current)

    assert first_session is None
    assert second_session == b"the user changed a width"
