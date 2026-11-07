"""The supplementary files of a package, and the objects that refer to them.

A stored file is only a name, a media type, and bytes in the container of the
package. File elements and the default thumbnail of a shell refer to it by
name, and the SDK writer writes exactly the files that are referred to. So
every change here keeps the two together: renaming or moving a file updates
its references in the same undo step (D15), and nothing is left pointing at a
name that no longer exists unless the user chose that.

The SDK container offers add, delete, and read. Only `DictSupplementaryFileContainer`
has `rename_file`, so the commands use the abstract interface, and rename with
the SDK method when the container has one.

Example:
    Moving a file to another folder, with its references::

        move_file(
            stack,
            observer,
            package.objStore,
            package.fileStore,
            "/aasx/files/a.pdf",
            "/aasx/docs",
        )
        stack.undo()
"""

from collections.abc import Iterable
from dataclasses import dataclass
import enum
import hashlib
import io
from typing import Any

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer

from aas_workingbench.application.changes import Change
from aas_workingbench.application.changes import ModelChangeObserver
from aas_workingbench.application.commands import Command
from aas_workingbench.application.commands import CommandStack
from aas_workingbench.application.edits import SetAttribute
from aas_workingbench.domain import part_names
from aas_workingbench.domain.file_references import FileReference
from aas_workingbench.domain.file_references import file_references
from aas_workingbench.domain.parts import Thumbnail


class FileOperationError(ValueError):
    """A change of the files that cannot be made, with a reason for the user."""


class FileNameTakenError(FileOperationError):
    """A stored file has the name already, or a name that is the same part."""


class NotTextError(FileOperationError):
    """The bytes of a file are not UTF-8 text, so it cannot be edited as text."""


class ReferenceChoice(enum.Enum):
    """What to do with the references to a file that is removed."""

    CLEAR = "clear"
    """Take the path out of every File element, and the default thumbnail."""
    LEAVE = "leave"
    """Leave the paths. A save is refused until they are repaired."""


@dataclass(frozen=True)
class StoredFileInfo:
    """What the files panel shows for one stored file.

    Attributes:
        name: The part name.
        content_type: The media type.
        size: The number of bytes.
        references: The File elements and thumbnails that refer to the file.
    """

    name: str
    content_type: str
    size: int
    references: tuple[FileReference, ...]

    @property
    def is_referenced(self) -> bool:
        """Whether a save writes the file, because something refers to it."""
        return bool(self.references)


def read_file(store: AbstractSupplementaryFileContainer, name: str) -> bytes:
    """Returns the bytes of a stored file.

    Raises:
        KeyError: If there is no such file.
    """
    buffer = io.BytesIO()
    store.write_file(name, buffer)
    return buffer.getvalue()


def file_infos(
    objects: Iterable[model.Identifiable],
    store: AbstractSupplementaryFileContainer,
) -> list[StoredFileInfo]:
    """Describes every stored file, sorted by name.

    Args:
        objects: The shells and submodels of the package.
        store: The files of the package.

    Returns:
        One entry for each stored file.
    """
    references = file_references(objects)
    infos: list[StoredFileInfo] = []
    for name in sorted(store):
        infos.append(
            StoredFileInfo(
                name,
                store.get_content_type(name),
                len(read_file(store, name)),
                tuple(ref for ref in references if ref.path == name),
            )
        )
    return infos


def find_dangling(
    objects: Iterable[model.Identifiable],
    store: AbstractSupplementaryFileContainer,
) -> list[FileReference]:
    """Finds the references to package files that are not stored.

    Every File element counts, also the ones under annotations. A path
    outside the package, such as a URL, is not dangling.
    """
    stored = set(store)
    return [ref for ref in file_references(objects) if ref.path not in stored]


def references_to(
    objects: Iterable[model.Identifiable], name: str
) -> list[FileReference]:
    """Finds the references that have exactly the path `name`."""
    return [ref for ref in file_references(objects) if ref.path == name]


# ---------------------------------------------------------------------------
# Commands on the container
# ---------------------------------------------------------------------------


def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


class _FileCommand(Command):
    def __init__(
        self,
        observer: ModelChangeObserver,
        store: AbstractSupplementaryFileContainer,
    ) -> None:
        self._observer = observer
        self._store = store

    def _notify(self) -> None:
        # The tree and the files panel read the container again.
        self._observer.notify(Change.changed(self._store))

    def _put(self, name: str, data: bytes, content_type: str) -> None:
        stored = self._store.add_file(name, io.BytesIO(data), content_type)
        if stored != name:
            # Cannot happen after the name was checked free, but a different
            # name would break the references that this command knows about.
            self._store.delete_file(stored)
            raise FileNameTakenError(f"'{name}' is taken in the package.")


