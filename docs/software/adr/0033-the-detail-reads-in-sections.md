# ADR 0033: The detail reads in sections, drawn as bands over the rows of the model

**Status:** Accepted

## Context

The UI proposals (`design/ui-proposals.md`, items 1.1 to 3.7) found that the editor was dense not because of its spacing, but because everything had the same weight: the package tree and the tab of an element looked like spreadsheets with headers, the tree spent 40% of its width on a Type column that the icon already said, and the tab listed every attribute in the order of the SDK, with the type of the metamodel beside each and four `(empty)` rows in most elements.

The proposals ask for the detail to read in sections (Value, Identification, Semantics, and Advanced in Edit mode), with the attributes that hold nothing in a closed section of their own in Read mode, under a header in two levels: a path bar that says where the element is, and a block that says which element it is.

The rows of a tab are the attributes of the object, one level of a `DetailedInfoTable`. The editor finds a row by its name in the SDK (`NAME_ROLE`), edits it, copies it, and pastes into it through that model and through `SearchProxyModel`. About 30 test files find attributes among the top rows of that model.

## Decision

- **A table in the domain says the section of each attribute.** `domain/attribute_sections.py` maps every attribute of the vocabulary of ADR 0022 to a section, looked up along the base classes as the vocabulary is. A test fails for an attribute of the vocabulary without a section. `place_of` moves an empty attribute to `Section.EMPTY` in Read mode, and `in_reading_order` gives the order of the rows. Inside a section the order of the SDK, or of a description with SAMM, stays, except that the description follows the display name.
- **The model keeps one level.** `DetailedInfoItem` adds its attributes in the order of their sections, and gives the section of a row in `SECTION_ROLE`. No row is added for a section, so a row is found, edited and copied as before.
- **The view draws the sections.** `AttrsTreeView` reads the sections of its top rows into `SectionBands` (`ui/detail_sections.py`), draws a band above the first row of each section in `drawRow`, and gives that row the height of the band more (the delegate's `sizeHint`). A click or Space on a band opens or closes the section. The rows of a closed section are hidden, and its first row keeps only the band. An editor of a cell of such a row goes below the band.
- **What starts closed.** Empty attributes start closed. Advanced starts closed while it holds nothing, and open when a qualifier, an extension or a data specification is set. A section that the user opened or closed stays so for the next element of the tab.
- **The type is no column.** The detail has no header and no Type column. The type of an attribute is in the tooltip of its name, and inside the field while a value is edited. The package tree shows the names only by default, with the type in the tooltip and in View > Columns, and its header shows only while it has two columns or more.
- **What comes from elsewhere is drawn beside a value.** The text of a value in languages reads in the first default language of the user, with a badge such as `en +2`. A semanticId reads the name of its concept as a link, with its id under it. A value gets the unit that its concept gives, as a badge, with a link to the concept. The panel of the concept below the attributes is gone, because the links open the concept in the tab, and Back returns.

## Consequences

- The sections cost no change to how rows are found, so the actions, the clipboard, the search of a tab, and the tests that find attributes by name keep working.
- The first row of a section is taller than the others, so the detail no longer has rows of one height (`setUniformRowHeights(False)`). A test that measures the height of a row measures one without a band.
- A row of a closed section exists and is hidden. Code that walks the rows of a tab still sees it.
- Without a header, nobody sizes the columns of a tab, and `tabTreeViewColumnsSized` is always false. The name column keeps fitting the room.
- A new attribute needs a section, or its test fails, as it needs a vocabulary entry.

## Alternatives considered

- **A row for each section in the model.** The tree would have opened and closed sections by itself, but every attribute would have moved one level down, and every place that finds an attribute among the top rows would have changed, in the code and in the tests.
- **A proxy model that adds the sections as a level.** The view already sits on `SearchProxyModel`, and code maps its indexes to the source in one step. A second proxy would break that.
- **A form of widgets in place of the tree.** It would have had to rebuild editing, the context menus, the clipboard, and the keyboard of the tree.
