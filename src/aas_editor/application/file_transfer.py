"""Bringing supplementary files along when objects are copied to a package.

A File element holds only the path of a file in its own package. Pasting a
submodel or element into another package leaves the path pointing at nothing
there, and the SDK then refuses to write the package. When the objects come
from a package whose files are known, the files they refer to are copied too,
as part of the same undo step as the paste.

Names never overwrite anything. A file is copied under its own name when the
target has no file of that name. An identical file is reused. A different file
under the same name, or under a name that differs only in case, makes the
copy get a numbered name, and the pasted paths follow it.

Example:
    Pasting a submodel, with its files::

        command = with_copied_files(
            AddMember(observer, objects, submodel),
            submodel,
            source_files,
            package.fileStore,
            observer,
        )
        stack.push(command)
"""

from collections.abc import Iterable
from dataclasses import dataclass
import hashlib
import logging
from typing import Any
import weakref

from basyx.aas import model
from basyx.aas.adapter.aasx import AbstractSupplementaryFileContainer

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.commands import CommandGroup
from aas_editor.application.edits import SetAttribute
from aas_editor.application.listeners import Listeners
from aas_editor.application.supplementary_files import AddFile
from aas_editor.application.supplementary_files import read_file
from aas_editor.domain import part_names
from aas_editor.domain.file_references import FileReference
from aas_editor.domain.file_references import references_in

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlannedCopy:
    """One file that is copied into the target package.

    Attributes:
        source: The name in the package it comes from.
        target: The name it gets in the target package.
        data: The content.
        content_type: The media type.
    """

    source: str
    target: str
    data: bytes
    content_type: str

    @property
    def renamed(self) -> bool:
        """Whether a different file had the name in the target."""
        return self.source != self.target


