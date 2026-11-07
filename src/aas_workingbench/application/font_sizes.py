"""Which saved font size of the trees the next session may keep.

The trees save their font size at every exit, so a user who never zoomed has
the old default saved. When a release lowers the default, that saved size
would keep every such user on the old one, and the rows would not fit.

A size is saved together with the version of the default that it was saved
under. A size from before versions existed that equals the old default counts
as the default, and takes the new one. Any other size was chosen by the user,
and is kept. The session that migrates saves the new version, so a user who
later zooms back to the old default keeps it.
"""

from typing import Final

FONT_SIZE_LAYOUT_VERSION: Final = 1
"""The version of the default font size that this release has."""

NO_VERSION: Final = 0
"""The version of a size that was saved before versions existed."""

OLD_DEFAULT_POINT_SIZE: Final = 12
"""The default size of the releases before `FONT_SIZE_LAYOUT_VERSION` 1."""


def migrated_font_size(
    saved: int,
    saved_version: int,
    new_default: int,
    current_version: int = FONT_SIZE_LAYOUT_VERSION,
) -> int:
    """Gives the size the trees start with, from the size of the last session.

    Args:
        saved: The size in points that the last session saved, or the default
            when it saved none.
        saved_version: The version of the default that the size was saved
            under. `NO_VERSION` for a size saved by an older release.
        new_default: The default size of this release in points.
        current_version: The version of the default that this release has.

    Returns:
        `new_default` for the old default of an older release, and `saved` for
        any other size and for a size of this version.
    """
    if saved_version < current_version and saved == OLD_DEFAULT_POINT_SIZE:
        return new_default
    return saved
