# ADR 0030: A file that a package declares is the user's content, and a save keeps it

**Status:** Accepted

This replaces a point of [ADR 0013](0013-supplementary-files.md), which says that a file that nothing refers to is dropped by an AASX save and by an AASX recovery, and that the editor warns about it. It also adds an exception to the rule that all AAS content goes through `basyx` (D3 of the [v1 editor plan](../../planning/v1-editor-plan.md), [ADR 0006](0006-safe-save.md)). The files of ADR 0013 and ADR 0006 stay as they are. Where they differ, this ADR is the later one, and only on these points.

## Context

An AASX declares each supplementary file with an `aas-suppl` relationship from the AAS part. The Technical Data template declares six images, and one File element names one of them. Opened in the editor, the Package files panel listed one file and the load report was empty. A plain save wrote that file and dropped the other five, with no warning, although the plan's goal is "no silent data loss" and D7 says that a save warns before it drops anything.

Probes against the pinned SDK (commit `412a53f`):

| Finding | Consequence |
|---|---|
| `AASXReader.read_into` stores only the files that a File element, an annotation (our `_TolerantReader`), or the default thumbnail of a shell names. It never reads the `aas-suppl` relationships. | A declared file that nothing names is not read, and is not in the file store. The Package files panel cannot list it. |
| 37 of the 132 bundled AASX templates declare files. None declares a part that is missing in the zip, and none declares a file twice. In the round-trip corpus (`tests/data` and every template), 17 packages lost declared files in a plain save before this change. | The loss was common, and in the templates that people start from. |
| `AASXWriter.write_all_aas_objects` takes `additional_relationships`, relationships that start at the AAS part, "in addition to the aas-suppl relationships which are created automatically". The writer has a public attribute `writer`, a `pyecma376_2.ZipPackageWriter`, whose `open_part(name, content_type)` writes a part. | A file that nothing names can be written with calls of the SDK and of its OPC package, and declared with a relationship that the SDK writes. No OPC XML is written by hand. |
| The SDK writes the target of its own `aas-suppl` relationships in lower case. The part keeps the case of its name. OPC compares names without case. | A declaration must be matched with the parts of the zip without case, and the part keeps its own spelling, or the name of a file changes at each save. |
| The relationship type of old files has `www.` in it. `_accept_old_relationships` already moves it to the current type for every part. | Old files need no code of their own. |

## Decision

- **Reading.** After `read_into`, `_TolerantReader.read_declared_files` reads the `aas-suppl` relationships of every AAS part it parsed (split parts included) through `reader.reader`, and stores each part in the file store with its content type. A part that is stored already is not read again, whether a File element named it or two parts or two relationships declare it, and a name that differs only in case counts as the same part. The spelling of the part in the zip is kept. This is a narrow exception to D3, recorded in the docstring of `infrastructure/package_io.py` and in D3 of the plan.
- **A file that cannot be loaded is told, never raised.** A declared part that is not in the zip, cannot be read, or has a name that a save could not write (`part_names.is_valid`) becomes an issue of the load report (`declared_file_not_loaded`: left out, scope part, with the AAS part and the name). The package stays whole: it is not partial, because the file does not hold the part.
- **Writing.** `_write_aasx` opens the part of each stored file that no File element and no shell thumbnail names, with `writer.writer.open_part`, before it calls `write_all_aas_objects`, and passes an `aas-suppl` `OPCRelationship` for each of them as `additional_relationships`. The SDK writes everything else. A save of a package that was not changed keeps all its files, and a save and an open give the same files. The package thumbnail that is also a stored file is written once, as before.
- **The user removes a file, not a save.** A file whose File element was removed stays in the package until it is removed in the Package files panel, which lists it. The rule `EDT-UNREFERENCED-FILE` still reports it in the Validation panel, and now says that a save keeps it.
- **No warning for an AASX.** `check_save` no longer warns about files that nothing refers to when the target is an AASX, because it drops none. A save to JSON or XML still warns that all files are not written, now with the code `FILES_NOT_WRITTEN`, which keeps the "Show package files..." button.
- **Crash recovery.** The AASX of a recovery carries every stored file, so `.files.json` is no longer written beside it. It is still written beside the JSON recovery of a package that the SDK cannot write as AASX (a File with no stored file), and `restore_from_recovery` still reads the `.files.json` that an earlier version wrote beside an AASX.

## Consequences

- The Package files panel lists every file that a package declares, and each can be removed, renamed, saved to disk, or linked to a File element.
- Saving the Technical Data template keeps its six images. The round-trip test over the corpus (`AAS_CORPUS_TEMPLATES=all`) compares the declared parts of each template before and after a save, read from the zip itself, and all 132 templates keep theirs. A save may declare more than the original did, because the SDK declares a file that a File element names.
- A package can carry files that nothing uses, and a save never cleans them up. The panel and the rule make them visible.
- The SDK writer can now write a File under an annotation, because that file is a stored file that nothing refers to by the walker of the SDK, and it is written with the files above. The save is still refused while one exists (ADR 0006), and lifting that refusal is a separate decision.
- Two guard tests in `tests/medium/test_declared_files.py` fail when the SDK reads declared files itself, which removes `read_declared_files`, or when `additional_relationships` or the public `writer` change, which needs another way to write the files.
- The editor never rewrites the relationship type of a file that it keeps, apart from the move from `www.` to the current type that every save has done already.

## Alternatives considered

- **Load the files only, and let the warning about files that nothing refers to list them.** Rejected by the owner: a file that a package declares is the user's content, so a save that says it is dropping it is still a save that drops it. It was the fallback if the writer could not write them, and the writer can.
- **Wrap the files in a fake submodel so that the SDK writer sees a File for each.** Rejected for the reason of ADR 0006 and ADR 0013: it leaves a junk part in the package.
- **Write the relationships by hand after the SDK has closed the package.** Rejected: it is hand-written OPC, and `additional_relationships` does the same through the SDK.
