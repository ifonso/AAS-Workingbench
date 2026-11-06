# ADR 0014: The rules run in the dock, in hints, and in the save gate, and the marker follows the stack

**Status:** Accepted

## Context

[ADR 0010](0010-validation-findings.md) built the rules and left their use open: nothing showed them, and a save did not run them. Work package 5b uses them in four places, and each raised a question.

| Question | Facts |
|---|---|
| How often do the rules run? | A run takes 45 ms for the largest template. The rules read the objects that the user edits, so a second thread would read them while they change. |
| What does D5 mean for a package with errors that the user cannot fix? | Six bundled templates have 120 one-letter idShorts, an error of AASd-002. A user who saves often would confirm the same list every time. |
| Where does the changed marker live? | Each item of each tab had its own `changed` flag. A tab reads its rows again after a change, which dropped the flag, and nothing cleared it after a save. |
| What is a hint? | Package Explorer shows hints that are no rule of the specification, such as a deprecated category. The plan says to reuse the rules and not write a second set of checks. |

## Decision

- **One service for each package runs the rules.** `ui/validation_service.py` runs them in the thread of the UI, debounced by 250 ms after the last change of the package or its history, and only while a view listens (the dock when it is visible, and the hints bar of a tab when hints mode is on). Typing never waits for a run. The dock and the hints read the same report.
- **A rule that raises cannot stop anything.** `validate(..., tolerant=True)` logs it and reports a warning of the rule `EDT-RULE-FAILED`, and keeps what the rule found before. The dock and the save gate use it. The default stays strict, so that tests find the defect.
- **The save gate is `SaveGate`.** It merges `check_save` and the errors of the rules (D5). The blockers come from `check_save` only, which knows the target format, so the two file rules `EDT-MISSING-FILE` and `EDT-FILE-IN-ANNOTATION` are left out of the merge. Other errors are warnings that need Save anyway. Warnings and hints do not interrupt.
- **Save anyway is asked once for an error.** After the user confirmed, the same errors (same rule, location and message) do not ask again for that package in this session. A new or changed error asks again. Content that a save drops (D7) is asked about on every save, because it depends on the target. This keeps D5, which says nothing is skipped silently: the user saw the list and chose.
- **Hints are rules.** `HINT_RULES` are rules in the same machinery, kept out of `ALL_RULES` so that the dock and the save gate do not show them. A hint that Package Explorer calls High is a warning, and a Notice is info. The tab shows the findings and hints whose anchor is its object. The dialogs show the same checks under a field while the user types, through `domain/validation/field_checks.py`, which the rules call too.
- **The marker belongs to the package.** `ChangeMarks` records the objects that changed or were added, and the objects above them. It follows the command stack: a save clears it, and so does an undo that returns to the saved state. Every tab and the package tree read the same marks, by object identity.

## Consequences

- Closing or hiding the dock stops the runs. The first run after it shows again costs 45 ms.
- A package with 120 AASd-002 errors asks once per session, and again when a new error appears. Save As to another file does not ask again either, because the package and its errors are the same.
- Marks are by identity, so a text or number cannot be marked. An edited attribute row that holds a text is not coloured, but the object above it is.
- A hint cannot be an error in the dock. Nothing stops a rule from being in both lists later.
- Hints mode is on at first, as in Package Explorer, and the View menu switches it off.

## Alternatives considered

- **Run the rules in a worker thread.** Rejected: the objects change under the rules, and a copy of a package costs more than the run.
- **Ask for every error on every save.** Rejected: it is the same list again and again for packages that the user cannot fix.
- **Never ask about errors.** Rejected: D5 says errors are shown before a save.
- **Write the hints as a separate set of checks in the UI.** Rejected: the plan says to reuse the rules, and one place for a check keeps the dialog and the dock from disagreeing.
- **Keep the flag on the rows.** Rejected: a tab reads its rows again after each change, and the flag is not shared between tabs.
