# Feature parity with AASX Package Explorer

The goal of this project is to reach the functionality of [Eclipse AASX Package Explorer](https://github.com/eclipse-aaspe/package-explorer) in a cross-platform Python application.

## Reference material

The target is specified in a set of 95 feature documents, in a sibling checkout:

```text
../package-explorer/design-docs/
```

| Document | Use it to |
|---|---|
| `README.md` | Understand the scope and how far to trust the documents |
| `FEATURE-INDEX.md` | Browse features with priority and platform risk |
| `MENU-MAP.md` | Go from a menu item to its feature document |
| `SPEC-MATRIX.md` | See which features depend on which spec |
| `KNOWN-DEFECTS.md` | See what not to copy from the original |

These documents are not committed to any repository yet, so they exist only on the machine where they were written.
Feature IDs such as `F-NAV-02` refer to them.

## Roadmap

Phases 1 to 5 follow the build order the design documents suggest.
The current focus is the editing scope of phases 1 and 2, as described in the [V1 editor plan](../planning/v1-editor-plan.md).

| Phase | Goal | Features |
|---|---|---|
| 0 | Engineering foundation | Tooling, tests, documentation (this phase) |
| 1 | Open, view, and save a package | F-PKG-01, F-PKG-02, F-REP-01, F-SHL-01, F-SHL-02, F-SHL-03, F-NAV-01, F-NAV-05, F-NAV-06 |
| 2 | Edit every entity | F-EDT-01 to F-EDT-06, F-EDT-08 |
| 3 | Daily-use parity | Remaining P1: validation, repositories, API, search, history, presets, files, references, core exchange formats |
| 4 | Template ecosystem | SMT and SAMM, generic forms, nameplate, documents, technical data, contact, BOM, AID |
| 5 | Specialist and legacy | P2, then a decision on each P3 |

### Decisions needed before phase 1

1. **Metamodel target:** decided: V3.1.x. See [ADR 0005](adr/0005-metamodel-and-validation.md).
2. **F-SHL-03 (AnyUI):** the original uses a declarative UI so desktop and web can share panels. Decide whether to adopt something similar, or build directly on Qt.
3. **F-CMP-03 (web edition):** decide whether it is in scope. The layered architecture keeps this possible, but it is a large effort.

## Status of P0 and P1 features

**How reliable this is.**
The rows of the editing features, F-EDT-01 to F-EDT-11, were checked in WP12 against every one of their 199 acceptance criteria, by reading the code and the tests, and by running the editor and looking at its windows.
The [acceptance audit](v1-acceptance-audit.md) has the evidence for each criterion, and `Partial` there means that criteria are listed as gaps or as out of scope.
The other rows are still the first assessment of 2026-11-06, from reading menus and searching the code, except where a row names a work package.
They were not run against their acceptance criteria, so treat `Partial` there as "something exists".
A picture of a window in this audit came from an offscreen platform, so it shows layout and text and not the behavior on a real display.

| Status | Meaning |
|---|---|
| Present | Main capability found in the code |
| Partial | Part of the capability found |
| Not found | No sign of it in the code |
| Decision | Depends on a decision above |

### Shell and package

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-SHL-01 | Main window and layout | P0 | Partial | Tree and tabs in `editorApp.py`. One command bar over the window acts on the view with the focus, the three bottom panels (Validation, Package files, Selection) are tabs of one strip with the arrangement saved and restored, a tab is as wide as its title (120 to 240 pixels), the path of a tab is a breadcrumb, and the window starts with a panel to open, create, or pick a recent file, with the right side blank until a package is open (UI plan phase H, [ADR 0028](adr/0028-main-window-layout.md)). The command palette (phase I) and the counts in the status bar (phase J) are done. Keyboard (UI plan phase L): `F6` and `Shift+F6` move between the tree, the tab, and the bottom panel, `Ctrl+1` and `Ctrl+2` go to the tree and the tab, `Ctrl+L` edits the path, Tab goes through the tab in reading order, the focus ring is two pixels and a token, and a walker test reads the names that a screen reader would read on the main surfaces and nine dialogs. Not done: NVDA, VoiceOver, and Orca were not tried, the rows of the trees keep the focus rectangle of the style, a header and a menu bar have no ring of their own, High contrast, and Linux and macOS. |
| F-SHL-02 | Commands and menus | P0 | Partial | `QAction` menus: File, Edit, View, Navigate, Validate, Tools, Help. The Edit menu and the command bar mirror the actions of the focused view, with their keys (UI plan phase H). Package files and Concept descriptions are still only in the context menu. Features add their actions to the context menus and the toolbar through a registry (`ui/actions.py`). The registry orders them in sections, with submenus, and hides what does not apply to the row. The menu bar has no registry. The command palette (Ctrl+K, `ui/command_palette.py`) lists the actions of the menus, the registry and the package tree with their keys and, for a disabled one, the reason when it is known, and jumps to elements by name. The context menu of an element has about 20 entries: the entries of the view (Zoom, Update, Folding, Open in), of the package (Save, Close), of structure (Move and paste), of names (Rename and references), and of locations are in submenus, and Cut, Copy, Paste and Delete stay at the top (WP17, WP19, [ADR 0024](adr/0024-package-tree-vocabulary-and-layout.md)). |
| F-SHL-03 | Declarative UI | P0 | Decision | Not found |
| F-SHL-04 | Options and configuration | P1 | Partial | Settings dialog |
| F-SHL-05 | Log and status | P1 | Partial | `log.log` and status tips, with no log panel. The status bar shows the mode, the counts of errors and warnings of the current package (a click opens the Validation panel), the hints of the current object, such as "3 hints here" (a click opens the Hints view of the panel, [ADR 0031](adr/0031-hints-say-where-you-are-and-the-panel-lists-them.md)), and the number of packages with unsaved changes. |
| F-PKG-01 | Package lifecycle | P0 | Present | New, open, recent, save (Ctrl+S, the package of the focused view: the tab, else the selected row), save all (Ctrl+Shift+S), save as, close, crash recovery. A file that cannot be read at all (metamodel 1 or 2, empty, damaged, wrong extension) is refused in words, without the failsafe question. A package that opens only in failsafe mode lists what the SDK left out: a dialog on open, a context menu action, and the text of the refused save (WP13, [ADR 0018](adr/0018-load-report.md)). The content is still not in the package, and not in a copy saved with Save As. |
| F-PKG-02 | AASX format | P0 | Present | Through BaSyx adapters, in `package.py` |
| F-PKG-03 | Auxiliary package | P1 | Not found | |
| F-PKG-04 | Check, validate, and fix | P1 | Partial | 24 rules over BaSyx objects for V3.1 (`domain/validation`, `application/validation.py`), and validation through `aas-test-engines` (V3.0). Each rule has an id and a severity, and the findings have the element to go to. The Validation dock lists the findings with filters and goes to the element, and the save gate asks about the errors (WP5b). The status bar counts them with the panel hidden, F8 and Shift+F8 go through the errors and warnings, and the bar of hints links to the panel ([ADR 0029](adr/0029-validation-runs-while-the-panel-is-hidden.md)). The panel has a Hints view that groups the hints of the package by kind and turns a kind off for the user ([ADR 0031](adr/0031-hints-say-where-you-are-and-the-panel-lists-them.md)). Fixes beyond Fix References are not done. See [Validation](validation.md). |
| F-PKG-05 | Finalize and verify | P1 | Not found | |

### Repositories and API

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-REP-01 | Package containers | P0 | Not found | Only local files. "Open from server" is commented out. |
| F-REP-02 | File repositories and recent list | P1 | Partial | Recent files only |
| F-REP-03 | Repository and Registry API | P1 | Not found | No HTTP client in the code |
| F-REP-04 | Upload to server | P1 | Not found | |
| F-REP-07 | Authentication and security | P1 | Not found | |

### Navigation

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-NAV-01 | Entity tree | P0 | Partial | `treeview_pack.py` |
| F-NAV-02 | History and editing locations | P1 | Partial | Back and forward in tabs, and Back after Jump to target. Push location and Pop location (Ctrl+Shift+P and Ctrl+Shift+O) keep a stack of rows, with their expand state, and skip rows that are gone (WP15). |
| F-NAV-03 | Find and replace | P1 | Partial | Search with regex and case filters, in the tree and in each tab (Ctrl+F). It finds the rows that match, not their parents, and shows "1 of 3". It searches names, not values. There is no replace |
| F-NAV-04 | Asset panel | P1 | Not found | |
| F-NAV-05 | View modes | P0 | Present | Edit mode and Read mode in the View menu, and hints mode. Read mode refuses every change and hides the rows of attributes that have no value (WP3b, WP5b). |
| F-NAV-06 | Right panel and content preview | P0 | Partial | Media preview in `widgets/tab.py`, in a splitter beside the attributes: a third of the tab, and dragged shut in a tab too narrow for both (WP17), with a button "Show preview of the file" while it is shut (WP19). A first run opens a window that fits the screen, so a tab on a large screen has room for the preview. |

### Editors

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-EDT-01 | Editor framework | P0 | Partial | Generic editors generated from type hints. The tabs name every attribute, type and list entry as the metamodel does, with its description on hover (WP17, [ADR 0022](adr/0022-attribute-vocabulary.md)), and the package tree and the cells read in the same words, with counts and names instead of a Python repr (WP19, [ADR 0024](adr/0024-package-tree-vocabulary-and-layout.md)). Read mode shows no null attributes (AC1), the changed marker follows the saved state in all tabs (AC3), and hints mode switches the advice on and off (AC4, AC5). A hint that throws does not break the panel (AC14). Push and pop of editing locations are done (AC10, AC11, WP15). WP18: after a delete the previous sibling is selected, and a hint rule that fails is shown in the tab. The add and edit forms use the same names (`valueType`, with its description on hover), and a form that adds to a list starts with one entry (UI plan phase C, [ADR 0026](adr/0026-forms-read-in-words-of-the-metamodel.md)). Audit: 12 criteria tested, 1 in part, 1 out of scope, 1 not applicable. |
| F-EDT-02 | Environment, AAS, AssetInformation | P0 | Partial | Through the generic editors. New shells get a `urn:uuid:` id, an id that another object has is refused, and Rename id updates the references to the shell. Deleting a shell leaves its submodels. Create AAS asks for AssetKind and the asset ids so AssetInformation is valid (AASd-131), with a generated global asset id, specific asset ids, and Generate (WP7). Hints warn about an empty global asset id and about two shells with one (AC9). Copy AAS with new Submodel ids copies an AAS, its global asset id, and its Submodels as one undo step, on an AAS and on the node of the shells (AC3, AC4), and Remove default thumbnail asks first and keeps the file (AC14), all in WP15. Not done: `Batch` as an asset kind (AC11), fetch and repository features. Audit: 9 criteria tested, 1 different on purpose, 7 out of scope. |
| F-EDT-03 | Submodel and SubmodelRef | P0 | Partial | Through the generic editors. Rename id updates the references, Delete shows the usages and offers to remove them, and Fix References repairs an idShort in the first key and wrong key types. Create concept description from the semantic id of a submodel, and from all semantic ids below it, with the question for IEC 61360 records, are done (WP10, AC10). The tab shows the description that the semantic id names, read-only and collapsed, or the notice of the original when it names none (AC15, WP16). The SMT actions are not done. Create Submodel linked to an AAS, Link existing Submodels, and Remove attributes (qualifiers, extensions, descriptions, display names, categories) are done in one undo step each (WP7). Audit: 12 criteria tested, 1 different on purpose, 2 out of scope (a read-only id in a dynamic environment needs Fetch), 1 not applicable. |
| F-EDT-04 | SubmodelElements | P0 | Partial | All 14 types are made, edited, undone, saved, and reloaded in a test. Values follow `valueType` (31 XSD types), a Range checks min and max, a Blob has a text and hex editor with file load and save, a list asks for its type first, and every attribute of BasicEventElement is editable. Sync idShort copies to the concept description. Refactor converts between element types and lists the losses before it changes anything (AC3 to AC6), a list can be rebuilt with other settings, Auto-detect fills them from the items (AC14), a list item shows its index (AC13), and strings and texts take line breaks. Elements move up and down, and can be pasted above and below (WP6). Create concept description from semantic id, Assign, and Auto-detect are in the context menu (WP10; AC20 has no case for an element, but a list item has no idShort, and nothing covers it; AC21 needs ECLASS, which is out of scope). The Base64 conversion of a Blob (AC9), default languages of a MultiLanguageProperty (AC2), the default and notice of an Entity (AC17), and a test of the output variables of an Operation (AC18) are done (WP14). Audit: 14 criteria tested, 6 different on purpose, 2 out of scope. |
| F-EDT-05 | ConceptDescription and IEC 61360 | P0 | Partial | WP10: add and edit an IEC 61360 record in a dialog with all 19 data types, units and level types and the reasons the SDK would refuse (AC2, AC4, AC5), remove empty attributes (AC6), fix data specification keys for all records (AC3 differs: the SDK has no record without content), import a value list from the clipboard with a preview (AC8; a pair needs a valueId), create descriptions from pairs (AC9), delete invalid descriptions through the delete flow, and list descriptions in the six orders of the original (AC10: list index, idShort, id, first use, by submodel elements, structured) and by name. Rename id updates the semantic ids, and Sync idShort fills the short name (AC15 differs: the SDK allows no empty preferred name). A preset adds an IEC 61360 record and a missing preset file is reported (AC17); it has no blank record to replace, because the SDK cannot hold one (AC16). WP16: the store of the package keeps the order of the file, so the list index is real and a permanent sort writes an order (AC11, AC12, with the message of the original for the three orders that cannot sort), the tab of an element shows its description (AC14), the record dialog removes a pair or the whole value list (AC7), "(none)" removes the data type (AC4), and a description with a SAMM element lists its id first and gets no hint about a missing record (AC18). Not done: the physical unit specification, SAMM modeling (F-SMT-05), and moving descriptions (AC13, AC19). Audit: 10 criteria tested, 1 in part, 6 different on purpose, 2 out of scope. |
| F-EDT-06 | Common attribute modules | P0 | Partial | Through the generic editors. The id is checked for duplicates, a new id is generated, an invalid idShort gets a suggestion (Fix), language tags are checked (BCP 47), and deleting a supplemental semantic id leaves the semantic id alone. Hints mode shows the findings about the object above its attributes, the status bar counts the hints of the current object, a kind of hint can be turned off in the Hints view of the Validation panel, and the create dialogs show the idShort, key value and global asset id checks while the user types (AC4, AC9, AC11, AC16). Add a data specification from a preset is done (WP11), for IEC 61360 only, and gives the one record of the preset (AC14: no blank record can exist in the SDK). The notices about missing descriptions and semantic ids, and AC1 with its Create w/ default, are not done. Audit: 11 criteria tested, 1 in part, 3 different on purpose, 1 out of scope. |
| F-EDT-07 | Qualifiers and Extensions | P1 | Partial | Through the generic editors. Add from a preset (qualifier, extension, specific asset id, and data specification) and add from the clipboard, to one or many selected objects, are done (WP11, see [Bulk editing](bulk-editing.md)). Presets are SDK JSON files, shipped and of the user, and files of Package Explorer are read. Not done: Upgrade qualifiers and Migrate to Extensions (V2 legacy), the SMT attribute records, Copy to clipboard and Paste into an existing qualifier or extension. A preset is added, and the blank qualifier that the original replaces cannot exist, because the SDK refuses one (AC1, WP16). Also not done: a hint for a blank name (AC12). Audit: 5 criteria tested, 3 different on purpose, 5 out of scope. |
| F-EDT-08 | Copy, paste, and reorder | P0 | Partial | Copy, cut, paste, and undo, with one history for each package. Cut removes the source from every kind of parent. Delete asks first when it is destructive, shows the usages, and is one undo step for a bulk delete. Move up, down, to top and to end (also for several rows, and for list items with their references), Paste above, below and into with numbered idShorts and new ids, SDK JSON on the clipboard, Clear paste buffer, and concept descriptions when copying between packages are done (WP6). Paste into an AAS takes Submodels and references to Submodels, skips a reference the AAS holds, and brings a Submodel from another package (WP7). Copying several rows puts the SDK's JSON on the clipboard and the concept descriptions come along, as for one row (fixed in WP12). Paste from text is a fallback when the clipboard cannot be read (AC8), and a cut from a list pastes elsewhere with the source gone (AC20), in WP15. Not done: Paste into a CD and a pending Cut (D12). The buffer is the system clipboard, so a paste buffer with priority over it is a decision (AC5, ADR 0020). Audit: 10 criteria tested, 3 in part, 3 different on purpose, 4 out of scope. |
| F-EDT-09 | Multi-element editing | P1 | Partial | Multi-select with bulk cut, copy, and delete. Change attribute with a pattern (idShort, description, display name, value as text) with a preview and refusals, Remove extensions by name or semantic id, and Move up, down, top and end across several containers are done (WP11). The pattern language is new and documented, not the one of the original. Auto-detect, Assign, and Create from all semantic ids of the concept description work package take the whole selection, and Fix data specification keys takes the selected descriptions. The Selection panel names the selection and has the buttons for it (AC1), a selection moves as a block, and nothing moves when its first row is on top (AC3, AC4), variables of mixed directions get neither Move nor Delete (AC19), and several supplementary files are removed at once (AC18), all in WP15 and recorded in ADR 0020. Not done: moving elements into another parent, and deleting identifiables in a repository (out of scope). WP18: Delete, Cut and Copy act on every selected row, also under different parents, in the order of the tree and in one undo step, and refuse rows of two packages ([ADR 0023](adr/0023-actions-on-the-whole-selection.md)). Audit: 10 criteria tested, 2 in part, 8 different on purpose, 1 not applicable. |
| F-EDT-10 | Supplementary files | P1 | Partial | A Package files panel and context menu actions: add (name checked, never overwritten), create and edit text (UTF-8), rename and move with the File elements and the thumbnail that refer to the file, remove (asks about the paths), save to disk, and a picker for File elements and the default thumbnail (D15). All with undo. Every file that a package declares is listed and kept by a save, also one that nothing refers to (ADR 0030). Saving to JSON or XML warns that the files are not written, an AASX save refuses dangling paths with a repair dialog, and recovery keeps the files. Copying to another package copies the files. The package thumbnail can be changed, and a paste over an element brings its files (WP15). Not done: drop of a file on the panel, and the Base64 conversion of a Blob (AC14, AC15). Centralize file is out of scope (AC12). Audit: 12 criteria tested, 3 different on purpose, 1 out of scope, 2 not applicable. |
| F-EDT-11 | References, semantics, lookups | P1 | Partial | A picker in every reference field: filtered by target type, derived keys, resolved or dangling status, the reason of an AASd-121 to 128 refusal, and free entry of external references. Jump to target with a message when it is missing, and Back returns (WP7). WP16: the picker lists the other open packages too and starts on concept descriptions for a semantic id (AC1), "Create empty concept description" (AC15), and a message where Create from semantic id cannot work (AC16). A file filter is in the chooser of the File element, because V3.1 has no key type for a stored file (AC5). Not done: ECLASS and IEC CDD, and the pool of known concepts (out of scope for v1). Audit: 9 criteria tested, 3 different on purpose, 10 out of scope. |

### Templates, exchange, plugins, and companions

| ID | Feature | Priority | Status | Evidence or gap |
|---|---|---|---|---|
| F-SMT-01 | Submodel from known definitions | P1 | Partial | 43 groups of IDTA templates as data files |
| F-SMT-07 | Predefined concepts library | P1 | Partial | Same template files. This design already avoids a defect of the original, which compiles them into the code. |
| F-EXC-03 | Submodel via JSON and HTTP | P1 | Partial | "Add as JSON" and "Edit as JSON", with no HTTP |
| F-PLG-01 | Plugin framework | P1 | Not found | |
| F-PLG-02 | Digital Nameplate viewer | P1 | Not found | |
| F-PLG-04 | Document Shelf | P1 | Not found | The Handover tool generates documents, but does not browse them. |
| F-PLG-05 | Technical Data viewer | P1 | Not found | |
| F-PLG-09 | Generic Forms | P1 | Not found | |
| F-PLG-10 | Export Table | P1 | Not found | |
| F-CMP-03 | Web edition | P1 | Decision | Not found |

### Where this application is already ahead

These have no direct equivalent in the P0 and P1 list, so keep them while working toward parity:

- Crash recovery
- Undo and redo, with one history for each package that restores the position of what was deleted
- References that stay right: a rename updates them with a preview, and a delete shows what refers to the object
- Excel import with mappings
- LLM-assisted Handover Documentation
- Validation with AAS Test Engines
- Theme selection, with light as the default and a dark theme, both checked for contrast ([ADR 0025](adr/0025-design-tokens-and-theme-architecture.md)), and split tabs
- A bundled font (Inter) and action icons that follow the theme and are sharp on high resolution screens ([ADR 0027](adr/0027-bundled-font-and-themed-icons.md))
- Theme selection, with light as the default and a dark theme, both checked for contrast ([ADR 0025](adr/0025-design-tokens-and-theme-architecture.md)), split tabs, and compact trees with a setting for the row density (UI plan phase F)
- Drawn icons for 24 kinds of AAS elements in the trees, one shape for each family and letters for each kind, in light and dark ([ADR 0027](adr/0027-bundled-font-and-themed-icons.md))
- Themes: Follow system, Light (the default), Dark, and Native. The old Breeze themes are gone, and a saved old name is mapped to Light or Dark (UI plan phase M)

## Working on a feature

1. Read its feature document, and check `KNOWN-DEFECTS.md`, so a defect of the original does not get copied.
2. Update its status in this file.
3. Turn its acceptance criteria into tests, as the [testing guide](../contributing/testing-guide.md) describes.
4. Follow the [target architecture](architecture.md#target-structure).
5. Mention the ID in the commit footer: `Refs: F-NAV-02`.
