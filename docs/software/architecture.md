# Architecture

AAS Manager is a desktop viewer and editor for Asset Administration Shell packages, built on PyQt6 and the Eclipse BaSyx Python SDK.
This page describes the code as it is today, and the structure that new code should follow.

## Repository layout

```text
.
├── src/aas_editor/        # application package
├── tests/                 # tests, organized by size
├── docs/                  # this documentation
├── aas_test_engines/      # data files bundled into frozen builds
├── aas_manager.spec       # PyInstaller build definition
├── Makefile               # development tasks
├── pyproject.toml         # metadata, dependencies, tool configuration
├── uv.lock                # exact dependency versions
└── CHANGELOG.md
```

## Current structure

| Module | Responsibility |
|---|---|
| `__main__.py` | Entry point. Creates `QApplication`, loads icons, and opens `EditorApp`. |
| `editorApp.py` | Main window, menus, toolbars, session save and restore. |
| `design.py` | Generated main window layout, from `mainwindow_base.ui`. |
| `package.py` | `Package`: holds the objects, files, thumbnail and properties of an opened package, adapts them to the layers below, and handles crash recovery files. |
| `models/` | Qt item models that adapt packages and AAS objects to tree views. |
| `treeviews/` | Tree views and their actions: `base.py` is shared, `treeview_pack.py` shows open packages, and `treeview_detailed.py` shows object attributes. |
| `widgets/` | Tabs, editors, search bar, message boxes. `tab.py` also previews media content. |
| `dialogs.py`, `delegates.py` | Add and edit dialogs generated from type hints, and inline cell editors. |
| `settings/` | Application constants, AAS type metadata, icons, shortcuts, and persistent settings. |
| `utils/` | Type hint introspection (`util_type.py`), general helpers, recovery, and the exception hook. |
| `additional/` | Extra AAS classes used by the editor. |
| `tools/aas_test/` | Checks files with `aas-test-engines`, which supports metamodel V3.0 only. |
| `tools/handover_doc_llm/` | Generates Handover Documentation from PDFs using LLMs. |
| `tools/import_feature/` | Generates AAS files from Excel using mappings. |
| `submodel_templates/` | IDTA templates, available when adding Submodels. |
| `themes/` | Qt stylesheets and their generated resources. |

### How the editor works

1. `PackTreeView` opens a file as a `Package`, and BaSyx loads its objects into an object store.
2. `models/` wraps the objects in tree items. Selecting one opens its attributes in a tab, shown by `AttrsTreeView`.
3. Attributes and editors come from **runtime type introspection**: `utils/util_type.py` and `getAttrTypeHint` read the type hints of BaSyx classes.
   This is why the editor handles new SDK attributes with little code, and also why it relies heavily on SDK internals.
4. Edits go through the model, which turns each one into a command and pushes it on the undo history of the package.
   A command changes the BaSyx objects and reports the change to the package's change observer, so that the models of all tabs show the same objects again (see [Change observer and commands](#change-observer-and-commands)).
   The package counts as changed while its history differs from the saved state.
5. Crash recovery writes changed packages to `settings/recovery/`, and the next start offers to restore them.

### Known structural problems

| Problem | Consequence |
|---|---|
| Importing `app_settings.py` creates Qt objects, and `dialogs.py` reads the primary screen at class definition. | Modules cannot be imported without a `QApplication`, and most tests are not small. |
| Domain logic is inside models, views, and widgets. | Logic cannot be reused, and is hard to test. |
| Application state is in `settings/settings.ini`, which is tracked by Git, inside the package. | Running the app modifies a tracked file, and an installed copy would write inside its own package. |
| `pyproject.toml` is read at runtime for metadata. | A wheel would not run, so frozen builds must bundle this file. |
| LLM and PDF dependencies are always installed. | Installs and builds are large, even for users who never open the Handover tool. |
| Introspection logs hundreds of handled tracebacks when opening a package. | Real errors are hard to find in the log. |
| `aas_editor` is a large module-level dependency web, with circular imports worked around at the end of `package.py`. | Import order is fragile. |

