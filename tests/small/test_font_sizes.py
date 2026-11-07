"""The font size of the trees moves to the new default exactly once."""

from aas_workingbench.application.font_sizes import FONT_SIZE_LAYOUT_VERSION
from aas_workingbench.application.font_sizes import NO_VERSION
from aas_workingbench.application.font_sizes import OLD_DEFAULT_POINT_SIZE
from aas_workingbench.application.font_sizes import migrated_font_size

NEW_DEFAULT = 10


def test_the_old_default_of_an_older_release_takes_the_new_default() -> None:
    size = migrated_font_size(OLD_DEFAULT_POINT_SIZE, NO_VERSION, NEW_DEFAULT)

    assert size == NEW_DEFAULT


def test_a_size_that_the_user_chose_is_kept() -> None:
    size = migrated_font_size(16, NO_VERSION, NEW_DEFAULT)

    assert size == 16


def test_a_smaller_size_than_the_new_default_is_kept() -> None:
    size = migrated_font_size(8, NO_VERSION, NEW_DEFAULT)

    assert size == 8


def test_the_old_default_chosen_after_the_migration_is_kept() -> None:
    size = migrated_font_size(
        OLD_DEFAULT_POINT_SIZE, FONT_SIZE_LAYOUT_VERSION, NEW_DEFAULT
    )

    assert size == OLD_DEFAULT_POINT_SIZE


def test_a_size_of_a_later_version_is_kept() -> None:
    size = migrated_font_size(
        OLD_DEFAULT_POINT_SIZE, FONT_SIZE_LAYOUT_VERSION + 1, NEW_DEFAULT
    )

    assert size == OLD_DEFAULT_POINT_SIZE


def test_the_new_default_stays_after_the_migration() -> None:
    migrated = migrated_font_size(
        OLD_DEFAULT_POINT_SIZE, NO_VERSION, NEW_DEFAULT
    )

    again = migrated_font_size(migrated, FONT_SIZE_LAYOUT_VERSION, NEW_DEFAULT)

    assert again == NEW_DEFAULT
