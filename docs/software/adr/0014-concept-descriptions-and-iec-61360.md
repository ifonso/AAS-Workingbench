# ADR 0014: Concept descriptions follow the semantic id by id, and IEC 61360 records are built from a checked draft

**Status:** Accepted

## Context

Work package 10 adds the concept description tools of the original editor. Probes of the pinned SDK and of the bundled templates (6695 descriptions) showed what shapes them:

- The SDK refuses an empty `preferred_name` and texts of the wrong length (18, 255, 1023 and 2048 characters) when the object is made, with a message for a programmer. It accepts an empty `unit`, `symbol`, `source_of_definition` and `value_format`, and an empty value list, which JSON writes as `"unit": ""` and `"valueReferencePairs": []`.
- `ValueReferencePair` compares by identity, and a value list is a set. Its order is not saved, and importing the same text twice doubles the list.
- A pair without a value id is written as `"valueId": null` in JSON. The SDK's strict reader refuses that, and its failsafe reader drops the pair and, with it, the pairs that are written next to it. XML is fine.
- A submodel in the SDK cannot have an element without an idShort (AASd-117), so the original's "take the idShort from the description when it is empty" has no case.
- The SDK names the template key of IEC 61360 `https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/1` (constraint AASc-3a-050). The 6695 bundled descriptions use four other spellings, mostly `3/0` with `http` or `https` and `IEC61360` or `Iec61360`. The original editor writes `.../DataSpecificationIec61360/3/0`.
- Tree rows of concept descriptions show the idShort, or the class name for a description without one. They were sorted by Qt's case-sensitive comparison, so equal names were in the order of the set, which changes between runs.

## Decision

- **The SDK's key is the current key.** New records get `.../DataSpecificationIEC61360/3/1`. Every other spelling that names the template is recognized as another spelling, and `Fix data specification keys` changes it only when the user ticks a box, because an older file may have been written for an older version. A reference that names something else is replaced without asking, when the content is IEC 61360. The content decides, as in the original.
- **A description is found by id.** A semantic id names a description when a key holds its id, the rule of `ReferenceIndex` and of the original. A new description gets the first key as its id. Assigning writes an external reference with one global key, not a model reference.
- **A semantic id is never replaced silently.** Assign shows the old and the new one and asks. Auto-detect only fills elements without a semantic id, matches the idShort exactly first and ignoring case second, and skips several matches.
- **An IEC 61360 record comes from a draft.** `Iec61360Draft` holds text. `check_draft` returns the reasons why the SDK would refuse it, in words, and notes for the constraints the SDK does not check (AASc-3a-008, 009 and 010). The dialog shows both while the user types and keeps the button off until the SDK would accept the record. Blank text means the attribute is absent, so nothing empty is created.
- **A pair needs a value id.** The importer reports a pair without one and does not add it, so a package never holds what the SDK cannot read back.
- **Value text is parsed, never evaluated.** Lines, and JSON through the SDK's decoder, one entry at a time, so a problem names its line or entry and the other entries are read. Size and count are limited.
- **Invalid means empty.** A concept description with no data specification, no `is_case_of` and no extension defines nothing, and the metamodel and the original both expect a data specification. Deleting goes through the delete flow, so the references to it are shown.
- **The view order is state of the view.** `SearchProxyModel` lists descriptions by name ignoring case with the id as tie-break, or by idShort, id, or first use. It never changes the package.

## Consequences

- Files written for `3/0` keep their keys until the user decides. Creating records in them mixes spellings, which the fix action resolves.
- The category rules AASc-3a-004 to 007 are not checked, because the text of Part 3a was not available. They can be added to `check_draft` without a change of structure.
- A user who wants an unused pair without value id has to give it one.
- The sort by first use is computed when it is chosen.

## Alternatives considered

- **The original's key `.../Iec61360/3/0`.** Rejected: the SDK documents another one for V3.1, and the editor targets V3.1 (D1).
- **Rewrite every older key on a fix.** Rejected: it would change 100% of the records of a typical IDTA template at one click.
- **Allow pairs without a value id and rely on XML.** Rejected: the same package saved as JSON loses them without a message.
- **A static sort of the set, as the original has.** Impossible: the order of a set is not saved (D16).
