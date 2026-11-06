# ADR 0010: Trees show the saved order, and the others are sorted by name

**Status:** Accepted

## Context

Work package 6 moves elements up, down, to the top and to the end. A probe of the running tree found that a moved element would not have moved on screen:

- `TreeView` calls `setSortingEnabled(True)`, and Qt 6 starts the header with column 0 sorted descending. So every tree, in the package view and in the tabs, listed `Zeta, Mid, Alpha` for elements saved as `Zeta, Alpha, Mid`. The `QSortFilterProxyModel` kept that order after a move of the rows, and the saved file differed from the order on screen.
- The header remembered the sort across sessions with `saveState` and `restoreState`.
- The SDK keeps shells, submodels and concept descriptions in sets. Their order is not saved and changes from run to run, so a sorted view is right for them, and a move of them is impossible (D16).
- `QSortFilterProxyModel` inserts a new source row of a sorted proxy where `lessThan` puts it, and a comparator that always answers "equal" puts it at the end, so undoing a delete showed the row at the end.
- Qt skips `sort` for the column and order the proxy has already.

## Decision

- A level whose rows have a saved order (the elements of a submodel, collection, list, entity or annotated relationship, the variables of an operation, qualifiers, extensions, and the attributes of an object) shows that order by default. A level without a saved order (the members of a set, an object store or a file container) is sorted by name, ascending.
- `SearchProxyModel.sort(-1)` is the natural order, and the header starts there. In the natural order `lessThan` compares the source rows for a level with a saved order, so rows that are added, moved or put back by undo appear where their object is. It leaves other levels to the default comparison.
- A click on a column header sorts every level by that column, as before. A third click returns to the natural order.
- A move of rows puts a sorted tree back to the natural order first, so the user sees the row move.
- The header does not restore the sort of the last session, because that sort would hide the order of the package at the next start.
- The proxy invalidates after each `sort`, because Qt ignores a sort that repeats the column and order of the natural order.

## Consequences

- The order of the tree equals the order in the saved file for every level that can be moved. Medium and large tests compare the rows with the objects and with the reloaded file.
- A user who sorted the tree loses that sort when moving an element. This is the cost of showing the move.
- Undoing the delete of a submodel, shell or concept description puts the row back in its sorted place, so the row of a set no longer ends up at the end.
- A user who liked the old descending default has to click the header. No one asked for it, and it matched no order of the file.
- A new kind of container whose type is a `Set` or an object store is sorted by name without a change here. Any other container shows its own order.

## Alternatives considered

- **Switch sorting off.** Rejected: the lists of shells, submodels and concept descriptions have no order and become hard to read, and the feature would be gone.
- **Reset the sort only when a move runs.** Rejected: the tree would still show the wrong order from the first start, before any move.
- **A comparator that returns false in the natural order.** Rejected: the proxy puts added rows at the end, so a paste in the middle would look misplaced.