class AddFile(_FileCommand):
    """Stores a file under a name, and removes it again on undo.

    The name must be free. A file with the same name, content and media type
    is not an error: nothing is added, and undo leaves that file alone.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        store: AbstractSupplementaryFileContainer,
        name: str,
        data: bytes,
        content_type: str,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            store: The files of the package.
            name: The part name. It is checked now.
            data: The content.
            content_type: The media type.
            description: Text for Undo and Redo.

        Raises:
            InvalidPartNameError: If the name is not a valid part name.
        """
        super().__init__(observer, store)
        self.description = description or f"Add file {name}"
        self._name = part_names.validate(name)
        self._data = data
        self._content_type = content_type
        self._added = False

    @property
    def name(self) -> str:
        """The name the file is stored under."""
        return self._name

    def apply(self) -> None:
        """Stores the file.

        Raises:
            FileNameTakenError: If another file has the name, or a name that
                is the same part.
        """
        clash = part_names.find_clash(self._name, list(self._store))
        if clash is None:
            self._put(self._name, self._data, self._content_type)
            self._added = True
        elif (
            clash == self._name
            and self._store.get_sha256(clash) == _digest(self._data)
            and self._store.get_content_type(clash) == self._content_type
        ):
            self._added = False
        else:
            raise FileNameTakenError(
                f"The package has a different file '{clash}' already."
            )
        self._notify()

    def revert(self) -> None:
        """Removes the file, unless it was there before."""
        if self._added:
            self._store.delete_file(self._name)
        self._notify()


class RemoveFile(_FileCommand):
    """Removes a file from the package, and stores it again on undo."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        store: AbstractSupplementaryFileContainer,
        name: str,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            store: The files of the package.
            name: The part name of the file to remove.
            description: Text for Undo and Redo.
        """
        super().__init__(observer, store)
        self.description = description or f"Remove file {name}"
        self._name = name
        self._data = b""
        self._content_type = ""

    def apply(self) -> None:
        """Remembers the file, and removes it.

        Raises:
            KeyError: If there is no such file. Nothing changes.
        """
        self._data = read_file(self._store, self._name)
        self._content_type = self._store.get_content_type(self._name)
        self._store.delete_file(self._name)
        self._notify()

    def revert(self) -> None:
        """Stores the file again under its name."""
        self._put(self._name, self._data, self._content_type)
        self._notify()


