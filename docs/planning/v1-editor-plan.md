# V1 editor plan

**Goal:** a complete AASX editor for metamodel V3.1.x.
A user can open any V3.1 package, edit every entity, and save a valid file without silent data loss.

**Status:** Approved for implementation, after one review round with SDK probes. Work packages are tracked in [Progress](#progress).

## Scope

The scope is every feature in `design-docs/edit/` (F-EDT-01 to F-EDT-11), plus the parts of other features that editing cannot work without: safe saving, validation, and view modes.
The original's menu layout and declarative UI are not goals, so this plan builds directly on Qt.

### Out of scope for v1

| Item | Reason |
|---|---|
| ECLASS and IEC CDD lookup and import (F-EDT-11, F-EXC-04) | Licensed data. Needs a legal review, and a bring-your-own-data design. |
| Add from pool of known concepts (F-EDT-11, F-SMT-02) | Needs the predefined concepts library, a template phase feature. |
| V2 migration, "Upgrade qualifiers", and "Migrate to Extensions" (F-EDT-07) | Legacy. BaSyx reads V3.0 and V3.1 only. |
| Emit event (F-EDT-04) | Runtime behavior, part of the server features. |
| SMT attribute records, conversions, checks, and guided add (F-SMT-01, 03, 04) | Submodel template phase. These records stay editable as ordinary Qualifiers and Extensions. |
| Stubs and Fetch, and repository delete (F-EDT-02, 03) | Repository features. V1 edits local files. |
| Finalize AAS (F-EDT-02, F-PKG-05) | Part of the release workflow, not editing. |
| Print code sheet (F-EXC-16) | Not editing. |
| Copy from an auxiliary package (F-EDT-08, F-PKG-03) | Copy between open packages covers this need. |
| Data Specification UoM (Part 3b, F-EDT-05) | The SDK has no class for it. |
| Moving AAS, Submodels, concept descriptions, or SubmodelRefs | The SDK stores them in sets, so the order cannot persist. See D16. |
| Pending Cut (F-EDT-08 AC3) | Cut stays immediate. See D12. |
| Take-over bar and per-keystroke writes (F-EDT-01) | A workaround for a defect in the original. |
| Metamodel V3.2 | The SDK does not implement it. |

## Decisions

The rationale for the first two is in [ADR 0005](../software/adr/0005-metamodel-and-validation.md).

| # | Topic | Decision |
|---|---|---|
| D1 | Metamodel | Target V3.1.x. The app's label says so. V3.0 files are read as V3.1, as the SDK does. |
| D2 | Validation | Our own rule set over BaSyx objects. `aas-test-engines` stays as a separate tool labeled V3.0, because no V3.1 release exists. |
| D3 | Data access | All AAS reading, writing, and mutation goes through `basyx`. No hand-written AAS JSON, XML, or OPC handling. Narrow exceptions, each isolated in `infrastructure/package_io.py` and covered by tests: a reader subclass overriding the SDK's `_add_supplementary_file` and `_collect_supplementary_files`, reading thumbnail metadata through `reader.reader`, and a writer subclass that marks an already written part as the package thumbnail. The SDK is pinned, so these stay stable until a deliberate upgrade. See [ADR 0006](../software/adr/0006-safe-save.md). |
| D4 | Saving | Validate, write to a temporary file with `failsafe=False`, then replace the target atomically. Failures leave the original untouched, and also leave `Package.file` unchanged on a failed Save As. |
| D5 | Validation gate | Errors are shown before saving, with Cancel and Save anyway. Nothing is skipped silently. Refusals with no Save anyway: a File pointing to a package path with no stored file, because the SDK cannot write that package or reopen it. Save anyway is asked once for each error in a session, see [ADR 0015](../software/adr/0015-validation-in-the-editor.md). |
| D6 | Partial loads | Every package opened through the failsafe branch is treated as partial, because the SDK does not report what it skipped. It must use Save As, and cannot overwrite its source. |
| D7 | Lost content | Saving warns before dropping anything: unreferenced supplementary files in AASX, all files in JSON and XML. The check walks annotations as well, using our own walker. |
| D8 | Auto-link | Saving no longer adds Submodel references to the first AAS. It becomes an explicit action. |
| D9 | Undo | Command-based, per package, addressed by AAS object identity, grouped for cascades, restores position, tracks the saved state. Closing a package is not undoable. |
| D10 | Rename id | Updates references automatically after a preview, as one undo step. Uses `SetIdentifiableStore`, which handles id edits correctly, unlike `DictIdentifiableStore`. |
| D11 | Delete | Shows usages when something references the target, then offers to remove those references or leave them. |
| D12 | Cut | Stays immediate, as today. Undo restores it. |
| D13 | Duplicates on paste | idShort gets a numeric suffix automatically (`Name_1`). Copied Identifiables get a new id. Cut then paste keeps the id, because changing it would leave references dangling, a defect the original has. |
| D14 | Generated ids | `urn:uuid:<uuid4>`, replacing the fixed `https://www.example.com/`. |
| D15 | File location | New files default to `/aasx/files/<name>`. Collisions are shown, and `File.value` follows the stored name. |
| D16 | Reorder | Offered within Submodel, SMC, SML, Entity, Operation variables, and annotations, where probes show order surviving a JSON and XML round trip. Warn when index references (AASd-128) are affected. Concept description sort only changes the view. |
| D17 | SML child idShort | Hide the SDK's generated names, as today. Never serialize them. |
| D18 | Edit and read modes | A global toggle, defaulting to edit. The command stack refuses mutations in read mode, and the UI disables the actions. |
| D19 | Order on rename | Renaming an idShort must keep the element's position. The SDK moves it to the end, so `domain/ordering.py` snapshots and restores order for every rename and replacement. |

## Architecture

New code follows [the target structure](../software/architecture.md#target-structure), and the first work package to use each layer creates it.

| Package | Contents |
|---|---|
| `domain/walking.py` | Walks every element, including annotations, which `basyx.aas.util.traversal` skips |
| `domain/ordering.py` | Snapshot and restore of namespace order, and reorder with rollback |
| `domain/ids.py` | Id generation, idShort suffixing |
| `domain/references.py` | Package-wide index of ids and referrers: duplicates, usages, dangling references |
| `domain/validation/` | Rules and reports |
| `domain/value_types.py` | Parsing and checking text against XSD value types |
| `application/changes.py` | Qt-free observer of model changes, which legacy Qt models subscribe to |
| `application/commands.py` | Command stack (D9) |
| `application/operations/` | Rename, delete, move, paste, create and link, convert |
| `application/save.py` | The save flow: validate, warn, write. Takes a `Protocol` and explicit options, not `Package` or `AppSettings`. |
| `infrastructure/package_io.py` | Atomic reading and writing through BaSyx adapters. Must not import `Package`. |
| `ui/` | New dialogs and panels: validation, usages, reference picker, file picker, bulk edit |

Legacy `Package`, models, and tree views call these layers through thin adapters.

### Layer rule

`domain` and `application` must not import PyQt.
Legacy modules restrict what they can reuse: `aas_editor.settings.*` (including `NOT_GIVEN`) and `aas_editor.package` load Qt, and `utils.util_classes` has a circular import.
`aas_editor`, `utils.util_type`, and `additional.classes` load no Qt.

The import test must run in a clean subprocess and assert that `PyQt6` is absent from `sys.modules`, because pytest-qt has already loaded it in the test process.

## User interface

The current layout stays: package tree on the left, attribute tabs on the right.
Compare each new surface with the screenshots in `design-docs/_evidence/` (`11-edit-*.png`), but follow the existing app's conventions, and do not copy the original's layout.

| Surface | Used for | Work package |
|---|---|---|
| Save warnings dialog | Lost content and validation errors | WP2, WP5b |
| Validation dock | Sortable findings, double-click to go to the element | WP5b |
| Usages dialog | Delete and rename previews | WP4 |
| Reference picker | Filter by target type, derive keys, show dangling state | WP7 |
| Create dialogs | AAS with AssetInformation, Submodel linked to an AAS | WP7 |
| Value editor | Input validated against `valueType`, for Property and Range | WP8a |
| Binary editor | Blob: load, save, content type, and safe text | WP8a |
| Package files panel | List, add, create and edit text files, remove, rename, link to a File element | WP9 |
| Concept tools | Create from `semanticId`, use existing, IEC 61360 record | WP10 |
| Context menu and toolbar | Move, paste above and below, bulk operations | WP6, WP11 |
| Bulk edit dialog | Pattern rename, change attribute, remove extensions, assign concept descriptions | WP11 |

## Testing

Follow the [testing guide](../contributing/testing-guide.md).

- **Small:** all of `domain` and `application`, using BaSyx objects built by helpers in `tests/factories.py`.
- **Medium:** package I/O, legacy adapters, and each new dialog using `qtbot`, with modal `exec()` stubbed.
- **Large:** one end-to-end flow for each work package with UI, on real packages.
- **Round-trip corpus:** read, save, and read again, and compare every package with the SDK objects **and its file parts**. Run it on `tests/data/` in CI. A local, optional mode adds `../Requester_screwing.aasx` and samples from `../package-explorer/src`, skipped when missing.
- **Regression fixtures:** a dangling File, a File under an annotation, and elements whose order must survive a rename.
- **Acceptance:** each feature document's acceptance criteria become tests, or are recorded as not applicable with the reason.
- **Fixtures:** new sample packages are created through BaSyx by a script, not by hand.

## Work packages

Each one is a branch that merges into `development` with `--no-ff`, with tests, a `CHANGELOG.md` entry, and any architecture or ADR updates.
Sizes are relative: S, M, L.

### WP1: `fix/editor-data-defects` (M)

Test foundation and the defects that silently corrupt data.

- Add `tests/factories.py`, the round-trip corpus, and the layer import test.
- Fix `testEditCreate` hanging, by stubbing modal dialogs.
- Text `"None"` no longer becomes null in `editItem`.
- A failed value edit is refused, and no longer rewrites `value_type`.
- Remove `eval` from the Blob editor.
- Clearing mandatory attributes such as `asset_information` is refused.
- An exception while saving shows an error, and does not close the app.
- Set `AAS_METAMODEL_VERSION` to 3.1, and read `.aasx` in binary in the `aas-test-engines` tool, labeling it V3.0.

### WP2: `feat/safe-save` (L), after WP1

- `infrastructure/package_io.py`, with D3, D4, and D6. Use `with` for every reader, because `os.replace` over a file with an open reader fails on Windows.
- A reader that tolerates dangling Files, recording them, so that such packages can be opened and repaired.
- `domain/walking.py`, including annotations. Load and write files under annotations, which the SDK skips, or refuse with a clear message.
- D7 warnings, and the D5 refusal for dangling Files. Paths outside the package, such as URLs, are not dangling.
- D8: remove auto-link from saving, and add an explicit action.
- Recovery files keep session-added supplementary files.
- Preserve the thumbnail and core properties when saving, capturing the part name and content type at open. Do not write a thumbnail part that is already written as `default_thumbnail`, since that duplicates the zip entry.

### WP3a: `refactor/model-change-observer` (L), after WP1

- `application/changes.py` and `application/commands.py`, addressed by AAS object identity.
- `domain/ordering.py`, including D19.
- Qt models subscribe to changes, so that all open tabs resync.
- Rewrite `update()`, and support inserting and moving items at a position. Rows are QObject child order today.

### WP3b: `feat/command-undo` (L), after WP2 and WP3a

- Migrate every mutation to commands: edit, add, delete, paste. Fix the `editItem` recursive `setData` path.
- Per-package stacks, grouping, saved-state tracking that drives the dirty flag, and bulk operations as one step.
- The read-only gate in the command stack (D18). The toggle's UI is here too.
- A small action-registration seam, so later work packages add actions without editing shared code.

### WP4: `feat/reference-integrity` (L), after WP3b

- `domain/references.py` and `domain/ids.py`.
- Generated ids (D14), and refusing duplicates on edit, which the SDK only checks on add.
- Rename with reference updates (D10), and Fix References.
- Delete with usages (D11), and delete confirmation.
- Sync idShort, and fix invalid idShort.

### WP5a: `feat/validation-rules` (M), after WP4

- `domain/validation/`: duplicates, dangling references, missing files, BCP47 tags, and the constraints the SDK does not enforce: AASd-006, 007, 012, 013, 077, 119, 129, 133, 134. Verify that list against the SDK while implementing.
- Find out why 53 of the 132 templates only open in failsafe mode. Report what strict reading rejects, and reduce how many packages D6 forces into Save As where this is safe.

### WP5b: `feat/validation-ui` (M), after WP5a

- Validation dock, and the save gate (D5).
- Hints mode, and inline hints in create dialogs for the same rules.
- Hide null attributes in read mode (F-EDT-01 AC1), and clear the "changed" marker after saving and when undo returns to the saved state (F-EDT-01 AC3).

### WP6: `feat/structure-operations` (M), after WP4

- Move up, down, to top, to end (D16).
- Paste above and below, duplicate naming (D13), and clearing the paste buffer.
- Clipboard JSON that can be pasted back.
- Copying between packages brings concept descriptions when requested.

### WP7: `feat/create-and-reference-flows` (L), after WP4

- Create AAS with valid AssetInformation, Submodel linked to an AAS, and link existing Submodels.
- AssetInformation helpers: global asset id and specific asset ids.
- Remove attributes of a Submodel in bulk.
- Reference picker, with target type filters, key defaults, and dangling status.
- Jump to reference target, with a message when it is missing, and returning to the last editing location.

### WP8a: `feat/value-editors` (L), after WP3b

- `domain/value_types.py`, and value entry following `valueType` for Property, Range (with min ≤ max), and SML.
- Binary-safe Blob editor.
- MultiLanguageProperty and description language checks.
- SML add that asks for the child type first, and child defaults.
- Check every element type's attributes against `11-edit-*.png` and BaSyx, including BasicEventElement, which the original does not fully expose.
- A test that deleting `supplementalSemanticId` does not clear `semanticId`, a defect in the original.

### WP8b: `feat/element-conversion` (M), after WP8a

- Convert between element types, warning before anything is lost, unlike the original.

### WP9: `feat/supplementary-files` (L), after WP2 and WP3b

- Package files panel: add, create and edit text files, remove, rename, and move files to a central folder, with undo.
- File element and default thumbnail linking through a picker (D15).
- Warn about unreferenced files before saving, and find dangling ones.
- Copying between packages also brings supplementary files.

### WP10: `feat/concept-descriptions` (M), after WP4

- Create a concept description from a `semanticId`, assign an existing one, or auto-detect one.
- Create concept descriptions from pairs, and delete invalid ones.
- Add an IEC 61360 record with the template key, with all data types and unit fields.
- Sort the view of concept descriptions (D16), and fix data specification keys.
- Import a value list from the clipboard.

### WP11: `feat/bulk-editing-and-presets` (M), after WP4 and WP6

- Bulk move, pattern rename, change attribute, remove extensions, and auto-detect or assign concept descriptions. Use a new, documented pattern language rather than the original's.
- Presets for qualifiers, extensions, specific asset ids, and data specifications, stored as JSON.
- Add qualifiers and extensions from the clipboard.

### WP12: `docs/v1-editor-release` (S), last

- Run all acceptance criteria and the corpus.
- Update `feature-parity.md` with final statuses, and `architecture.md`.
- Compare each surface with the running Package Explorer or its evidence screenshots.
- List what remains.

## Order of work

```text
WP1 ─┬─ WP2 ──┐
     └─ WP3a ─┴─ WP3b ─┬─ WP4 ─┬─ WP5a ─ WP5b
                       │       ├─ WP6 ─ WP11
                       │       ├─ WP7
                       │       └─ WP10
                       ├─ WP8a ─ WP8b
                       └─ WP9
All ─ WP12
```

- WP2 and WP3a can run in parallel, but merge WP2 first.
- After WP3b, WP8 and WP10 can run in parallel. Merge the other work packages one at a time, because they share `treeview_pack.py` and `base.py`.

## Exit criteria for v1

- Every F-EDT capability is implemented or listed under [Out of scope](#out-of-scope-for-v1).
- `make check` passes, and new layers have no type-checking warnings.
- The whole corpus round-trips without losing content or file parts.
- Every failure to save leaves the original file intact.
- All 14 SubmodelElement types can be created, edited, moved where valid, undone, saved, and reloaded in a test.

## Progress

| WP | Branch | Status |
|---|---|---|
| WP1 | `fix/editor-data-defects` | Done |
| WP2 | `feat/safe-save` | Done |
| WP3a | `refactor/model-change-observer` | Done |
| WP3b | `feat/command-undo` | Done |
| WP4 | `feat/reference-integrity` | Done |
| WP5a | `feat/validation-rules` | Done |
| WP5b | `feat/validation-ui` | Done |
| WP6 | `feat/structure-operations` | Done |
| WP7 | `feat/create-and-reference-flows` | Done |
| WP8a | `feat/value-editors` | Done |
| WP8b | `feat/element-conversion` | Done |
| WP9 | `feat/supplementary-files` | Done |
| WP10 | `feat/concept-descriptions` | Done |
| WP11 | `feat/bulk-editing-and-presets` | Done |
| WP12 | `docs/v1-editor-release` | Done |

## Exit criteria result

Checked by WP12 on 2026-11-06. The evidence for each criterion that has a test is in the [acceptance audit](../software/v1-acceptance-audit.md).

| Criterion | Result | Evidence |
|---|---|---|
| Every F-EDT capability is implemented or listed under Out of scope | **Not met** | Of 199 acceptance criteria, 22 are neither implemented nor in the Out of scope table (listed below), and 9 more rest only on a "Known limit" of the changelog. |
| `make check` passes, and new layers have no type-checking warnings | Met | `ruff format --check`, `ruff check`, and `pyright` have no errors. `pyright` on `domain`, `application`, `infrastructure` and `ui` has 0 errors and 0 warnings. The legacy modules and the tests have 1231 warnings. `make` itself was not run. Its commands were. |
| The whole corpus round-trips without losing content or file parts | **Met for 83 of 132 packages, and not for the 49 that open only in failsafe** | `AAS_CORPUS_TEMPLATES=all` passes (853 passed, 18 skipped). For the 49 the test compares the package that failsafe loaded with the saved one, so it proves that a save adds no further loss, and cannot see what the SDK left out when it opened the file. See rank 1. |
| Every failure to save leaves the original file intact | Met | `test_safe_save.py` checks the bytes and the folder after a writer that fails, a Save As over an existing file, an unknown extension, and, since WP12, a replace that the system refuses. A full disk and a power cut were not tried. |
| All 14 SubmodelElement types can be created, edited, moved where valid, undone, saved, and reloaded in a test | Met | `test_element_types.py` does all but the move, for each of the 14. `test_element_moves.py`, added by WP12, does the move, with undo, redo, save and reload, for each of the 14. |

## What remains after v1

Ranked by how much it costs a user.
The numbers refer to criteria in the [acceptance audit](../software/v1-acceptance-audit.md).
Nothing here was started in WP12, because each needs a design.

1. **A package that opens only in failsafe loses what the SDK skipped, without a list.**
   49 of the 132 bundled templates open this way, and D6 makes them Save As only, so the source file is safe.
   Counting `idShort` in the XML of the file against the elements that were loaded, 37 of the 49 load fewer, mostly one (a duplicate concept description), but the three Bill of Materials extension templates load 20 of 40 and the Hierarchical Structures template 3 of 13. This is a count of `idShort` entries, so it is an estimate.
   The editor does not tell what was dropped, and the corpus test cannot see it.
   A reader that lists the skipped objects needs the SDK, or a reader of our own, which D3 rules out.
2. **A Blob cannot be converted between Base64 text and bytes** (F-EDT-04 AC9, F-EDT-10 AC14 and AC15).
   A Blob that holds Base64 text is common, and the user has to decode it elsewhere.
3. **No selection panel, and no limits for a mixed selection** (F-EDT-09 AC1, AC18, AC19).
   Move and Delete are offered for the variables of an Operation of mixed directions, where the original offers neither.
   Several supplementary files cannot be removed at once.
   The way a selection moves (each row one place, not made adjacent) is not recorded as a decision (AC3, AC4).
4. **No push and pop of editing locations** (F-EDT-01 AC10, AC11).
   Back after Jump to target and the Back of the tabs cover most of it.
5. **Defaults and notices that the original gives for new objects** (F-EDT-04 AC2, AC17; F-EDT-06 AC1, AC5; F-EDT-07 AC12; F-EDT-02 AC11, AC13).
   Default languages of a new MultiLanguageProperty, the notice for the asset id of an Entity, "Create w/ default" and the notices about missing descriptions, ids made from a template (`urn:x:DDDD`), a hint for a blank name of an extension, `Batch` as an asset kind.
6. **Small gaps in the editors.**
   Move language entries (F-EDT-06 AC15), a read-only category (AC16), a fallback text field when the clipboard is denied (F-EDT-08 AC8), Copy recursively of an AAS (F-EDT-02 AC3, AC4), delete the thumbnail (AC14), paste into an existing qualifier (F-EDT-07 AC5).
8. **The tabs still speak Python.**
   The type column shows `NoneType`, `Namespa...` and `Constrain...`, the type hint column shows `Optional[Union[Duration, DateTime, ...]]`, attributes are in snake case (`value_type`, `display_name`), and list entries are called `DictItem 1`.
   A new user cannot tell what these mean, and the original names the AAS attribute and its description.
   It needs a vocabulary for every attribute, not a column rule.
9. **Layout that was not made for a small window.**
   The context menu of an element still has 38 entries, because the editor's own Save, Close, Zoom, Folding and Open in entries come with them.
   The preview of a stored image or document takes half of its tab, and squeezes the attribute table at the default window size.
   A column order, hidden columns and the sizes of docks that a user changed are restored from the last session, so the new column widths only show on a first run.
10. **What is not verified.**
    The pictures of this audit came from an offscreen platform, so they show layout and text, and not the behavior of a real display: scaling on a high-resolution screen, the theme colors on real monitors, the preview of media (it was black offscreen), and keyboard focus.
    The large tests run only by hand, and not in CI.
