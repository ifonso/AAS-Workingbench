#  Copyright (C) 2021  Igor Garmaev, garmaev@gmx.net
#
#  This program is made available under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
#  without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
#  A copy of the GNU General Public License is available at http://www.gnu.org/licenses/

import hashlib
import io
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Union, Iterable, Optional
import mimetypes

from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
from basyx.aas.adapter.json import write_aas_json_file
from basyx.aas.model import (
    AssetAdministrationShell,
    Submodel,
    ConceptDescription,
    SetIdentifiableStore,
    Key,
    ModelReference,
)

from aas_editor.application.save import SaveOptions
from aas_editor.infrastructure.package_io import (
    PackageParts,
    read_package,
    write_package,
)
from aas_editor.settings.defaults import DEFAULT_COMPLETIONS
from aas_editor.settings.app_settings import AppSettings


class Package:
    def __init__(self, file: Union[str, Path] = "", failsafe=False):
        """:raise TypeError if file has wrong file type"""
        self.objStore = SetIdentifiableStore()
        self.fileStore = DictSupplementaryFileContainer()
        # Parts of the file that the object store and file store do not hold.
        self.thumbnail = None
        self.coreProperties = None
        # File elements that pointed to a part missing in the package on open.
        self.missingFiles = ()
        # True if opened in failsafe mode: the SDK does not report what it
        # skipped, so the package must not overwrite its source (D6).
        self.partial = False
        # The file the content was read from, or None for a new package.
        self.sourceFile = None
        # Hashes of the supplementary files as read, to find the files that
        # were added or changed during the session.
        self._loadedFileHashes = {}
        self.file = file
        if file:
            self._read(failsafe)
        for obj in self.objStore:
            DEFAULT_COMPLETIONS[Key]["value"].append(obj.id)
        self._changed = False

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, file):
        self._file = Path(file).absolute()

    @property
    def changed(self) -> bool:
        """True if the package holds modifications which are not written to its file yet."""
        return self._changed

    @changed.setter
    def changed(self, value: bool):
        self._changed = bool(value)

    @property
    def writeJsonInAasx(self):
        return AppSettings.WRITE_JSON_IN_AASX.value()

    @property
    def writePrettyJson(self):
        return AppSettings.WRITE_PRETTY_JSON.value()

    @property
    def sortKeysInJson(self):
        return AppSettings.SORT_KEYS_IN_JSON.value()

    def save_options(self) -> SaveOptions:
        """The settings that change what a save writes, read once."""
        return SaveOptions(
            write_json_in_aasx=bool(self.writeJsonInAasx),
            pretty_json=bool(self.writePrettyJson),
            sort_json_keys=bool(self.sortKeysInJson),
        )

    def save_source(self) -> PackageParts:
        """The content of the package, as the save flow reads it."""
        return PackageParts(
            objects=self.objStore,
            files=self.fileStore,
            thumbnail=self.thumbnail,
            core_properties=self.coreProperties,
            missing_files=self.missingFiles,
            partial=self.partial,
            source_file=self.sourceFile,
        )

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.file.as_posix()

    def _read(self, failsafe):
        self._adopt(read_package(self.file, failsafe=failsafe))

    def _adopt(self, parts: PackageParts):
        """Takes over everything that was read from a package file."""
        self.objStore = parts.objects
        self.fileStore = parts.files
        self.thumbnail = parts.thumbnail
        self.coreProperties = parts.core_properties
        self.missingFiles = parts.missing_files
        self.partial = parts.partial
        self.sourceFile = parts.source_file
        self._loadedFileHashes = self._file_hashes()

    def _file_hashes(self) -> dict:
        return {
            name: self.fileStore.get_sha256(name) for name in self.fileStore
        }

    def session_file_names(self) -> list:
        """Names of the supplementary files that are new or changed since open."""
        return [
            name
            for name, digest in self._file_hashes().items()
            if self._loadedFileHashes.get(name) != digest
        ]

    def write(self, file: str = None):
        """Writes the package, all or nothing.

        The target is replaced only when the whole package was written, and
        ``self.file`` changes only then. A failed save leaves both as they were.
        This does not check for lost content: the save flow in
        ``aas_editor.application.save`` does, before it calls this.

        :raise TypeError if the file has a wrong file type
        :raise KeyError if a File element has no stored file
        """
        target = Path(file).absolute() if file else self.file
        write_package(target, self.save_source(), self.save_options())
        self.file = target

    def _recovery_stem(self, for_file: Path = None) -> str:
        file = self.file if for_file is None else Path(for_file)
        return hashlib.sha256(file.as_posix().encode()).hexdigest()[:12]

    def recovery_path(self, recovery_dir: Path) -> Path:
        return recovery_dir / f"{self._recovery_stem()}.json"

    def write_recovery(self, recovery_dir: Path) -> Path:
        recovery_dir.mkdir(parents=True, exist_ok=True)
        original_file = self._file
        stem = self._recovery_stem()
        meta_path = recovery_dir / f"{stem}.meta.json"

        # Recovery holds only the object store as JSON: this skips the AASX zip
        # and its supplementary files, keeping periodic writes cheap. Restore
        # reloads the files from the original. Files added during the session
        # exist nowhere else, so then the recovery is a complete AASX instead.
        rec_path = None
        if self.session_file_names():
            rec_path = self._write_aasx_recovery(recovery_dir / f"{stem}.aasx")
        if rec_path is None:
            rec_path = self._write_json_recovery(recovery_dir, stem)
        # The other kind of recovery file is stale now.
        other = ".json" if rec_path.suffix == ".aasx" else ".aasx"
        (recovery_dir / f"{stem}{other}").unlink(missing_ok=True)

        # Meta is written last: find_recovery_files() only offers entries with a
        # meta file, so an incomplete recovery is never presented for restoring.
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "original_path": original_file.as_posix(),
                    "recovery_filename": rec_path.name,
                    "partial": self.partial,
                },
                f,
            )
        return rec_path

    def _write_aasx_recovery(self, rec_path: Path) -> Optional[Path]:
        """Writes the whole package, all or nothing. None if that failed."""
        try:
            write_package(rec_path, self.save_source(), self.save_options())
        except KeyError:
            # A File element without a stored file: the SDK cannot write this
            # package. The JSON recovery still holds the objects.
            logging.warning(
                "AASX recovery not possible, writing JSON: %s",
                self.file,
                exc_info=True,
            )
            return None
        return rec_path

    def _write_json_recovery(self, recovery_dir: Path, stem: str) -> Path:
        rec_path = recovery_dir / f"{stem}.json"
        tmp_path = recovery_dir / f"{stem}.tmp.json"
        # Temp file first: a write that fails halfway must not replace a complete
        # recovery file with a truncated one.
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                write_aas_json_file(f, self.objStore)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        try:
            os.replace(tmp_path, rec_path)
        except Exception:
            # e.g. cross-device or permission error: do not leave the temp write behind
            tmp_path.unlink(missing_ok=True)
            raise
        return rec_path

    def delete_recovery(
        self, recovery_dir: Path, for_file: Path = None
    ) -> None:
        # for_file lets callers target a previous path (e.g. after Save-As mutated self.file)
        file = self.file if for_file is None else Path(for_file)
        stem = self._recovery_stem(file)
        for suffix in (".json", ".aasx", ".meta.json", ".tmp.json"):
            candidate = recovery_dir / f"{stem}{suffix}"
            candidate.unlink(missing_ok=True)

    @classmethod
    def restore_from_recovery(
        cls, recovery: Path, original_path: Path
    ) -> "Package":
        """Build a package from a recovery file, targeting its original file.

        A JSON recovery holds only the objects. They are paired with the
        supplementary files, thumbnail, and properties of the original AASX on
        disk, so a later save rebuilds the complete AASX. If the original is
        missing, those cannot be recovered. An AASX recovery is complete, and
        keeps the files that were added after the original was opened.
        """
        pack = cls(recovery)
        pack.file = original_path
        pack.sourceFile = pack.file
        pack.partial = cls._recovery_was_partial(recovery) or pack.partial
        if pack.file.suffix.lower() == ".aasx":
            if pack.file.exists():
                original = read_package(pack.file, failsafe=True)
                if recovery.suffix.lower() != ".aasx":
                    pack.fileStore = original.files
                    pack.thumbnail = original.thumbnail
                    pack.coreProperties = original.core_properties
                    pack.missingFiles = original.missing_files
                # Whatever differs from the original on disk is new.
                pack._loadedFileHashes = {
                    name: original.files.get_sha256(name)
                    for name in original.files
                }
            else:
                logging.warning(
                    "Original AASX missing, supplementary files not recovered: %s",
                    pack.file,
                )
        return pack

    @staticmethod
    def _recovery_was_partial(recovery: Path) -> bool:
        meta = recovery.parent / f"{recovery.stem}.meta.json"
        try:
            with open(meta, encoding="utf-8") as f:
                return bool(json.load(f).get("partial", False))
        except (OSError, ValueError):
            return False

    def all_submodels_to_aas(self) -> int:
        """Add references of all existing submodels to the first AAS.

        Saving no longer does this on its own (D8). It is an explicit action.

        :return: the number of references that were added
        """
        for shell in self.shells:
            before = len(shell.submodel)
            for submodel in self.submodels:
                shell.submodel.add(ModelReference.from_referable(submodel))
            return len(shell.submodel) - before
        return 0

    @property
    def name(self):
        return self.file.name

    @name.setter
    def name(self, name):
        self.file = self.file.parent.joinpath(name)

    @property
    def shells(self) -> Iterable[AssetAdministrationShell]:
        return self._iter_objects(AssetAdministrationShell)

    @property
    def submodels(self) -> Iterable[Submodel]:
        return self._iter_objects(Submodel)

    @property
    def concept_descriptions(self) -> Iterable[ConceptDescription]:
        return self._iter_objects(ConceptDescription)

    # @property
    # def others(self):
    #     for obj in self.objStore:
    #         if not isinstance(obj,
    #                           (AssetAdministrationShell, Asset, Submodel, ConceptDescription)):
    #             yield obj

    def _iter_objects(self, objtype):
        for obj in self.objStore:
            if isinstance(obj, objtype):
                yield obj

    @property
    def files(self):
        for file in self.fileStore:
            yield file

    def add(self, obj):
        if isinstance(obj, StoredFile):
            newName = self.fileStore.add_file(
                name=obj.name, file=obj.file(), content_type=obj.mime_type
            )
            obj.setFileStore(newName, self.fileStore)
        else:
            self.objStore.add(obj)

    def discard(self, obj):
        self.objStore.discard(obj)

    @property
    def numOfShells(self) -> int:
        return len(tuple(self.shells))

    @property
    def numOfSubmodels(self) -> int:
        return len(tuple(self.submodels))

    @property
    def numOfConceptDescriptions(self) -> int:
        return len(tuple(self.concept_descriptions))


