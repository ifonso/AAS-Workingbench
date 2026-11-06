"""Which saved state of a header the next session may restore.

A header remembers the order, the widths, and the hidden columns that the user
left it with, and the next session restores them. That also restores the
defaults of an old release: when a release changes the default columns, the
saved state hides the new layout from everyone who ran the program before.

The state is saved together with the version of the layout that it was made
for. A state of another version is not restored, so the new default shows once.
The state that is saved at the end of that session has the new version, so what
the user changes after that is kept.
"""

from typing import TypeVar

State = TypeVar("State")

NO_VERSION = 0
"""The version of a state that was saved before versions existed."""


def restorable_state(
    saved: State | None, saved_version: int, current_version: int
) -> State | None:
    """Returns the saved state if it belongs to the current layout.

    Args:
        saved: The state that the last session saved, or None.
        saved_version: The version of the layout that the state was saved
            for. `NO_VERSION` if the state was saved without one.
        current_version: The version of the layout that this release has.

    Returns:
        The state to restore, or None if the header should keep its default.
    """
    if not saved or saved_version != current_version:
        return None
    return saved
