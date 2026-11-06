"""Tests for the package thumbnail (F-EDT-10 AC5)."""

import pytest

from aas_editor.application import supplementary_files as files
from aas_editor.application.changes import observer_for
from aas_editor.application.commands import CommandStack
from aas_editor.domain.parts import Thumbnail
from aas_editor.domain.parts import ThumbnailError
from aas_editor.domain.parts import new_thumbnail


class _Package:
    """Stands in for a package: it has a thumbnail."""

    def __init__(self, thumbnail: Thumbnail | None = None) -> None:
        self.thumbnail = thumbnail


class TestNewThumbnail:
    def test_the_part_is_named_after_the_extension_of_the_file(self) -> None:
        thumbnail = new_thumbnail("My Logo.PNG", b"png", "image/png")

        assert thumbnail == Thumbnail(
            "/docProps/thumbnail.png", "image/png", b"png"
        )

    def test_a_windows_path_gives_its_extension(self) -> None:
        thumbnail = new_thumbnail("C:\\pics\\logo.jpeg", b"j", "image/jpeg")

        assert thumbnail.name == "/docProps/thumbnail.jpeg"

    @pytest.mark.parametrize(
        ("name", "data", "content_type", "reason"),
        [
            ("notes.txt", b"x", "text/plain", "not an image"),
            ("empty.png", b"", "image/png", "is empty"),
            ("logo", b"x", "image/png", "no usable file extension"),
            ("logo.p ng", b"x", "image/png", "no usable file extension"),
        ],
    )
    def test_a_file_that_cannot_be_a_thumbnail_is_refused_with_a_reason(
        self, name: str, data: bytes, content_type: str, reason: str
    ) -> None:
        with pytest.raises(ThumbnailError, match=reason):
            new_thumbnail(name, data, content_type)


class TestChange:
    def test_the_change_is_one_undoable_step(self) -> None:
        package = _Package()
        stack = CommandStack()
        thumbnail = new_thumbnail("a.png", b"a", "image/png")

        changed = files.change_package_thumbnail(
            stack, observer_for(package), package, thumbnail
        )
        after = package.thumbnail
        stack.undo()
        undone = package.thumbnail
        stack.redo()

        assert changed
        assert (after, undone, package.thumbnail) == (
            thumbnail,
            None,
            thumbnail,
        )

    def test_it_replaces_an_existing_thumbnail(self) -> None:
        old = new_thumbnail("old.png", b"old", "image/png")
        package = _Package(old)
        stack = CommandStack()
        new = new_thumbnail("new.jpg", b"new", "image/jpeg")

        files.change_package_thumbnail(
            stack, observer_for(package), package, new
        )
        stack.undo()

        assert package.thumbnail == old

    def test_the_same_thumbnail_changes_nothing(self) -> None:
        thumbnail = new_thumbnail("a.png", b"a", "image/png")
        package = _Package(thumbnail)
        stack = CommandStack()

        changed = files.change_package_thumbnail(
            stack, observer_for(package), package, thumbnail
        )

        assert not changed
        assert not stack.can_undo
