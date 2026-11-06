# V1 acceptance audit

The result of WP12: every acceptance criterion of the editing features F-EDT-01 to F-EDT-11, checked against the code and the tests of this repository.
The criteria are in section 9 of each document in `../package-explorer/design-docs/edit/`, outside this repository.
Without that folder the table below still reads, and the numbers refer to its lists.

## How to read this

Earlier reports said "covered" for most of these.
This audit opened the test behind each claim and asked whether it asserts the behavior or only that nothing crashes.
A criterion with a test that covers part of it is `P`, with the missing part named.

| Class | Meaning |
|---|---|
| T | Tested: a test asserts the behavior. |
| P | Tested in part, or the code does it and a test shows part of it. The missing part is named. |
| I | Implemented, and no test asserts it. |
| D | Different on purpose: a decision (D1 to D19 of the [plan](../planning/v1-editor-plan.md)), an [ADR](adr/README.md), or the [changelog](../../CHANGELOG.md) says so. |
| O | Out of scope for v1: a row of "Out of scope for v1" in the plan, or a "Known limit" of the changelog. A row only in the changelog is marked "limit". |
| G | A gap: not implemented, and not listed in the plan as out of scope. |
| N | Does not apply to a desktop application: scripting, touch, browser, repositories. |

## Count

| Document | T | P | I | D | O | G | N | Total |
|---|---|---|---|---|---|---|---|---|
| F-EDT-01 Editor framework | 12 | 1 | 0 | 0 | 1 | 0 | 1 | 15 |
| F-EDT-02 Environment, AAS, AssetInformation | 9 | 0 | 0 | 1 | 7 | 0 | 0 | 17 |
| F-EDT-03 Submodel and SubmodelRef | 12 | 0 | 0 | 1 | 2 | 0 | 1 | 16 |
| F-EDT-04 SubmodelElements | 14 | 0 | 0 | 6 | 2 | 0 | 0 | 22 |
| F-EDT-05 ConceptDescription and IEC 61360 | 10 | 1 | 0 | 6 | 2 | 0 | 0 | 19 |
| F-EDT-06 Common attribute modules | 11 | 1 | 0 | 3 | 1 | 0 | 0 | 16 |
| F-EDT-07 Qualifiers and Extensions | 5 | 0 | 0 | 3 | 5 | 0 | 0 | 13 |
| F-EDT-08 Copy, paste, reorder | 10 | 3 | 0 | 3 | 4 | 0 | 0 | 20 |
| F-EDT-09 Multi-element editing | 10 | 2 | 0 | 8 | 0 | 0 | 1 | 21 |
| F-EDT-10 Supplementary files | 12 | 0 | 0 | 3 | 1 | 0 | 2 | 18 |
| F-EDT-11 References, semantics, lookups | 9 | 0 | 0 | 3 | 10 | 0 | 0 | 22 |
| **All** | **114** | **8** | **0** | **37** | **35** | **0** | **5** | **199** |
Of 199 criteria, 114 have a test that asserts them, and 8 more are tested in part.
No criterion is left as a gap, and none is left implemented without a test. WP13 to WP17 closed the 22 gaps that WP12 found, or reclassified them with a reason given in the rows and the ADRs, and WP18 went through the 52 rows that were `P` or `I` (see [What WP18 found](#what-wp18-found)). What still costs a user is in [What remains after v1](../planning/v1-editor-plan.md#what-remains-after-v1).
The 8 `P` rows are about the wording of a message or a log line (F-EDT-05 AC17, F-EDT-06 AC13, F-EDT-08 AC7, AC10 and AC11, F-EDT-09 AC7 and AC17), and the press of a key (F-EDT-01 AC13), which needs a display.
Most O rows are ECLASS (F-EDT-04 AC21, F-EDT-11 AC8 to AC14, AC18 and AC22) and repository features, which the plan keeps out of v1.

## What this audit checked itself

Ten claims looked doubtful, and were checked in the code or by running it.

| Claim | Result |
|---|---|
| F-EDT-09 AC7 says that copying several rows is done. | The clipboard got the display names of the rows, one per line, and the buffer did not know its package, so a paste into another package skipped the concept descriptions and the files. **Defect, fixed** with two tests that failed first (`fix(editor): copy several rows as JSON and remember their package`). AC7 is `P`: the JSON array is there, the log line of the original is not. |
| F-EDT-08 AC9 and F-EDT-08 "copying between packages brings concept descriptions". | True for one row, false for several, for the same reason. Fixed together with the above. |
| F-EDT-01 AC7: deleting the last entry makes the list attribute absent. | Two tests assert that the list stays, empty. The file does not show it: serialized, an emptied `qualifier` is not written (probe). `P`. |
| F-EDT-09 AC3 and AC4: Move up on rows 2 and 4 of 6. | The code moves each selected row one place, to 1 and 3. The original makes them adjacent, at 1 and 2, and does nothing when the first selected row is at the top, while the code moves the others. Not recorded anywhere as a decision. `P`. **Closed by WP15**: the move is the original's, with a mirrored Down, and ADR 0020 records it. Both are `T` now. |
| F-EDT-10 AC8: a `.zip` gets `text/plain` for parity. | The code guesses from the extension, and gives `application/x-zip-compressed` on this machine, the registry of Windows, and `application/octet-stream` for an unknown one. The test asserts only "not text/plain". `D`, and the answer depends on the platform. |
| F-EDT-04 AC22: a null `orderRelevant` is shown as the default (true). | The SDK has a bool that is true by default, and a file without `orderRelevant` reads as true (probe). The case cannot occur. `P`, because the tests assert the default only for a new list. |
| F-EDT-04 AC9 and F-EDT-10 AC14, AC15: Base64 to binary and back for a Blob. | No code. The editor shows the bytes as text or hex. A gap. **Closed by WP14**: two actions of the Blob, `T`. |
| F-EDT-01 AC10, AC11: push and pop of an editing location. | No code. Back after Jump to target, and Back in the tabs, are the nearest thing. A gap. **Closed by WP15**: `T`. |
| F-EDT-05 AC10: the view orders of concept descriptions. | Four of six: name, idShort, id, first use. "List index", "By SubmodelElements" and the structured order are not offered. A gap. **Closed in WP16**: the store of the package keeps the order of the file now, so the list index exists, and all six are offered ([ADR 0021](adr/0021-order-of-the-file-and-concept-description-gaps.md)). |
| F-EDT-04 AC2: new MultiLanguageProperty has a row for each default language. | No setting of default languages. A gap. **Closed by WP14**: a setting, `T`. |

## What WP18 found

WP18 read the criterion of each `P` and `I` row in the specification, and wrote the missing assertion through the public API or a view.
Of the 52 rows, 42 became `T`, 2 became `D` (F-EDT-10 AC2, F-EDT-11 AC4), 1 went from `I` to `P` (F-EDT-01 AC13), and 8 stayed `P`.
Five rows were covered by tests that the first audit did not find (F-EDT-02 AC6, F-EDT-03 AC6, AC10 and AC11, F-EDT-07 AC4), and the rows cite them now.

The defects, with the test that failed first:

| Where | Defect | Fix |
|---|---|---|
| Part 1 | Delete, Cut and Copy on rows of two parents acted on the rows of the first parent only, and said nothing. | They act on every row, in the order of the tree, and refuse rows of two packages ([ADR 0023](adr/0023-actions-on-the-whole-selection.md), `test_cross_parent_selection.py`). |
| Part 1 | Move on rows of two packages pushed its commands on the history of one of them. | The move actions are off for such a selection. |
| Part 1 | A cell never suggested values: the delegate looked them up by the text of the cell, in a table keyed by class, and built the completer with a keyword that PyQt6 does not have. | Looked up by the owner and the attribute (`test_cell_completions.py`). |
| Part 1 | A refresh of a tab selected the current row alone, so the Move actions on language entries saw one row after a click with Ctrl. | The current row changes without the selection (`test_language_moves.py`). |
| Part 1 | A submenu that its owner deleted broke every later refresh of the view, so one test made 28 paste tests fail. | The view skips a deleted submenu (`test_action_registry.py`). |
| Part 2 | F-EDT-01 AC8: after a delete the tree selected the parent, not the previous sibling. | The sibling above, or the parent for the first row. |
| Part 2 | F-EDT-01 AC14: a hint rule that raised reached only the Validation dock, and not the tab where the hints are. | The bar lists the failure with every object. |
| Part 2 | F-EDT-11 AC7: undo of an edit of the supplemental semantic ids left the new reference in, because the SDK refills that list in place. | `SetAttribute` keeps a copy of such a list. |
| Part 2, not fixed | A File or Blob made without a content type is written without one, and no rule reports it, but V3.1 requires `contentType`. The SDK refuses `""`, so the editor cannot start with the value of the table. | Open: a rule, or a required field in the dialog. |

One item was not a defect.
A shell with no `idShort` (the Bill of Materials report) is read, shown by its type name, saved and read again (`test_objects_without_id_short.py`): the report counts `idShort` entries, and such a shell has none, so it is not lost.
One fixture was wrong, and is fixed: `test_load_report_flow.py` let the window of its view be collected, so three of its tests failed when the file ran alone.

## F-EDT-01 Editor framework

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_framework_criteria.py::test_in_read_mode_no_cell_of_a_tab_can_be_edited` (no cell of a tab has the editable flag, `edit()` refuses each of them, and the editing actions are off), `::test_in_read_mode_an_attribute_without_a_value_has_no_row`. For the package tree, `test_undo_views.py::TestReadModeInTheViews`. "No editing control appears" is shown as: nothing can open an editor. It was not looked at on a display. |
| 2 | T | `test_framework_criteria.py::test_a_typed_text_reaches_the_model_when_it_is_committed`: while the editor holds the new text the model has the old one, and after the commit of the cell it has the new one in one undo step. The element and the submodel above it are marked in the tree. |
| 3 | T | `test_change_markers.py::test_the_tree_marks_the_element_and_the_objects_above_it`, `::test_a_save_clears_the_marker_in_the_tree_and_in_every_tab`. |
| 4 | T | `test_framework_criteria.py::test_with_an_advisory_shown_editing_and_saving_are_still_possible`: the bar shows an `Error:` line for a wrong idShort, the value is edited, the save check has no blocker, and the file has the new value. `test_hints.py::test_bar_lists_the_hints_of_the_shown_object`. |
| 5 | T | `test_hints.py::test_bar_is_off_when_hints_mode_is_off`. |
| 6 | T | `test_framework_criteria.py::test_creating_an_attribute_that_is_not_set_redraws_the_row`: the row says `(not set)`, the Create dialog fills it, and the row shows the value, saved. The default row (one entry in the first default language) is in `test_user_defaults.py::TestDefaultLanguages::test_creating_a_display_name_starts_with_one_row_in_the_first_language`. |
| 7 | T | `test_framework_criteria.py::test_deleting_the_last_qualifier_leaves_no_attribute_in_the_file`: the SDK has no null for a list, so the model holds an empty one, the tab shows `(empty)`, and the file has no `qualifiers`. |
| 8 | T | The previous sibling is current after a delete, and the parent when the first row went (`test_framework_criteria.py::test_after_a_delete_the_previous_sibling_is_current`, `::test_after_a_delete_of_the_first_element_its_parent_is_current`). Declined: `test_reference_integrity.py::TestDelete::test_cancelling_the_usages_dialog_deletes_nothing`, `::test_deleting_a_submodel_without_usages_asks_for_confirmation`. **Defect found, fixed**: the tree went to the parent ([ADR 0023](adr/0023-actions-on-the-whole-selection.md)). |
| 9 | O | Plan: "Moving AAS, Submodels, concept descriptions, or SubmodelRefs"; D16. |
| 10 | T | `test_location_actions.py::test_pop_selects_the_pushed_row_with_its_expand_state`, `::test_a_collapsed_row_comes_back_collapsed`, `::test_pop_goes_back_through_the_pushes_in_reverse`, and `tests/small/test_locations.py`. Ctrl+Shift+P and Ctrl+Shift+O, tested not to collide with `settings/shortcuts.py` and the registered actions. |
| 11 | T | `test_location_actions.py::test_pop_on_an_empty_stack_changes_nothing_and_does_not_fail`, and `::test_a_pushed_row_that_was_deleted_is_skipped` for a stale location, which the original keeps. |
| 12 | N | Scripting. |
| 13 | P | `test_framework_criteria.py::test_every_gesture_is_bound_to_one_action_of_the_view`: each gesture is the shortcut of one action of the view, none is shared, and the standard ones are there. Delete in Read mode has a test. The press of a key is not tested: the offscreen platform has no active window, so Qt sends no shortcut (`QTest.keySequence` triggered none of the actions). It needs a display. |
| 14 | T | `test_framework_criteria.py::test_a_hint_rule_that_raises_is_shown_with_the_object`: the bar of a tab lists the failure with the rule, and `test_validation_hints.py::test_tolerant_validate_reports_a_warning_when_a_rule_raises` for the report. The severity is Warning: the scale has Error, Warning and Info, and the High of the original is Warning here, as in F-EDT-06 AC9. **Defect found, fixed**: only the Validation dock showed the failure. |
| 15 | T | `test_framework_criteria.py::test_a_redraw_keeps_hints_mode_and_the_sort_order`: hints mode and the sort column and order are the same after an edit, an undo, a redo and an undo. The IRI display and the SMT check of the original do not exist in this editor, so there is no state of them. |

## F-EDT-02 Environment, AAS, AssetInformation

| AC | Class | Evidence |
|---|---|---|
| 1 | D | [ADR 0019](adr/0019-defaults-and-notices-of-new-objects.md): a new AAS is an Instance, where the original makes NotApplicable (its own notice says Instance is usual). `test_create_flows.py::TestCreateShell::test_the_action_makes_a_shell_with_valid_asset_information`: kind Instance, the new row is selected, `urn:uuid:` id, valid AssetInformation, reload, undo. `test_asset_kind.py::test_a_new_shell_is_an_instance_unless_the_user_chooses_another`. |
| 2 | T | `test_shell_and_submodel_criteria.py::test_a_template_submodel_is_free_and_becomes_the_current_row`: kind Template, in no shell, and the current row. `test_create_flows.py::TestCreateSubmodel::test_template_kind_and_no_shell_make_a_free_submodel`. |
| 3 | T | `test_shell_copy_actions.py::test_on_the_node_of_the_shells_it_asks_which_to_copy`, `::test_the_environment_and_a_submodel_have_no_copy_of_an_aas`. "Copy AAS with new Submodel ids..." is on an AAS and on the shells node, and not on the package. |
| 4 | T | `test_shell_copy_actions.py::test_the_copy_has_new_ids_and_refers_to_new_submodels`, `tests/small/test_copy_shell.py` (new ids, references resolve to the copies, the original is unchanged, one undo step). A pasted shell keeps referring to the same Submodels (D13). |
| 5 | O | Plan: "Copy from an auxiliary package". |
| 6 | T | `test_reference_integrity.py::TestDelete::test_deleting_a_shell_leaves_its_submodels_for_f_edt_02_criterion_6` (confirmed: the shell goes and both Submodels stay), `test_shell_and_submodel_criteria.py::test_deleting_a_shell_is_one_step_and_undo_brings_it_back_with_its_submodels`, `::test_declining_the_question_keeps_the_shell`. The editor asks once and never deletes the Submodels with the shell, so there is no second question to decline. |
| 7 | O | Plan: "Stubs and Fetch, and repository delete". |
| 8 | T | `test_shell_and_submodel_criteria.py::test_renaming_a_shell_updates_the_references_to_it` (the reference of another shell follows, and one undo gives everything back), `::test_a_rename_that_cannot_be_done_says_why_and_changes_nothing`: the dialog names the id that another object has, and the accept button is off. The failure message is that text. |
| 9 | T | `test_shell_and_submodel_criteria.py::test_the_tab_of_a_shell_with_a_blank_global_asset_id_shows_the_advisory` and `::test_the_tab_of_two_shells_with_one_global_asset_id_shows_the_duplicate`: the bar of the tab of the shell lists them, and the bar of another shell does not. The dialog hint is in `test_hints.py::test_inline_hint_says_that_the_global_asset_id_is_empty`. A missing id is AASd-131, which the SDK enforces. |
| 10 | T | `test_shell_and_submodel_criteria.py::test_each_asset_kind_is_written_as_its_literal_and_read_back`: each of the four kinds is made in the dialog, is written as `"assetKind": "<literal>"` by the SDK's JSON, and is the same kind after a save and a reload. `test_create_flows.py::test_every_asset_kind_of_v3_1_is_offered`. |
| 11 | O | The plan's row "Metamodel V3.2": `Batch` is a literal of V3.2 and the SDK has no such kind (probe). A file with it is refused as a whole, and failsafe mode leaves the shell out (`test_asset_kind.py::test_a_file_with_batch_is_refused_as_a_whole`, `::test_in_failsafe_mode_the_shell_with_batch_is_left_out_and_the_package_partial`). The four kinds of V3.1 are read and written as they are (`::test_each_kind_of_v3_1_is_read_and_written_as_it_is`). |
| 12 | O | Plan: "Print code sheet". |
| 13 | T | `test_specific_asset_id_delete.py::test_the_last_specific_asset_id_goes_and_the_file_has_no_list`: the model has an empty list, which the SDK has no null for, and the file has none. `::test_the_last_asset_id_of_a_shell_without_a_global_one_is_kept` for AASd-131. One undo step: `::test_the_removal_is_one_undo_step`. |
| 14 | T | `test_package_files_ui.py::test_the_default_thumbnail_is_removed_after_a_question_and_the_file_stays`, `::test_a_removed_default_thumbnail_can_be_chosen_again`. The question comes first, and the file stays in the package. |
| 15 | O | Plan: "Stubs and Fetch". |
| 16 | O | Plan: "Stubs and Fetch". |
| 17 | O | Plan: "Finalize AAS". |

## F-EDT-03 Submodel and SubmodelRef

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_create_flows.py::TestCreateSubmodel::test_with_a_shell_the_submodel_and_its_reference_are_one_step`: kind Instance, the new row is selected (focus), one reference with the Submodel, one undo step. |
| 2 | T | `test_shell_and_submodel_criteria.py::test_a_template_submodel_is_made_with_the_id_of_the_template_pattern`: the Template kind takes the template of its kind from the settings (`urn:tmpl:` and four digits, and the Instance pattern for an Instance), and the id is in the saved file. `test_user_defaults.py::test_a_submodel_takes_the_template_of_its_kind` for the dialog. |
| 3 | T | `test_shell_and_submodel_criteria.py::test_linking_an_existing_submodel_adds_a_reference_and_no_copy`: the number of objects is the same, and the reference resolves to the Submodel that was chosen. `test_paste_into_shell_action.py::test_a_pasted_reference_is_added_and_the_submodel_stays_shared` for a pasted reference. |
| 4 | T | `test_shell_and_submodel_criteria.py::test_a_copy_of_a_submodel_within_a_package_is_deep`: a new id, a reference, and no object shared with the original, down to the element in a collection. `test_paste_into_shell_action.py::test_a_copied_submodel_is_added_with_a_new_id_and_a_reference` (saved, reloaded, one undo step). |
| 5 | T | `test_shell_and_submodel_criteria.py::test_a_submodel_copied_to_another_package_brings_its_concept_descriptions`: the Submodel, its reference, and the description that an element names. The editor has no "Copy single": a copy is deep, as the original's really is (its `shallowCopy` limits only the descriptions, F-EDT-08 section 10). |
| 6 | T | `test_reference_integrity.py::TestDelete::test_deleting_a_reference_of_a_shell_keeps_the_submodel_for_f_edt_03_criterion_6`: the reference goes from the tab of the shell, both Submodels stay, and nothing is asked. |
| 7 | T | `test_shell_and_submodel_criteria.py::test_deleting_a_submodel_also_removes_the_references_of_every_shell`: the Submodel is asked about once (its usages), the references of both shells go with it, and one undo gives all of it back. `test_delete.py::test_deleting_a_submodel_removes_the_reference_of_the_shell`. |
| 8 | T | `test_shell_and_submodel_criteria.py::test_deleting_a_free_submodel_removes_it_from_the_package`, with one undo step. |
| 9 | T | `test_shell_and_submodel_criteria.py::test_a_reference_to_no_submodel_can_be_edited` (through its dialog, one undo step) and `::test_a_reference_to_no_submodel_can_be_removed_and_is_not_written`. `test_paste_into_shell_action.py::test_a_reference_to_nothing_is_pasted_and_reported_as_dangling`. |
| 10 | T | `test_concept_actions.py::TestCreateFromAll`, on the Submodel row: Cancel changes nothing (`::test_cancel_changes_nothing`), and Yes is one undo step that makes the descriptions with an IEC 61360 record whose preferred name is the idShort in `en` (`::test_with_records_the_names_come_from_the_idshort`). |
| 11 | T | `test_create_flows.py::TestRemoveAttributes::test_all_qualifiers_go_in_one_step_and_the_question_names_them`: the Submodel and every descendant have no qualifier, in the model and in the reloaded file, and extensions stay (`::test_extensions_stay_when_only_qualifiers_are_chosen`). |
| 12 | T | `test_shell_and_submodel_criteria.py::test_renaming_a_submodel_updates_the_shell_and_the_semantic_references`: the reference of the shell and a semantic id that holds the old id follow, in one undo step. `test_rename.py::test_rename_updates_semantic_ids_of_a_concept_description`. |
| 13 | O | The plan's row "Stubs and Fetch": a dynamic environment exists only after a fetch, and the editor edits local files. There is no such environment to make the id read-only (searched: no code for it), and Rename is offered for every shell, submodel and concept description. |
| 14 | O | Plan: "Stubs and Fetch". |
| 15 | D | The tab of a submodel shows the description that its semantic id names, read-only and collapsed, and the notice of the original when it names none ([ADR 0021](adr/0021-order-of-the-file-and-concept-description-gaps.md)): `test_embedded_concept.py::TestPanel::test_a_submodel_shows_its_description_too`, `::test_a_semantic_id_that_names_nothing_shows_the_notice`. The original's display is an editor. |
| 16 | N | Scripting. |

## F-EDT-04 SubmodelElements

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_element_criteria.py`, one test for each group of types, with only what the form needs filled in: Property and Range are `xs:string`, a File and a Blob have no content type and no value, a list is order-relevant, an event is an input that is off, an entity is self-managed, the others are empty, and the new element is the current row. The table asks for a content type of `""`, which V3.1 and the SDK refuse (a content type has at least one character), so it is missing. A ReferenceElement has no value, because the SDK cannot hold a reference without a key. `test_element_types.py::test_element_is_made_edited_undone_saved_and_read_again` for the filled cases. |
| 2 | T | `test_user_defaults.py::TestDefaultLanguages::test_a_new_multi_language_property_has_an_empty_row_for_each_language` (`en,de` gives two rows, and the texts become the value). A row that stays empty is left out and no text gives no value, because the SDK refuses an empty text (`::test_a_row_without_text_is_left_out`, `::test_no_text_at_all_means_no_value`). `test_default_languages.py` for the setting. |
| 3 | T | `test_element_criteria.py::test_a_property_that_becomes_a_range_keeps_its_type_and_common_attributes`: min and max are the value, the value type stays, and the idShort, category, description, display name, semantic id, qualifier and extension are the same, in the saved file too. `test_conversion.py::test_a_property_becomes_a_range_with_its_value_as_minimum_and_maximum`. |
| 4 | T | `test_element_conversion.py::test_a_file_becomes_a_blob_with_the_content_of_the_stored_file`, `::..._with_its_path_when_the_content_is_declined`. |
| 5 | D | [ADR 0012](adr/0012-replacing-an-element-shows-what-is-lost.md): items that do not fit are named, and the idShorts of list items are not written. `test_conversion.py::test_a_collection_becomes_a_list_that_keeps_the_items_that_fit`. |
| 6 | T | `test_conversion.py::test_an_operation_keeps_every_variable_when_it_becomes_a_collection`. |
| 7 | T | `tests/large/test_typed_values_flow.py`. Large, so not in CI. |
| 8 | T | `test_element_edit_criteria.py::test_a_range_refuses_a_text_that_is_no_number_and_keeps_its_limits`: the cell refuses `abc` for an `xs:int` range with a message and no trace, and the limits and the history are unchanged. `test_value_editor.py::TestValueEdit::test_refuses_to_give_a_value_when_the_text_is_wrong`. |
| 9 | T | `test_blob_actions.py::test_base64_text_becomes_the_bytes_in_one_undoable_step` (`SGVsbG8=` gives the bytes of `Hello` in the domain test), `::test_text_that_is_no_base64_is_refused_with_a_reason` (unchanged, with the character that is wrong; the original logs). No question first: undo replaces it (ADR 0019). |
| 10 | D | The Blob editor shows hex when the content is no text (`test_value_editor.py::TestBinaryEdit`). No question before editing. |
| 11 | D | The add dialog of a list offers only its type, so there is nothing to warn about (changelog). |
| 12 | D | The SDK refuses or drops the item, and the editor says so (ADR 0012). |
| 13 | T | `test_list_item_index.py` (three tests: shown, read-only, follows a move). |
| 14 | D | The most common semantic id of the items, not the first child (ADR 0012). |
| 15 | O | Plan: "Emit event". |
| 16 | T | `test_element_types.py` for BasicEventElement, and `::test_form_and_attributes_have_every_attribute_of_the_class`. |
| 17 | T | `test_entity_form.py::test_a_new_entity_is_self_managed_and_asks_for_the_global_asset_id`: the type is preset, the form says "Please choose the global identifier for the SelfManagedEntity" until the field has text. `test_validation_hints.py::test_a_self_managed_entity_without_a_global_asset_id_gets_a_notice` for the same notice in the bar of a tab. |
| 18 | T | `test_element_types.py::test_a_variable_goes_into_the_list_it_was_added_under_only`, for the input, output and in/out lists: the variable is in that list only, one undo step, saved and reloaded. The Operation case of `test_element_types.py` adds to the input and the output list. The three lists share one namespace, so a name used in one is refused in another (AASd-022). |
| 19 | T | `test_element_edit_criteria.py::test_a_cut_element_pasted_into_the_input_variables_leaves_its_source`: cut from a collection, Paste into the input variables of an Operation: the source is empty, the variable is in the input list only, and two undo steps give the start back. |
| 20 | D | An element has an idShort. Items of a list do not, and the case is not covered (ADR 0014). |
| 21 | O | Plan: ECLASS. |
| 22 | T | `test_element_edit_criteria.py::test_a_list_without_order_relevant_in_the_file_shows_the_default`: a JSON file without `orderRelevant` shows `True` in the tab. For a new list, `test_element_types.py` (the form shows it ticked). |

## F-EDT-05 ConceptDescription and IEC 61360

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_attribute_criteria.py::test_add_on_the_node_makes_a_description_with_a_generated_id`: Add on the node makes a description with a `urn:uuid:` id, it is the current row, the id is in the saved file, and one undo gives the package back. |
| 2 | D | The SDK refuses an empty preferred name. The dialog starts with a row filled with the idShort (ADR 0014). |
| 3 | D | A record is made with its content in one step, so the defect of the original cannot occur (ADR 0014). `test_concept_actions.py::test_adding_a_record_with_the_template_key`. |
| 4 | T | `test_concept_records.py::TestDataType::test_a_chosen_data_type_is_stored_as_the_literal`, `::test_choosing_none_removes_the_data_type` (undo, redo, save and read again). |
| 5 | T | `test_concept_dialogs.py::TestIec61360Dialog::test_a_short_name_over_18_characters_shows_why_and_blocks`. |
| 6 | T | `test_concept_actions.py::test_empty_attributes_are_removed_in_one_step`. |
| 7 | T | `test_concept_records.py::TestValueList::test_removing_the_only_pair_leaves_no_value_list`, `::test_remove_value_list_takes_every_pair_away`. Done in the record dialog (Remove pair, Remove value list), not in a menu of the pair. |
| 8 | T | `test_value_list_text.py::TestLines`, `test_concept_actions.py::test_the_clipboard_is_imported_after_the_preview`. A line without a value id is reported, not silently skipped. |
| 9 | T | `test_concept_actions.py::test_each_pair_with_an_id_becomes_a_description`, `test_concepts.py::test_a_pair_becomes_a_description_with_an_iec_record`. |
| 10 | D | All six orders (and the name) are offered, and the tree lists the descriptions as each says without changing the package ([ADR 0021](adr/0021-order-of-the-file-and-concept-description-gaps.md)): `test_concept_orders.py::TestOrders`, `test_concept_order.py`. The three new ones order the one list. They do not make the branches or the nesting under the elements that the original's tree shows. |
| 11 | T | The store keeps the order of the file now (ADR 0021). `test_concept_orders.py::TestSort::test_sorting_by_id_short_writes_the_order_and_goes_back_to_the_list_index` (the file, the view, and a save), `::test_one_undo_gives_the_old_order_of_the_file_back`. The question has an undo instead of "cannot be reverted". |
| 12 | T | `test_concept_orders.py::TestSort::test_an_order_that_cannot_sort_gives_the_message_and_changes_nothing`, for list index, by elements and structured. |
| 13 | O | Plan: moving concept descriptions. The store keeps an order now, so it could be built. |
| 14 | D | The tab of an element shows its description, read-only and collapsed, with no move panel because a tab has none (`test_embedded_concept.py::TestPanel`, `::TestInATab`). It is not hidden for "By SubmodelElements", because the descriptions are not nested in this tree and it would show them nowhere (ADR 0021). |
| 15 | D | Sync fills the short name, because the preferred name cannot be empty (changelog). |
| 16 | D | The SDK cannot hold a blank record: `test_blank_member_probes.py` (made, edited, and read from a file, also in failsafe mode). The preset adds the one record, which is the end state of the criterion: `test_preset_actions.py::test_a_data_specification_preset_gives_one_record_and_no_blank_one` (ADR 0021). |
| 17 | P | `test_preset_files.py::test_a_missing_shipped_file_is_reported`. Wording differs. WP18 left it: only the wording differs. |
| 18 | T | Both things the criterion asks for: `test_samm_panel.py::test_a_samm_description_lists_id_before_id_short`, `::test_a_samm_description_gets_no_such_hint`, and the recognition in `test_samm.py`. Editing SAMM elements is F-SMT-05, not F-EDT, and is not done (the extension is edited as an extension). |
| 19 | O | Plan: moving concept descriptions. |

## F-EDT-06 Common attribute modules

| AC | Class | Evidence |
|---|---|---|
| 1 | D | [ADR 0019](adr/0019-defaults-and-notices-of-new-objects.md). The notices for a missing or one-language display name and description are hint rules (`test_validation_hints.py::test_a_missing_display_name_and_description_are_notices`, `::test_texts_in_one_language_get_the_notice_for_several_languages`). "Create w/ default" starts the dialog with one row in the first default language, and the row waits for text, because the SDK refuses an empty entry (`test_user_defaults.py::TestDefaultLanguages::test_creating_a_display_name_starts_with_one_row_in_the_first_language`). |
| 2 | T | `test_ids.py::test_fix_replaces_blank_and_symbols_for_aas_criterion_2`. |
| 3 | T | `test_ids.py::test_fix_uses_prefix_and_digits_when_nothing_is_usable`. |
| 4 | T | `test_hints.py::test_inline_hint_says_why_an_id_short_is_wrong_while_typing`. The editor also fixes a leading digit, which the original does not. |
| 5 | T | `test_user_defaults.py::test_generate_in_the_rename_dialog_follows_the_template_and_renames`: Generate twice gives `urn:x:` and four digits, and the rename and its references follow. `test_id_templates.py` for the format (`D`, `X`, `A`, the backslash, random digits). The create dialogs and the generic forms use the templates too. |
| 6 | O | Plan: repositories. |
| 7 | T | `test_reference_picker_fields.py::TestFreeEntry::test_a_typed_external_reference_is_kept`. |
| 8 | T | `test_reference_picker_fields.py::TestFreeEntry::test_the_target_type_follows_the_last_key_type`. |
| 9 | T | `test_validation_hints.py::test_key_whitespace_is_a_warning_on_the_element_with_the_semantic_id`. |
| 10 | T | Same test as F-EDT-01 AC7: the last qualifier goes, the list is empty (the SDK has no null), and the file has no `qualifiers`. |
| 11 | T | `test_attribute_criteria.py::test_with_hints_off_no_hint_is_shown_and_the_fields_are_unchanged`: with hints off the bar is empty and hidden, every cell of the tab reads as before, and nothing changed in the package. `test_hints.py::test_inline_hint_is_off_when_hints_mode_is_off`. |
| 12 | T | `test_attribute_criteria.py::test_in_read_mode_a_tab_offers_no_action_that_changes_something` (every editing action and every registered action that changes a package is off), and no row for a null attribute (`test_framework_criteria.py::test_in_read_mode_an_attribute_without_a_value_has_no_row`). |
| 13 | P | `test_data_spec_operations.py::TestFixKeys`. The action has another name and no log line. WP18 left it: a name and a log line. |
| 14 | D | Same as F-EDT-05 AC16: no blank record can exist, and the preset adds the one record (`test_blank_member_probes.py`, `test_preset_actions.py::test_a_data_specification_preset_gives_one_record_and_no_blank_one`, ADR 0021). |
| 15 | T | `test_language_moves.py::test_move_down_changes_the_order_and_the_rows_follow` (rows are read again), `::test_the_move_is_one_undo_step_and_is_saved`, and `test_language_order.py` for the plan and the order in the file. |
| 16 | D | `test_category_row.py`: the category stays editable, with the deprecation hint (`test_validation_hints.py::test_category_is_an_info_hint_when_an_element_has_one`). The spec asks for read-only, but the rules AASc-3a-004 to 007 tie the category of a concept description to its data type, so a user must be able to change it, and the V3.1 metamodel still has it (ADR 0019). |

## F-EDT-07 Qualifiers and Extensions

| AC | Class | Evidence |
|---|---|---|
| 1 | D | The SDK cannot hold a blank qualifier (the type needs a character: `test_blank_member_probes.py`), so there is none to replace. The end state is asserted: one qualifier with type, value, kind and semantic id (`test_preset_actions.py::test_a_qualifier_preset_gives_one_qualifier_with_its_semantic_id`, `::test_a_qualifier_preset_is_added_to_every_selected_element`; ADR 0021). |
| 2 | D | A missing preset file is listed in the dialog and the dialog still opens (ADR 0017). |
| 3 | T | `test_preset_actions.py::test_a_qualifier_on_the_clipboard_is_added`. |
| 4 | T | Both ways in refuse bad text: `test_preset_actions.py::test_bad_clipboard_content_is_refused_with_a_message` (add from the clipboard) and `test_paste_qualifier_action.py::test_text_that_is_no_qualifier_changes_nothing_and_says_why` (paste into a qualifier). The element and the history are unchanged, and the user is told why. The message is a dialog, where the original logs. |
| 5 | T | `test_paste_qualifier_action.py::test_the_content_is_pasted_and_the_kind_stays` and `test_paste_qualifier.py::test_the_content_is_taken_over_and_the_kind_stays`: parity, the kind of the target stays (ADR 0019). A type another qualifier has is refused (AASd-021), and a text that is no qualifier changes nothing and says why (AC4 for this action). |
| 6 | T | `test_attribute_criteria.py::test_the_last_qualifier_cannot_move_down_and_the_list_stays` (the action is off, the file is unchanged, no history), `::test_a_qualifier_moves_up_in_one_undo_step_and_the_file_follows`. |
| 7 | O | Plan: "Upgrade qualifiers". |
| 8 | O | Plan: "Migrate to Extensions". |
| 9 | O | Plan: "SMT attribute records". |
| 10 | O | Same row. |
| 11 | D | A specific asset id without a value asks for it (ADR 0017). |
| 12 | T | `test_validation_hints.py::test_a_blank_name_of_an_extension_or_specific_asset_id_is_a_hint`, and `test_entity_form.py::test_a_blank_name_of_an_extension_shows_the_hint_in_its_form`. The dialog of a specific asset id refuses a blank name with `A specific asset id needs a name` (`test_create_flows.py::TestAssetIds::test_the_dialog_needs_a_name_and_a_value`). The SDK refuses a blank name, so no object has one. |
| 13 | O | Same row as 9. |

## F-EDT-08 Copy, paste, reorder

| AC | Class | Evidence |
|---|---|---|
| 1 | D | D13: `Name_1`, not `Name---XXXXXXXX`. `test_paste_actions.py::test_copy_then_paste_below_adds_a_numbered_duplicate_after_it`. |
| 2 | T | `test_paste_actions.py::test_cut_then_paste_above_keeps_the_name_and_removes_the_source`. |
| 3 | O | Plan: "Pending Cut"; D12. |
| 4 | T | `test_paste_actions.py::test_a_second_paste_gives_a_further_duplicate`. |
| 5 | D | [ADR 0020](adr/0020-selection-locations-and-clipboard.md): the buffer is a mirror of the system clipboard, and a newer copy wins. `test_paste_actions.py::test_json_that_is_newer_on_the_clipboard_replaces_the_buffer`. |
| 6 | T | `test_paste_criteria.py::test_json_with_the_name_of_a_sibling_is_added_with_a_numbered_name`: with the buffer cleared, JSON of `A` is added next to an existing `A` as `A_1`, the original keeps its value, and one undo takes the new one away. `test_paste_actions.py::test_json_from_another_program_pastes_after_the_buffer_is_cleared`. |
| 7 | P | `test_paste_actions.py::test_bad_clipboard_text_is_refused_with_a_message`. The text differs from the spec. WP18 left it: only the wording differs. |
| 8 | T | `test_paste_actions.py::TestPasteFromText` (an empty clipboard and buffer, a bad text, the places, a pending cut), `test_paste_into_shell_action.py::test_submodel_json_typed_into_the_box_is_added_to_the_shell`. A desktop never denies the clipboard, so the action does not read it. |
| 9 | T | `test_paste_criteria.py::test_copied_elements_paste_in_the_order_of_the_tree_not_of_the_clicks`: A, B and C selected as C, A, B paste as A, B, C. `test_paste_actions.py::test_several_copied_elements_paste_below_in_their_order`. The order of the clicks is not kept (ADR 0020, ADR 0023). |
| 10 | P | `test_paste.py::TestElements::test_a_submodel_cannot_be_pasted_among_elements`. The text is not asserted. WP18 left it: the criterion gives the text, and the editor says it in its own words on purpose. |
| 11 | P | `test_paste_into_shell_action.py::test_pasting_the_same_reference_again_is_skipped_and_said`. A dialog, where the original logs. WP18 left it: a dialog where the original logs. |
| 12 | T | `test_paste_into_shell.py::TestSubmodels::test_a_submodel_unknown_to_the_package_is_added_with_its_reference`. |
| 13 | D | D16: no move for concept descriptions, so there is no dialog. |
| 14 | T | `test_move.py::TestCanMove::test_up_is_not_possible_on_the_first_member`. |
| 15 | T | `test_reference_integrity.py::TestDelete::test_deleting_a_submodel_without_usages_asks_for_confirmation`, `::test_shift_skips_the_question_but_not_the_usages`. |
| 16 | O | Plan: "Copy from an auxiliary package". Copy between open packages is done and tested for one row and, since this audit, for several. |
| 17 | O | Same. |
| 18 | O | Same. |
| 19 | T | `test_paste_actions.py::test_annotations_can_be_pasted_above`. |
| 20 | T | `test_paste_actions.py::test_a_cut_from_a_list_pasted_into_a_collection_leaves_the_list_without_it`, with save, reload and undo. |

## F-EDT-09 Multi-element editing

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_selection_panel.py::test_two_siblings_give_the_header_and_the_actions_of_a_selection`, `::test_the_dock_opens_for_a_selection_until_the_user_closes_it`. A dock below the tree, not a replacement of the tabs ([ADR 0020](adr/0020-selection-locations-and-clipboard.md)). Seen offscreen only. |
| 2 | D | Actions are offered across parents, and each row moves in its own container (changelog). |
| 3 | T | `test_move.py::TestNewOrder::test_selected_rows_become_adjacent_as_in_package_explorer` (rows 2 and 4 of 6 end at 1 and 2), `test_move_actions.py::test_a_move_up_makes_rows_two_and_four_adjacent_at_one_and_two`. "In order of selection" is the order of the container, which Qt can give (ADR 0020). |
| 4 | T | `test_move.py::TestNewOrder::test_selected_rows_become_adjacent_as_in_package_explorer` (`UP` with the first selected row on top), `test_move_actions.py::test_a_move_up_does_nothing_when_the_first_selected_row_is_on_top`: nothing changes, and the action is off. |
| 5 | T | Same test, `TO_END`. |
| 6 | T | `test_bulk_criteria.py::test_declining_the_delete_of_several_referenced_objects_changes_nothing` and `::test_declining_the_question_for_several_submodels_changes_nothing` (No: the package is the same, no history), `::test_confirming_the_delete_of_several_rows_removes_all_of_them`, and `test_reference_integrity.py::TestDelete::test_deleting_several_referenced_objects_shows_one_dialog_and_one_step`. Across parents: `test_cross_parent_selection.py::test_delete_removes_the_rows_of_every_parent_in_one_undo_step`. |
| 7 | P | `test_paste_actions.py::test_copying_several_elements_puts_their_json_on_the_clipboard`, added by this audit. The log line is not written. WP18 left it: the log line. |
| 8 | D | A new pattern language ([ADR 0017](adr/0017-presets-and-the-pattern-language.md)). `ABC_*` is `ABC_{old}`. |
| 9 | D | Same. |
| 10 | D | Same. |
| 11 | D | Same. `{old\|capitalize}`. |
| 12 | D | Same. |
| 13 | D | Same. |
| 14 | D | Same. |
| 15 | T | `test_bulk_edit.py::TestTexts::test_an_element_without_the_language_is_skipped_and_the_rest_change`. |
| 16 | T | `test_bulk_actions.py::test_extensions_with_a_name_are_removed_in_one_step`. |
| 17 | P | `test_bulk_dialogs.py::test_without_extensions_the_removal_has_nothing_to_choose`. No log text. WP18 left it: the log text. |
| 18 | T | `test_package_files_ui.py::test_several_files_are_removed_as_one_step_with_one_question`, `::test_the_panel_removes_several_selected_files_at_once`, and `test_stored_file_delete.py::test_several_stored_files_are_deleted_in_one_step_with_one_question` for the tree. Removed at once, and not marked pending. |
| 19 | T | `test_move_actions.py::test_variables_of_mixed_directions_get_neither_move_nor_delete`, `tests/small/test_selection.py::TestVariableDirections`. Cut and Copy stay. |
| 20 | N | Touch. |
| 21 | T | `test_bulk_criteria.py::test_a_bulk_action_flags_the_package_until_it_is_undone`: move, delete, cut, change attribute and remove extensions each make `package.changed` true, and undo makes it false again. `test_undo_views.py::test_window_is_modified_after_an_edit_and_clean_after_undo`. |

## F-EDT-10 Supplementary files

| AC | Class | Evidence |
|---|---|---|
| 1 | D | A dock panel, not a node. In Read mode its buttons are off (`tests/large/test_package_files_flow.py`, D18). |
| 2 | D | The folder is `/aasx/files` (D15), and a file is in the package at once, undone with Undo, so there is no `(add pending)` leaf and no `⭠ source`: the stored files are a dock panel (D18). The name `a b.pdf` becomes `a_b.pdf` and the media type is guessed: `test_package_files_ui.py::test_adding_a_file_sanitizes_the_name_and_guesses_the_media_type`. The changelog says so. |
| 3 | T | `test_file_criteria.py::test_a_file_that_was_added_and_removed_before_a_save_is_not_written`: the file is not in the store, and neither the part nor a relationship is in the saved package. |
| 4 | T | `test_file_criteria.py::test_a_removed_file_is_gone_from_the_saved_package_with_its_relationship`: before the delete the part and its relationship are in the zip, after it neither is, the other files stay, and the File element no longer has the path. `test_supplementary_files_roundtrip.py::test_removing_a_file_and_its_paths`. A stored file that no File element refers to is not written by the SDK at all. |
| 5 | T | `test_package_files_ui.py::test_the_package_thumbnail_is_changed_saved_and_read_back` (root of the package, saved, read back, undo), `::test_a_changed_package_thumbnail_survives_a_crash`, `tests/small/test_package_thumbnail.py`. No leaf with `[Thumbnail]`: the panel names the thumbnail (D18). |
| 6 | T | `test_package_files_ui.py::test_choosing_a_file_for_a_file_element_keeps_its_media_type`. |
| 7 | T | `test_package_files_ui.py::test_adding_a_file_for_a_file_element_sets_value_and_media_type`. |
| 8 | D | The media type is guessed, and `application/octet-stream` when unknown (changelog). Checked above. |
| 9 | T | `test_package_files_ui.py::test_creating_a_text_file_with_a_taken_name_warns_and_changes_nothing`. |
| 10 | T | `test_supplementary_files.py::test_editing_a_text_file_keeps_non_ascii_text_and_line_breaks`, `test_supplementary_files_roundtrip.py::test_editing_a_text_file_keeps_utf8_text`. |
| 11 | T | `test_package_files_ui.py::test_removing_a_file_asks_about_its_references`. |
| 12 | O | Plan: "Centralize file", a repository feature that writes to a remote store at once ([ADR 0020](adr/0020-selection-locations-and-clipboard.md)). "Move file to folder" is the local counterpart. |
| 13 | T | `test_blob_actions.py::test_loading_a_file_sets_the_bytes_in_one_undoable_step`. |
| 14 | T | `test_blob_content.py::test_decode_base64_spells_the_bytes_of_the_text` (`SGVsbG8=` gives `Hello`) and `test_blob_actions.py::test_base64_text_becomes_the_bytes_in_one_undoable_step`. |
| 15 | T | The size label is shown (`test_value_editor.py::TestBinaryEdit::test_shows_content_that_is_no_text_as_hex`: "9 bytes, binary"), and "Blob: Bytes to Base64 text" is offered for every Blob with content (`test_blob_actions.py::test_bytes_become_base64_text_in_one_undoable_step`, `::test_the_conversion_there_and_back_gives_the_bytes_again`). |
| 16 | T | `test_element_conversion.py::test_a_file_becomes_a_blob_with_the_content_of_the_stored_file`. |
| 17 | N | Browser. |
| 18 | N | Browser. |

## F-EDT-11 References, semantics, lookups

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_reference_picker_packages.py::TestDialog::test_both_packages_are_listed_with_the_package_of_each`, `::test_the_picker_of_a_form_offers_the_description_of_the_other_package` (through the form of a semantic id), `test_reference_picker_sources.py`. The semantic id of a submodel or element starts on the filter "Concept descriptions", as the original does. |
| 2 | T | `test_reference_picker_fields.py::TestPickingATarget::test_a_concept_description_gives_an_external_reference_to_its_id`. |
| 3 | T | `test_reference_picker_fields.py::test_the_model_kind_keeps_the_concept_description_key_type`. |
| 4 | D | The picker lists only the targets that fit the field (`test_reference_picker.py::TestCandidates`, `::test_filters_for_submodel_reference_offer_submodels_only`), so there is no row to select that does not fit, and a wrong typed reference blocks OK with the reason (`test_reference_picker_fields.py::TestRefusals::test_an_sdk_refusal_is_shown_as_a_reason_and_blocks_ok`). A row that gives no reference, such as a detached element, disables OK (`ReferencePickerDialog._update_preview`). |
| 5 | D | A reference cannot point at a stored file, because V3.1 has no key type for one (`test_file_choice_dialog.py::test_no_key_type_of_v31_names_a_stored_file`), so the file filter is the chooser of the File element: it lists the stored files only and gives the name that becomes the value (`test_file_choice_dialog.py`, `test_package_files_ui.py::test_choosing_a_file_for_a_file_element_keeps_its_media_type`; ADR 0021). |
| 6 | O | Plan: "Add from pool of known concepts". |
| 7 | T | `test_picker_criteria.py::test_picking_for_a_supplemental_semantic_id_appends_a_reference`: the picked description is a new GlobalReference key in a new reference after the one that was there, the semantic id is unchanged, and one undo gives the start back. **Defect found, fixed**: undo of this edit left the new reference in (`tests/small/test_edits.py::test_set_attribute_restores_a_list_that_the_sdk_replaces_in_place`). |
| 8 | O | Plan: ECLASS. |
| 9 | O | Same. |
| 10 | O | Same. |
| 11 | O | Same. |
| 12 | O | Same. |
| 13 | O | Same. |
| 14 | O | Same. |
| 15 | T | `test_concept_create_empty.py` (a `urn:uuid:` id and nothing else, selected, one undo step, saved; the semantic id of an element is the same object afterwards). |
| 16 | T | `test_concept_actions.py::TestCreateFromSemanticId::test_an_element_without_semantic_id_says_why_nothing_is_created`. The text is `Cannot create a concept description because no valid semantic id is present in ...`. |
| 17 | T | `test_concepts.py::TestNewConcept::test_the_id_is_the_first_key_and_the_names_come_from_the_element`. |
| 18 | O | Part of ECLASS import. |
| 19 | D | Jump works in the tabs, where references are shown, not in the tree (changelog). `test_reference_jump.py`. |
| 20 | T | `test_reference_jump.py::test_a_reference_that_resolves_in_part_opens_the_closest_object`. |
| 21 | T | `test_reference_jump.py::test_a_reference_to_an_unknown_id_says_the_target_is_missing`. |
| 22 | O | ECLASS actions do not exist, so none is shown. |