@dataclass(frozen=True)
class TransferPlan:
    """What bringing the files of copied objects along would do.

    Attributes:
        copies: The files to add to the target package.
        reused: The names of files that the target has already, identical.
        missing: Paths that the objects refer to, but the source package has
            no file for. They are left as they are.
        invalid: Paths in the source that are not valid part names. They are
            not copied.
        changes: The references whose path changes, with the new path.
    """

    copies: tuple[PlannedCopy, ...] = ()
    reused: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()
    changes: tuple[tuple[FileReference, str], ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether there is nothing to report or do."""
        return not (self.copies or self.reused or self.missing or self.invalid)

    @property
    def renamed(self) -> tuple[PlannedCopy, ...]:
        """The copies that got another name, because of a collision."""
        return tuple(copy for copy in self.copies if copy.renamed)

    def summary(self) -> str:
        """Returns one sentence for the status bar."""
        parts: list[str] = []
        if self.copies:
            parts.append(f"{len(self.copies)} file(s) copied")
        if self.renamed:
            names = ", ".join(
                f"{copy.source} as {copy.target}" for copy in self.renamed
            )
            parts.append(f"renamed because the name was taken: {names}")
        if self.reused:
            parts.append(f"{len(self.reused)} identical file(s) reused")
        if self.missing:
            parts.append(
                f"{len(self.missing)} file(s) not found in the source package"
            )
        if self.invalid:
            parts.append(f"{len(self.invalid)} file name(s) not valid")
        return "Pasted with files: " + "; ".join(parts) if parts else ""


def plan_transfer(
    references: Iterable[FileReference],
    source: AbstractSupplementaryFileContainer,
    target: AbstractSupplementaryFileContainer,
) -> TransferPlan:
    """Plans which files to copy, and which paths to change.

    Args:
        references: The references of the objects that are copied.
        source: The files of the package they come from.
        target: The files of the package they go to.

    Returns:
        The plan. Nothing changes.
    """
    taken = list(target)
    copies: dict[str, PlannedCopy] = {}
    reused: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []
    mapping: dict[str, str] = {}
    changes: list[tuple[FileReference, str]] = []
    reference_list = list(references)
    for path in dict.fromkeys(ref.path for ref in reference_list):
        if path not in source:
            missing.append(path)
            continue
        if not part_names.is_valid(path):
            invalid.append(path)
            continue
        data = read_file(source, path)
        content_type = source.get_content_type(path)
        digest = hashlib.sha256(data).digest()
        clash = part_names.find_clash(path, taken)
        if clash is None:
            name = path
        elif (
            clash == path
            and clash in target
            and target.get_sha256(clash) == digest
            and target.get_content_type(clash) == content_type
        ):
            reused.append(path)
            mapping[path] = path
            continue
        else:
            name = part_names.unique_name(path, taken)
        taken.append(name)
        mapping[path] = name
        copies[path] = PlannedCopy(path, name, data, content_type)
    for reference in reference_list:
        new = mapping.get(reference.path)
        if new is not None and new != reference.path:
            changes.append((reference, new))
    return TransferPlan(
        tuple(copies.values()),
        tuple(reused),
        tuple(missing),
        tuple(invalid),
        tuple(changes),
    )


def with_copied_files(
    command: Command,
    obj: object,
    source: AbstractSupplementaryFileContainer | None,
    target: AbstractSupplementaryFileContainer,
    observer: ModelChangeObserver,
) -> Command:
    """Wraps the command that adds copied objects, so that their files follow.

    Args:
        command: The command that adds the objects to the package.
        obj: The object that is added: a shell, submodel, or element.
        source: The files of the package the object was copied from, or None
            when that is not known. Then nothing is brought along.
        target: The files of the package the object goes to.
        observer: Where the commands report.

    Returns:
        The command itself when no file needs to be brought along. Otherwise
        a group that adds the files, adds the object, and points the pasted
        paths at the stored names, as one undo step. The plan is announced to
        `transfer_reports`.
    """
    if source is None or source is target:
        return command
    if not isinstance(obj, (model.Identifiable, model.SubmodelElement)):
        return command
    before, after = transfer_commands(
        observer, references_in(obj), source, target
    )
    if not before and not after:
        return command
    return CommandGroup(command.description, [*before, command, *after])


def transfer_commands(
    observer: ModelChangeObserver,
    references: Iterable[FileReference],
    source: AbstractSupplementaryFileContainer,
    target: AbstractSupplementaryFileContainer,
) -> tuple[list[Command], list[Command]]:
    """Builds the commands that bring the files of copied objects along.

    The plan is announced to `transfer_reports`, so that the window can tell
    the user what was copied, reused, or numbered.

    Args:
        observer: Where the commands report.
        references: The references of the copies that are pasted. Their
            holders are the objects of the copies, not of the original.
        source: The files of the package the objects were copied from.
        target: The files of the package they are pasted into.

    Returns:
        The commands that add the files, which come before the commands that
        insert the copies, and the commands that point the pasted paths at the
        stored names, which come after. Both are empty when there is nothing
        to bring.
    """
    plan = plan_transfer(references, source, target)
    if plan.is_empty:
        return [], []
    adds: list[Command] = [
        AddFile(
            observer,
            target,
            copy.target,
            copy.data,
            copy.content_type,
            description=f"Copy file {copy.target}",
        )
        for copy in plan.copies
    ]
    updates: list[Command] = []
    for reference, new in plan.changes:
        holder: Any = reference.holder
        updates.append(
            SetAttribute(
                observer,
                holder,
                reference.attribute,
                new,
                description=f"Update {reference.location}",
            )
        )
    if plan.missing or plan.invalid:
        logger.warning(
            "Pasted objects refer to files that were not copied: %s",
            [*plan.missing, *plan.invalid],
        )
    transfer_reports.notify(plan)
    return adds, updates


# Called with the plan when a paste brings files along, so that the window can
# tell the user. A bound method is held weakly.
transfer_reports: Listeners[[TransferPlan]] = Listeners()


class PackageContent:
    """The objects and files of a package that was read to copy from it.

    Attributes:
        objStore: The shells, submodels, and concept descriptions.
        fileStore: The supplementary files.
    """

    def __init__(
        self,
        objects: model.AbstractObjectStore[
            model.Identifier, model.Identifiable
        ],
        files: AbstractSupplementaryFileContainer,
    ) -> None:
        self.objStore = objects
        self.fileStore = files


class CopySource:
    """Remembers the package that objects were last copied from.

    The copied objects hold paths only. The model that adds them asks here
    where the files are. The package is held weakly, so a closed package is
    forgotten. Anything with a `fileStore` can be the source, such as a
    template that was read for its submodels.
    """

    def __init__(self) -> None:
        self._source: weakref.ref[Any] | None = None

    def remember(self, source: object) -> None:
        """Remembers the package that is copied from."""
        self._source = weakref.ref(source)

    def forget(self) -> None:
        """Forgets the source, for example when the clipboard is cleared."""
        self._source = None

    @property
    def store(self) -> AbstractSupplementaryFileContainer | None:
        """The files of the source package, or None if unknown or closed."""
        source = self._source() if self._source is not None else None
        store: AbstractSupplementaryFileContainer | None = getattr(
            source, "fileStore", None
        )
        return store


copy_source = CopySource()
