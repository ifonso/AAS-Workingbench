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
- Rename id for shells, submodels and concept descriptions, and Rename idShort for elements, in the context menu of the package tree. Both update every reference that has the old id or goes through the old idShort, in semantic ids, supplemental semantic ids, value ids, `refers_to`, the references of a shell, relationships, data specifications and every other field, and in list positions. A preview lists the references that change. The rename and the updates are one undo step. An id or idShort typed in a cell takes the same path.
- Delete shows what refers to the objects, and offers to remove those references or leave them. A reference that is required, such as the end of a relationship, stays. Deleting a shell, submodel or concept description, or an element with elements below it, asks first, and Shift skips that question. Deleting several objects shows one dialog and is one undo step. Cut asks nothing and leaves the references.
- Deleting an item of a list moves the references to the items behind it up by one, so they keep pointing at the same item.
- Fix References in the context menu repairs references that name an object by its idShort instead of its id, and keys that have the wrong type. It lists what it cannot repair.
- Sync idShort copies the idShort of an element to the concept description of its semantic id, where that has no idShort or short name.
- An invalid idShort, or one that a sibling has, gets a suggestion such as `My_motor` or `Name_1`, which the user can accept.
- A test that reads every class of the SDK and fails when the walk over references misses a reference field.

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
- The Blob editor ran the entered text as Python code. It now accepts only a bytes literal such as `b'text'`.
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

### Removed

- `Guidelines.md`, replaced by `docs/contributing/style-guide.md`.
- The setting "Automatically add refs of existing submodels to AAS when saving file". Saving no longer links Submodels to the first AAS, and it was on by default.
- The undo list of 10 steps in each tab. The history of a package replaces it.

## 0.4.13 - 2026-08-28

The last version inherited from upstream [rwth-iat/aas_manager](https://github.com/rwth-iat/aas_manager).
See the [upstream releases](https://github.com/rwth-iat/aas_manager/releases) for earlier changes.
