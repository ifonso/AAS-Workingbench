# ADR 0010: Validation rules report findings, and a partial load stays partial

**Status:** Accepted

## Context

[ADR 0005](0005-metamodel-and-validation.md) decided to write rules over BaSyx objects.
Work package 5a built them and probed the pinned SDK (ADR 0004) for each constraint of the specification, which changed the plan:

| Finding | Consequence |
|---|---|
| The SDK refuses most violations when an object is made or added, and some of them again on a later edit. Of AASd-006, 007, 012, 013, 077, 119, 129, 133, and 134, it enforces 077 and 134, AASd-013 is in no V3 text, and AASd-012 compares meanings. | Fewer rules than planned, and others that the plan did not list: AASd-002 (one letter), 005, 020, 109, 116, 118, and 130. |
| Changing `value_type` leaves the value in the old type, and the SDK then writes a file that it cannot read. | A rule for Property, Range, Extension and Qualifier values. |
| Of the 132 bundled templates, 49 fail a strict read. 30 of them lose a second object with the same id, and none of those loses only an equal copy. | Whether D6 can be relaxed. |
| The SDK logs each object that failsafe mode drops. | The loss can be listed. |

## Decision

- **A rule yields findings.** A finding has a rule id (`AASd-nnn`, or `EDT-...` for an editor rule), a severity, a message, the object, and the element to go to. Rules are plain functions of a `ValidationContext` that walks the package once, so a run is linear: 43 ms for the largest template.
- **Severity follows the specification.** An error is a broken "shall" or a package that the SDK cannot write. A warning is legal and probably wrong, such as a model reference with no target, which may point into another package. A control character or a space in an `anyURI` value is a warning, because XSD 1.0 allows it.
- **Only two findings block a save**, a File with no stored file and a File under an annotation (`blocks_save`), as D5 says. They use the functions of `save.py`, so the rules and `check_save` agree. Other errors are for Save anyway, and `save_check_for` maps a report to a `SaveCheck`. Nothing runs the rules on a save yet, because the save gate is WP5b, and no package that saved before refuses to save now.
- **The rule follows the V3.1 text.** AASd-129 has no exception for operation variables, which V3.2 adds. AASd-137 and 138 are not implemented.
- **A rule is written only where an invalid state can exist.** A reference cannot be changed, so AASd-121 to 128 have no rule. `coverage.COVERAGE` records, for each constraint, the SDK, a rule, or neither, with the probe, and `test_validation_sdk_probes.py` fails when an SDK upgrade changes one.
- **D6 stays.** No cause of the 49 failsafe packages loses nothing, and no reader option can keep a second object with the same id. A package opened in failsafe mode still needs Save As. `tests/medium/test_failsafe_causes.py` fails when a package starts to qualify for a relaxation, or when a cause changes.

## Consequences

- The dock (WP5b) shows a report, and the save gate merges `save_check_for(report)` into `check_save`.
- A user can learn which constraints are unchecked. AASd-006 and 007 compare only against a value list in the package.
- The 569 dangling references in the templates are mostly placeholder ids. The dock needs a severity filter to stay usable.
- The log of the SDK can say what failsafe mode skipped. This is not built, and an AASX with the same id in two parts is dropped without a log line.

## Alternatives considered

- **Treat every error as a blocker.** Rejected: D5 says Save anyway for all but the two the SDK cannot write, and the corpus has errors in official templates.
- **Run the rules on every save now.** Rejected: it changes the behavior of Save before the dialog for it exists.
- **Drop equal copies of an object with a shared id when reading.** Rejected: it applies to no template, and needs a decoder subclass of the SDK for nothing.
- **Give a concept description with the id of its submodel a new id.** Rejected: a semantic id that points at the shared id would then mean one of two objects by guess.
