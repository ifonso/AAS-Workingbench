"""What the user can do with the files of one package.

The files panel, the context menu actions, and the repair dialog all call this
class. It asks the user through `aas_editor.ui.file_dialogs`, runs the
operations of `aas_editor.application.supplementary_files` on the history of
the package, and tells the user why something did not work. It holds no rules
of its own.
"""

from collections.abc import Callable
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Protocol
from typing import TypeVar

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer
from PyQt6.QtWidgets import QWidget

from aas_editor.application import supplementary_files as files
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.changes import observer_for
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandStack
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.supplementary_files import ReferenceChoice
from aas_editor.domain import part_names
from aas_editor.domain.file_references import FileReference
from aas_editor.domain.parts import Thumbnail
from aas_editor.domain.parts import new_thumbnail
from aas_editor.ui import file_dialogs
from aas_editor.ui.delete_flow import DeleteCancelled
from aas_editor.ui.delete_flow import PreparedDelete
from aas_editor.ui.file_dialogs import ReferenceAnswer

T = TypeVar("T")

# What the operations refuse with, in words for the user.
_REFUSALS = (ReadOnlyError, files.FileOperationError, ValueError, KeyError)


class FilePackage(Protocol):
    """What the controller needs from a package."""

    @property
    def objStore(
        self,
    ) -> model.AbstractObjectStore[model.Identifier, model.Identifiable]:
        """The shells, submodels, and concept descriptions."""
        ...

    @property
    def fileStore(self) -> AbstractSupplementaryFileContainer:
        """The supplementary files."""
        ...

    @property
    def commandStack(self) -> CommandStack:
        """The undo history."""
        ...

    thumbnail: Thumbnail | None
    """The package thumbnail, or None."""


