# ADR 0031: The status bar counts the hints of the current object, and the Validation panel lists the hints of the package

**Status:** Accepted

This changes two points that earlier ADRs recorded. [ADR 0015](0015-validation-in-the-editor.md) says that `HINT_RULES` stay out of `ALL_RULES` "so that the dock and the save gate do not show them". [ADR 0029](0029-validation-runs-while-the-panel-is-hidden.md) says that "the status bar names the hints apart, and the panel says that it does not list them", and puts the count of hints of the current package in the status bar. The files of both stay as they are. Where they differ, this ADR is the later one, and only on these points. The rest of both stands: the service, the debounce, the tolerant mode, the save gate, and the rules.

## Context

The owner used the status bar of phase J on real files. "Edit mode | 0 errors, 1 warning | 183 hints | All changes saved" is the line for the Technical Data template. The 183 are 63 without a display name, 60 without a description, 30 with a description in one language, 28 with a deprecated category and 2 with whitespace in a key. The owner's Requester file shows 202. Four things were wrong with the number:

- It never reaches zero, because nearly every element has a few of the commonest hints.
- It sits next to the count of errors and reads as a count of defects.
- It cannot be clicked.
- It does not say where the hints are.

The hint rules found these things correctly. A template lacks display names and descriptions on purpose, so the finding is true and the person does not want it.

## Decision

- **The status bar counts the hints of the object that is current.** It shows "3 hints here", and nothing when the object has none or when hints mode is off. The object is the one of the current row of the package tree, or the object of the current tab when the focus is in a tab, the way the bar above a tab picks its object. The count is a button with the look of the errors and warnings button. Its report is the one that the service already makes with hints, so no rule runs more often than before.
- **The Validation panel has a Hints view.** A tab bar at the top of the panel chooses between "Errors and warnings", which is the list of before with its filters and its count, and "Hints". The Hints view groups the hints of the whole package by rule, with a readable name and a count ("Missing description 60"), and each group opens to the elements. A double click or Enter on an element selects it in the tree. This view is the one place with a count for the package. A click on "3 hints here" opens the panel on it. A click on the errors and warnings, and a click on a bar above a tab that has an error, open the list of findings.
- **`F8` and `Shift+F8` are as before.** They go through the errors and warnings only. The note on the list of findings now says that the Hints view lists the hints.
- **A kind of hint can be turned off, for the user and not for the package.** Each group of the Hints view has a check box. A kind that is off is left out of "3 hints here" and of the bar above a tab, stays in the Hints view in a quiet color so that it can be turned on again, and a button there turns every kind on. The set of kinds is kept in `settings.ini` as `disabledHintKinds`, the rule ids joined by commas. It is not written to the AASX file, and it does not change the package or its undo history.
- **What the rules find does not change.** `HINT_RULES` keep their findings and their severities. `ALL_RULES`, the save gate, the counts of errors and warnings, and `is_hint` are as before. A kind that is off hides findings from the views and nothing else. The panel's listening to the hints is new: while the panel is visible the service runs with hints, which the status bar already asks for while hints mode is on.

## Consequences

- A person sees a number that is about what is in front of them, and that can be zero.
- The package-wide number exists in one place, and it is a list that a person can act on.
- A person who turns "Missing description" off for a template keeps it off for the next package too, including a package of their own where they may want it. The panel says how many kinds are off, and the button turns them on.
- The hints bar and the status bar now both read the set of kinds, so a change shows in both at once.
- With hints mode off the panel still opens on the Hints view and lists the hints, because the person asked for it, and it says that the tabs and the status bar show none.
- Which object is current when the focus is in a tab that shows an object of another package than the tree's current row is not handled: the status bar reads the report of the package of the current row, so it shows no hints for that object.
- The readable names are written in `application/hints.py` for the eleven rules, and a test fails when a rule has none.

## Alternatives considered

- **Keep the package-wide count in the status bar and make it a button.** Rejected: it would still never reach zero, and it would still sit next to the errors.
- **Turn a kind off for the package, in the AASX file.** Rejected: the file format has no place for it, and the owner asked for the user's settings. It also would not help a person who edits many templates.
- **Add the hints to the list of findings with a filter.** Rejected: the list has a row for each finding and a count that the person can drive to zero. Hundreds of hints of one kind would bury the findings, and F8 and the save gate would need to know the difference. A view that groups by rule fits the data.
- **Turn off a single hint on one element.** Not done. A kind is the unit that templates leave out on purpose.