## New layers in use

These modules exist today. Each layer is created by the first work package that needs it.

| Module | Responsibility |
|---|---|
| `domain/walking.py` | Walks every element of a submodel, including the annotations that `basyx.aas.util.traversal` skips. |
| `domain/file_references.py` | Lists the paths that objects use to refer to files in the package, finds those with no stored file, and finds stored files that nothing refers to. A URL is not a package path. |
| `domain/parts.py` | Values for the parts of an AASX besides its objects: the thumbnail, the core properties, and a missing file. |
| `application/save.py` | The save flow. `check_save` returns blockers (no way around them) and warnings (save anyway), and `save` writes only when there are no blockers and the user confirms the warnings. It takes a `SaveSource` protocol and explicit `SaveOptions`, never `Package` or `AppSettings`. |
| `infrastructure/package_io.py` | Reads and writes AASX, JSON and XML through BaSyx. A write goes to a temporary file with `failsafe=False` and replaces the target in one step. It does not import `Package`. |
| `ui/save_warnings.py` | The dialogs for blockers, warnings, and missing files. They show decisions that `application/save.py` made. |
| `ui/actions.py` | The registry where features add actions to the context menus and the toolbar (see [Registering an action](#registering-an-action)). |
| `domain/value_types.py` | Parses, formats, and checks text for each of the 31 XSD value types, using `from_xsd` and `xsd_repr` of the SDK and the checks it lacks. Also converts a value through its text, and checks the limits of a Range. |
| `domain/typed_values.py` | The rules for the attributes that follow a `value_type` (Property, Range, Qualifier, Extension): text becomes a value, a Range keeps min at or below max, and a change of the type plans the converted values or refuses. Also recognizes the type hints of values and value types. |
| `domain/language_tags.py` | Checks that a language tag is well-formed BCP 47, with the reason when it is not. Standard library only, and the same syntax as the SDK. |
| `domain/blob_content.py` | Shows the bytes of a Blob as text or as hex, and reads them back. Keeps Windows line breaks. |
| `domain/list_children.py` | What a new child of a SubmodelElementList gets from the list: its type, value type, and semantic id. |
| `ui/value_editor.py` | `ValueTypeBox`, `ValueLineEdit`, `ValueEdit`, `BinaryEdit`, and `ValueEditDialog`. They only show the rules of the domain modules (see [Entering values](#entering-values)). |
| `ui/blob_actions.py` | The context menu actions that load and save the bytes of a Blob. Registered by `__main__.py` with `register_blob_actions`. |
| `domain/replacement.py` | What replacing an element by a new one would do: `ReplacementPlan` with the new element, the `Loss` list, notes, and where the items went. Found without changing anything. |
| `domain/element_copy.py` | Copies of elements without their parent, the attributes all elements share, and how to write a value for a message. |
| `domain/conversion.py` | Which element types convert to which, and what each conversion keeps and loses (see [Replacing an element](#replacing-an-element)). |
| `domain/list_settings.py` | What a `SubmodelElementList` fixes, choosing settings from items, and the rebuild of a list with other settings. |
| `application/operations/replace.py` | `ReplaceElement` and `replacement_command`: the swap, and the updates to the references through the element, as one undo step. |
| `ui/conversion_actions.py` | The context menu actions "Convert to another element type..." and "Change list settings...". Registered by `__main__.py` with `register_conversion_actions`. |
| `ui/replacement_dialogs.py` | The dialog that lists what is lost, the chooser of the type, and the dialog of the list settings. |
| `domain/ids.py` | Generated ids (`urn:uuid:`, D14), numbered idShorts for copies (D13), and `fix_id_short`, which turns any text into a valid idShort. |
| `domain/references.py` | Finds every place where an AAS object stores a reference (`iter_slots`), and `ReferenceIndex`, which tells duplicate ids, the usages of an object, and dangling references (see [Reference integrity](#reference-integrity)). |
| `application/operations/` | The plans and commands that keep references intact: `rename.py`, `delete.py`, `fix.py`, and `references.py`, which turns reference changes into commands. |
| `ui/reference_dialogs.py` | The dialogs for renames, deletes and repairs: the preview of references, the rename dialog with Fix and Generate, and the delete dialog with the usages. |
| `ui/reference_actions.py`, `ui/delete_flow.py` | The actions Rename id, Rename idShort, Sync idShort and Fix References, and the questions that come before a delete. |

### How saving works

1. `PackTreeView.savePack` builds a `SaveSource` from the `Package` with `Package.save_source()`, and calls `application.save.save`.
2. The check runs. A blocker shows a dialog and stops. A warning asks the user, with Cancel as the default.
3. `package_io.write_package` writes, and `Package.recordSaved` changes `Package.file` only afterwards, so a failed Save As leaves the package where it was.

A package that was opened through the failsafe branch is partial (D6). It cannot overwrite the file it was read from.
The SDK does not say what failsafe mode skipped, so every such package counts.

Saving does not add Submodel references to the first AAS (D8). `Package.all_submodels_to_aas` is an explicit action in the context menu.

Crash recovery writes the objects as JSON. When files were added since the package was opened, it writes a complete AASX instead, so that restoring keeps them.

## Target structure

New features use four layers, as decided in [ADR 0002](adr/0002-layered-architecture.md).
Dependencies point only in the direction shown:

```text
ui ───────────► application ───────► domain
                     ▲
infrastructure ──────┘
```

| Layer | Package | Holds | May import |
|---|---|---|---|
| Domain | `aas_editor/domain/` | AAS rules and validation, without I/O | Standard library, BaSyx |
| Application | `aas_editor/application/` | Use cases, such as "connect to a repository". Defines interfaces (`typing.Protocol`) for external systems. | Domain |
| Infrastructure | `aas_editor/infrastructure/` | Implementations of those interfaces: file formats, HTTP clients, credential storage | Application, domain, external libraries |
| UI | `aas_editor/ui/` | Qt widgets and models that call use cases | Application, domain |

`__main__.py` is the composition root, where implementations are connected to the use cases that need them.

### Rules

- `domain` and `application` never import PyQt, so their tests can be small.
- UI code holds no business logic, and only translates between user events and use cases.
- Code does no significant work at import time.
- Long-running work, such as network calls, must not block the UI thread.
- The first feature to use a layer creates its package. `tests/medium/test_layers.py` imports every module of `domain` and `application` in a clean subprocess, and fails if PyQt6 is loaded. It skips a layer that does not exist yet.

### Modules in the layers

| Module | Layer | Responsibility |
|---|---|---|
| `domain/ordering.py` | Domain | Snapshot and restore of the order of a `NamespaceSet`, inserting, moving, and replacing members, and renaming an idShort without moving the element. Every change rolls back when the SDK refuses an object. |
| `application/changes.py` | Application | `Change` (added, removed, moved, changed), `ModelChangeObserver`, and `observer_for(package)`. |
| `domain/containers.py` | Domain | Adding, removing, and replacing members of the containers of BaSyx objects (namespace sets, lists, sets, and mappings), and telling the position, so that a command can put a member back. |
| `application/commands.py` | Application | `Command`, `CommandGroup`, and `CommandStack` with undo, redo, atomic groups, a saved-state marker, and the read gate. |
| `application/edits.py` | Application | The commands of the editor: `SetAttribute`, `SetValueType`, `AddMember`, `RemoveMember`, `ReplaceMember`, `AddSupplementaryFile`, and `link_submodels`. `SetAttribute` keeps the position of the owner for every attribute. |
| `application/editing.py` | Application | `EditMode`, the global switch between Edit and Read mode (D18). |
| `application/listeners.py` | Application | The callback list behind all of them. It holds bound methods weakly. |

### Change observer and commands

[ADR 0007](adr/0007-command-stack-and-change-observer.md) records the design.

- A command holds the BaSyx objects it changes, because each tab has its own item model, and rows or model indexes mean nothing to another tab.
- A command reports what it did to `observer_for(package)`, both when applied and when reverted. The report names the object, and for added, removed, and moved ones also the container and the position.
- `StandardTable` subscribes. It finds the items that show the object and updates them.
  Items of the package tree add, remove, and move rows one by one, and items of the attribute tabs read their rows again.
- A model that made a change itself passes itself as `origin`, so it does not update twice.

### Undo, the saved state, and Read mode

- Every package has one `CommandStack`, `Package.commandStack`. Undo and redo of a view act on the package of its current item, or on the package of its tab. The package tree uses the only open package when nothing is selected.
  The history keeps 10000 steps.
- The models make the commands: `setData` for edits, `addItem` for adds, and `clearRows` for deletes, which includes clearing an attribute to its default.
  Nothing else changes the objects of a package. A new feature creates a command in `application/edits.py` or next to its own logic, and pushes it on the stack.
- Several changes that belong together are one step with `stack.group(...)`.
  Deleting or pasting several selected rows, adding several entries, and linking all Submodels to the AAS are each one step. A group that fails undoes what it did.
- A command reports in `apply` and in `revert`, so a model has one way to follow a change, whether it came from an edit, an undo, or a redo.
  The model that pushes an edit passes itself as the `origin` of the first report, and updates itself, so that its own tab keeps the expanded rows and the current row.
  A view also puts back the expanded rows and the current row after a model read the rows below an item again.
  A view moves its current row only for the action it ran itself, so a tab that follows another tab keeps its place.
- A delete restores the position of the member. A set has no position, and the rows of such a container are added at the end.
- Dirty state comes from `stack.is_clean`: `Package.changed` is true while the history is not at the saved state.
  A successful save calls `mark_saved`, and a failed or refused save does not. Editing after an undo of a saved step leaves the package changed for good, until the next save.
  Content that differs from its file without a step, such as a package restored after a crash, is marked with `mark_unsaved`.
  Crash recovery uses the same flag, and removes the recovery file once undo returns to the saved state.
- Closing a package, and opening one, are not edits and have no step (D9).
- Read mode (D18): the `EditMode` switch, in the View menu, starts in Edit mode. In Read mode the stack raises `ReadOnlyError` for a push, an undo, and a redo, and the views show its message.
  The views also disable the editing actions, and the models drop `ItemIsEditable`, so nothing can be edited inline.
- A tab closes when the object it shows is no longer part of its package, and also when its package is closed.
  The last tab of the main window is emptied instead.

### Entering values

[ADR 0008](adr/0008-values-follow-their-type.md) records the decisions.

- **One place parses text.** `StandardTable.attributeCommand` is where the models turn an edit of an attribute into a command. For a Property, Range, Qualifier, or Extension it calls `typed_values.prepare_edit`, so text is parsed for the `value_type` of the object, and a change of the `value_type` becomes a `SetValueType` command that converts the values with it. A refusal is an `InvalidValueError` with a message for the user. `setData` shows the message as it is, without a traceback, like those of `ReadOnlyError` and `AASConstraintViolation` (the tuple `REFUSALS`).
- **The editors pass text.** A cell of a value uses `ValueLineEdit` (the delegate asks the model for the object and attribute of the cell with `EDIT_TARGET_ROLE`). The Edit/Create action of a value or of the bytes of a Blob opens a `ValueEditDialog`, chosen by `value_dialog_args`. The generated forms get `TypedValueInputWidget` for a hint of `ValueDataType`, and `ValueTypeInputWidget` for `DataTypeDefXsd`, from `InputWidgetUtil`. `ObjGroupBox.linkValueWidgets` connects the value widget to the widget of the type, or to a type that the form hides.
- **Bytes.** `BytesEdit` is the `BinaryEdit` with the interface of the generated forms. It replaced the editor of Python literals. It suggests the media type of a loaded file to the `content_type` widget of the form.
- **Languages.** The model checks a language entry before it replaces one (`StandardTable._checkedMember`), and `LangStringSetGroupBox` checks all entries of a form.
- **Children of a list.** `TreeView._applyListChildDefaults` is the one place where the add dialog of a SubmodelElementList is given the type, the value type, and the semantic id of the list, with `domain.list_children.child_defaults`.
- **Several lines.** `ValueEdit` shows a `MultiLineTextEdit` for an `xs:string`, and a line for every other type. The generated forms give the text of each language of a `LangStringSet` the same box, through the `multilineParams` argument that reaches the leaf widgets. The box returns the exact text it was given until the user edits it, and keeps Windows line breaks. A cell of a view is still one line.
- **Items of a list.** `ListIndexItem` shows the position of an item in a read-only `index` row, read from the list whenever it is shown, in place of the generated idShort.
- **Testing the forms.** `tests/medium/forms.py` drives the generated dialogs by parameter name and stands in for `exec`, so that tests make elements through the real dialogs. The parametrized test in `tests/medium/test_element_types.py` compares the form and the attribute list of each of the 14 element types with the constructor of the class, so that an attribute that a new SDK adds fails it.

### Replacing an element

[ADR 0010](adr/0010-replacing-an-element-shows-what-is-lost.md) records the decisions. The SDK cannot change the class of an element, or what a list fixes, so both build a new element through its constructor and swap it in place.

1. `plan_conversion` or `plan_list_rebuild` makes a plan: the preview of the new element, what it lacks (`losses`), and where each direct item went (`child_keys`).
2. `plan_reference_updates` finds the model references through the element with the `ReferenceIndex`. They get the key type and target class of the new element, and the new position or idShort of an item. References into items that are gone are listed, and stay.
3. The user sees the losses and the orphaned references, with Cancel as the default. A plan without either asks nothing.
4. `replacement_command` is one step: the reference commands first, then `ReplaceElement`, which builds the element again, so that its items carry the updated references, and swaps it with `containers.replace_member`. The position stays, and undo gives back the old element itself.

| Group | Types | Carried over |
|---|---|---|
| Value elements | Property, Range, MultiLanguageProperty, File, Blob | The value as text. Property and Range keep the value type for each other. A Range gives its `min` and takes `min` and `max` from one value. A MultiLanguageProperty gives one text (English if present). A File's path is the text of a Blob, or the content of the stored file. |
| Reference elements | ReferenceElement, RelationshipElement, AnnotatedRelationshipElement | `first` (the `value` of a ReferenceElement), and `second` between relationships. |
| Containers | SubmodelElementCollection, SubmodelElementList, Entity, Operation | The items, as copies. A list takes the most common type, value type, and semantic id and keeps the items that fit. An Operation takes all items as input variables. An Entity is a CoManagedEntity. |
| Capability | Capability | Only the shared attributes, both ways. |
| BasicEventElement | BasicEventElement | Only the shared attributes. It converts to every type, but no type converts to it. |

Every pair carries the shared attributes: idShort, display name, category, description, semantic id, supplemental semantic ids, qualifiers, extensions, and embedded data specifications. Any pair across groups carries nothing else, and lists everything specific as lost. An item of a list, and nothing in a list, converts, because the list fixes its type (AASd-108), and the annotations of a relationship convert to data elements only.

### Registering an action

A feature adds an action to the context menu of the tree views, and to the toolbar, without editing `treeview_pack.py` or `base.py`.
Describe the action with an `ActionSpec` and register it when your module is imported:

```python
from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext, ActionSpec, ViewKind
from aas_editor.ui.actions import register_action


def mark_as_parameter(context: ActionContext) -> None:
    element = context.index.data(OBJECT_ROLE)
    # One step in the history of the package. Read mode refuses it.
    context.push(
        SetAttribute(
            observer_for(context.package), element, "category", "PARAMETER"
        )
    )


register_action(
    ActionSpec(
        action_id="example.mark_as_parameter",
        text="Mark as parameter",
        run=mark_as_parameter,
        is_enabled=lambda context: context.index.isValid(),
        views=ViewKind.PACKAGES,  # or DETAILS, or ANY
        toolbar=True,
    )
)
```

- Every tree view builds an action for each spec that fits its kind of view when it is created. Register before the first view exists, for example by importing your module in the composition root, `__main__.py`, after its existing imports.
- `is_enabled` is asked whenever the current item changes. `mutates` is true by default, and then the action is also disabled in Read mode and in views that do not allow editing.
- `ActionContext` has the view, the current index, the selection, the package, and its stack. `toolbar=True` adds the action to the main toolbar, and `order` sorts the actions.

### Reference integrity

[ADR 0009](adr/0009-reference-integrity.md) records the design.

- A reference of the SDK is immutable, so changing one means replacing it where it is stored. `iter_slots` finds those places by reading the attributes of the SDK objects, with no list of fields. `ReferenceSlot` names the object, the attribute, and the list or set that holds the reference.
- `ReferenceIndex(package.objStore)` is built for one operation and dropped. It answers `is_taken(id)`, `duplicate_ids()`, `usages_of(targets)`, `through(path)`, `resolve(reference)`, and `dangling()`. Building it takes about 17 ms for the largest bundled template.
- Every operation first makes a plan without changing anything, then builds commands for the plan:
  - `plan_rename_id` and `plan_rename_id_short` give a `RenamePlan`, and `RenameCommand` makes the rename and the updates of the references as one step. A duplicate id and an invalid idShort are refused with a `RenameError`, and the idShort error carries a suggestion.
  - `plan_delete` gives a `DeletePlan` with the usages, the references that can be taken away, and those that must stay. `prompt_for` says what to ask, and `delete_commands` or `cleanup_commands` build the commands.
  - `plan_fix_references` gives the repairs and what cannot be repaired. `sync_id_short_commands` copies an idShort to a concept description.
- The tree views ask through `ui/delete_flow.prepare_delete` before they delete the selected rows. The item models send an id or idShort typed in a cell through `ui/reference_actions.rename_command`, so a cell edit and the Rename action take the same path.
- `register_reference_actions()` adds the actions to the registry. `__main__.py` calls it before the first view exists.
- A feature that moves or replaces elements must keep references right in the same step. For positions in a list, use `rewrite_keys` with a `KeyRename` for each item that moved.

### Working with legacy code

- Put new features in the layers, and connect them to the legacy UI with a thin adapter.
- When a change requires substantial work in a legacy module, move the affected logic to a layer first, in a separate `refactor` commit.
- Do not rewrite legacy code that no planned feature needs to change.

Type checking and lint rules are strict in the new packages, and relaxed in legacy ones.
See [ADR 0003](adr/0003-python-style.md).

## Key dependencies

| Dependency | Used for |
|---|---|
| PyQt6, PyQt6-WebEngine, PyQt6-QScintilla | User interface, content preview, JSON editor |
| basyx-python-sdk | AAS metamodel and AASX, JSON, and XML adapters ([ADR 0004](adr/0004-basyx-sdk-pin.md)) |
| aas-test-engines | File validation |
| openpyxl | Excel import |
| langchain and related packages, sentence-transformers, faiss-cpu, pypdf | Handover Documentation tool |

## Related documents

- [Decision records](adr/README.md)
- [Feature parity roadmap](feature-parity.md)
