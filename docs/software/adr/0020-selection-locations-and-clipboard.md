# ADR 0020: A selection moves as a block, and the panel, locations, and clipboard fallback that go with it

**Status:** Accepted

## Context

WP15 closes the criteria of F-EDT-01, 02, 08, 09, and 10 that were gaps or rested on a changelog limit.
Most are small, but four decisions are not obvious, and one of them reverses what the code did without a record.

| Finding | Consequence |
|---|---|
| The code moved each selected row one place, so rows 2 and 4 of 6 went to 1 and 3. The original takes the selected rows out, and puts them back next to each other at the lowest selected index minus one. Rows 2 and 4 end at 1 and 2, and nothing happens when the lowest row is at the top (F-EDT-09 AC3, AC4). | The move is the original's. No decision had been recorded for the other behavior. |
| The original inserts "in order of selection". The selection model of Qt keeps ranges of rows, not the order of the clicks, and a range made with Shift has no click order at all. F-EDT-08 AC9 is already tested in tree order. | The block keeps the order of the container. |
| The SDK keeps the variables of an Operation in three sets (`input_variable`, `output_variable`, `in_output_variable`). A variable does not know its direction, only which set holds it. | The direction is found by looking for the element in the sets of its parent. |
| The keyboard shortcuts `Ctrl+Shift+P` and `Ctrl+Shift+O` of the original are free: `settings/shortcuts.py` and the registered actions use neither. | The original's keys are kept. |
| Qt has no denied clipboard on a desktop. `QClipboard.text()` returns an empty string. A platform that cannot be read (a remote session, a sandbox) looks like an empty clipboard. | The fallback is an action that never reads the clipboard. |
| `AASXWriter.write_thumbnail` writes the package thumbnail and its relationship. A thumbnail that is also the default thumbnail of a shell is already handled by `_ThumbnailLinkingWriter` (ADR 0006). | A change of the package thumbnail needs no new workaround. It sets `Package.thumbnail`, which the save writes. |
| An AAS object can be held by weak reference. | The stack of editing locations does not keep a closed package or a deleted object alive. |

## Decision

