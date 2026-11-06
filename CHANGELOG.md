# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

Phase 0 prepares the project for [feature parity with AASX Package Explorer](docs/software/feature-parity.md).

### Added

- A Makefile as the single entry point for development tasks.
- Linting and formatting with ruff, and type checking with pyright, both enforced in CI.
- Project documentation in `docs/`: architecture, decision records, guides for testing, style, commits, and branching, and instructions for AI agents.
- `python -m aas_editor` as a way to start the application.
- A round-trip test that saves a corpus of packages and compares their objects and file parts, with an optional local mode for packages outside the repository.
- A test that `domain` and `application` do not import PyQt, and helpers in `tests/factories.py` that build BaSyx objects.
- Packages that point to a file missing in the package now open, and list the missing files. Before, 13 of the 132 bundled AASX templates failed to open. Such a package can be saved as JSON or XML, or as AASX after the paths are removed.
- A dialog before a save that would drop content: stored files that nothing refers to in an AASX, and files, the thumbnail and the properties in a JSON or XML file. Save anyway and Cancel, with Cancel as the default.
- A dialog that refuses a save that cannot work: a File without a stored file, a File under an annotation, and a package opened in recovery mode that would overwrite its source. Nothing is written then.
- The context menu action "Add references to all Submodels to the first AAS", which saving did on its own before.
- Files under the annotations of an annotated relationship are read from an AASX. The SDK skipped them.
- The round-trip test now covers the bundled AASX templates, and compares thumbnail, properties and zip entries. A sample runs by default, and `AAS_CORPUS_TEMPLATES=all` runs every template.
- Undo and redo for every edit, add, delete, and paste, with one history of 10000 steps for each package. Undo and redo act on the package of the current item or tab, and show the step in their text, such as "Undo Delete Pump".
- Undo gives back the position of what was deleted, such as an element in the middle of a collection, or a language entry in a description.
- Deleting, cutting, or pasting several selected rows is one undo step, and so is linking all Submodels to the AAS.
- An Edit mode and a Read mode in the View menu. Edit mode is the default. In Read mode every change, including undo and redo, is refused with a message, the editing actions are disabled, and nothing can be edited in a cell.
- A registry for actions in `aas_editor.ui.actions`, so that features add actions to the context menus and the toolbar without changing the tree views. See the [architecture guide](docs/software/architecture.md#registering-an-action).
- A tab whose object was deleted, in another tab or by undo, now closes, and so does a tab of a closed package.
- Values follow their value type. Typing `12` into an `xs:int` Property gives an `xs:int`, and `abc` is refused with a message such as "'abc' is not a valid xs:int: it must be a whole number such as 12 or -3". This holds in cells, in the dialog for one value, and in the add and edit forms, for Property, Range, Qualifier, and Extension. All 31 XSD types work, including dates, durations, and integers beyond 64 bits. The text is checked as you type.
- The value type is chosen from a list of `xs:` names. Before, the form listed Python classes.
- A Range refuses a minimum above its maximum, in cells and in dialogs.
- Changing the value type converts the value through its text in one undo step, such as `"12"` as `xs:string` to the `xs:int` 12. If the value does not fit, the change is refused and nothing changes. A Property in a list that fixes the value type cannot leave it.
- A Blob editor that shows the content as text when it is UTF-8 text, and as hex otherwise, with loading from a file, saving to a file, and the media type of a loaded file. The bytes stay exactly as they were until you edit them, and a Windows text keeps its line breaks. Content above 1 MiB is not shown, and can still be saved and replaced. Typing a Python literal such as `b'text'` is no longer needed.
- The context menu of a Blob has "Load Blob content from file..." and "Save Blob content to file...". Saving also works in Read mode.
- Language tags of display names, descriptions, and MultiLanguageProperty values are checked for BCP 47. A malformed tag, an empty text, or a language used twice is refused with the reason, such as "use a hyphen, not an underscore, as in en-US". The list of languages offers 13 codes instead of 5.
- Adding to a SubmodelElementList opens a dialog for the type of the list, with the value type of the list fixed and the semantic id of the list filled in. Before, any type could be chosen, and the SDK refused the wrong ones afterwards.
- The form of a new SubmodelElementList offers only element types that can be made, and shows `order_relevant` ticked, as the SDK default is true. Editing what a list fixes when it is made, such as `order_relevant`, is refused with a message that says to make a new list.
- Every attribute of the 14 submodel element types can be reached in the form and in the tab, including `direction`, `state`, `messageTopic`, `messageBroker`, `lastUpdate`, `minInterval`, and `maxInterval` of a BasicEventElement, which the original editor lacks.
- Rename id for shells, submodels and concept descriptions, and Rename idShort for elements, in the context menu of the package tree. Both update every reference that has the old id or goes through the old idShort, in semantic ids, supplemental semantic ids, value ids, `refers_to`, the references of a shell, relationships, data specifications and every other field, and in list positions. A preview lists the references that change. The rename and the updates are one undo step. An id or idShort typed in a cell takes the same path.
- Delete shows what refers to the objects, and offers to remove those references or leave them. A reference that is required, such as the end of a relationship, stays. Deleting a shell, submodel or concept description, or an element with elements below it, asks first, and Shift skips that question. Deleting several objects shows one dialog and is one undo step. Cut asks nothing and leaves the references.
- Deleting an item of a list moves the references to the items behind it up by one, so they keep pointing at the same item.
- Fix References in the context menu repairs references that name an object by its idShort instead of its id, and keys that have the wrong type. It lists what it cannot repair.
- Sync idShort copies the idShort of an element to the concept description of its semantic id, where that has no idShort or short name.
- An invalid idShort, or one that a sibling has, gets a suggestion such as `My_motor` or `Name_1`, which the user can accept.
- A test that reads every class of the SDK and fails when the walk over references misses a reference field.
- Move up, Move down, Move to top and Move to end for the elements of a submodel, collection, list, entity and annotated relationship, the variables of an operation, and the qualifiers and extensions of an object, in the context menu and with Shift+Ctrl+Up, Down, Home and End. Move up and down are on the toolbar. A move of several selected rows is one undo step, and the rows stay selected. The actions are disabled when the move would change nothing, such as Move up on the first row, and in Read mode.
- Moving an item of a SubmodelElementList gives the references to the items that changed position their new keys in the same undo step (AASd-128).
- Paste above, Paste below and Paste into, with Ctrl+Alt+V, Ctrl+Shift+V and Ctrl+Shift+Alt+V. A paste inserts copies at the position, so pasting again gives a further duplicate, and several copied rows keep their order. Pasting into the annotations of an annotated relationship works. A paste is one undo step, and a refused object leaves the package as it was.
- A pasted element whose idShort a sibling has gets a number (`Pump_1`), and a pasted shell, submodel or concept description gets a new id. A pasted cut keeps its id. The existing Paste does the same.
- Copy puts the SDK's JSON on the system clipboard, and paste reads JSON from the clipboard through the SDK, so elements can move between instances of the editor. Text that is no valid AAS object is refused with a message. Nothing from the clipboard is evaluated.
- Clear paste buffer in the context menu empties the paste buffer and the system clipboard.
- Pasting elements into another package asks whether the concept descriptions that their semantic ids refer to should be copied. A description that the package has with the same content is reused, and one with the same id and other content asks whether to keep the existing one or to add the copy under a new id, which the pasted elements then use. Adding the descriptions is part of the paste's undo step.
- `application/operations/companions.py` gathers what goes with a copy between packages, as one place for later work to add the supplementary files.

### Changed

- The project is now managed only with uv, including CI and release builds, and `uv.lock` pins all dependencies.
- The code moved to `src/aas_editor/`, and tests moved to `tests/`, organized by size.
- All non-generated code is formatted with ruff, using Google's 80-column limit.
- `basyx-python-sdk` now uses the `aas_manager/develop` branch of the fork, pinned to a commit. This moves the SDK to metamodel V3.1.
- Python 3.11 is now the minimum version, as the SDK requires.
- `torch` now comes from the CPU-only index on Windows and Linux, which also applies to Linux release builds.
- `pyinstaller` moved from runtime dependencies to the `build` dependency group.
- The default branch is `main`, and integration happens on `development`.
- The application now names metamodel V3.1 in its title and About dialog. The AAS Test tool is labeled V3.0, because `aas-test-engines` checks only that version.
- An uncaught exception now shows an error with its traceback, and the application keeps running. It no longer exits.
- Saving writes to a temporary file next to the target and replaces the target only when the whole package was written.
- A package opened in recovery mode, after the first attempt to read it failed, can no longer overwrite its file. Use Save As.
- Save All, and Save and Close All, skip packages without changes.
- Crash recovery writes a complete AASX when files were added since the package was opened.
- The package uses `SetIdentifiableStore` instead of the deprecated `SetObjectStore`.
- The modified marker of a package follows its undo history. Undoing back to the saved state clears it, undoing a saved edit sets it again, and a failed or refused save leaves it set.
- Crash recovery removes the recovery file of a package once undo has brought the package back to its saved state.
- Closing a package, and opening one, are no longer steps of an undo history.
- Adding a reference that a shell has already, or an entry with a key that a mapping has, replaces nothing silently. A reference is refused with an error, and an entry replaces the old one as an edit that can be undone.
- The package tree and the tabs show the order that is saved in the file. They sorted every level by name, descending, so a moved element stayed where it was. Levels with a saved order, such as the elements of a submodel, show that order, and the shells, submodels and concept descriptions, which the SDK keeps in sets, are sorted by name, ascending. A click on a column header still sorts the whole tree, and a move puts the tree back to the saved order. The sort is no longer restored from the last session. See [ADR 0010](docs/software/adr/0010-natural-order-in-trees.md).
- Copying an element or an object puts its JSON on the system clipboard instead of its display text.
- The actions of the tree views update when the selection, the rows, or the paste buffer change.

### Fixed

- Setting the semantic id of an element moved it to the end of its siblings, and undo did not put it back. The position is kept for every attribute now.
- Deleting a row in a tab that selects whole rows ran the delete once for each column, and removed up to three more rows behind it.
- Giving an item of a list a semantic id that differs from its siblings was refused, as AASd-114 demands, but the SDK had taken the item out of the list by then, and it was lost. The item stays now.
- An id edited in an attribute or a cell could be the id of another object, and left every reference to the old id pointing at nothing. The edit is refused for a duplicate, and updates the references.
- The add dialogs for shells and submodels proposed the fixed id `https://www.example.com/`, so the second new object failed. They propose a new `urn:uuid:` id, and so does the dialog for a concept description.

- Installation failed because the `aas_manager/v301` branch of the SDK fork no longer exists.
- The Excel import tool raised `NameError` instead of showing an error dialog when an operation failed.
- Invalid escape sequences in regular expressions produced `SyntaxWarning`.
- Entering the text "None" in an attribute set it to nothing. The text is now kept, and a real clear still works with Delete.
- A value that did not fit a Property, such as text for an integer, silently changed its `value_type`. The edit is now refused with an error.
- Clearing a mandatory attribute, such as `asset_information` of a shell, left an invalid object or crashed the application. It is now refused with an error.
- Typing a value into a Property that had none, or into a date or a number beyond 32 bits, failed or was refused. The cell editor limited whole numbers to 32 bits.
- Deleting a supplemental semantic id failed with "Unknown parent object type", and the semantic id stays untouched, which the original editor got wrong. Deleting a selected row in a tab deleted once for each cell of the row, so it could delete the next entries too.
- Editing the minimum or maximum interval of a BasicEventElement in a dialog raised an error.
- Editing a language entry to a language that another entry has failed with a traceback. It is refused with a message.
- The type of the children of a list could be chosen from classes that cannot be made.
- The Blob editor ran the entered text as Python code. It now shows the content as text or hex, and nothing is run.
- A failure while saving, such as an unwritable folder, closed the application. It now shows an error.
- The AAS Test tool could not check an AASX file, because it opened the file as text. It now opens files in binary mode.
- `testEditCreate` hung the large tests because a modal dialog blocked it. The large tests now stub modal dialogs.
- A save that failed could leave a damaged file, and a failed Save As changed the file of the package. The original now stays as it was, byte for byte.
- Saving an AASX dropped the package thumbnail and the properties such as author and title. They are kept now.
- Saving an AASX could write the thumbnail part twice.
- Closing a package with Save closed it even when the save failed or was refused, and the changes were lost. It stays open now.
- Saving a File under an annotation lost the file without a message. An AASX save is refused instead.
- Crash recovery lost files that were added since the package was opened, and the thumbnail and properties of the original.
- Renaming an idShort, or replacing an element, moved it to the end of its parent in the saved file. It now keeps its position.
- An edit, an added element, or a deleted element in one tab did not show in other tabs that show the same object. They now update.
- Undo of a delete put the element at the end of its parent instead of its position.
- Deleting a child closed the tab of its container, because the tabs were compared with the parent of the deleted rows.
- A tab moved its current row to the last inserted row when another tab added a row, and could lose its current row when another tab changed the object. A tab now moves only for what its own user did.
- A tab that showed an object deleted in another tab stayed open and out of date.
- The Paste action could add the object of the paste buffer itself, so a second paste, or a paste into a collection that has the idShort, failed. It adds a copy with a free name.
- Undoing the delete of a shell, submodel or concept description put the row at the end of its list. The rows of such lists are sorted by name, so the row returns to its sorted place.

### Removed

- `Guidelines.md`, replaced by `docs/contributing/style-guide.md`.
- The setting "Automatically add refs of existing submodels to AAS when saving file". Saving no longer links Submodels to the first AAS, and it was on by default.
- The undo list of 10 steps in each tab. The history of a package replaces it.

### Known limits

- The type, `order_relevant`, semantic id, and value type of a SubmodelElementList cannot be changed after the list is made, because the SDK has no setters. Make a new list.
- A string with line breaks is shown in a value line but cannot be typed there.
- Shells, submodels, concept descriptions and the Submodel references of a shell cannot be moved, because the SDK keeps them in sets whose order is not saved (D16). Their view is sorted by name.
- Paste into an AAS is not offered. A pasted submodel is added to the package without a reference from a shell. Link it with the action that links the submodels.
- Cut still removes the element at once (D12), so Escape or a missing paste does not bring it back, except by undo.
- A paste of elements into a SubmodelElementList does not check the type of the list in advance. The SDK refuses a wrong element (AASd-107), the paste is undone as a whole, and the message says why.
- The paste buffer and the system clipboard are one: a newer copy anywhere replaces the buffer. The original keeps its internal buffer first.

## 0.4.13 - 2026-08-28

The last version inherited from upstream [rwth-iat/aas_manager](https://github.com/rwth-iat/aas_manager).
See the [upstream releases](https://github.com/rwth-iat/aas_manager/releases) for earlier changes.
