# ADR 0006: Write packages atomically, and keep three isolated workarounds for the SDK

**Status:** Accepted

## Context

The [v1 editor plan](../../planning/v1-editor-plan.md) says that all AAS reading and writing goes through `basyx` (D3), and that a failed save leaves the original intact (D4).
Probes against the pinned SDK (commit `412a53f`) found that it cannot do this alone:

| Finding | Consequence |
|---|---|
| A File element that points to a part missing in the package makes `AASXReader.read_into` raise `KeyError`, in strict and in failsafe mode. | 13 of the 132 bundled AASX templates cannot be opened. |
| `AASXWriter(failsafe=True)` writes such a package and drops the file with a warning. `failsafe=False` raises. | A save either loses a file silently, or fails after it has opened the target. |
| `walk_submodel` skips the annotations of an `AnnotatedRelationshipElement`. Reader and writer use it to find Files. | A File under an annotation is lost on read and on write, even with `failsafe=False`. |
| `write_thumbnail` for a part that was already written as the default thumbnail adds a second zip entry, with only a `UserWarning`. | The thumbnail of many real packages is also their default thumbnail. |
| `get_thumbnail` returns the bytes only. | The part name and the content type are lost. |
| `read_into` does not report what failsafe mode skipped. | A package opened in failsafe mode may lack objects, and saving over its source loses them for good. |
| On Windows, `os.replace` over a file with an open reader raises `PermissionError`. | Readers must be closed. |

## Decision

- `infrastructure/package_io.py` writes to a temporary file in the folder of the target, with `failsafe=False`, flushes it, and replaces the target with `os.replace`. A failure removes the temporary file and leaves the target as it was.
  `Package.file` changes only after the write succeeded.
- The editor decides what a save refuses or drops before it writes (`application/save.py`): a File without a stored file, a File under an annotation, and a partial package that would overwrite its source are refused. Dropped files, thumbnail and properties need a confirmation.
- Three workarounds touch SDK internals. All are in `package_io.py`, each has a guard test in `tests/medium/test_package_io.py` that fails when the SDK stops behaving this way, and each can go when the guard fails after an upgrade:
  1. `_TolerantReader` overrides the protected `_add_supplementary_file` and `_collect_supplementary_files` of `AASXReader`. It records a missing part and goes on, and it also reads Files under annotations.
  2. `_read_thumbnail` reads the part name and the content type of the package thumbnail through `reader.reader`.
  3. `_ThumbnailLinkingWriter` sets the protected `_thumbnail_part` of `AASXWriter`, so that a part the writer has written already becomes the package thumbnail without a second zip entry.
- A File under an annotation is read, but an AASX save is refused while one exists. The writer cannot be made to write that file without writing OPC parts by hand, which D3 forbids. Saving as JSON or XML is possible, with the usual warning about dropped files.
- Crash recovery stays JSON, as it is cheap. When files were added since the package was opened, it is a complete AASX, because those files exist nowhere else.
- `Package` uses `SetIdentifiableStore`. The deprecated `SetObjectStore` is a subclass with the same behavior, so editing an id still works.

## Consequences

- Packages with a missing file open, and the user can repair them. They cannot be saved as AASX until the path is removed or the file added.
- The SDK is pinned (ADR 0004), so the workarounds stay stable. An upgrade runs the guard tests first, and the guards tell which workaround to remove.
- A package thumbnail that is also the default thumbnail is written once, with its relationship, so the SDK's duplicate-entry warning no longer appears.
- A File under an annotation cannot be saved to AASX. An upstream fix in the SDK (walking annotations in `traversal.walk_submodel`) removes this limit and two of the workarounds.
- Rejected: wrapping a fake submodel in a split part so that the writer sees annotation Files. It leaves a junk part in the package that other tools may read.
