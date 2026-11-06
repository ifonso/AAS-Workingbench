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
| F-EDT-01 Editor framework | 2 | 4 | 5 | 0 | 1 | 2 | 1 | 15 |
| F-EDT-02 Environment, AAS, AssetInformation | 1 | 4 | 4 | 1 | 7 | 0 | 0 | 17 |
| F-EDT-03 Submodel and SubmodelRef | 1 | 8 | 3 | 0 | 3 | 0 | 1 | 16 |
| F-EDT-04 SubmodelElements | 9 | 4 | 1 | 6 | 2 | 0 | 0 | 22 |
| F-EDT-05 ConceptDescription and IEC 61360 | 4 | 3 | 1 | 5 | 4 | 2 | 0 | 19 |
| F-EDT-06 Common attribute modules | 9 | 4 | 0 | 1 | 2 | 0 | 0 | 16 |
| F-EDT-07 Qualifiers and Extensions | 3 | 3 | 0 | 2 | 5 | 0 | 0 | 13 |
| F-EDT-08 Copy, paste, reorder | 6 | 6 | 0 | 2 | 5 | 1 | 0 | 20 |
| F-EDT-09 Multi-element editing | 3 | 6 | 0 | 8 | 0 | 3 | 1 | 21 |
| F-EDT-10 Supplementary files | 9 | 3 | 0 | 2 | 2 | 0 | 2 | 18 |
| F-EDT-11 References, semantics, lookups | 5 | 3 | 0 | 1 | 11 | 2 | 0 | 22 |
| **All** | **39** | **52** | **14** | **26** | **41** | **22** | **5** | **199** |

