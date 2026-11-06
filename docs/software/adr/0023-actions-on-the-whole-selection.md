# ADR 0023: Delete, cut and copy act on the whole selection, or refuse

**Status:** Accepted

## Context

WP18 asked of each criterion that the audit left open whether a test asserts the claim.
Looking for the cases that a test would have caught turned up one defect that touches a decision: the selection of rows under two parents.
F-EDT-09 AC2 is `D` in the audit: the actions are offered across parents, and each row moves in its own container.
The Selection panel and the bulk actions say that they work across parents.

| Finding | Consequence |
|---|---|
| `getTopLevelSameLevelIndexes` kept the rows of the first parent only. Delete, Cut and Copy on rows of two parents acted on the first parent's rows and said nothing. | Rows that the action drops without a word are a defect, not a limit. |
| `selectedIndexes()` lists the selected rows in the order of the selection, not of the tree. A copy took its objects in that order. | A paste has no stable order unless the rows are put in one. |
| Deleting rows one after another from the top shifts the rows of later siblings, and with them the parents of rows still to be deleted. | A delete has to go from the bottom of the tree up. |
| Each package has its own undo history, its own concept descriptions and its own files. A copy remembers one source package (ADR 0020). | One step, and one source, cannot cover rows of two packages. |
| The original puts the focus on the previous sibling after a delete, and the tree went to the parent. | F-EDT-01 AC8 asks for the sibling. |
| A hint rule that raises is caught and becomes a finding `EDT-RULE-FAILED` that belongs to the rule, not to an object. The bar above a tab lists the findings of the shown object, so the failure reached only the Validation dock. | F-EDT-01 AC14 asks for it where the hints are shown. |

## Decision

- **Delete, Cut and Copy take every selected row once.** A row counts once however many of its cells are selected, a row below a selected row goes with it, and the rows may have different parents.
- **The rows are in the order of the tree.** A copy and a cut put their objects on the clipboard in that order, so a paste gives the order of the tree, as F-EDT-08 AC9 asks and not the order of the clicks (ADR 0020 gave the same reason for moves).
- **A delete runs from the bottom of the tree up**, inside one history group, so one undo brings every row back.
- **Rows of two packages are refused with a message, and nothing changes.** For a Cut, the copy and the delete are both skipped. The user selects rows of one package.
- **After a delete the focus goes to the sibling above the deleted row**, and to the parent when it was the first row.
- **A rule that raised is listed with every object** in the bar above a tab. It is a finding of the package, and the user needs to see that a hint is missing wherever the hints are.

`ui/selection_rows.py` holds the rule (`top_level_rows`, `in_one_package`, `show_refusal`), and `TreeView.selectedRowsFor` uses it.

## Consequences

- The move actions already worked on the rows of every container. They pushed their commands on the history of the current row, so a move of rows of two packages marked the wrong package and undid in the wrong history. They are now off for such a selection, as they are for a variable mix, and nothing moves.
- The message for two packages is one text for the three actions, with the verb of the action.
- The failure of a rule shows on every tab while hints mode is on. It is a Warning, as in the dock, and the original's "High" advisory has the same place on the scale (see F-EDT-06 AC9 in the audit).