class RenameFile(_FileCommand):
    """Gives a stored file another name. Its references are not touched."""

    def __init__(
        self,
        observer: ModelChangeObserver,
        store: AbstractSupplementaryFileContainer,
        old: str,
        new: str,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            store: The files of the package.
            old: The part name of the file.
            new: The new part name. It is checked now.
            description: Text for Undo and Redo.

        Raises:
            InvalidPartNameError: If the new name is not a valid part name.
        """
        super().__init__(observer, store)
        self.description = description or f"Rename file {old}"
        self._old = old
        self._new = part_names.validate(new)

    def apply(self) -> None:
        """Renames the file.

        Raises:
            KeyError: If there is no file with the old name.
            FileNameTakenError: If another file has the new name, or a name
                that is the same part. The SDK would merge or renumber.
        """
        self._move(self._old, self._new)

    def revert(self) -> None:
        """Gives the file its old name."""
        self._move(self._new, self._old)

    def _move(self, source: str, target: str) -> None:
        if source not in self._store:
            raise KeyError(source)
        others = [name for name in self._store if name != source]
        clash = part_names.find_clash(target, others)
        if clash is not None:
            raise FileNameTakenError(
                f"The package has a file '{clash}' already."
            )
        if isinstance(self._store, DictSupplementaryFileContainer):
            stored = self._store.rename_file(source, target)
            if stored != target:
                raise FileNameTakenError(f"'{target}' is taken in the package.")
        else:
            data = read_file(self._store, source)
            content_type = self._store.get_content_type(source)
            self._store.delete_file(source)
            self._put(target, data, content_type)
        self._notify()


class ReplaceFile(_FileCommand):
    """Changes the bytes of a stored file, and the media type if wanted.

    The name stays, so the references stay. Undo gives the old bytes back.
    """

    def __init__(
        self,
        observer: ModelChangeObserver,
        store: AbstractSupplementaryFileContainer,
        name: str,
        data: bytes,
        content_type: str | None = None,
        description: str | None = None,
    ) -> None:
        """Creates the command without changing anything.

        Args:
            observer: Where to report the change.
            store: The files of the package.
            name: The part name of the file.
            data: The new content.
            content_type: The new media type, None to keep the old one.
            description: Text for Undo and Redo.
        """
        super().__init__(observer, store)
        self.description = description or f"Edit file {name}"
        self._name = name
        self._data = data
        self._content_type = content_type
        self._old_data = b""
        self._old_content_type = ""

    def apply(self) -> None:
        """Replaces the content.

        Raises:
            KeyError: If there is no such file. Nothing changes.
        """
        self._old_data = read_file(self._store, self._name)
        self._old_content_type = self._store.get_content_type(self._name)
        self._store.delete_file(self._name)
        self._put(
            self._name,
            self._data,
            self._content_type or self._old_content_type,
        )
        self._notify()

    def revert(self) -> None:
        """Puts the old content back."""
        self._store.delete_file(self._name)
        self._put(self._name, self._old_data, self._old_content_type)
        self._notify()


# ---------------------------------------------------------------------------
# Operations for the user's actions
# ---------------------------------------------------------------------------


def resolve_new_name(
    store: AbstractSupplementaryFileContainer,
    wanted: str,
    data: bytes,
    content_type: str,
) -> tuple[str, bool]:
    """Chooses the name for a new file so that nothing is overwritten.

    Args:
        store: The files of the package.
        wanted: The wanted part name.
        data: The content.
        content_type: The media type.

    Returns:
        The name to store under, and whether the package has this very file
        under that name already, so that nothing needs to be added. If another
        file has the name, or differs only in case, the name gets a number.

    Raises:
        InvalidPartNameError: If the wanted name is not valid.
    """
    wanted = part_names.validate(wanted)
    clash = part_names.find_clash(wanted, list(store))
    if (
        clash == wanted
        and store.get_sha256(wanted) == _digest(data)
        and store.get_content_type(wanted) == content_type
    ):
        return wanted, True
    return part_names.unique_name(wanted, list(store)), False


def add_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    wanted: str,
    data: bytes,
    content_type: str,
) -> str:
    """Stores a new file as one step, never overwriting a different file.

    Args:
        stack: The history of the package.
        observer: Where to report the change.
        store: The files of the package.
        wanted: The wanted part name.
        data: The content.
        content_type: The media type.

    Returns:
        The name it is stored under, which is numbered when the wanted name
        holds a different file.

    Raises:
        InvalidPartNameError: If the wanted name is not valid.
        ReadOnlyError: In Read mode.
    """
    name, _ = resolve_new_name(store, wanted, data, content_type)
    stack.push(AddFile(observer, store, name, data, content_type))
    return name


def link_commands(
    observer: ModelChangeObserver,
    reference: FileReference | model.File,
    name: str,
    content_type: str | None = None,
) -> list[Command]:
    """Builds the commands that make a File element or a thumbnail refer to a file.

    Args:
        observer: Where to report the changes.
        reference: A File element, or a reference found by `file_references`.
        name: The part name of the stored file.
        content_type: The media type to set as well, None to leave it.

    Returns:
        The commands, which the caller pushes.
    """
    commands: list[Command] = []
    if isinstance(reference, model.File):
        holder: Any = reference
        attribute = "value"
    else:
        holder = reference.holder
        attribute = reference.attribute
    commands.append(
        SetAttribute(
            observer,
            holder,
            attribute,
            name,
            description=f"Link {name}",
        )
    )
    if content_type is not None and holder.content_type != content_type:
        commands.append(
            SetAttribute(observer, holder, "content_type", content_type)
        )
    return commands


def link_file_element(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    element: model.File,
    name: str,
    adopt_content_type: bool = False,
) -> None:
    """Makes a File element refer to a stored file, as one step (D15).

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        store: The files of the package.
        element: The File element.
        name: The part name of a stored file.
        adopt_content_type: Also set the media type of the element to the one
            of the file. The original leaves it unchanged when a file is chosen
            and sets it when a file is uploaded.

    Raises:
        FileOperationError: If the package has no such file.
    """
    if name not in store:
        raise FileOperationError(f"The package has no file '{name}'.")
    content_type = store.get_content_type(name) if adopt_content_type else None
    with stack.group(f"Link {element.id_short} to {name}"):
        for command in link_commands(observer, element, name, content_type):
            stack.push(command)


def link_thumbnail(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    asset_information: model.AssetInformation,
    name: str,
) -> None:
    """Makes a stored file the default thumbnail of an asset, as one step.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        store: The files of the package.
        asset_information: The AssetInformation of a shell.
        name: The part name of a stored file.

    Raises:
        FileOperationError: If the package has no such file.
    """
    if name not in store:
        raise FileOperationError(f"The package has no file '{name}'.")
    content_type = store.get_content_type(name)
    resource = asset_information.default_thumbnail
    with stack.group(f"Set the default thumbnail to {name}"):
        if resource is None:
            stack.push(
                SetAttribute(
                    observer,
                    asset_information,
                    "default_thumbnail",
                    model.Resource(name, content_type),
                )
            )
        else:
            stack.push(SetAttribute(observer, resource, "path", name))
            stack.push(
                SetAttribute(observer, resource, "content_type", content_type)
            )


def remove_thumbnail(
    stack: CommandStack,
    observer: ModelChangeObserver,
    asset_information: model.AssetInformation,
) -> None:
    """Takes the default thumbnail away from an asset, as one step.

    The stored file stays in the package. Nothing refers to it any more, so a
    save lists it with the other files that nothing refers to.

    Args:
        stack: The history of the package.
        observer: Where to report the change.
        asset_information: The AssetInformation of a shell.

    Raises:
        FileOperationError: If the asset has no default thumbnail.
    """
    if asset_information.default_thumbnail is None:
        raise FileOperationError("The AAS has no default thumbnail.")
    stack.push(
        SetAttribute(
            observer,
            asset_information,
            "default_thumbnail",
            None,
            description="Remove the default thumbnail",
        )
    )


def change_package_thumbnail(
    stack: CommandStack,
    observer: ModelChangeObserver,
    package: object,
    thumbnail: Thumbnail,
) -> bool:
    """Makes an image the thumbnail of the package, as one step (F-EDT-10 AC5).

    The package thumbnail is the image that a file browser shows for the file.
    It is a part of its own, and not a stored file: no File element refers to
    it, and the file store does not list it.

    Args:
        stack: The history of the package.
        observer: Where to report the change.
        package: The package. It needs a `thumbnail` attribute.
        thumbnail: What `parts.new_thumbnail` made.

    Returns:
        False when the package has this thumbnail already, so nothing changed.
    """
    command = SetAttribute(
        observer,
        package,
        "thumbnail",
        thumbnail,
        description="Change the package thumbnail",
    )
    if command.is_noop:
        return False
    stack.push(command)
    return True


def clear_reference_command(
    observer: ModelChangeObserver, reference: FileReference
) -> Command:
    """Builds the command that takes a path out of its File or thumbnail.

    A File element gets no value. A default thumbnail is taken away, because
    its path is required.
    """
    if reference.is_thumbnail and reference.asset_information is not None:
        return SetAttribute(
            observer,
            reference.asset_information,
            "default_thumbnail",
            None,
            description="Remove the default thumbnail",
        )
    return SetAttribute(
        observer,
        reference.holder,
        reference.attribute,
        None,
        description=f"Clear the path of {reference.location}",
    )


def add_and_link(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    element: model.File,
    wanted: str,
    data: bytes,
    content_type: str,
) -> str:
    """Stores a new file and makes a File element refer to it, as one step.

    The media type of the element becomes the one of the file.

    Returns:
        The name the file is stored under.
    """
    with stack.group(f"Add file {wanted} to {element.id_short}"):
        name = add_file(stack, observer, store, wanted, data, content_type)
        for command in link_commands(observer, element, name, content_type):
            stack.push(command)
    return name


def new_text_file_name(
    store: AbstractSupplementaryFileContainer, wanted: str
) -> str:
    """Checks the wanted name of a text file that is created.

    Raises:
        InvalidPartNameError: If the name is not valid.
        FileNameTakenError: If a file has the name, or one that differs only
            in case. The original warns and changes nothing.
    """
    wanted = part_names.validate(wanted)
    clash = part_names.find_clash(wanted, list(store))
    if clash is not None:
        raise FileNameTakenError(
            f"The package has a file '{clash}' already. Use a different name."
        )
    return wanted


def create_text_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    wanted: str,
    text: str = "",
) -> str:
    """Creates a text file in the package as one step, saved as UTF-8.

    Args:
        stack: The history of the package.
        observer: Where to report the change.
        store: The files of the package.
        wanted: The part name. Its extension sets the media type, and
            `text/plain` is used when the extension says nothing about text.
        text: The content.

    Returns:
        The name of the new file.

    Raises:
        InvalidPartNameError: If the name is not valid.
        FileNameTakenError: If the name is taken.
    """
    wanted = new_text_file_name(store, wanted)
    content_type = part_names.guess_content_type(wanted)
    if not part_names.is_text_type(content_type):
        content_type = "text/plain"
    stack.push(
        AddFile(
            observer,
            store,
            wanted,
            text.encode("utf-8"),
            content_type,
            description=f"Create text file {wanted}",
        )
    )
    return wanted


def read_text(store: AbstractSupplementaryFileContainer, name: str) -> str:
    """Reads a stored file as UTF-8 text.

    Raises:
        KeyError: If there is no such file.
        NotTextError: If the bytes are not valid UTF-8.
    """
    try:
        return read_file(store, name).decode("utf-8")
    except UnicodeDecodeError as error:
        raise NotTextError(
            f"'{name}' is not UTF-8 text, so it cannot be edited as text."
        ) from error


def edit_text_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    store: AbstractSupplementaryFileContainer,
    name: str,
    text: str,
) -> bool:
    """Replaces the content of a stored text file with UTF-8, as one step.

    Returns:
        False if the text is the content already and nothing was pushed.
    """
    data = text.encode("utf-8")
    if read_file(store, name) == data:
        return False
    stack.push(ReplaceFile(observer, store, name, data))
    return True


def rename_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    objects: Iterable[model.Identifiable],
    store: AbstractSupplementaryFileContainer,
    old: str,
    new: str,
) -> int:
    """Renames a file and updates what refers to it, as one step (D15).

    Every File element and thumbnail with the old path gets the new one,
    annotations included, so nothing dangles.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        objects: The shells and submodels of the package.
        store: The files of the package.
        old: The part name of the file.
        new: The new part name.

    Returns:
        The number of references that were updated.

    Raises:
        KeyError: If there is no file with the old name.
        InvalidPartNameError: If the new name is not valid.
        FileNameTakenError: If another file has the new name.
    """
    references = references_to(objects, old)
    with stack.group(f"Rename file {old}"):
        stack.push(RenameFile(observer, store, old, new))
        for reference in references:
            stack.push(
                SetAttribute(
                    observer,
                    reference.holder,
                    reference.attribute,
                    new,
                    description=f"Update {reference.location}",
                )
            )
    return len(references)


def move_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    objects: Iterable[model.Identifiable],
    store: AbstractSupplementaryFileContainer,
    name: str,
    folder: str,
) -> int:
    """Moves a file to another folder, with its references, as one step.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        objects: The shells and submodels of the package.
        store: The files of the package.
        name: The part name of the file.
        folder: The target folder, such as `/aasx/central`. Missing folders
            need no step: a package has no folders of its own.

    Returns:
        The number of references that were updated.

    Raises:
        InvalidPartNameError: If the folder is not valid.
        FileNameTakenError: If the folder has a file of that name already.
    """
    target = part_names.part_name(folder, part_names.file_name_of(name))
    return rename_file(stack, observer, objects, store, name, target)


def remove_file(
    stack: CommandStack,
    observer: ModelChangeObserver,
    objects: Iterable[model.Identifiable],
    store: AbstractSupplementaryFileContainer,
    name: str,
    choice: ReferenceChoice = ReferenceChoice.LEAVE,
) -> int:
    """Removes a stored file as one step, and perhaps the references to it.

    Args:
        stack: The history of the package.
        observer: Where to report the changes.
        objects: The shells and submodels of the package.
        store: The files of the package.
        name: The part name of the file.
        choice: What to do with the references. The original leaves them (and
            clears the path of the one element it was started from).

    Returns:
        The number of references that were cleared.

    Raises:
        KeyError: If there is no such file.
    """
    references = (
        references_to(objects, name) if choice is ReferenceChoice.CLEAR else []
    )
    with stack.group(f"Remove file {name}"):
        for reference in references:
            stack.push(clear_reference_command(observer, reference))
        stack.push(RemoveFile(observer, store, name))
    return len(references)


def remove_commands(
    observer: ModelChangeObserver,
    objects: Iterable[model.Identifiable],
    name: str,
    choice: ReferenceChoice,
) -> list[Command]:
    """Builds the commands for the references of a file that is removed.

    The command that removes the file itself is not included.
    """
    if choice is not ReferenceChoice.CLEAR:
        return []
    return [
        clear_reference_command(observer, reference)
        for reference in references_to(objects, name)
    ]