- **A moved selection becomes adjacent.** Up puts the selected rows of a container one place above the first of them, and does nothing when the first is at the top, also if the others could move. Top and End are as before. **Down is the mirror of Up** and not the original's `lowest index + 1`: the block ends one place below the last selected row, and nothing happens when that row is at the bottom. The original's rule would move a row at the bottom of a selection upwards when the user asked to move down. The AC has no case for Down, so this is a deliberate difference. Each container of a selection that reaches into several moves on its own (D16, `plan_bulk_move`).
- **The block keeps the order of the container**, not the order of the clicks, for the reason above.
- **Move and Delete are not offered for variables of different directions.** The Move actions are off and the panel hides them, and Delete is off and hidden in the menu of the tree. Cut and Copy stay. Other rows in the selection do not count towards a mix.
- **The selection panel is a dock below the tree** (`ui/selection_panel.py`), the equivalent of the panel that replaces the editor in the original. Here the tabs on the right keep showing the current object. The header is `Multiple selected elements` for two rows or more. It names the kinds, tells whether the rows share a parent, and has buttons for the moves, Cut, Copy, Delete, Change attribute, and Remove extensions. Each button is the action of the tree view, so it is enabled, disabled, or hidden when the menu entry is. The dock opens by itself for the first multiple selection, and stays closed after the user closes it. The panel does not repeat the other entries of the context menu.
- **F-EDT-09 AC2 stays different** (it was already D): actions are offered across parents, each row moves in its own container, and the panel says how many parents there are.
- **Editing locations are a stack of weak references** (`application/locations.py`). Push stores the object of the current row, its package, and whether the row is expanded. Pop selects the last location that the tree still shows, restores the expand state, and drops locations of objects or packages that are gone, with a message in the status bar. Pop on an empty stack changes nothing. The stack is not saved with the session. Both actions work in Read mode.
- **F-EDT-08 AC5 stays different.** The buffer of the tree is a mirror of the system clipboard: a newer copy anywhere, in this program or another, replaces it. The original keeps its internal buffer first. We keep the mirror because it needs no state that can disagree with what the user copied last, and what the buffer adds (the package a copy came from, and whether it was cut) is kept only for copies made here. A test shows that JSON that is newer on the clipboard is pasted.
- **Paste from text** is the fallback of F-EDT-08 AC8. It opens a box for the JSON and offers the places that fit the selected row (below, above, into). The text is read by the same path as clipboard JSON (`load_objects`), with the same refusals. It touches neither the buffer nor the clipboard, and a pending cut stays.
- **Copy AAS with new Submodel ids** (`application/operations/copy_shell.py`) copies an AAS through the SDK's JSON, and gives it, its `globalAssetId` and each Submodel it refers to new `urn:uuid:` ids. The new AAS refers to the copies. A reference inside a copy that points into another copied Submodel follows the copy, so the copies refer to each other as the originals did. Concept descriptions and stored files are shared, as the package is the same. A reference to a Submodel that the package does not hold is kept and reported. The action is on an AAS and on the node of the shells (where it asks which AAS), and not on the package, as in F-EDT-02 AC3. Copy and Paste of an AAS is as before: a new id, and the same Submodels (D13). Copying from another package and with its files stays out of scope (the plan's "Copy from an auxiliary package").
- **Several stored files are removed in one step with one question.** The files panel takes several rows. The tree already did. The package thumbnail is a part of its own, so it is not in this list.
- **The package thumbnail is changed from an image on disk.** It is stored as `/thumbnail.<extension>` in the root of the package, as the original does (F-EDT-10 AC5), and is one undo step. A file that is no image, is empty, or has no extension is refused with a reason. The files panel shows its name. A change makes the crash recovery an AASX, because the JSON recovery would bring back the thumbnail of the original file.
- **Remove default thumbnail** asks first, takes the Resource away, and keeps the stored file. The file then shows as not referenced, and a save warns about it (D7).
- **A paste over an element, or over a Submodel or AAS, brings its files** from the package the copy was made in, as a paste beside it does, in the same undo step. This closes the limit "Replace paste doesn't bring files".
- **"Centralize file" is out of scope for v1** (F-EDT-10 AC12). It writes a copy of a file with an HTTP POST to a store from the options of the original, and sets the value to the new address. That is a repository feature, as the Stubs and Fetch the plan leaves out, and it changes a remote system at once, outside the undo history and the safe save (D4). "Move file to folder" is its local counterpart inside the package.

## Consequences

- A user of Package Explorer finds the move they know. A user of the earlier version of this editor sees rows jump together when they move a spread selection.
- The Down difference means a row of a selection can move less than the original moves it.
- The dock adds a place that follows the selection of the tree. It reads the actions of the view, so a new action shows up in it only after its id is added to the panel.
- The panel was looked at offscreen only (see the report of WP15).

## Alternatives considered

- **The original's Down (`lowest index + 1`).** Rejected, for the reason above. It is one function (`new_order`) to change if parity matters more.
- **Keeping the order of the clicks.** Rejected: Qt does not keep it, and building it means tracking every click and key press of the view.
- **A panel in place of the tabs.** Rejected: it hides the object that the tabs show, and a multiple selection often comes from looking at one of them.
- **Clearing the location stack when a package closes.** Rejected for weak references, which need no hook in the window and cannot miss a case.
- **A paste action that opens the box by itself when the buffer is empty.** Rejected: the paste actions are off without a buffer, and enabling them would change what every paste test checks. Paste from text is next to them.
- **Implementing Centralize file with `urllib`.** Rejected for v1: there is no list of stores to choose from, no place for the credentials, and no way to undo it.