class StoredFile:
    def __init__(
        self,
        name: Optional[str] = None,
        fileStore: Optional[DictSupplementaryFileContainer] = None,
        filePath: Optional[str] = None,
    ):
        if filePath:
            self._filePath = Path(filePath).absolute()
        else:
            self._filePath = filePath

        self.setFileStore(name, fileStore)

    def savedInStore(self) -> bool:
        return (
            True
            if isinstance(self._fileStore, DictSupplementaryFileContainer)
            else False
        )

    @property
    def name(self):
        if self.savedInStore():
            return self._name
        else:
            return f"/{self._filePath.name}"

    @name.setter
    def name(self, new_name: str):
        if not isinstance(new_name, str) or new_name.strip() == "":
            raise TypeError("new name must be a non-empty string")

        if self.savedInStore():
            new_stored_name = self._fileStore.rename_file(self.name, new_name)
            self._name = new_stored_name
        else:
            if self._filePath is None:
                raise ValueError("No local file path available to rename")
            new_path = self._filePath.parent.joinpath(new_name)
            if new_path.exists():
                raise FileExistsError(f"Target file already exists: {new_path}")
            self._filePath.rename(new_path)
            self._filePath = new_path

    @property
    def mime_type(self) -> str:
        if self.savedInStore():
            return self._fileStore.get_content_type(self.name)
        else:
            mimetypes.init()
            mime_type = mimetypes.guess_type(self._filePath)[0]
            if mime_type is None:
                mime_type = "application/octet-stream"
            return mime_type

    @property
    def value(self) -> bytes:
        return self.file().getvalue()

    def file(self) -> io.BytesIO:
        if self.savedInStore():
            file_content = io.BytesIO()
            self._fileStore.write_file(self.name, file_content)
        else:
            with open(self._filePath, "rb") as f:
                file_content = io.BytesIO(f.read())
        return file_content

    def setFileStore(
        self, name: str, fileStore: DictSupplementaryFileContainer
    ):
        if name is None or isinstance(name, str):
            self._name = name
        else:
            raise TypeError("arg 1 must be of type str or None")

        if fileStore is None or isinstance(
            fileStore, DictSupplementaryFileContainer
        ):
            self._fileStore = fileStore
        else:
            raise TypeError(
                "arg 2 must be of type DictSupplementaryFileContainer or None"
            )


# Register Package and StoredFile into aas_settings after both classes are fully defined.
# Imported here to break the circular dependency: package → settings → aas_settings → package.
import aas_editor.settings.package_settings  # noqa: F401