Of 199 criteria, 39 have a test that asserts them, and 52 more are tested in part.
The 22 gaps are in [What remains after v1](../planning/v1-editor-plan.md#what-remains-after-v1), ranked by what they cost a user.
Most O rows are ECLASS (F-EDT-04 AC21, F-EDT-11 AC8 to AC14, AC18 and AC22) and repository features, which the plan keeps out of v1. Nine rest only on a "Known limit" of the changelog, and not on a row of the plan's table: F-EDT-03 AC15, F-EDT-05 AC14 and AC16, F-EDT-06 AC1 and AC14, F-EDT-08 AC5, F-EDT-10 AC5 and AC12, and F-EDT-11 AC1.

## What this audit checked itself

Ten claims looked doubtful, and were checked in the code or by running it.

| Claim | Result |
|---|---|
| F-EDT-09 AC7 says that copying several rows is done. | The clipboard got the display names of the rows, one per line, and the buffer did not know its package, so a paste into another package skipped the concept descriptions and the files. **Defect, fixed** with two tests that failed first (`fix(editor): copy several rows as JSON and remember their package`). AC7 is `P`: the JSON array is there, the log line of the original is not. |
| F-EDT-08 AC9 and F-EDT-08 "copying between packages brings concept descriptions". | True for one row, false for several, for the same reason. Fixed together with the above. |
| F-EDT-01 AC7: deleting the last entry makes the list attribute absent. | Two tests assert that the list stays, empty. The file does not show it: serialized, an emptied `qualifier` is not written (probe). `P`. |
| F-EDT-09 AC3 and AC4: Move up on rows 2 and 4 of 6. | The code moves each selected row one place, to 1 and 3. The original makes them adjacent, at 1 and 2, and does nothing when the first selected row is at the top, while the code moves the others. Not recorded anywhere as a decision. `P`. |
| F-EDT-10 AC8: a `.zip` gets `text/plain` for parity. | The code guesses from the extension, and gives `application/x-zip-compressed` on this machine, the registry of Windows, and `application/octet-stream` for an unknown one. The test asserts only "not text/plain". `D`, and the answer depends on the platform. |
| F-EDT-04 AC22: a null `orderRelevant` is shown as the default (true). | The SDK has a bool that is true by default, and a file without `orderRelevant` reads as true (probe). The case cannot occur. `P`, because the tests assert the default only for a new list. |
| F-EDT-04 AC9 and F-EDT-10 AC14, AC15: Base64 to binary and back for a Blob. | No code. The editor shows the bytes as text or hex. A gap. **Closed by WP14**: two actions of the Blob, `T`. |
| F-EDT-01 AC10, AC11: push and pop of an editing location. | No code. Back after Jump to target, and Back in the tabs, are the nearest thing. A gap. |
| F-EDT-05 AC10: the view orders of concept descriptions. | Four of six: name, idShort, id, first use. "List index", "By SubmodelElements" and the structured order are not offered. A gap. |
| F-EDT-04 AC2: new MultiLanguageProperty has a row for each default language. | No setting of default languages. A gap. **Closed by WP14**: a setting, `T`. |

## F-EDT-01 Editor framework

| AC | Class | Evidence |
|---|---|---|
| 1 | P | `test_hints.py::test_read_mode_shows_no_row_for_a_null_attribute`, and the same in `tests/large/test_validation_flow.py`. No test that no editing control is on screen. |
| 2 | I | `models/table_standard.py` `setData`. No test types into a field and checks when the model changes. |
| 3 | T | `test_change_markers.py::test_the_tree_marks_the_element_and_the_objects_above_it`, `::test_a_save_clears_the_marker_in_the_tree_and_in_every_tab`. |
| 4 | P | `test_hints.py::test_bar_lists_the_hints_of_the_shown_object`. That editing and saving stay possible is not asserted. |
| 5 | T | `test_hints.py::test_bar_is_off_when_hints_mode_is_off`. |
| 6 | I | `widgets/groupBoxes.py` (the Create button of an optional attribute). No test of the default and the redraw. |
| 7 | P | Empty list stays in the object and is not written (see above). |
| 8 | I | `ui/delete_flow.py`. The question is tested for a delete of objects with usages, and focus moving to the previous sibling is not. |
| 9 | O | Plan: "Moving AAS, Submodels, concept descriptions, or SubmodelRefs"; D16. |
| 10 | G | No push of a location. |
| 11 | G | No pop of a location. |
| 12 | N | Scripting. |
| 13 | I | Shortcuts in `settings/shortcuts.py` and the actions. Only the Delete key in Read mode has a test. |
| 14 | P | `test_validation_hints.py::test_tolerant_validate_reports_a_warning_when_a_rule_raises`. The severity is Warning, not High, and there is no test in a panel. |
| 15 | I | No test that a redraw keeps hints, sort order and the other flags. |

## F-EDT-02 Environment, AAS, AssetInformation

| AC | Class | Evidence |
|---|---|---|
| 1 | D | [ADR 0019](adr/0019-defaults-and-notices-of-new-objects.md): a new AAS is an Instance, where the original makes NotApplicable (its own notice says Instance is usual). `test_create_flows.py::TestCreateShell::test_the_action_makes_a_shell_with_valid_asset_information`: kind Instance, the new row is selected, `urn:uuid:` id, valid AssetInformation, reload, undo. `test_asset_kind.py::test_a_new_shell_is_an_instance_unless_the_user_chooses_another`. |
| 2 | P | `test_create_flows.py::test_template_kind_and_no_shell_make_a_free_submodel`. |
| 3 | I | Copy actions are in the context menu of every object. No test that they are absent on the environment. |
| 4 | I | A pasted shell gets a new id (D13). Copy recursively with new Submodel ids is not a separate action. |
| 5 | O | Plan: "Copy from an auxiliary package". |
| 6 | I | Deleting a shell leaves its Submodels. No test of the declined question. |
| 7 | O | Plan: "Stubs and Fetch, and repository delete". |
| 8 | P | `test_rename.py::test_rename_updates_the_references_of_the_shell`. The failure warning is not tested. |
| 9 | P | `test_hints.py::test_inline_hint_says_that_the_global_asset_id_is_empty`, a hint in the create dialog. The advisory in a panel, and the duplicate, are rules with tests in `test_validation_hints.py`, not in a panel. |
| 10 | P | `test_create_flows.py::test_every_asset_kind_of_v3_1_is_offered`. The serialized output is not compared. |
| 11 | O | The plan's row "Metamodel V3.2": `Batch` is a literal of V3.2 and the SDK has no such kind (probe). A file with it is refused as a whole, and failsafe mode leaves the shell out (`test_asset_kind.py::test_a_file_with_batch_is_refused_as_a_whole`, `::test_in_failsafe_mode_the_shell_with_batch_is_left_out_and_the_package_partial`). The four kinds of V3.1 are read and written as they are (`::test_each_kind_of_v3_1_is_read_and_written_as_it_is`). |
| 12 | O | Plan: "Print code sheet". |
| 13 | T | `test_specific_asset_id_delete.py::test_the_last_specific_asset_id_goes_and_the_file_has_no_list`: the model has an empty list, which the SDK has no null for, and the file has none. `::test_the_last_asset_id_of_a_shell_without_a_global_one_is_kept` for AASd-131. One undo step: `::test_the_removal_is_one_undo_step`. |
| 14 | I | `test_package_files_ui.py` links and chooses a thumbnail. Deleting it and the create button are not tested. |
| 15 | O | Plan: "Stubs and Fetch". |
| 16 | O | Plan: "Stubs and Fetch". |
| 17 | O | Plan: "Finalize AAS". |

## F-EDT-03 Submodel and SubmodelRef

| AC | Class | Evidence |
|---|---|---|
| 1 | T | `test_create_flows.py::TestCreateSubmodel::test_with_a_shell_the_submodel_and_its_reference_are_one_step`: kind Instance, the new row is selected (focus), one reference with the Submodel, one undo step. |
| 2 | P | `test_create_flows.py::test_template_kind_and_no_shell_make_a_free_submodel`. The id pattern of templates is not asserted. |
| 3 | P | `test_paste_into_shell_action.py::test_a_pasted_reference_is_added_and_the_submodel_stays_shared`. |
| 4 | P | `test_paste_into_shell_action.py::test_a_copied_submodel_is_added_with_a_new_id_and_a_reference`. |
| 5 | I | `application/operations/companions.py`, no test of the shallow copy. |
| 6 | I | `ui/delete_flow.py`, no test of the second question declined. |
| 7 | P | `test_delete.py::test_deleting_a_submodel_removes_the_reference_of_the_shell`. |
| 8 | P | `test_delete.py::test_delete_removes_the_target_and_the_references`. |
| 9 | P | `test_paste_into_shell_action.py::test_a_reference_to_nothing_is_pasted_and_reported_as_dangling`. Editing and removing it are not tested. |
| 10 | I | `application/operations/concepts.py`. The record with the preferred name from the idShort is tested in `test_concept_actions.py`, but not through the Submodel with a cancel. |
| 11 | P | `test_create_flows.py::test_all_qualifiers_go_in_one_step_and_the_question_names_them`. |
| 12 | P | `test_rename.py::test_rename_updates_semantic_ids_of_a_concept_description`. |
| 13 | O | The plan's row "Stubs and Fetch": a dynamic environment exists only after a fetch, and the editor edits local files. There is no such environment to make the id read-only (searched: no code for it), and Rename is offered for every shell, submodel and concept description. |
| 14 | O | Plan: "Stubs and Fetch". |
| 15 | O | Limit: the embedded display of a description is not done. |
| 16 | N | Scripting. |

## F-EDT-04 SubmodelElements

| AC | Class | Evidence |
|---|---|---|
| 1 | P | `test_element_types.py::test_element_is_made_edited_undone_saved_and_read_again` for all 14 types. The defaults of the table are not asserted, because each case fills every field. |
| 2 | T | `test_user_defaults.py::TestDefaultLanguages::test_a_new_multi_language_property_has_an_empty_row_for_each_language` (`en,de` gives two rows, and the texts become the value). A row that stays empty is left out and no text gives no value, because the SDK refuses an empty text (`::test_a_row_without_text_is_left_out`, `::test_no_text_at_all_means_no_value`). `test_default_languages.py` for the setting. |
| 3 | P | `test_conversion.py::test_a_property_becomes_a_range_with_its_value_as_minimum_and_maximum`. What a Property keeps is tested for another target. |
| 4 | T | `test_element_conversion.py::test_a_file_becomes_a_blob_with_the_content_of_the_stored_file`, `::..._with_its_path_when_the_content_is_declined`. |
| 5 | D | [ADR 0012](adr/0012-replacing-an-element-shows-what-is-lost.md): items that do not fit are named, and the idShorts of list items are not written. `test_conversion.py::test_a_collection_becomes_a_list_that_keeps_the_items_that_fit`. |
| 6 | T | `test_conversion.py::test_an_operation_keeps_every_variable_when_it_becomes_a_collection`. |
| 7 | T | `tests/large/test_typed_values_flow.py`. Large, so not in CI. |
| 8 | P | `test_value_editor.py::TestValueEdit::test_refuses_to_give_a_value_when_the_text_is_wrong`. |
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
| 19 | I | Generic paste (`test_paste_actions.py`). No test with an Operation as parent. |
| 20 | D | An element has an idShort. Items of a list do not, and the case is not covered (ADR 0014). |
| 21 | O | Plan: ECLASS. |
| 22 | P | The SDK has a bool that is true by default, and reads true for a file without it. The tests assert the default for new lists only. |

## F-EDT-05 ConceptDescription and IEC 61360

| AC | Class | Evidence |
|---|---|---|
| 1 | I | "Add concept description" on the node, with a generated id. Tested through Create from semantic id, not the node. |
| 2 | D | The SDK refuses an empty preferred name. The dialog starts with a row filled with the idShort (ADR 0014). |
| 3 | D | A record is made with its content in one step, so the defect of the original cannot occur (ADR 0014). `test_concept_actions.py::test_adding_a_record_with_the_template_key`. |
| 4 | P | Stored data type tested. Delete through "(none)" is not. |
| 5 | T | `test_concept_dialogs.py::TestIec61360Dialog::test_a_short_name_over_18_characters_shows_why_and_blocks`. |
| 6 | T | `test_concept_actions.py::test_empty_attributes_are_removed_in_one_step`. |
| 7 | G | The dialog cannot delete a value list as a whole. |
| 8 | T | `test_value_list_text.py::TestLines`, `test_concept_actions.py::test_the_clipboard_is_imported_after_the_preview`. A line without a value id is reported, not silently skipped. |
| 9 | T | `test_concept_actions.py::test_each_pair_with_an_id_becomes_a_description`, `test_concepts.py::test_a_pair_becomes_a_description_with_an_iec_record`. |
| 10 | P | Four orders, with tests. Three of the six are missing (see above). |
| 11 | D | The order is a view only, D16. |
| 12 | D | Same. "By SubmodelElements" is not offered. |
| 13 | O | Plan: moving concept descriptions. |
| 14 | O | Limit: the embedded display in the panel of an element. |
| 15 | D | Sync fills the short name, because the preferred name cannot be empty (changelog). |
| 16 | O | Limit: a preset adds, and does not replace a blank record. |
| 17 | P | `test_preset_files.py::test_a_missing_shipped_file_is_reported`. Wording differs. |
| 18 | G | No SAMM. |
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
| 10 | P | Removing all qualifiers is tested. Deleting the only qualifier row is not, and the list stays empty (see F-EDT-01 AC7). |
| 11 | P | `test_hints.py::test_inline_hint_is_off_when_hints_mode_is_off`. "Fields unchanged" is not asserted. |
| 12 | P | `test_hints.py::test_read_mode_shows_no_row_for_a_null_attribute`. No test that no action button is on screen. |
| 13 | P | `test_data_spec_operations.py::TestFixKeys`. The action has another name and no log line. |
| 14 | O | Limit: a preset never replaces a blank record. |
| 15 | T | `test_language_moves.py::test_move_down_changes_the_order_and_the_rows_follow` (rows are read again), `::test_the_move_is_one_undo_step_and_is_saved`, and `test_language_order.py` for the plan and the order in the file. |
| 16 | T | `test_category_row.py`: a category with content is a row that cannot be edited and gives a reason when typed over, an element without one has no row in Edit or Read mode, Delete removes it in one undo step, and the package tree column refuses it too. The hint is `test_validation_hints.py::test_category_is_an_info_hint_when_an_element_has_one`. The dialog of a new element still has the field (ADR 0019). |

## F-EDT-07 Qualifiers and Extensions

| AC | Class | Evidence |
|---|---|---|
| 1 | P | `test_preset_actions.py::test_a_qualifier_preset_is_added_to_every_selected_element`: type, value, kind. The blank qualifier is not replaced (limit). |
| 2 | D | A missing preset file is listed in the dialog and the dialog still opens (ADR 0017). |
| 3 | T | `test_preset_actions.py::test_a_qualifier_on_the_clipboard_is_added`. |
| 4 | P | `test_preset_actions.py::test_bad_clipboard_content_is_refused_with_a_message`. Only "add from clipboard" exists, not "paste". |
| 5 | T | `test_paste_qualifier_action.py::test_the_content_is_pasted_and_the_kind_stays` and `test_paste_qualifier.py::test_the_content_is_taken_over_and_the_kind_stays`: parity, the kind of the target stays (ADR 0019). A type another qualifier has is refused (AASd-021), and a text that is no qualifier changes nothing and says why (AC4 for this action). |
| 6 | P | Move of elements is tested. No test moves a qualifier or an extension, although the changelog says they move. |
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
| 5 | O | Limit: the buffer and the system clipboard are one. |
| 6 | P | `test_paste_actions.py::test_json_from_another_program_pastes_after_the_buffer_is_cleared`. No idShort collision. |
| 7 | P | `test_paste_actions.py::test_bad_clipboard_text_is_refused_with_a_message`. The text differs from the spec. |
| 8 | G | No fallback text input when the clipboard is denied. |
| 9 | P | `test_paste_actions.py::test_several_copied_elements_paste_below_in_their_order`, in tree order. The order of selection is not tested. |
| 10 | P | `test_paste.py::TestElements::test_a_submodel_cannot_be_pasted_among_elements`. The text is not asserted. |
| 11 | P | `test_paste_into_shell_action.py::test_pasting_the_same_reference_again_is_skipped_and_said`. A dialog, where the original logs. |
| 12 | T | `test_paste_into_shell.py::TestSubmodels::test_a_submodel_unknown_to_the_package_is_added_with_its_reference`. |
| 13 | D | D16: no move for concept descriptions, so there is no dialog. |
| 14 | T | `test_move.py::TestCanMove::test_up_is_not_possible_on_the_first_member`. |
| 15 | T | `test_reference_integrity.py::TestDelete::test_deleting_a_submodel_without_usages_asks_for_confirmation`, `::test_shift_skips_the_question_but_not_the_usages`. |
| 16 | O | Plan: "Copy from an auxiliary package". Copy between open packages is done and tested for one row and, since this audit, for several. |
| 17 | O | Same. |
| 18 | O | Same. |
| 19 | T | `test_paste_actions.py::test_annotations_can_be_pasted_above`. |
| 20 | P | Removal and undo of a cut from a list are tested. The paste elsewhere is not in the same test. |

## F-EDT-09 Multi-element editing

| AC | Class | Evidence |
|---|---|---|
| 1 | G | No panel for the selection. The actions are in the context menu. |
| 2 | D | Actions are offered across parents, and each row moves in its own container (changelog). |
| 3 | P | `test_move.py::TestNewOrder::test_the_selection_moves_as_a_block_where_it_can`. The result differs from the spec (see above). |
| 4 | P | Same test, one row at the top. |
| 5 | T | Same test, `TO_END`. |
| 6 | P | `test_reference_integrity.py::test_deleting_several_referenced_objects_shows_one_dialog_and_one_step`. No "No" on several rows. |
| 7 | P | `test_paste_actions.py::test_copying_several_elements_puts_their_json_on_the_clipboard`, added by this audit. The log line is not written. |
| 8 | D | A new pattern language ([ADR 0017](adr/0017-presets-and-the-pattern-language.md)). `ABC_*` is `ABC_{old}`. |
| 9 | D | Same. |
| 10 | D | Same. |
| 11 | D | Same. `{old\|capitalize}`. |
| 12 | D | Same. |
| 13 | D | Same. |
| 14 | D | Same. |
| 15 | T | `test_bulk_edit.py::TestTexts::test_an_element_without_the_language_is_skipped_and_the_rest_change`. |
| 16 | T | `test_bulk_actions.py::test_extensions_with_a_name_are_removed_in_one_step`. |
| 17 | P | `test_bulk_dialogs.py::test_without_extensions_the_removal_has_nothing_to_choose`. No log text. |
| 18 | G | Several supplementary files cannot be removed at once. |
| 19 | G | Move is offered for variables of mixed directions, and Delete too. |
| 20 | N | Touch. |
| 21 | P | `test_undo_views.py::test_window_is_modified_after_an_edit_and_clean_after_undo` for an edit. No bulk action asserts it. The changed marker follows the history for every command. |

## F-EDT-10 Supplementary files

| AC | Class | Evidence |
|---|---|---|
| 1 | D | A dock panel, not a node. In Read mode its buttons are off (`tests/large/test_package_files_flow.py`, D18). |
| 2 | P | `test_package_files_ui.py::test_adding_a_file_sanitizes_the_name_and_guesses_the_media_type`. The folder is `/aasx/files` (D15), and there is no "pending" state. |
| 3 | P | `test_package_files_ui.py::test_removing_a_file_nothing_refers_to_asks_nothing`. |
| 4 | P | `test_supplementary_files_roundtrip.py::test_removing_a_file_and_its_paths`: gone after save and reload. |
| 5 | O | Limit: the package thumbnail cannot be changed. |
| 6 | T | `test_package_files_ui.py::test_choosing_a_file_for_a_file_element_keeps_its_media_type`. |
| 7 | T | `test_package_files_ui.py::test_adding_a_file_for_a_file_element_sets_value_and_media_type`. |
| 8 | D | The media type is guessed, and `application/octet-stream` when unknown (changelog). Checked above. |
| 9 | T | `test_package_files_ui.py::test_creating_a_text_file_with_a_taken_name_warns_and_changes_nothing`. |
| 10 | T | `test_supplementary_files.py::test_editing_a_text_file_keeps_non_ascii_text_and_line_breaks`, `test_supplementary_files_roundtrip.py::test_editing_a_text_file_keeps_utf8_text`. |
| 11 | T | `test_package_files_ui.py::test_removing_a_file_asks_about_its_references`. |
| 12 | O | Limit: Centralize file. |
| 13 | T | `test_blob_actions.py::test_loading_a_file_sets_the_bytes_in_one_undoable_step`. |
| 14 | T | `test_blob_content.py::test_decode_base64_spells_the_bytes_of_the_text` (`SGVsbG8=` gives `Hello`) and `test_blob_actions.py::test_base64_text_becomes_the_bytes_in_one_undoable_step`. |
| 15 | T | The size label is shown (`test_value_editor.py::TestBinaryEdit::test_shows_content_that_is_no_text_as_hex`: "9 bytes, binary"), and "Blob: Bytes to Base64 text" is offered for every Blob with content (`test_blob_actions.py::test_bytes_become_base64_text_in_one_undoable_step`, `::test_the_conversion_there_and_back_gives_the_bytes_again`). |
| 16 | T | `test_element_conversion.py::test_a_file_becomes_a_blob_with_the_content_of_the_stored_file`. |
| 17 | N | Browser. |
| 18 | N | Browser. |

## F-EDT-11 References, semantics, lookups

| AC | Class | Evidence |
|---|---|---|
| 1 | O | Limit: the picker lists the open package only. |
| 2 | T | `test_reference_picker_fields.py::TestPickingATarget::test_a_concept_description_gives_an_external_reference_to_its_id`. |
| 3 | T | `test_reference_picker_fields.py::test_the_model_kind_keeps_the_concept_description_key_type`. |
| 4 | P | `test_reference_picker_fields.py::test_an_sdk_refusal_is_shown_as_a_reason_and_blocks_ok`. There is no "Select" for a non-matching row, because the picker lists only matching ones. |
| 5 | P | The stored files have their own chooser (`FileChoiceDialog`, tested through the File element). The reference picker has no file filter. |
| 6 | O | Plan: "Add from pool of known concepts". |
| 7 | P | `test_reference_picker_fields.py::test_every_reference_field_gets_the_picker` includes the supplemental semantic id. Appending is not asserted. |
| 8 | O | Plan: ECLASS. |
| 9 | O | Same. |
| 10 | O | Same. |
| 11 | O | Same. |
| 12 | O | Same. |
| 13 | O | Same. |
| 14 | O | Same. |
| 15 | G | No "Create empty" concept description. |
| 16 | G | The action is off for an element with no semantic id, and says nothing. |
| 17 | T | `test_concepts.py::TestNewConcept::test_the_id_is_the_first_key_and_the_names_come_from_the_element`. |
| 18 | O | Part of ECLASS import. |
| 19 | D | Jump works in the tabs, where references are shown, not in the tree (changelog). `test_reference_jump.py`. |
| 20 | T | `test_reference_jump.py::test_a_reference_that_resolves_in_part_opens_the_closest_object`. |
| 21 | T | `test_reference_jump.py::test_a_reference_to_an_unknown_id_says_the_target_is_missing`. |
| 22 | O | ECLASS actions do not exist, so none is shown. |