class FileController:
    """The actions of the user on the files of a package."""

    def __init__(
        self, package: FilePackage, parent: QWidget | None = None
    ) -> None:
        """Creates the controller.

        Args:
            package: The package whose files are changed.
            parent: The parent widget of the dialogs.
        """
        self._package = package
        self._parent = parent

    # -- access ------------------------------------------------------------

    @property
    def stack(self) -> CommandStack:
        """The history of the package."""
        return self._package.commandStack

    @property
    def store(self) -> AbstractSupplementaryFileContainer:
        """The files of the package."""
        return self._package.fileStore

    @property
    def observer(self) -> ModelChangeObserver:
        """Where changes of the package are reported."""
        return observer_for(self._package)

    @property
    def objects(
        self,
    ) -> model.AbstractObjectStore[model.Identifier, model.Identifiable]:
        """The shells and submodels of the package."""
        return self._package.objStore

    def infos(self) -> list[files.StoredFileInfo]:
        """Describes the stored files."""
        return files.file_infos(self.objects, self.store)

    def dangling(self) -> list[FileReference]:
        """The references to files that are not stored."""
        return files.find_dangling(self.objects, self.store)

    def _attempt(self, action: Callable[[], T]) -> tuple[bool, T | None]:
        try:
            return True, action()
        except _REFUSALS as error:
            message = error.args[0] if isinstance(error, KeyError) else error
            file_dialogs.show_warning(self._parent, str(message))
        except OSError as error:
            file_dialogs.show_warning(
                self._parent, f"The file could not be read or written: {error}"
            )
        return False, None

    # -- files of the package ----------------------------------------------

    def add_from_disk(
        self, folder: str = part_names.DEFAULT_FOLDER
    ) -> str | None:
        """Asks for a file on disk and adds it to the package.

        Returns:
            The name it is stored under, or None.
        """
        picked = file_dialogs.pick_file_to_add(self._parent)
        if picked is None:
            return None
        return self._add_picked(picked, folder, None)

    def _add_picked(
        self,
        picked: Path,
        folder: str,
        element: model.File | None,
    ) -> str | None:
        path = picked
        ok, data = self._attempt(path.read_bytes)
        if not ok or data is None:
            return None
        ok, wanted = self._attempt(
            lambda: part_names.part_name(folder, path.name)
        )
        if not ok or wanted is None:
            return None
        answer = file_dialogs.ask_text(
            self._parent,
            "Add file to package",
            "Name in the package:",
            wanted,
        )
        if answer is None:
            return None
        content_type = part_names.guess_content_type(path.name)

        def add() -> str:
            if element is None:
                return files.add_file(
                    self.stack,
                    self.observer,
                    self.store,
                    answer,
                    data,
                    content_type,
                )
            return files.add_and_link(
                self.stack,
                self.observer,
                self.store,
                element,
                answer,
                data,
                content_type,
            )

        ok, stored = self._attempt(add)
        if ok and stored is not None and stored != answer:
            file_dialogs.show_information(
                self._parent,
                f"The package has a different file named '{answer}'. The new "
                f"file is stored as '{stored}'.",
            )
        return stored if ok else None

    def new_text_file(self, element: model.File | None = None) -> str | None:
        """Asks for a name and creates an empty text file.

        Args:
            element: A File element to link to the new file in the same step.

        Returns:
            The name of the new file, or None.
        """
        default = (
            f"{part_names.DEFAULT_FOLDER}/"
            f"Textfile_{datetime.now():%Y%m%d%H%M%S}.txt"
        )
        answer = file_dialogs.ask_text(
            self._parent, "Create text file", "Name in the package:", default
        )
        if answer is None:
            return None

        def create() -> str:
            if element is None:
                return files.create_text_file(
                    self.stack, self.observer, self.store, answer
                )
            with self.stack.group(f"Create text file for {element.id_short}"):
                name = files.create_text_file(
                    self.stack, self.observer, self.store, answer
                )
                for command in files.link_commands(
                    self.observer,
                    element,
                    name,
                    self.store.get_content_type(name),
                ):
                    self.stack.push(command)
            return name

        ok, name = self._attempt(create)
        return name if ok else None

    def edit_text(self, name: str) -> bool:
        """Opens a stored text file in an editor and stores the changes.

        Returns:
            True if the content changed.
        """
        ok, text = self._attempt(lambda: files.read_text(self.store, name))
        if not ok or text is None:
            return False
        edited = file_dialogs.edit_text(name, text, self._parent)
        if edited is None:
            return False
        ok, changed = self._attempt(
            lambda: files.edit_text_file(
                self.stack, self.observer, self.store, name, edited
            )
        )
        return bool(ok and changed)

    def rename(self, name: str) -> str | None:
        """Asks for a new name and renames the file with its references.

        Returns:
            The new name, or None.
        """
        count = len(files.references_to(self.objects, name))
        suffix = (
            f"\n{count} reference(s) will be updated."
            if count
            else "\nNothing refers to this file."
        )
        answer = file_dialogs.ask_text(
            self._parent, "Rename file", f"New name:{suffix}", name
        )
        if answer is None or answer == name:
            return None
        ok, _ = self._attempt(
            lambda: files.rename_file(
                self.stack,
                self.observer,
                self.objects,
                self.store,
                name,
                answer,
            )
        )
        return answer if ok else None

    def move(self, name: str) -> str | None:
        """Asks for a folder and moves the file there with its references.

        Returns:
            The new name, or None.
        """
        count = len(files.references_to(self.objects, name))
        suffix = (
            f"\n{count} reference(s) will be updated."
            if count
            else "\nNothing refers to this file."
        )
        answer = file_dialogs.ask_text(
            self._parent,
            "Move file to folder",
            f"Folder in the package, such as /aasx/central:{suffix}",
            part_names.folder_of(name),
        )
        if answer is None:
            return None
        ok, _ = self._attempt(
            lambda: files.move_file(
                self.stack,
                self.observer,
                self.objects,
                self.store,
                name,
                answer,
            )
        )
        if not ok:
            return None
        return part_names.part_name(answer, part_names.file_name_of(name))

    def remove(self, name: str) -> bool:
        """Removes a stored file, asking what to do with its references.

        Returns:
            True if the file was removed.
        """
        choice = self.removal_choice(name)
        if choice is None:
            return False
        ok, _ = self._attempt(
            lambda: files.remove_file(
                self.stack,
                self.observer,
                self.objects,
                self.store,
                name,
                choice,
            )
        )
        return ok

    def remove_many(self, names: Sequence[str]) -> bool:
        """Removes several stored files as one step, asking once.

        One question covers the references to all of them. Cancelling it
        removes nothing, and one undo brings every file back with the paths
        that were cleared (F-EDT-09 AC18).

        Returns:
            True if the files were removed.
        """
        chosen = list(names)
        if not chosen:
            return False
        try:
            prepared = prepare_file_delete(self._package, chosen, self._parent)
        except DeleteCancelled:
            return False

        def work() -> None:
            with self.stack.group(prepared.description):
                for command in prepared.commands:
                    self.stack.push(command)
                for name in chosen:
                    self.stack.push(
                        files.RemoveFile(self.observer, self.store, name)
                    )

        ok, _ = self._attempt(work)
        return ok

    def removal_choice(self, name: str) -> ReferenceChoice | None:
        """Asks what to do with the references to a file about to go.

        Returns:
            The choice, `LEAVE` when nothing refers to the file, or None if
            the user cancelled.
        """
        references = files.references_to(self.objects, name)
        if not references:
            return ReferenceChoice.LEAVE
        answer = file_dialogs.ask_remove_references(references, self._parent)
        if answer is ReferenceAnswer.CANCEL:
            return None
        return (
            ReferenceChoice.CLEAR
            if answer is ReferenceAnswer.CLEAR
            else ReferenceChoice.LEAVE
        )

    def save_to_disk(self, name: str) -> bool:
        """Asks where to write a stored file, and writes it there.

        Returns:
            True if the file was written.
        """
        target = file_dialogs.pick_path_to_save(
            self._parent, part_names.local_file_name(name)
        )
        if target is None:
            return False
        ok, _ = self._attempt(
            lambda: target.write_bytes(files.read_file(self.store, name))
        )
        return ok

    # -- links from File elements and thumbnails -----------------------------

    def choose_for(self, element: model.File) -> bool:
        """Asks which stored file a File element refers to, and links it.

        The media type of the element stays as it is.

        Returns:
            True if the element was linked.
        """
        name = file_dialogs.choose_stored_file(
            self.infos(),
            element.value,
            "Choose package file",
            self._parent,
        )
        if name is None:
            return False
        ok, _ = self._attempt(
            lambda: files.link_file_element(
                self.stack, self.observer, self.store, element, name
            )
        )
        return ok

    def add_for(self, element: model.File) -> str | None:
        """Adds a file from disk to the package and links the element to it.

        The media type of the element becomes the one of the file.
        """
        picked = file_dialogs.pick_file_to_add(self._parent)
        if picked is None:
            return None
        return self._add_picked(picked, part_names.DEFAULT_FOLDER, element)

    def edit_text_of(self, element: model.File) -> bool:
        """Edits the stored text file that a File element refers to."""
        name = element.value
        if not name or name not in self.store:
            file_dialogs.show_warning(
                self._parent,
                "The File element does not refer to a file in the package.",
            )
            return False
        return self.edit_text(name)

    def choose_thumbnail(self, asset: model.AssetInformation) -> bool:
        """Asks which stored file is the default thumbnail, and sets it."""
        current = asset.default_thumbnail
        name = file_dialogs.choose_stored_file(
            self.infos(),
            current.path if current is not None else None,
            "Choose default thumbnail",
            self._parent,
        )
        if name is None:
            return False
        ok, _ = self._attempt(
            lambda: files.link_thumbnail(
                self.stack, self.observer, self.store, asset, name
            )
        )
        return ok

    def add_thumbnail(self, asset: model.AssetInformation) -> str | None:
        """Adds an image from disk and sets it as the default thumbnail."""
        picked = file_dialogs.pick_file_to_add(self._parent)
        if picked is None:
            return None
        try:
            with self.stack.group("Add file as default thumbnail"):
                name = self._add_picked(picked, part_names.DEFAULT_FOLDER, None)
                if name is None:
                    # Nothing was added, so the group stays empty.
                    return None
                files.link_thumbnail(
                    self.stack, self.observer, self.store, asset, name
                )
        except _REFUSALS as error:
            file_dialogs.show_warning(self._parent, str(error))
            return None
        return name

    def change_package_thumbnail(self) -> bool:
        """Asks for an image and makes it the thumbnail of the package.

        The thumbnail is the image that a file browser shows for the AASX
        file. It is not one of the stored files (F-EDT-10 AC5).

        Returns:
            True if the thumbnail changed.
        """
        picked = file_dialogs.pick_thumbnail_image(self._parent)
        if picked is None:
            return False
        ok, data = self._attempt(picked.read_bytes)
        if not ok or data is None:
            return False
        ok, thumbnail = self._attempt(
            lambda: new_thumbnail(
                picked.name, data, part_names.guess_content_type(picked.name)
            )
        )
        if not ok or thumbnail is None:
            return False
        ok, changed = self._attempt(
            lambda: files.change_package_thumbnail(
                self.stack, self.observer, self._package, thumbnail
            )
        )
        return bool(ok and changed)

    def remove_thumbnail(self, asset: model.AssetInformation) -> bool:
        """Takes the default thumbnail away after a question (F-EDT-02 AC14).

        The stored file stays in the package. After this the asset has none,
        and the choose and add actions set a new one.

        Returns:
            True if the thumbnail was removed.
        """
        current = asset.default_thumbnail
        if current is None:
            file_dialogs.show_warning(
                self._parent, "The AAS has no default thumbnail."
            )
            return False
        if not file_dialogs.confirm(
            self._parent,
            f"Remove the default thumbnail '{current.path}' of this AAS? "
            "The file stays in the package.",
        ):
            return False
        ok, _ = self._attempt(
            lambda: files.remove_thumbnail(self.stack, self.observer, asset)
        )
        return ok

    # -- repair ------------------------------------------------------------

    def repair_dangling(self) -> None:
        """Shows the dangling references and lets the user repair them."""
        dialog = file_dialogs.DanglingDialog(self._parent)

        def refresh() -> None:
            dialog.show_references(self.dangling())

        def choose() -> None:
            references = dialog.selected_references()
            name = file_dialogs.choose_stored_file(
                self.infos(), None, "Choose package file", self._parent
            )
            if references and name is not None:
                self.relink(references, name)
            refresh()

        def add() -> None:
            references = dialog.selected_references()
            picked = file_dialogs.pick_file_to_add(self._parent)
            if references and picked is not None:
                self.add_and_relink(references, picked)
            refresh()

        def clear() -> None:
            references = dialog.selected_references()
            if references:
                self.clear_references(references)
            refresh()

        dialog.choose_button.clicked.connect(choose)  # pyright: ignore[reportOptionalMemberAccess]
        dialog.add_button.clicked.connect(add)  # pyright: ignore[reportOptionalMemberAccess]
        dialog.clear_button.clicked.connect(clear)  # pyright: ignore[reportOptionalMemberAccess]
        refresh()
        dialog.exec()

    def relink(self, references: Sequence[FileReference], name: str) -> bool:
        """Makes the references point to a stored file, as one step."""

        def link() -> None:
            with self.stack.group(
                f"Repair {len(references)} file reference(s)"
            ):
                for reference in references:
                    for command in files.link_commands(
                        self.observer, reference, name
                    ):
                        self.stack.push(command)

        ok, _ = self._attempt(link)
        return ok

    def add_and_relink(
        self, references: Sequence[FileReference], picked: Path
    ) -> bool:
        """Adds a file from disk, and points the references to it."""
        path = picked

        def work() -> None:
            data = path.read_bytes()
            wanted = part_names.part_name(part_names.DEFAULT_FOLDER, path.name)
            with self.stack.group(
                f"Repair {len(references)} file reference(s)"
            ):
                name = files.add_file(
                    self.stack,
                    self.observer,
                    self.store,
                    wanted,
                    data,
                    part_names.guess_content_type(path.name),
                )
                for reference in references:
                    for command in files.link_commands(
                        self.observer, reference, name
                    ):
                        self.stack.push(command)

        ok, _ = self._attempt(work)
        return ok

    def clear_references(self, references: Sequence[FileReference]) -> bool:
        """Takes the paths out of the references, as one step."""

        def clear() -> None:
            with self.stack.group(f"Clear {len(references)} file path(s)"):
                for reference in references:
                    self.stack.push(
                        files.clear_reference_command(self.observer, reference)
                    )

        ok, _ = self._attempt(clear)
        return ok


