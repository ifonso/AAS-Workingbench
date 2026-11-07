# Architecture

AAS Workingbench is a desktop viewer and editor for Asset Administration Shell packages, built on PyQt6 and the Eclipse BaSyx Python SDK.
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
| `__main__.py` | Entry point and composition root. Creates `QApplication`, sets the application font (before any module that reads a `QFont` at import), registers the actions of each feature, and opens `EditorApp`. |
| `editorApp.py` | Main window, menus, the command bar, the tabbed docks, session save and restore. |
| `design.py` | The layout of the main window, written by hand (see [ADR 0028](adr/0028-main-window-layout.md)). `mainwindow_base.ui` is the record of where it started, and no source. |
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

### How the editor works

1. `PackTreeView` opens a file as a `Package`, and BaSyx loads its objects into an object store.
2. `models/` wraps the objects in tree items. Selecting one opens its attributes in a tab, shown by `AttrsTreeView`.
3. Attributes and editors come from **runtime type introspection**: `utils/util_type.py` and `getAttrTypeHint` read the type hints of BaSyx classes.
   This is why the editor handles new SDK attributes with little code, and also why it relies heavily on SDK internals.
   What a tab shows is not the introspected name: `domain/attribute_vocabulary.py` gives the name of the metamodel, the type, and the description of each attribute. The editor still edits by the name of the SDK, which `NAME_ROLE` holds, and a test fails for an attribute without an entry.
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
| `domain/load_report.py` | What the SDK left out when it read a package: turns its log records into issues (left out, kept, or not understood, with the kind, line or id, part, reason, and the full text), and writes a summary and a text to copy. It does no logging and reads no files. |
| `infrastructure/package_io.py` | Reads and writes AASX, JSON and XML through BaSyx. A write goes to a temporary file with `failsafe=False` and replaces the target in one step. A read listens to the log of the SDK for its length, and gives the report of what a failsafe read skipped. It does not import `Package`. |
| `infrastructure/open_problems.py` | Looks at a file and at the error of reading it, and says in a sentence why it cannot be opened: gone, locked, wrong extension, empty, not a ZIP or OPC package, not valid JSON or XML, or made for metamodel 1 or 2. For these the failsafe branch is not offered. `ui/open_warnings.py` shows the sentence. |
| `ui/load_report_dialog.py`, `ui/load_report_actions.py` | The dialog that lists what was left out of a package, and the context menu action that shows it again. |
| `ui/save_warnings.py` | The dialogs for blockers, warnings, and missing files. They show decisions that `application/save.py` made. |
| `ui/actions.py` | The registry where features add actions to the context menus and the toolbar. It also decides the order of the menu: sections by the prefix of the action id, separators, submenus for the crowded sections, and hiding what does not apply (see [Registering an action](#registering-an-action)). |
| `domain/design_tokens.py` | The table that the look is made from: the colors of the light and the dark theme, the list of every text and icon pair with its least contrast, spacing, radii, density, and the type ramp. No Qt (see [ADR 0025](adr/0025-design-tokens-and-theme-architecture.md)). |
| `ui/theme/` | `stylesheet.py` fills `app.qss.template` with the tokens, `palette.py` makes the `QPalette`, `assets.py` draws the images that the sheet needs, and `manager.py` puts a theme on the application with Fusion, forces the color scheme, follows the system when asked, and emits `changed`. `theme_manager()` switches a theme, and `current_tokens()` gives the colors in use. Read a color when drawing or styling, never at import. The themes are Follow system, Light, Dark, and Native, which gives back the style and the palette that the application started with and has no style sheet. `application/theme_choice.py` has their ids and labels and maps a saved name, including the names of the old themes, to one of them (Light is the default). |
| `ui/theme/fonts.py`, `ui/theme/icons.py`, `ui/theme/kind_icons.py`, `fonts/`, `icons/tabler/`, `icons/kinds/` | The font and the icons (see [ADR 0027](adr/0027-bundled-font-and-themed-icons.md)). `fonts.py` registers the bundled Inter and sets the application font to it at the body size of the type ramp. `icons.py` has `ThemedIconEngine`, which draws an SVG file that uses `currentColor` in the color of an `IconRole` in the theme in use, at the pixel ratio of the screen, so a `QIcon` made at import follows a switch of theme. `tabler_icon(name, role)` makes an icon of the bundled Tabler set, and `svg_icon(path, role)` of any file, which is how a new kind of icon is added. `settings/icons.py` keeps the names of the action icons. `kind_icons.py` has `kind_name(obj)` and `kind_icon(obj)`: the file stem and the icon of the kind of an object, from `KIND_FILES` (a subclass takes the file of its nearest base, and a `ModelReference` to a Submodel is a `submodel_reference`). The 24 files of `icons/kinds/` are the project's own drawings, and `StandardItem.updateIcon` uses them. The licenses of Inter and Tabler are in their folders and in `NOTICE`, and `NOTICE` records the kind icons. |
| `ui/colors.py` | The colors of problems and advisories in dialogs, read from the tokens of the theme in use when a widget is styled. They are functions, because a string fixed at import cannot follow a switch of theme. |
| `ui/command_bar.py` | The buttons of the command bar and the entries of the Edit menu. `MirroredAction` follows an action of a view, with its enabled state and its key, and triggers it, and `FocusedViewActions` makes each follow the tree or the tab that had the focus last. The view's action owns the key, and the mirror only shows it (see [ADR 0028](adr/0028-main-window-layout.md)). |
| `ui/pane_navigation.py` | `F6`, `Shift+F6`, `Ctrl+1`, and `Ctrl+2`: the panes of the window (tree or start panel, tab, bottom panel) and the actions that move the focus between them. A pane is a list of holder widgets and a function that finds what takes the focus, or None while the pane is not shown. The window gives the panes, and the module knows no tree. |
| `ui/breadcrumb.py`, `ui/empty_state.py` | The path of a tab as segments that open their object, with the text field of the address behind a click on the blank area, and the start of the window in place of the tree while no package is open. Neither knows a tree or a package. |
| `ui/colors.py` | The colors of problems and advisories in dialogs, read from the tokens of the theme in use when a widget is styled. They are functions, because a string fixed at import cannot follow a switch of theme. `style_as_problem`, `style_as_advisory`, and `keep_styled` style a widget and style it again after each switch, for a dialog that stays open. |
| `ui/dialog_layout.py` | The pattern of a dialog: 12 pixels of padding and 8 between parts (`DIALOG_PADDING` and `DIALOG_GAP` in the tokens), the buttons in a `QDialogButtonBox` from `make_button_box`, and `finish_dialog`, which pads the layout, sets again the default that a box had before it was inside the dialog, and marks the main action with the property `primary`. The style sheet fills `primary` buttons with the accent and outlines a default button that is not primary. `focus_first_field` gives the first field the focus in a dialog that made its buttons first. |
| `ui/theme/` | `stylesheet.py` fills `app.qss.template` with the tokens, `palette.py` makes the `QPalette`, `assets.py` draws the images that the sheet needs, and `manager.py` puts a theme on the application with Fusion, forces the color scheme, follows the system when asked, and emits `changed`. `theme_manager()` switches a theme, `current_tokens()` gives the colors in use, and `theme_manager().set_density(...)` changes the density. Read a color when drawing or styling, never at import. The themes are Follow system, Light, Dark, and Native, which gives back the style and the palette that the application started with and has no style sheet. `application/theme_choice.py` has their ids and labels and maps a saved name, including the names of the old themes, to one of them (Light is the default). |
| `ui/colors.py` | The colors of problems and advisories in dialogs, read from the tokens of the theme in use when a widget is styled. They are functions, because a string fixed at import cannot follow a switch of theme. |
| `ui/compact_rows.py` | What a row of a tree is made of besides its text. `row_size_hint` gives the height of the delegate, from the density of the theme and the font of the row, because Qt ignores the height of a row in a style sheet. `paint_row_signs` paints the bar of a selected row and the dot of a name that changed or was added since the save. `ColorDelegate` calls both. The row, its colors and its fonts are read when it is drawn, so a switch of theme or density needs only a repaint and a layout. |
| `application/font_sizes.py` | `migrated_font_size`: the old default of 12 pt takes the new default once, by the version of the default that was saved with the size, and any other size stays. |
| `domain/value_types.py` | Parses, formats, and checks text for each of the 31 XSD value types, using `from_xsd` and `xsd_repr` of the SDK and the checks it lacks. Also converts a value through its text, and checks the limits of a Range. |
| `domain/typed_values.py` | The rules for the attributes that follow a `value_type` (Property, Range, Qualifier, Extension): text becomes a value, a Range keeps min at or below max, and a change of the type plans the converted values or refuses. Also recognizes the type hints of values and value types. |
| `domain/language_tags.py` | Checks that a language tag is well-formed BCP 47, with the reason when it is not. Standard library only, and the same syntax as the SDK. |
| `domain/blob_content.py` | Shows the bytes of a Blob as text or as hex, and reads them back. Keeps Windows line breaks. Also turns Base64 text into the bytes it spells and back, with the reason when the text is no Base64. |
| `domain/list_children.py` | What a new child of a SubmodelElementList gets from the list: its type, value type, and semantic id. |
| `ui/value_editor.py` | `ValueTypeBox`, `ValueLineEdit`, `ValueEdit`, `BinaryEdit`, and `ValueEditDialog`. They only show the rules of the domain modules (see [Entering values](#entering-values)). |
| `ui/blob_actions.py` | The context menu actions that load, save, and convert the bytes of a Blob (Base64 text to bytes and back). Registered by `__main__.py` with `register_blob_actions`. |
| `domain/default_languages.py`, `domain/id_templates.py`, `ui/user_defaults.py` | The setting of default languages and the templates of generated ids (`urn:x:DDDD`) as texts that are read and checked, and the one place that reads them from `AppSettings` (see [ADR 0019](adr/0019-defaults-and-notices-of-new-objects.md)). |
| `application/operations/language_order.py` | `plan_language_move` and `language_move_command`: moving the entries of a multi-language text by their language, with `ReorderLanguages` of `edits.py`. |
| `application/operations/paste_qualifier.py` | `plan_paste_into_qualifier` and `paste_qualifier_commands`: taking the clipboard qualifier into an existing one, which keeps its kind. |
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
| `domain/part_names.py` | The names of stored files: checks a name as an OPC part name that cannot leave the package, makes a name from a folder and a local file name, finds names that are the same part (case-blind), numbers a taken name, and guesses the media type (`application/octet-stream` when unknown). |
| `application/supplementary_files.py` | The stored files and what refers to them. The commands `AddFile`, `RemoveFile`, `RenameFile`, and `ReplaceFile`, and the operations that group them with the changes to File elements and the thumbnail: add, rename, move, remove, create and edit text, link, and find dangling references. |
| `application/file_transfer.py` | Brings the files of copied objects along when they are pasted into another package: plans the copies, reuses identical files, numbers a taken name, and updates the pasted paths. Also remembers the package that was copied from. |
| `ui/file_controller.py` | What the user can do with the files of one package: asks through `ui/file_dialogs.py`, runs the operations on the history of the package, and shows why something was refused. Also asks about the references of files that the package tree deletes. |
| `ui/file_dialogs.py` | The pickers, the questions, the text editor, and the list of dangling references. |
| `ui/package_files.py` | The Package files panel and its dock. |
| `ui/file_actions.py` | The context menu actions for stored files, File elements, and the default thumbnail. Registered by `__main__.py` with `register_file_actions`. |
| `domain/validation/` | The rules over BaSyx objects: `rules/` has 24 rules in seven modules, `context.py` walks the package once for all of them, `engine.validate` runs them, `findings.py` has `Finding` and `ValidationReport`, and `coverage.py` records for each constraint whether the SDK, a rule, or neither enforces it (see [Validation](#validation)). |
| `application/validation.py` | `validate_package(source)` runs the rules on anything that has `objects` and `files`, such as the result of `Package.save_source()`. `save_check_for(report)` maps a report to the blockers and warnings of a save (D5). |
| `application/change_marks.py` | `ChangeMarks`: the objects that changed or were added since the save, cleared by the command stack at the saved state (see [Validation](#validation)). |
| `application/hints.py` | `HintsMode`, the global switch of hints mode. |
| `ui/validation_service.py`, `ui/validation_dock.py`, `ui/validation_window.py`, `ui/validation_status.py` | The service that runs the rules for a package, the dock that lists the findings, the connection of the dock, the status counts and F8 to the main window, and the counts of errors, warnings and hints in the status bar. |
| `application/command_palette.py`, `ui/command_palette.py`, `ui/palette_sources.py` | The command palette (Ctrl+K). The application module has the entries, the match and order for a query, and the commands used last, without Qt. `palette_sources` makes the entries from the menus, the registry and the open packages, and `command_palette` is the widget and the controller that runs a picked entry. |
| `ui/hints_bar.py`, `ui/inline_hints.py`, `ui/tree_navigation.py` | The hints above a tab, the hints under dialog fields, and selecting an object in the package tree. |
| `domain/clipboard_json.py` | AAS objects as the SDK's JSON for the system clipboard, and back, with `ClipboardError` for anything that is no valid AAS object. Also the copy that a paste inserts. |
| `application/operations/move.py` | `plan_move` and `move_commands`: the new order for the moved members, and the keys that references through list items get (see [Structure operations](#structure-operations)). |
| `application/operations/paste.py` | `plan_paste` and `paste_commands`: copies with a free idShort or a new id, inserted at a position. |
| `application/operations/companions.py` | `gather_companions`, `plan_concepts`, `concept_commands`, and `retarget_semantic_ids`: what goes with a copy between packages. It lists the file references of the copies too. |
| `ui/move_actions.py`, `ui/paste_actions.py`, `ui/paste_dialogs.py` | The move and paste actions and the questions of a paste between packages. |
| `domain/asset_information.py`, `application/operations/create.py` | `build_asset_information` and `build_specific_asset_id` check the asset ids and say what is wrong (AASd-131). `new_shell` and `new_submodel` make valid objects with generated ids, `add_shell` and `add_submodel` put them in as one step, and the asset id commands edit a shell. |
| `application/operations/bulk.py` | `plan_remove_attributes` finds the qualifiers, extensions, descriptions, display names, or categories of a Submodel and everything below, and `removal_commands` removes them. |
| `domain/reference_picker.py` | The rules of the reference picker (see [Entering references](#entering-references)). |
| `ui/create_dialogs.py`, `ui/create_actions.py`, `ui/bulk_actions.py` | The dialogs and the actions Create AAS, Create Submodel, Link existing Submodels, Generate global asset id, Add specific asset id, and Remove attributes. |
| `ui/reference_picker.py`, `ui/reference_fields.py`, `ui/reference_jump.py` | The picker dialog, the form fields that hold it, and Jump to target. |
| `domain/member_json.py` | Reads and writes qualifiers, extensions, specific asset ids, and data specifications as the SDK's JSON, by placing them in a holder that the SDK's decoder reads. `MemberKind`, `MemberJsonError`, `clone_member`. |
| `domain/presets.py` | `parse_presets` turns the text of a preset file into `Preset`s and `Problem`s without raising, `merge_presets` lets the user's presets replace the shipped ones. |
| `domain/rename_pattern.py` | The pattern language of bulk changes: `compile_pattern`, `render`, `PatternContext`, and `PatternError` (see [Bulk editing](bulk-editing.md)). |
| `infrastructure/submodel_templates.py` | Lists the 252 bundled submodel template files without reading them, and reads one when asked, once, in failsafe mode. The menu "Add existing submodel" of the package tree fills the menu of a file when it is first shown, so a window does not read them all at its start. Nothing changes what it read, and a paste copies the submodel. |
| `infrastructure/preset_files.py` | Reads the shipped files (`aas_editor/presets/`) and the files of the user, and reports each unreadable file as a problem. |
| `application/operations/bulk_edit.py` | `plan_change_attribute` previews a pattern change of an idShort, description, display name, or value, and `change_commands` builds it. Also `group_extensions` and `remove_extension_commands`. |
| `application/operations/bulk_move.py` | `plan_bulk_move` moves a selection in each of its containers, with one rewrite of the references through moved list items. |
| `application/operations/attach.py` | `plan_attach` and `attach_commands` add a member to many owners and skip those that have it. |
| `ui/bulk_dialogs.py`, `ui/bulk_edit_actions.py` | The dialog with the preview, the removal of extensions, and their actions. Registered by `__main__.py` with `register_bulk_edit_actions`. |
| `ui/preset_dialogs.py`, `ui/preset_actions.py` | The preset list and the actions for presets and the clipboard. Registered with `register_preset_actions`. |
| `domain/data_specifications.py` | The IEC 61360 template key and how to tell its spellings apart, `Iec61360Draft` (the content as text), `check_draft` (reasons the SDK would refuse it, and notes for AASc-3a-008, 009 and 010), `build_record`, and `empty_attributes`. |
| `domain/value_list_text.py` | `parse_value_pairs`: value list pairs from lines or JSON, one entry at a time, never evaluated. |
| `domain/concepts.py`, `domain/concept_order.py` | Submodels and elements with their semantic ids, new descriptions from a semantic id or a pair, matching by idShort, empty descriptions, and the view orders of descriptions. |
| `application/operations/concepts.py`, `application/operations/data_specs.py` | `plan_create`, `plan_assign`, `plan_detect`, `plan_from_pairs`, `plan_invalid`; and the commands for records, template keys, empty attributes, and value list imports (see [Concept descriptions](#concept-descriptions)). |
| `ui/concept_actions.py`, `ui/concept_dialogs.py`, `ui/iec61360_dialog.py`, `ui/value_list_dialog.py` | The actions in the context menu of the package tree, registered by `__main__.py` with `register_concept_actions`, and their dialogs. |
| `domain/selection.py` | The facts about a selection: `summarize` (how many rows, of which kinds, in how many parents), and `has_mixed_variable_directions`, which tells a selection of Operation variables of different directions, where Move and Delete are not offered (see [ADR 0020](adr/0020-selection-locations-and-clipboard.md)). |
| `application/locations.py` | `LocationStack`: the pushed editing locations, held by weak reference, so a closed package or a deleted object is skipped by Pop. |
| `application/operations/copy_shell.py` | `plan_copy_shell` and `copy_shell_commands`: an AAS with its global asset id and Submodels under new ids, and the references between the copies. |
| `ui/selection_panel.py` | The Selection dock below the package tree. Its buttons are the actions of the tree view. |
| `ui/selection_rows.py` | The rows that Delete, Cut and Copy act on: each selected row once, in the order of the tree, under any parent, and a refusal for rows of two packages ([ADR 0023](adr/0023-actions-on-the-whole-selection.md)). |
| `ui/location_actions.py`, `ui/shell_copy_actions.py` | Push location and Pop location, and Copy AAS with new Submodel ids. Registered by `__main__.py`. |
| `domain/attribute_vocabulary.py` | For each attribute of each class: the name of the metamodel (`displayName`), the name of its type (`list of Qualifier`), and a short description from Part 1. Keyed by class name and found along the base classes. `attribute_info`, `metamodel_name`, and `entries` (see [ADR 0022](adr/0022-attribute-vocabulary.md)). |
| `domain/form_labels.py` | What a generated form calls a field: `field_label` gives the name of the metamodel, the mark of a required field, and the description for the tooltip. No Qt (see [ADR 0026](adr/0026-forms-read-in-words-of-the-metamodel.md)). |
| `domain/attribute_display.py` | What a tab reads for a value that Python would show badly: `value_type_name` (`xs:double`), `type_column_text`, `value_text` (`(not set)`, `(empty)`), and `entry_label`, the name of an entry of a list. |
| `domain/readable_values.py` | What a cell reads for a value that Python shows as a repr: `readable_text` (`Origin: datasheet`, `2 qualifiers`, `8 bytes`), `count_text`, `content_text`. Only the display role uses it (see [ADR 0024](adr/0024-package-tree-vocabulary-and-layout.md)). |
| `domain/tree_names.py` | What the package tree calls its groups of objects (`Submodels`, `inputVariable`) and the type of its rows. The tree is still found by the name of the SDK. |
| `domain/window_layout.py` | The size of the first window from the room of the screen, the widths of the two zones, and how a saved orientation of the zones is read from whatever form the store gives back (`saved_orientation`). |
| `application/header_state.py` | `restorable_state`: a saved header state, and the saved sizes of the zones, are restored only for the version of the layout that they were made for. |
| `domain/ordered_store.py` | `OrderedIdentifiableStore`: the store of a package, a `SetIdentifiableStore` that keeps the order of `add`, so the order of a file survives an open and a save ([ADR 0021](adr/0021-order-of-the-file-and-concept-description-gaps.md)). |
| `domain/samm.py` | Recognizes a concept description that carries a SAMM element in an extension, reads the links of its JSON, and puts the identification first in the attributes of such a description. It does not edit SAMM. |
| `domain/concept_summary.py`, `ui/embedded_concept.py` | What the embedded display shows about a description, and the panel of the tab that shows it below the attributes of a submodel or an element. The tab only builds it and gives it the object (see [Concept descriptions](#concept-descriptions)). |
| `application/operations/sort_concepts.py` | `plan_sort` and `sort_command`: the permanent sort of the descriptions, one undo step, refused for the orders that cannot sort. |
| `domain/validation/rules/concepts.py` | AASc-3a-004 to 007: the data types that a category of a description allows. |

### Supplementary files

[ADR 0013](adr/0013-supplementary-files.md) records the SDK findings and the decisions.

- **Where it is in the interface.** The package tree already lists the stored files below `fileStore`. Their context menu has the actions, the same functions are buttons of the Package files panel (View > Panels), and File elements and shells have the picker in their context menu (D15).
- **One group for a file and its references.** Rename and Move change the name in the container and every File element, annotation, and thumbnail that has the old name, so one undo restores both. `FileReference` holds the object that has the path (`holder`), the attribute (`value` of a File, `path` of a Resource), and for a thumbnail its AssetInformation.
- **Nothing is overwritten.** A new file with a taken name gets a numbered name, an identical file is reused, and a rename onto a taken name is refused. Names that differ only in case are taken.
- **Names come from the file being edited,** so they are checked by `part_names.validate` when a file is added, created, renamed, or moved. A name that could leave the package is refused with a reason.
- **The tree follows the container.** A command reports `Change.changed` for the container, and the item of the file store reads its rows again (`PackTreeViewItem.repopulatesOnChange`).
- **Deleting a stored file in the tree** goes through `PackTreeView.prepareDelete` (the usages question of the delete flow), then the model removes the file with `RemoveFile`.
- **Copying to another package.** `TreeClipboard.source` records the package at copy time, and the clipboard hands it to `copy_source`. The paste actions (above, below, into) ask `gather_companions` for the file references of the copies and add the commands of `transfer_commands` to the paste group. The older Paste goes through `StandardTable.addItem`, which wraps the add with `with_copied_files`. Both add the files and update the pasted paths in the same undo step, and the window shows what was copied or numbered in the status bar.
- **Save.** `check_save` returns the dangling Files as a blocker with the code `DANGLING_FILES`, and the stored files that nothing refers to as a warning with `UNREFERENCED_FILES`. The dialogs offer "Repair file references..." and "Show package files...".
- **Crash recovery.** When any stored file differs from the opened state, the recovery is an AASX. The files that nothing refers to cannot be in it, so they are written to `<stem>.files.json` next to it, and `restore_from_recovery` reads them again.

### How saving works

1. `PackTreeView.savePack` builds a `SaveSource` from the `Package` with `Package.save_source()`, and calls `application.save.save`.
2. The check runs. A blocker shows a dialog and stops. A warning asks the user, with Cancel as the default.
3. `package_io.write_package` writes, and `Package.recordSaved` changes `Package.file` only afterwards, so a failed Save As leaves the package where it was.

A package that was opened through the failsafe branch is partial (D6). It cannot overwrite the file it was read from.
The SDK logs what failsafe mode skips, and `package_io.read_package` captures those records into `PackageParts.load_report` (`domain/load_report.py`, [ADR 0018](adr/0018-load-report.md)). The editor shows the list when the package opens, from the context menu later, and in the text of the refused save. The report does not bring the content back, so every failsafe package still counts, also when its report is empty.
A package that opened strictly is partial too, when an object has the id of a different object in an earlier part, because the SDK skips it without a record. `_TolerantReader` finds those.

Saving does not add Submodel references to the first AAS (D8). `Package.all_submodels_to_aas` is an explicit action in the context menu.

Crash recovery writes the objects as JSON. When files were added, removed, renamed, or changed since the package was opened, it writes a complete AASX instead, so that restoring keeps them. Files that nothing refers to go to a `.files.json` beside it (see [Supplementary files](#supplementary-files)).

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
- **Labels of the forms.** `ObjGroupBox` labels a field with the name of the metamodel from `domain/form_labels.py` (`valueType*`), with the description as the tooltip, but finds and fills it by the name of the SDK (`paramWidgets`, `CreateOptionalParamBtn.paramName`). The label is a `QLabel` with the property `sdkName` and the field as its buddy, and `ObjGroupBox.labelOf` returns it. The add dialog of a list asks `EditObjDialog` for `firstEntry`, which calls `IterableGroupBox.startWithEntry` (see [ADR 0026](adr/0026-forms-read-in-words-of-the-metamodel.md)). An entry of a list is titled by `entry_title` (`Reference 1`, `Text 1`), and the two fields of a language entry read `language` and `text` in a form, while the tabs keep `key` and `value`. A box does not pass its title to the fields inside it.
- **Testing the forms.** `tests/medium/forms.py` drives the generated dialogs by parameter name and stands in for `exec`, so that tests make elements through the real dialogs. The parametrized test in `tests/medium/test_element_types.py` compares the form and the attribute list of each of the 14 element types with the constructor of the class, so that an attribute that a new SDK adds fails it.

### Replacing an element

[ADR 0012](adr/0012-replacing-an-element-shows-what-is-lost.md) records the decisions. The SDK cannot change the class of an element, or what a list fixes, so both build a new element through its constructor and swap it in place.

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

Every pair carries the shared attributes: idShort, display name, category, description, semantic id, supplemental semantic ids, qualifiers, extensions, and embedded data specifications. Any pair across groups carries nothing else, and lists everything specific as lost. An item of a list does not convert, because the list fixes its type (AASd-108), and the annotations of a relationship convert to data elements only.

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
- `ActionContext` has the view, the current index, the selection, the package, and its stack. `toolbar=True` adds the action to the main toolbar.
- **Where it goes in the menu.** The prefix of `action_id` before the dot picks the section: `create` and `asset`, `structure`, `references` and `reference`, `conversion`, `concepts`, `bulk`, `preset` and `clipboard`, `files` and `blob`. An unknown prefix goes last. Sections are separated, and `order` sorts only inside a section, so two features that choose the same number no longer mix their actions. `concepts`, the group of `bulk`, `preset` and `clipboard`, and `files` are submenus. Add a prefix to `_MENU_SECTIONS` in `ui/actions.py` for a new section.
- **What the menu shows.** An action whose `is_enabled` is false for the current item is hidden, so the menu of a Property lists about 40 entries and not all 90 that are registered. An action that applies but changes a package is shown and disabled in Read mode. Toolbar actions are never hidden. So write `is_enabled` as "does this apply to the row", and not as "is there a package", or the action shows on every row.

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

### Validation

[ADR 0010](adr/0010-validation-findings.md) records the design, and [Validation](validation.md) has the constraint table and the results on the templates.

- A `Rule` has an id (`AASd-nnn` or `EDT-...`), a title, its source, and a function from a `ValidationContext` to `Finding`s. `ALL_RULES` lists them, and `validate(objects, stored_files)` returns a `ValidationReport`, errors first.
- A finding names the object that is wrong (`subject`) and the shell, submodel, description or element to select (`anchor`). `blocks_save` is true only for the two findings that the SDK cannot write as AASX: a File with no stored file and a File under an annotation. They use `domain.file_references`, as `application/save.py` does.
- Add a rule by writing a function in a module of `rules/`, adding a `Rule` to its `RULES`, and a row to `coverage.COVERAGE` or `EDITOR_RULE_REASONS`. A test fails when the rules and the table disagree. Write the failing case with an edit or an argument that the SDK does not check, because the SDK refuses most invalid objects when they are made.
- A rule goes over the views of the context, so a run is linear: 43 ms for Purchase Order.
- `validate(..., tolerant=True)` turns a rule that raises into a warning of the rule `EDT-RULE-FAILED`. The dock and the save gate use it.
- **Save gate.** `SaveGate.check` is the `checker` of `application.save.save`. It merges `check_save` with `save_check_for(report)`, leaving out the two file rules that `check_save` already blocks. `SaveGate.confirm` remembers the errors the user accepted, so the same errors do not ask again. `Package.saveGate` holds one for each package, and `PackTreeView.savePack` passes it to `save`. The `code` of a `SaveIssue` is kept, so the dialogs still offer to repair file references or to show the package files.
- **Service.** `service_for(package)` returns the one `ValidationService` of a package. A view calls `listen(token, with_hints)` and `stop_listening(token)`. The service restarts a 250 ms timer on each change of the package and its history, and runs `validate_package` when the timer fires. It runs only while a view listens, in the thread of the UI. The status bar (`ValidationStatus`) listens for as long as a package is current, so the rules run with the dock hidden ([ADR 0029](adr/0029-validation-runs-while-the-panel-is-hidden.md)), and the wait after a change is at least five times the cost of the last run.
- **Dock.** `ValidationController` (`ui/validation_window.py`) is created by `EditorApp` before its menus. It adds the dock at the bottom, follows the package of the current row of the tree, and clears when the package is closed. A double click calls `select_object(tree, finding.anchor, package)`. The View menu lists the dock under Panels, and the hints action. The controller also owns the counts for the status bar, F8 and Shift+F8 (`step_finding` over `stepping_findings(report)`, errors and warnings only), and `finding_links()`, through which the bar of a tab asks the window to open a finding in the dock. `count_findings` counts a hint rule's finding as a hint whatever its severity, so the counts match what the dock lists.
- **Hints.** `hints_mode()` is on at first. `HintsBar` (one for each tab) lists `hints_for(report, object)`. `attach_inline_hint` is called by `ObjGroupBox.getInputWidget` for every parameter, and gives a hint under a text field when `field_problem(owner, param, text)` has one.
- **Marker.** `Package.changeMarks` is made with the package. The observer marks the object and its parents, and the models mark the objects of the rows above a change too. The models read it in `_markColor`, and repaint after a pass of the event loop. `ChangeMarks` clears itself when the command stack is at the saved state.
- **Read mode.** `DetailedInfoItem._populateUnknown` skips null attributes while the editor is in Read mode, and `DetailedInfoTable` reads its rows again when the mode changes.

### Structure operations

[ADR 0011](adr/0011-natural-order-in-trees.md) records the order of the trees.

- **Order.** `ReorderMembers` (in `application/edits.py`) puts a `NamespaceSet` or a list into a new order and reports `Change.moved` for each member that changed its row, lowest final row first, so a model that moves one row at a time ends in the new order. `domain.containers.reorder_members` does the work through `domain.ordering.reorder`. Shells, submodels, concept descriptions and the references of a shell live in sets and cannot move (D16).
- **Moves.** `plan_move(container, selected, kind, objects)` returns a `MovePlan`, or None when the order would not change. For several selected members of one container, `new_order` takes them out and puts them back next to each other: up one place above the first of them (nothing changes when it is on top), down as the mirror, and top and end at the ends. They keep the order of the container ([ADR 0020](adr/0020-selection-locations-and-clipboard.md)). For a `SubmodelElementList` the plan holds `rewrite_keys` changes with a `KeyRename` for every item whose position changed, and `move_commands` builds the reorder followed by `reference_commands`. Push them in one group.
- **The tree shows the order.** `SearchProxyModel` is in the natural order unless the user clicked a header (`sort(-1)`): a level with a saved order compares source rows, other levels are sorted by name. A move resets a sorted header. The header neither starts sorted nor restores a sort.
- **Search matches rows, and Save keys follow the selection.** `SearchProxyModel.search` keeps the parents of a match visible (recursive filtering) but returns only the rows that match themselves. `SearchBar` shows "k of n", and `bindFind(owner)` binds the Find key to the focus inside one widget, so the tree and each tab have their own bar without an ambiguous shortcut. `Ctrl+S` is `PackTreeView.saveAct`, which saves `focusedPackage()` (the package of the tab that holds the focus, else `activePackage()`: the package of the selected row, or the only open one), and `Ctrl+Shift+S` is Save All. `PackTreeView.unsavedPackagesChanged` carries the number of changed packages to the status bar.
- **Paste.** `plan_paste(container, items, index, keep_ids, taken_ids)` clones the items through `domain.clipboard_json.clone`, so the buffer can be pasted again and nothing keeps a parent. An idShort is made free with `unique_id_short`, and an identifiable gets `new_identifier()` unless it is a cut that can keep its id. `ui/paste_actions.py` reads the buffer, `TreeClipboard.objects`, where text on the system clipboard that is AAS JSON has already become objects (`TreeView._appendClipboardText`). The existing Paste uses `pasteCopyFor` for the same naming.
- **Between packages.** `TreeClipboard.source` is the package a copy came from. A paste into another package calls `gather_companions` (the concept descriptions of the semantic ids of the items and of everything below them) and `plan_concepts` (add, reuse when the JSON is equal, conflict otherwise), asks through `ui/paste_dialogs.py`, and puts `concept_commands` in the same group as the paste. A description added under a new id is followed by `retarget_semantic_ids` on the copies before they are inserted. `Companions` is the place to add other things that travel with a copy, such as supplementary files.
- **Actions.** `register_move_actions()` and `register_paste_actions()` add `structure.move_*`, `structure.paste_*`, `structure.paste_text` (Paste from text, which reads no clipboard), and `structure.clear_buffer`. The tree views refresh the enabled states when the selection, the rows, or the buffer change.

### Entering references

[ADR 0016](adr/0016-reference-fields-and-creation-dialogs.md) records the decisions.

- `widgetUtil.getWidget4typehint` gives every `Reference`, `ExternalReference`, and `ModelReference[...]` hint a `ReferenceFieldMixin` form. It keeps the key rows of the generated form and adds a "Choose from package..." button, and a line that says whether the reference resolves, dangles (and which key is missing), or points outside of the package.
- `rule_for_hint` turns the hint into a `ReferenceRule`: which kinds are accepted and which classes may be the target. `candidates` lists the shells, Submodels, concept descriptions and elements, `reference_to` derives the keys, and `status_of` checks a reference against a `ReferenceIndex`.
- The package comes from the tree view that opened the dialog (`package_of`), or from a `package` attribute of the dialog.
- The form builds the reference while the user types. When the SDK refuses the keys, the form shows its message and keeps OK off, so the user sees the reason (AASd-121 to 128) and not a traceback.
- Jump to target (`reference.jump`) is registered for the tabs. It opens the target in the same tab, so the tab's Back returns to the object being edited.
- Paste into an AAS goes through `plan_paste_into_shell` and `shell_paste_commands` in `application/operations/paste.py`, and `ui/paste_actions._paste_into_shell`.

### Creating

`new_shell` and `new_submodel` make objects that the SDK accepts, with ids from `new_identifier`. `add_shell` and `add_submodel` push one step each, and the second also pushes the reference from the shell. The dialogs validate while the user types by building the object, so OK is off with the reason. `register_create_actions`, `register_bulk_actions`, and `register_jump_actions` are called by `__main__.py`.

### Bulk operations and presets

[ADR 0017](adr/0017-presets-and-the-pattern-language.md) records the decisions, and [Bulk editing](bulk-editing.md) is the guide for users.

- **Plan, preview, build.** Each operation first makes a plan without changing anything, as the other operations do. A dialog shows the plan, and `*_commands` builds the commands, which are pushed inside one `stack.group(...)`. Several objects change as one undo step, and a failure while pushing undoes what was done.
- **Statuses.** A `BulkPlan` has an entry for each selected object: `CHANGE`, `UNCHANGED`, `SKIPPED` (nothing to change), or `REFUSED` (not allowed). One refused entry makes `can_apply` false. An `AttachPlan` has `ADD` and `SKIPPED`, and a skipped owner never stops the others.
- **Renames.** The new idShorts are checked against the names after the whole change. Several renames share one `rewrite_keys` call, so a reference through a renamed parent and a renamed child is rewritten once. When a new name is the current name of another selected element, the commands rename through temporary names first, inside the same group.
- **Moves.** `plan_move` still moves the members of one container. `plan_bulk_move` groups a selection by container and gives each its new order, and `ui/move_actions.py` uses it for every selection. The keys of references through moved list items are found once for all containers (`position_renames`). Nothing moves to another parent.
- **Members from outside.** A preset and the clipboard both give JSON, which `domain/member_json.py` reads through the SDK. `Preset.make()` and `clone_member` give a new member for each owner, because the SDK lets a qualifier or extension belong to one owner only.
- **Concept descriptions.** The actions of `ui/concept_actions.py` (Assign, Auto-detect, Create from all semantic ids, Fix data specification keys) take the whole selection already, so bulk editing adds no matching of its own (see [Concept descriptions](#concept-descriptions)).
- **Untrusted files.** `infrastructure/preset_files.py` never raises for a file. A bad entry is a `Problem`, and the dialog lists the problems.
- **Actions.** `register_bulk_edit_actions()` and `register_preset_actions()` add `bulk.change_attribute`, `bulk.remove_extensions`, `preset.add_*`, and `clipboard.add_*` to the registry. The preset and clipboard actions also work in a tab, on the row of an attribute such as `asset_information` or `qualifier`.

### Concept descriptions

[ADR 0014](adr/0014-concept-descriptions-and-iec-61360.md) records the SDK findings and the decisions.

- **Plans, then commands.** Each operation of `application/operations/concepts.py` makes a plan without changing anything (`CreatePlan`, `AssignPlan`, `DetectPlan`, `PairsPlan`, `InvalidConcept`), with a `summary` sentence and the items it skips and why. The `*_commands` functions build `AddMember` and `SetAttribute` commands, and the action pushes them in one group, so one undo takes everything back.
- **Finding the description.** A semantic id names a description when one of its keys holds the id (`fix.concept_of`). Creating takes the first key as the id. Assigning writes an external reference with one global key. A semantic id that is set is replaced only after the user saw the old and the new one, and Auto-detect never replaces one.
- **IEC 61360 records.** The dialog edits an `Iec61360Draft`, and `check_draft` is asked after every keystroke. Its errors are the reasons why the SDK would raise (empty preferred name, a language tag, lengths 18, 255, 1023 and 2048), and its advisories are constraints the SDK does not check. `build_record` raises `DraftError` with all reasons, and makes no attribute empty. Editing replaces the content of the record with `SetAttribute`, so the record keeps its place and the spelling of its key.
- **Value lists.** `parse_value_pairs` reads lines and JSON. JSON entries are decoded one at a time through the SDK's `StrictAASFromJsonDecoder`, with a skeleton that the SDK wrote, so a bad entry names its place and the others are read. `plan_value_list_import` compares pairs by value and value id keys, because the SDK compares them by identity, and the command sets a new set so undo gives the old one back.
- **Delete invalid.** `ui/concept_actions` lists the empty descriptions with their usages, asks which to delete, and then calls `ui.delete_flow.prepare_delete` and removes the descriptions in the same group as the reference cleanup.
- **View order.** `SearchProxyModel.setConceptOrder` takes a `ConceptOrder` and the ranks that `ranks_for` worked out for the orders that use ranks (list index, first use, by elements, structured). It applies while the tree is in the natural order and ignores a column that the user clicked. It never changes the package. `concepts.sort` is the one action that changes the order of the store: it plans with `plan_sort`, shows the new order, and pushes `ReorderMembers` on the store, which reports no rows because a view lists each kind of object under a node of its own ([ADR 0021](adr/0021-order-of-the-file-and-concept-description-gaps.md)).
- **Embedded display.** `EmbeddedConceptPanel` is built by `TabWithTreeView` next to the hints bar. `set_target(package, object)` shows the description that the semantic id of a submodel or element names, and refreshes after each change of the package, once for a burst. It holds no editing control. The open button calls `open_in_tab`, so Back of the tab returns.
- **Other open packages in the picker.** `PickerSource` and `candidates_in` list the targets of several packages. `reference_fields.open_packages_of` finds the other open packages through the tree view that the dialog was made for, and `is_semantic_id_of_element` tells the picker to start on the filter of concept descriptions.

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
- [Validation](validation.md)
