# ADR 0007: Edits as commands on AAS objects, reported to an observer

**Status:** Accepted

## Context

Undo today lives in the item models, and it cannot support a package-wide history:

- Each tab has its own `DetailedInfoTable` with its own undo deque, so one package has many histories.
- An undo entry holds a `QPersistentModelIndex`, which means nothing to another tab's model.
- Dirty state is set by the view, and closing a package is an undo entry.
- When one tab edits an object, other tabs that show it stay stale.

The models also make order changes hard:

- Rows are the QObject children of an item, so a row can only be appended.
- `update()` nests begin and end calls and emits Qt signals by hand, which violates the model contract.
- The SDK moves an element to the end of its namespace when its idShort changes, and `editItem` replaces set members the same way. Undo of a delete re-adds at the end.

Probes against the pinned SDK showed that the order of a `NamespaceSet` survives a JSON and XML round trip for Submodel, SubmodelElementCollection, Entity, Operation variables, annotations, and SubmodelElementList. A `NamespaceSet` has no `insert`, so reordering needs `clear()` followed by `add()` for each object.

## Decision

- **Commands address AAS objects by identity.** A command holds the BaSyx objects it changes, never a row or a model index. One `CommandStack` for each package, in `aas_editor.application.commands`, with atomic nested groups for cascades and a saved-state marker. The marker stays dirty when the saved state can no longer be reached, for example after undo followed by a new edit.
- **Commands report to a `ModelChangeObserver`.** `aas_editor.application.changes` defines four kinds of change: added, removed, moved, and changed. Each names the object, and for added, removed, and moved ones the container and position. Commands report in both `apply` and `revert`. An observer belongs to a package, found with `observer_for(package)`.
- **Qt models subscribe.** `StandardTable` follows the observer and updates the items that show the changed object. A change carries an `origin`, so the model that made it, and already updated itself, ignores it. Pack tree items add, remove, and move rows one by one. Detail items read their rows again, because their names contain list positions.
- **Order lives in `aas_editor.domain.ordering`.** It snapshots and restores namespace order, inserts and moves members, replaces a member in place, and renames an idShort without moving the element (D19). Every change rolls back when the SDK refuses an object.
- Both new layers import no Qt, and `tests/medium/test_layers.py` checks that.

The legacy mutation paths in the models report their changes to the observer already, so tabs resync today. They still keep the old undo deques. Replacing them with commands is the next work package.

## Consequences

- Several tabs, a future validation dock, and a reference index can all learn about edits from one place.
- Undo works across tabs and restores positions, once the models stop recording their own undo entries.
- Reporting a change is the duty of whoever mutates the object. A mutation that skips it leaves other tabs stale, so all edits must go through commands.
- `SubmodelElementList` reorders regenerate its hidden idShorts. They are never serialized, so this is harmless.
- Rows of the models are still QObject children. Insertion and moves reparent the following siblings, which costs time linear in the number of siblings.
- Subscribers are held weakly when they are bound methods, so models do not stay alive because of a subscription.

## Alternatives considered

- **`QUndoStack` with `QPersistentModelIndex`.** Rejected because indexes belong to one model, and the stack would have to live in the UI layer, where it could not have small tests.
- **Qt signals on the domain objects.** Rejected because `domain` and `application` must not import PyQt.
- **Replacing the item models with new ones now.** Rejected because no planned feature needs it. The legacy models are changed only as far as the new behavior requires.