def prepare_file_delete(
    package: FilePackage,
    names: Sequence[str],
    parent: QWidget | None = None,
) -> PreparedDelete:
    """Asks what to do with the references to files that are about to go.

    A tree view calls this before it deletes the rows of stored files. It
    returns the commands that take the paths out, which the view pushes in the
    same group as the deletes, so that one undo brings back everything.

    Args:
        package: The package that holds the files.
        names: The part names of the files.
        parent: The parent widget of the question.

    Returns:
        The commands for the references. Empty when nothing refers to the
        files, or when the user chose to leave the paths.

    Raises:
        DeleteCancelled: If the user cancelled.
    """
    objects = package.objStore
    references = [
        reference
        for name in names
        for reference in files.references_to(objects, name)
    ]
    description = (
        f"Remove file {names[0]}"
        if len(names) == 1
        else f"Remove {len(names)} files"
    )
    if not references:
        return PreparedDelete([], description)
    answer = file_dialogs.ask_remove_references(references, parent)
    if answer is ReferenceAnswer.CANCEL:
        raise DeleteCancelled
    commands: list[Command] = []
    if answer is ReferenceAnswer.CLEAR:
        observer = observer_for(package)
        commands = [
            files.clear_reference_command(observer, reference)
            for reference in references
        ]
    return PreparedDelete(commands, description)
