# ADR 0024: The package tree and the cells read in words of the AAS, and a layout that fits the screen

**Status:** Accepted

## Context

[ADR 0022](0022-attribute-vocabulary.md) made the tabs speak AAS and left the package tree as it was: its nodes read `shells`, `concept_descriptions`, `fileStore` and `input_variable`, its type column read `OrderedIdentifiableStore` and `DictSupplementaryFileContainer`, and the cells of the tabs and of the extra columns of the tree still showed `Extension(name=Origin)`, `{Qualifier(type=...)}`, `(Key(type=SUBMODEL, value=...),)`, and `b'\x89PNG...`. A look at the app on a real display (Windows, 1920 by 1080) added four defects of the same kind: the first window was 1194 by 624 whatever the screen, so a tab was under 720 pixels and the preview of a file started dragged shut with no sign that it existed; the hints bar took four lines for almost every element; the toolbars were cut into a "..." menu; and the attribute column cut `embeddedDataSpecifications`.

A probe of what reads the displayed name of a row of the tree found:

- `NAME_ROLE` (the attribute of the SDK, or the idShort) is what editing, the restore of expanded rows, the paste and create actions, the tests, and the `index.data(NAME_ROLE) == "submodels"` tests use. None reads the text of the first column.
- The display role of the first column is read by the sort and the search (`SearchProxyModel`), by the title of a tab (`TabWithTreeView.windowTitle`), by the address line and its completer (`getTreeItemPath`), and by Copy for a row that is not an object of the AAS. All of them want the text that a person sees.
- The tests find rows by `NAME_ROLE` through the helpers `find` and `find_path`. None needed a change.

## Decision

- **A display name next to the lookup key.** `PackTreeViewItem` has `isNode` (the row groups the objects of its parent and was made from `packViewAttrs`), `displayName`, and `typeText`. `NAME_ROLE`, `objName`, and `objectName` are as before. The display role of the first column is `displayName`: `Asset Administration Shells`, `Submodels`, `Concept Descriptions`, `Files`, and for the variables of an operation the name of the metamodel from the vocabulary, `inputVariable`. The words are in `domain/tree_names.py`, which has no Qt.
- **A node has no type.** The type column of a row that only groups objects is empty, and its tooltip is the description of the group. An object has the class of the metamodel. `StoredFile`, which only the editor has, reads `SupplementaryFile`. The value column of a node counts what is below it (`1 submodel`).
- **The tab of a node is titled by the display name**, and its type line reads what the tree reads.
- **Cells read what a person reads.** `domain/readable_values.py` builds the text, and `simplifyInfo` asks it first. An extension, a qualifier, and a specific asset id read `name: value`. A set or list reads a count with the word for its entries (`2 qualifiers`, `1 embedded data specification`, `3 references`, `2 keys`, `4 items` for a mixture). A reference keeps its last key. Asset information, a resource, an administration, and a data specification read a short sentence. Bytes read their size. A Blob and a stored file read the size and the content type (`105885 bytes, image/png`). A text that Python would show as `Name(...)` and that nothing names reads the name of the class. Text, numbers, enumerations, texts of languages, and references are left as they were. **Only the display role changes.** The edit role, the copy role, and the objects that the edit forms get are the objects themselves. Copy of an element still puts the JSON of the SDK on the system clipboard. Copy of a cell of a row that is no AAS object puts the text of the cell, as it did, and that text is now the readable one.
- **The context menu has about twenty entries.** Three more sections of the registry are submenus, next to the three that were: "Move and paste" (structure), "Rename and references", and "Location" (push and pop). Cut, Copy, Paste, and Delete are not registered actions and stay at the top level, with Edit, Add, Undo, and Redo. A shared action is never hidden, as before. A test helper (`tests/menus.py`) finds an action through the submenus, so tests no longer depend on the place of an entry, and `registeredActions.find` still finds it by id.
- **Saved layouts are versioned.** `restorable_state` (ADR 0022) now also guards the header of the package tree (`PACK_TREE_HEADER_LAYOUT_VERSION`) and the sizes of the two zones (`ZONES_LAYOUT_VERSION`), with the layout of the tab headers raised to 3 because the default widths changed. A state of another version is dropped once.
- **The first window fits the screen.** `domain/window_layout.py` has no Qt. A first run takes 85 percent of the room of the screen, not less than 1194 by 624 unless the screen is smaller, and a saved size wins. The two zones start at a share of the window (40 percent, at least 520 pixels), and the tree gets the width that its toolbar needs when the tab keeps 720 pixels for it.
- **A collapsed preview has a button** ("Show preview of the file") in the tab, which is shown while the preview is dragged shut and hidden otherwise.
- **The attribute and type columns fit the common names.** They are measured with the font of the tab for `embeddedDataSpecifications` and `MultiLanguageNameType`, within a share of the width of a narrow view, so the value keeps room. A column that the user sized, or a saved state, is not refitted. The address line of a tab no longer claims its own width, so the buttons next to it are not cut.
- **Several hints are one line.** Two or more hints (the lowest severity) share a line that names their rules, with every sentence in the tooltip. One hint, errors, and warnings keep their sentence. The findings are unchanged.

## Consequences

- The tree and the tabs read alike. A person who searches the tree for `Submodels` finds the node, and one who searches for `submodels` does not, as ADR 0022 decided for the tabs.
- The address line shows `Submodels` where it showed `submodels`. The completer and the line use the same text, so they agree, but an address written by hand in the old words is not found.
- A row that is not an AAS object copies a readable text, and not a repr, as plain text. Nothing pastes it (the paste buffer holds the objects), so no behavior depends on it. Copy of a qualifier or extension row does not put JSON on the system clipboard, so "Add qualifier from clipboard" cannot take it. `dump_members` exists for that and is not called by Copy. This was so before and is not changed here.
- The main toolbar of the tree needs about 790 pixels for all its buttons, with the two text buttons "Paste above" and "Paste below". At the smallest first window (1194 pixels) it still cuts them into the "..." menu, and the tree does not get more because the tab needs its room. A first window on a larger screen shows them all.
- The widths are measured with the font of the tab, so a larger zoom at the start gives wider columns, and a zoom after the start does not refit them.

## Alternatives considered

- **Rename the nodes in the model.** Rejected, for the reasons of ADR 0022: the lookup by name is in more than twenty places and in the tests.
- **Show the class of the SDK for a node, but shorter.** Rejected: a node is not an object of the AAS, so there is no honest type to show.
- **Put structure paste and move in the top level and the rest in submenus.** Rejected: the menu would stay about 25 entries long. Paste is one click from the top, and has a shortcut.
- **Join the hints with the Validation dock, and show none in the tab.** Rejected: the bar is how a person sees a problem of the object that is open, and the findings are asserted by tests.
- **Open the first window at the size of the screen.** Rejected: a maximized-looking window on first start hides the desktop. A share keeps a margin.
