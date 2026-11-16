# ADR 0034: The status bar counts the hints of the package, in the blue of information

**Status:** Accepted. Changes a point of [ADR 0031](0031-hints-say-where-you-are-and-the-panel-lists-them.md).

## Context

ADR 0031 made the status bar count the hints of the current object only ("3 hints here"), because a count of the whole package never reaches zero, and in the yellow of warnings it read as a count of defects.

The UI proposals (`design/ui-proposals.md`, 1.5 and 5.1) change both causes. Hints and findings of the level Info are now blue, the color of information (`status_info`), so yellow means a warning only. And the status bar holds the problems and the hints as buttons that open the panel, as Package Explorer users read them: "No problems" and "523 hints".

## Decision

- The hints button of the status bar counts the hints of the package that the panel lists, leaving out the kinds that the user turned off, such as "523 hints", with the blue icon of information. It is hidden while the package has none, and while hints mode is off. A click opens the Hints view of the panel.
- Its tooltip still says how many hints the current object has, so the count of ADR 0031 is not lost.
- The errors and warnings read "No problems" when there are none, and else only what there is, such as "1 error" or "1 error, 2 warnings", with the icon of the worst of them.
- The bar above a tab still lists the hints of its object, as ADR 0031 decided.

## Consequences

- The count of the status bar and the count of the Hints view are the same number, so a user can tell where the number comes from.
- The count changes only with the package, not when another row becomes current.
- `ValidationStatus.hints_here` stays, for the tooltip, and `hints_total` is the count of the button.

## Alternatives considered

- **Keep "N hints here".** It is the count that changes as one walks the tree, but the mockup and the proposal ask for the count of the package, and the blue of information removes the reason against it.
- **Show both counts on the button.** The bar is short, and the tooltip has room for the second count.
