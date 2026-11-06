# ADR 0018: A package that opens in failsafe mode lists what the SDK left out

**Status:** Accepted

## Context

D6 treats every package that opens through the failsafe branch as partial, so that it cannot overwrite its source.
It said that the SDK does not report what it skipped, and the editor told the user only to use Save As.
[ADR 0010](0010-validation-findings.md) had noted that the log of the SDK can say what was skipped, and did not build it.
Probes against the pinned SDK (ADR 0004) and the 136 AASX files of the repository found:

| Finding | Consequence |
|---|---|
| Of the 132 bundled templates, 83 open strictly and 49 only in failsafe mode. Each of the 49 logs at least one `ERROR` record while it is read, and the 83 log none at warning level or above. | The log is a complete account of what failsafe mode skips in the corpus, and a strict read needs none. |
| The XML reader logs one record for each construct that it skips, such as `AASConstraintViolation: A semantic_id must be defined ... (Constraint AASd-118)` followed by ` -> Failed to construct ns0:submodel on line 33 using construct_submodel!`. A nested failure is one record with several ` -> ` lines, the causes first and the construct that was left out last. | One issue for each record, about the last construct. |
| The same code logs warnings that mean something else: a key type that does not match (nothing lost), and a second data specification that is ignored (something lost). | The text decides. A warning that no pattern knows is reported as not understood, and is not counted as a loss. |
| The JSON reader logs two records for one skipped object, why it failed and that the list skipped it. | They are merged by model type, id, and idShort. |
| The JSON failsafe reader raises `ValueError` for a reference with no keys or a value that does not parse, where the XML reader skips the item. | Such a JSON file cannot be opened at all. This is a limit of the SDK, and not changed here. |
| The AASX reader skips an object whose id an earlier part has, in strict and in failsafe mode, and logs **nothing**. Read from `_read_aas_part_into`, and reproduced with an AASX of two parts. | The one loss that the log cannot show, and that a strict package can have. |
| Two elements with the same idShort in one submodel fail the whole submodel (AASd-022), because the SDK adds the elements while it builds it. | A single defect can cost a whole submodel, so the report must say what is gone and not what is wrong. |
| The SDK gives a list item with no idShort a generated one, `generated_submodel_list_hack_...`. | A count of idShort entries must leave those out. WP12 did not, and counted 37 of 49 packages short where 45 are. |

## Decision

- **The reader captures the log of the SDK for the length of one read.** `_SdkLogCapture` in `infrastructure/package_io.py` adds a handler to the `basyx` logger and removes it when the read ends, also when it raises. It lowers the level of that logger to warning only if the level is higher, and puts it back. It keeps only the records of the thread that reads. Records of a strict read are dropped, because a strict read raises where a failsafe read skips, and what it logs is a remark about content that was kept.
- **A record becomes a `LoadIssue`** (`domain/load_report.py`, no logging, no Qt): the severity, the outcome (left out, kept, or not understood), the scope (object, element, detail, part), the subject, the line or id, the OPC part, the reason, and the text of the record in full. A record that no pattern knows is kept whole as not understood. `LoadReport` counts, sorts the biggest losses first, writes a summary and a text to copy, and turns into plain data for the crash recovery.
- **The reader also finds what the SDK skips silently.** `_TolerantReader` overrides the protected `_parse_aas_part`, which only notes the part and the objects it returns, and then reports an object whose id an earlier part has and whose JSON differs from the one that was kept. An equal copy is not a loss. This is a fourth narrow exception to D3, with a guard test that fails when the SDK starts to log it. A package with such an object is partial, in strict mode too.
- **The user is told in three places.** A dialog when a package opens, with a summary of the counts and the kinds of object, the full list, and a button that copies it. A context menu action on the package that shows it again. The text of the refused save, which names what is missing, lists the first ten items, and has a button for the full list. It also says that the copy that Save As writes will not have this content either.
- **D6 stays**, with the corrected reason: the package lacks what the SDK refused to read, and a report does not bring it back.

## What cannot be kept

No reader option keeps any of the content, and this was checked against the options of `read_aas_xml_file_into`, `read_aas_json_file_into` and `AASXReader.read_into`:

- `failsafe` only chooses between raising and skipping.
- `replace_existing`, `ignore_existing` and `override_existing` decide what happens to an object that the object store already holds. They do not touch a second object with the same id inside one document or one package, which the SDK skips on its own.
- `decoder` is documented and lets a subclass change how an element is built. That is a reader of our own, which D3 rules out, and it would still have to choose values for what the model refuses.
- No setting turns off the constraints of the model classes (AASd-002, 014, 021, 022, 109, 118, 123, 127, 131), and the store holds one object for each id.
- A text with no text, a key type that does not exist, and a short name above 18 characters are refused by the classes of the SDK as V3.1 forbids them. Keeping them is a repair.

So the content stays lost on Save As. The corpus is made of templates with defects that the SDK is right to refuse.

## Consequences

- Silent loss of a whole submodel is gone from the editor. All 49 packages show what was left out, and each of the 83 second objects with a shared id that the XML reader skips is named by its id.
- The count is of records, not of lost content. One failed construct can hold a whole tree, and an element that failed inside a submodel that failed as well is counted twice, so a summary of "1 object and 1 element" can be one subtree. `test_load_report_corpus.py` checks the report against the `idShort` entries in the XML of every template: the entries that the object store lacks are exactly those below the places that the report names, which is stronger than a count.
- A package that opened strictly with an object that differs from one in an earlier part is now partial and opens a dialog. None of the 83 strict templates is.
- The report of a package is kept in the crash recovery, so a restored package still tells what was left out.
- The patterns depend on the text of the SDK. The corpus test fails when a record is not understood, or when a pattern stops matching.
- Not done: telling an equal copy of an object that the XML reader skips for sharing an id from a different one. The reader does not hand the second object over. The report says that the first was kept.

## Alternatives considered

- **Pass a decoder that records what it builds.** `tests/medium/failsafe_causes.py` does this to compare duplicates. It is a reader of our own in the product, for a gain that the log gives.
- **Parse the XML of the package for a count.** Hand-written AAS XML (D3). The test does it once, as an independent check, and the editor never does.
- **Show the report in the validation dock.** The dock lists findings of rules about objects that exist. What the SDK left out has no object to go to, and it is a fact about the file, so a dialog and a menu action fit it better.
- **Make the first-open message list every record.** The 49 packages have up to 87 records, so the list is in a box that scrolls, under a summary of five lines.
