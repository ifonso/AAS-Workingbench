# ADR 0029: The rules run while the Validation panel is hidden, so that the status bar can count

**Status:** Accepted

This reopens one point of [ADR 0015](0015-validation-in-the-editor.md), which says that the service runs the rules "only while a view listens (the dock when it is visible, and the hints bar of a tab when hints mode is on)" and that "closing or hiding the dock stops the runs". The file of ADR 0015 stays as it is. Where the two differ, this ADR is the later one, and only on that point.

## Context

The [UI and UX plan](../../planning/ui-ux-plan.md) found in U3 that nothing on the screen says what state the package is in. The Validation panel starts hidden and, by ADR 0015, runs no rules until it is shown, so a person learns about errors when they save. Phase J of the plan puts the counts of errors, warnings and hints in the status bar. A count that is right needs a report, so the rules must run while the panel is hidden. The plan says to measure the cost first, on the largest bundled package, because ADR 0015 records only "45 ms for the largest template".

### The measurement

`validate_package(source, with_hints=True)` is the most expensive run, because it adds the eleven hint rules. It was timed in the thread of the UI on the 132 bundled templates and the showcase package of the plan (133 packages), each read once and validated 7 times, and on the two largest ones 40 times. One Windows 11 machine, Python 3.12, no other load. The size is the number of shells, submodels, concept descriptions and elements.

| Package | Objects | First run | Median | 95th percentile | Slowest run |
|---|---|---|---|---|---|
| Purchase Order, `IDTA-02050_Template_PurchaseOrder` (the largest) | 1142 | 57 ms | 53 ms | 65 ms | 79 ms |
| Purchase Order, V3.1 variant | 1142 | 97 ms | 55 ms | 69 ms | 97 ms |
| The next six in size | 406 to 436 | 14 to 19 ms | 16 to 19 ms | | 25 ms |
| Synthetic submodel, flat, not bundled | 5000 | 141 ms | 138 ms | 157 ms | 171 ms |
| Synthetic submodel, flat, not bundled | 10000 | 269 ms | 304 ms | 311 ms | 332 ms |

Without the hint rules the largest package takes 44 to 56 ms, which is the 45 ms of ADR 0015. The cost is 30 to 50 microseconds for each object, and linear, as ADR 0015 said. The highest median of all 133 packages, with hints, is the 65 ms of the Purchase Order V3.1 file in the first run of 7. The first run is not slower than the others, apart from one run of 97 ms that is an outlier of the second Purchase Order file.

**The limit that this ADR takes:** a run on the largest bundled package takes under 100 ms at the median, so that the pause after a burst of edits stays under a tenth of a second. This is a choice of this ADR, not a measured limit of how people perceive a pause. The median of 55 ms is inside it, and the slowest run of 97 ms is just inside it.

### What already runs

Hints mode is on at first, and then the hints bar of the tab that shows an object of the package already listens, with hints. In the default setting the rules therefore already run after every edit, whatever the state of the panel. The runs that are new are those of a package that no open tab shows, and those with hints mode off.

## Decision

- **The status bar listens.** `ui/validation_status.py` is a widget of the status bar that listens to the service of the current package for as long as the package is current, with the hints while hints mode is on. The rules run when the package becomes current, and after its edits, debounced as before, with the panel hidden or shown. The service, the debounce, the thread and the tolerant mode are those of ADR 0015.
- **The panel is as before.** It listens only while it is visible, but it takes every report that the service makes, so it is up to date when it shows again.
- **The wait follows the cost.** After a run the service waits at least 250 ms, and at least five times as long as the last run took, before the next. A package of 10 000 objects, which takes 300 ms, waits 1.5 s, so the rules take no more than a sixth of the time of the UI. A bundled package keeps 250 ms.
- **The counts read the report by who lists it.** Errors and warnings are those of the rules of the specification, the same ones that the panel lists. A hint is a finding of a hint rule, whatever severity that rule gives it, or a finding with the severity of a notice. The status bar names the hints apart, and the panel says that it does not list them.

## Consequences

- Hiding or closing the panel no longer stops the runs. Opening a package costs one run, about 55 ms for the largest bundled one.
- With hints mode off and no tab on the package, a package now costs the runs that before it did not. For the bundled packages that is under 100 ms for one run after each burst of edits.
- A package that is much larger than any bundled one pauses once after each burst, for about 30 to 50 ms for each 1000 objects. The wait that grows with the cost keeps this to a sixth of the time. No package of 10 000 objects is bundled, and a real one was not measured: the figures for it come from a synthetic submodel of flat properties, which has no deep nesting and no references.
- The numbers come from one machine. A slower one scales them, and the limit of 100 ms is then missed by the largest bundled package at 1.8 times the time measured here.
- The responsiveness of the window while a person types was not measured. The run waits 250 ms after the last change, so typing itself does not wait for a run.

## Alternatives considered

- **Keep running only while a view listens.** Rejected: the status bar would show nothing, or a count that is out of date, until the panel is opened, which is the problem U3 describes.
- **Run only when the package opens and when it is saved.** Rejected: the count would be wrong after the first edit.
- **Run the rules in a worker thread.** Rejected again for the reason of ADR 0015: the rules read the objects that the user edits, and a copy of a package costs more than a run.
- **Run on idle only.** Not tried. The debounce is already a wait for a pause, and the cost that grows the wait does the rest.
