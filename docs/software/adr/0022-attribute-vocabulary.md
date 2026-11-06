# ADR 0022: Tabs name attributes with a vocabulary of the metamodel, and show what the editor edits unchanged

**Status:** Accepted

## Context

The tabs showed what Python introspection finds. A Property read like this:

- the type column said `NoneType` for a null attribute, `Namespa...` for a set, and `Constrain...` for a list,
- the type hint column said `Optional[Union[Duration, DateTime, Date, ...]]`,
- the attributes were `id_short`, `display_name`, and `value_type`,
- the entries of a text were `DictItem 0` and `DictItem 1`, and those of a set of qualifiers `Qualifier 0`.

A person who knows the AAS but no Python cannot read this. Package Explorer shows `idShort` and `displayName`, with a sentence about each.

A probe of what reads the displayed text found these places:

- `NAME_ROLE` holds the name of the row, which is the attribute of the SDK. Editing (`getAttrTypeHint`, `attributeCommand`, `value_dialog_args`), the order of attributes (`ATTR_ORDER`), the restore of expanded rows after a rebuild, and the actions that test `index.data(NAME_ROLE) == "submodels"` use it. None uses the text of the first column.
- `SearchProxyModel.lessThan` sorts the levels without a saved order by the display role of the first column, and the search bar filters by the display role of the attribute and value columns.
- `NamespaceSet` (the qualifiers and extensions of an element) is a `Set`, so `hasSavedOrder` sorted its rows by name. The names were `Qualifier 0`, `Qualifier 1`, which sorted into the order of insertion by chance.
- `delegates.py` looks up the completions of a cell by its display role, as if that were the attribute. The cell that is edited is the value, so the lookup does not use the first column, and the code was not changed. It looks like a defect that was there before.

## Decision

- **A vocabulary as data** in `domain/attribute_vocabulary.py`, which imports no Qt. It has an entry for each attribute of each class: the name of the metamodel, the name of its type, and a description. The names, types and descriptions are from Part 1 of the specification, version 3.1.2 (IDTA-01001, the `v3.1.2` tag of `aas-specs-metamodel`), shortened and not quoted. The entries are keyed by the name of the class and found along the base classes, so `Referable` names `idShort` once. The type is the type of the metamodel (`MultiLanguageNameType`, `Reference`, `xs:string`, `list of Qualifier`, `ValueDataType`), never a Python generic.
- **Three groups have no definition in Part 1.** The IEC 61360 content is defined by IDTA-01003-a, which was not at hand, so its descriptions are short statements of what the attribute holds. The classes of the editor (`Package`, `StoredFile`, `DictItem`) and the attributes that only the SDK has (the type of a `ModelReference`, the position of a list item) are marked `in_metamodel=False`. The SDK has no `OperationVariable`: its input and output variables are elements, so `Operation` has the type `list of OperationVariable` of the specification, and the entries below are elements.
- **What is displayed is separate from what is edited.** `NAME_ROLE` and `objName` stay the attribute of the SDK. `DetailedInfoItem` gets a `label` for the entries of a list, and `displayName`, `typeText` and `attributeInfo` for the cells. Only the display role, the tooltip and the help text change. Nothing that edits reads them.
- **One type column.** The type that a person reads is the type that the metamodel declares, except for a value that follows its value type (`xs:double`) and a reference (`ExternalReference`). A null attribute is named by its declared type. The type hint column is kept, renamed "Python type", and hidden by default, because it says what the type column says in the words of Python and the import tool needs four columns.
- **Null and empty values** read `(not set)` and `(empty)`, and a value type reads `xs:double`, not `Double`.
- **Entries are named by their key.** The language of a text, the idShort of an element, the type of a qualifier, the name of an extension or a specific asset id, and for any other entry its position in brackets. The `name` of the row stays `DictItem 0`, because the restore of expanded rows finds rows by it.
- **Qualifiers and extensions keep the order of the file.** `hasSavedOrder` treats a `NamespaceSet` as ordered, as ADR 0011 said it did. Its names now sort by key, which would be a visible change. Other sets (a set of references, a store) are sorted by what they show.
- **The search and the header sort act on what is shown.** A person looks for `displayName` and sorts by what is in the column.
- **A test that no attribute goes unnamed.** It walks every class of the SDK modules `aas`, `base`, `concept` and `submodel` that a tab shows as attributes, takes the attributes that a tab would list, and fails for one without an entry. A second test walks the rows that tabs make for the four bundled packages. A later SDK class or attribute fails them and gets a name, and does not appear in a tab as Python.
- **A layout version for the saved columns.** The header state of the tabs is saved with `TAB_HEADER_LAYOUT_VERSION`. `restorable_state` (in `application/header_state.py`) restores a state only for the version that it was made for. A state without a version counts as an older one. The state saved when the session ends has the new version, so what the user changes afterwards is kept.
- **A shared action is never hidden to shorten a menu.** The Save, Close, Zoom, Folding, Update and Open in actions are also in the File menu, the toolbars, and the views, and hiding an action hides it everywhere and switches off its shortcut. They are moved into the submenus "View" and "Package", and only the entry of the submenu is hidden where it does not apply.
- **The preview is a splitter** with a share of a third and 360 pixels at least for the attributes. A tab narrower than 720 pixels starts with the preview dragged shut. The share that the user dragged is kept in the tab.

## Consequences

- A tab reads in the words of the AAS, and a hover shows the description. A new SDK attribute is found by a failing test, not by a user.
- The package tree still shows `concept_descriptions`, `fileStore` and `input_variable` as nodes, and the class of the SDK in its type column. The editor finds those nodes by name, so a separate display role has to be made first. That is a later work package.
- The vocabulary describes metamodel 3.1. A move to 3.2 needs a review of the entries, which the test cannot do, because it checks that an entry exists and not that it is right.
- The descriptions are shortened by hand. A reader who needs the exact text has the specification.
- A row of the tab of a set without a saved order is sorted by the label it shows, so `[10]` comes before `[2]` for entries without a key. It was `ModelReference 10` before `ModelReference 2`.
- The menu of an element has 25 to 27 entries instead of 38, and not fewer, because the actions of the sections that features registered, and the tests of the paste actions that find them by their place in the menu, would change. The sections can be put in submenus one by one.
- A header state that was saved by an earlier release is dropped once. The user loses the widths they dragged, for the sake of seeing the new default, and the pack tree and the docks are not versioned.

## Alternatives considered

- **Rename the attribute in the model (`objName`).** Rejected: editing, the order, the restore of expanded rows, and many actions look the name up, and a wrong name would edit nothing or the wrong attribute.
- **Derive the names by a rule (snake case to camel case).** Rejected: `in_output_variable` is `inoutputVariable`, `supplemental_semantic_id` has the singular of a list, and a rule gives no type and no description. The brief called for a vocabulary, not a column rule.
- **Read the descriptions from the docstrings of the SDK.** Rejected: many attributes have none, and the existing `getAttrDoc` already does this for the ones that have, which is why most tooltips were empty.
- **Drop the type hint column from the model.** Rejected: the import tool builds its columns on it, and the index of a column is used in several places.
- **Hide the Save and Close actions of the context menu.** Rejected: the actions are shared with the File menu and the toolbar.
