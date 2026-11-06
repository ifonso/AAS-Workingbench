# ADR 0013: Stored files change with their references, and never overwrite

**Status:** Accepted

## Context

A stored file is a name, a media type, and bytes in the container of the package. File elements and the default thumbnail of a shell refer to it by its name, and the SDK writer writes exactly the files that are referred to. Probes against the pinned SDK (commit `412a53f`) found:

| Finding | Consequence |
|---|---|
| `AbstractSupplementaryFileContainer` has `add_file`, `delete_file`, `write_file`, `get_content_type`, `get_sha256`. Only `DictSupplementaryFileContainer` has `rename_file`. No method changes the content or the media type of a name. | Rename can use the SDK method only on the dict container. Editing is a delete followed by an add. |
| `add_file` with a taken name and the same hash and media type returns the name and adds nothing. With other content, or only another media type, it returns a numbered name such as `a_0001.txt`. | A command cannot assume that an add created the file. Undo of an add that found its file there must not delete it. |
| Content is stored once for each hash, with a reference count. `delete_file` drops the bytes with the last name. | A command that removes a file must keep the bytes to put it back. |
| `rename_file` onto a name with the same content merges the two names without a message, and onto other content gives a numbered name. | A rename onto an existing name is refused before the call. |
| The container accepts any text as a name, such as `/../x`, `relative`, or `/a\b`. The writer refuses these with a `ValueError`, late. Two names that differ only in case are both written. | Names are checked as part names when they are made, and case-blind clashes count as taken. |
| The writer writes only the files that a File element or a thumbnail refers to. | A file that nothing refers to is dropped by an AASX save and by an AASX recovery. |

## Decision

- **Commands on the container** in `application/supplementary_files.py`: `AddFile`, `RemoveFile`, `RenameFile`, and `ReplaceFile`. They use the abstract interface, and the SDK `rename_file` when the container has it. Each reports `Change.changed(container)`, so the package tree and the files panel read the container again.
- **A file and its references change in one group.** `rename_file`, `move_file`, and `remove_file` build the commands for the File elements, the annotations, and the thumbnail that refer to the name, so one undo restores both. The references come from `domain/file_references`, whose `FileReference` now holds the object that has the path.
- **Nothing overwrites.** A new file with a taken name gets a number, an identical file is reused, a rename or move onto a taken name is refused, and a name that differs only in case is taken. This also holds when objects are copied to another package (`application/file_transfer.py`).
- **Names are validated in the domain** (`domain/part_names.py`): the OPC rules of the writer, no backslash, no empty, `.` or `..` segment, no trace of a drive. A name on disk is made safe with one replacement rule, and a name for extracting never chooses a folder.
- **Copying between packages is a wrapper of the add command.** The model asks `with_copied_files` before it pushes an add. The source package is remembered at copy time in `copy_source`, held weakly. A paste from a source that is not known adds no file.
- **Crash recovery keeps the files that the AASX cannot carry.** When files differ from the opened state, the recovery is an AASX. Files that nothing refers to go to a `.files.json` next to it, and `restore_from_recovery` reads them again.
- **The Delete key and the panel share the question** about the references of a file: remove the paths, leave them, or cancel. Paths that are left are dangling, and an AASX save is refused until they are repaired (D5), with a repair dialog one click away.

## Consequences

- Rename, Move, and Remove are one undo step with their references. Nothing dangles unless the user chose it.
- Another SDK container works with the commands, except that rename is a delete and an add, which loses the position in a dict.
- A paste that replaces an existing element does not bring files, because it does not go through the add of the model. This is listed as a known limit.
- The package thumbnail (an OPC part, not a File) is not linked to a stored file, and stays as it was read.
- The recovery of a package with a File under an annotation or a dangling path falls back to JSON plus the extra files for the session's new or changed files. A rename or remove in such a package is not restored.

## Alternatives considered

- **Updating references with a rename dialog that offers "leave them".** Rejected: a rename that leaves the old name pointing at nothing has no use, and the AASX save would refuse it.
- **Wrapping the dangling or unreferenced files in a fake submodel so that the writer keeps them.** Rejected for the reason of [ADR 0006](0006-safe-save.md): it leaves a junk part in the package.
- **A file model class with its own identity.** Rejected: the tree rows are stand-ins for names, and the container is the one source of truth.
