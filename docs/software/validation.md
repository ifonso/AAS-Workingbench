# Validation

The editor checks a package against metamodel V3.1.x with its own rules, written over BaSyx objects ([ADR 0005](adr/0005-metamodel-and-validation.md)).
This page says which constraints the SDK enforces, which a rule enforces, and which neither can, then what the rules find in the 132 bundled templates, and why 49 of those templates open only in failsafe mode.
Every number here comes from a test in `tests/`, named next to the table.

## Using the rules

```python
from aas_editor.application.validation import save_check_for, validate_package

# Linear in the size of the package: 45 ms for Purchase Order.
report = validate_package(package.save_source())
for finding in report.errors:
    print(finding.rule_id, finding.location, finding.message)
# The blockers and the confirmable errors of a save (D5).
check = save_check_for(report)
```

| Part | Where | What |
|---|---|---|
| Rules | `domain/validation/rules/` | 24 rules, one module for each topic. A rule takes a `ValidationContext` and yields `Finding`s. |
| Context | `domain/validation/context.py` | The package walked once for all rules: elements, qualifiers, extensions, semantic holders, language texts, file references, coded values. |
| Engine | `domain/validation/engine.py` | `validate(objects, stored_files=None, rules=ALL_RULES, tolerant=False)` returns a `ValidationReport`. A rule that raises is a defect and is not caught, unless `tolerant` is true: then it is logged and reported as a warning of the rule `EDT-RULE-FAILED`. |
| Findings | `domain/validation/findings.py` | `Finding` (rule id, severity, message, subject, anchor, attribute, `blocks_save`) and `ValidationReport` (`errors`, `warnings`, `blocking`, `of_rule`, `counts_by_rule`). |
| Coverage | `domain/validation/coverage.py` | The table below, as data. A test keeps it in step with the rules. |
| Hint rules | `domain/validation/rules/hints.py` | `HINT_RULES`: six rules for hints mode, outside `ALL_RULES`. |
| Field checks | `domain/validation/field_checks.py` | The checks of single texts, which the rules and the hints under dialog fields share. |
| Application | `application/validation.py` | `validate_package(source)`, `save_check_for(report)`, and `SaveGate`, the check of a save. |
| Service | `ui/validation_service.py` | One for each package. It runs the rules, debounced, for the dock and the hints. |
| Dock | `ui/validation_dock.py` | The findings with the severity and rule filters. |

**The validation dock (WP5b):** a finding has `anchor`, the shell, submodel, concept description or element to select when the user opens it, and `subject`, the object that is wrong (a `Qualifier`, a `SpecificAssetId`, or a file name).
`anchor` is `None` for a finding about the package, such as a file that nothing refers to.
The dock lists them with severity, rule, location and message, filters by severity and by rule, and selects the `anchor` on a double click. `ValidationReport.of(findings)` sorts errors first and keeps the document order within a severity, but the order inside a severity follows an unordered set for shells, submodels, and descriptions.

### Severity and the save gate (D5)

| Severity | Meaning | Gate |
|---|---|---|
| Error | A "shall" of the specification is broken, or the SDK cannot write the package as AASX | Shown before a save, with Save anyway |
| Warning | Legal, but probably wrong | Listed in the dock only |
| Info | A hint | No rule uses it yet |

`blocks_save` is true only for a File whose path has no stored file (`EDT-MISSING-FILE`) and for a File under an annotation (`EDT-FILE-IN-ANNOTATION`).
These are the refusals that `application/save.py` already makes with the same `domain.file_references` functions, so `check_save` is unchanged.
`tests/small/test_application_validation.py` checks that the blocking findings and the blockers of `check_save` agree.
`save_check_for` maps a report to a `SaveCheck`: blocking findings are blockers, and the other errors are the warnings that the user may confirm.
`SaveGate.check` merges it with `check_save`. The two file rules are left out of the merge, because `check_save` blocks them with the target format in mind (a JSON target needs no stored file). The other errors are asked about once for each package and session: the same rule, place and message do not ask again after "Save anyway", and a new or changed error does. The warnings of `check_save` (D7) ask on every save.

Six bundled templates have one-letter idShorts, so a save asks once. This fits D5, which wants errors shown and not skipped, and it stops a user who cannot fix a template from confirming 120 errors on every save ([ADR 0015](adr/0015-validation-in-the-editor.md)).

A control character in the value of a Property (`AASd-130`) does not block: the XML writer of the SDK raises `ValueError` for it, which the save flow reports with the target untouched, and JSON writes it.

## The rules

| Rule | Severity | Checks | Why the SDK does not |
|---|---|---|---|
| `EDT-DUPLICATE-ID` | Error | Two shells, submodels or descriptions with one id | The store checks an id when an object is added, not when it is edited. A saved file keeps one object of the two. |
| `AASd-002` | Error | idShort matches `^[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9_]+$` | The SDK accepts one letter (see the evidence below) |
| `AASd-005` | Error | A revision needs a version | Checked when the object is made, not when the version is cleared |
| `AASd-006`, `AASd-007` | Error | A qualifier or property value equals the coded value that `valueId` points at | Not checked. Possible only when `valueId` is a pair in a value list of the package. |
| `AASd-020` | Error | A qualifier value fits its value type | Not checked when the value type changes |
| `EDT-VALUE-TYPE` | Error, warning for `anyURI` | The same for Property, Range and Extension. An extension with a value needs a value type. | The SDK writes the file and cannot read it back (ADR 0008) |
| `EDT-RANGE-ORDER` | Warning | A Range with min above max | The specification has no number for it |
| `AASd-109` | Error | List items have the value type of the list | Checked when an item is added, not when its value type changes |
| `AASd-116` | Error | No specific asset id named `globalAssetId`, in any case | Not checked |
| `AASd-118` | Error | A supplemental semantic id needs a semantic id | Refused on add and on clear, accepted when an object is made with a supplemental id only |
| `AASd-119` | Error | A template qualifier on a submodel needs kind Template | Not checked |
| `AASd-129` | Error | A template qualifier on an element needs a template submodel | Not checked |
| `AASc-3a-004` | Error | A description of the category PROPERTY or VALUE has an IEC 61360 data type of its group (14 types) | Part 3a. Not checked |
| `AASc-3a-005` | Error | The category REFERENCE has the data type STRING, IRI or IRDI | Part 3a. Not checked |
| `AASc-3a-006` | Error | The category DOCUMENT has the data type FILE, BLOB or HTML | Part 3a. Not checked |
| `AASc-3a-007` | Error | The category QUALIFIER_TYPE has a data type | Part 3a. Not checked |
| `AASd-130` | Error | A string value has only XML characters | Checked for names, texts and ids, not for values |
| `AASd-133` | Error | An external subject id is an external reference | Not checked |
| `EDT-DANGLING-REFERENCE` | Warning | A model reference with no target in the package | Not the SDK's job. An external reference never counts. |
| `EDT-MISSING-FILE` | Error, blocks | A File or thumbnail path with no stored file | The writer raises `KeyError` (ADR 0006) |
| `EDT-FILE-IN-ANNOTATION` | Error, blocks | A File under an annotation | The writer skips annotations (ADR 0006) |
| `EDT-UNREFERENCED-FILE` | Warning | A stored file that nothing refers to | A save drops it, after a warning (D7) |
| `EDT-LANGUAGE-TAG` | Error, warning for case | Malformed BCP 47 tags, and tags that differ only in case | The SDK keeps `en` and `EN` as two entries. It refuses a malformed tag when the text is made. |

Language tags are checked for being well-formed, with no registry ([ADR 0008](adr/0008-values-follow-their-type.md)).
A malformed tag cannot arise in memory, so only the case rule has a failing test.

## What the SDK enforces, what a rule enforces, and what neither can

The probes are in `tests/small/test_validation_sdk_probes.py`: a violation built through the constructor and through a later edit, on the pinned commit (ADR 0004).
The list of constraints is the one in the local specification (`aas-specs-metamodel`, Part 1), whose text is V3.2.
AASd-137 and AASd-138 are V3.2 only, and AASd-129 got a V3.2 exception, which the rule does not apply.

| Constraint | About | Who | Evidence |
|---|---|---|---|
| AASd-002 | idShort pattern | SDK and rule | The SDK refuses a leading digit, a trailing hyphen and other characters, on make and on set. It accepts one letter. |
| AASd-005 | revision needs version | SDK and rule | Refused on make. Accepted: `version = None` afterwards. |
| AASd-006 | qualifier value is the coded value | Rule | Accepted by the SDK. Checked only against a value list in the package. |
| AASd-007 | property value is the coded value | Rule | Same. |
| AASd-012 | multi-language value and `valueId` mean the same | Neither | Accepted by the SDK. It compares meanings, and a value list has one text for a coded value, not one for each language. |
| AASd-013 | range of kind Instance has min or max | Not in V3 | In no V3.0, V3.1 or V3.2 text, and `Range` has no `kind`. The SDK docstring still cites it, which is probably where the work package list found it. |
| AASd-014 | self-managed entity has an asset id | SDK | Refused on make, on setting the type, and on clearing the last asset id |
| AASd-020 | qualifier value fits value type | SDK and rule | Refused on make and on setting the value. Accepted: changing `value_type`. |
| AASd-021 | one qualifier of each type | SDK | Refused on add and on editing the type |
| AASd-022 | unique idShort | SDK | Refused on add and on editing the idShort |
| AASd-077 | unique extension name | SDK | Refused on add and on editing the name. The work package list thought it unenforced. |
| AASd-107 | list item semantic id | SDK | Refused on add and on editing the item |
| AASd-108 | list item type | SDK | Refused on add, and the list type cannot change |
| AASd-109 | list item value type | SDK and rule | Refused on add. Accepted: changing `value_type` of an item. |
| AASd-114 | item semantic ids agree | SDK | Refused on add and on editing |
| AASd-115 | a missing item semantic id is the list's | Neither | A rule of interpretation, so nothing can be violated |
| AASd-116 | `globalAssetId` is reserved | Rule | Accepted by the SDK, in any case |
| AASd-117 | idShort outside lists | SDK | Refused on add and on clearing, in a submodel, collection, entity, operation, and annotation |
| AASd-118 | supplemental needs semantic | SDK and rule | Refused on add and on clear. Accepted: making an object with a supplemental id only. |
| AASd-119 | template qualifier, kind | Rule | Accepted. Only a Submodel has a kind in V3.1. |
| AASd-121 to AASd-128 | keys of references | SDK | Refused when the reference is made. References and keys cannot be changed, so no invalid one exists in memory. |
| AASd-129 | template qualifier, submodel | Rule | Accepted. The rule uses the V3.1 text. |
| AASd-130 | XML characters | SDK and rule | Refused for names, texts, ids and paths. Accepted in the value of a Property. |
| AASd-131 | asset information has an asset id | SDK | Refused on make and on clearing |
| AASd-133 | external subject is external | Rule | Accepted: a model reference |
| AASd-134 | operation variable idShorts | SDK | Refused on add across the three sets, and on editing the idShort. The work package list thought it unenforced. |
| AASd-137, AASd-138 | | Not in V3.1 | New in V3.2. The SDK does not implement them. |

The work package list named AASd-006, 007, 012, 013, 077, 119, 129, 133 and 134 as unenforced.
The probes changed it: 077 and 134 are enforced, 013 does not exist in V3, 012 cannot be checked, and 006 and 007 can be checked in part.
They added AASd-002, 005, 020, 109, 116, 118 and 130.

AASc-3a-004 to 007 are the constraints of Part 3a that tie the category of a concept description to the data type of its IEC 61360 record. The Part 3a text is not in the local specifications, so the wording and the sets of data types come from the verification code of Package Explorer (`AasCore.Aas3_1`, `verification.cs` and `constants.cs`), which is generated from it. None of the 132 bundled templates sets one of these categories (their descriptions have none, `PARAMETER` or `CONSTANT`), so none gets a finding. The other constraints of Part 3a that the editor knows are advisories of the IEC 61360 dialog (AASc-3a-008 to 010), not rules.

AASd-129 follows the V3.1 text, without the exception of V3.2 for operation variables.
No bundled template has a template qualifier in an instance submodel, so the exception changes nothing for them.

## Hints

Hints mode adds the findings of six hint rules to the report. A hint that Package Explorer calls High is a warning, and a Notice is info. The dock and the save gate do not list them.

| Rule | Severity | Hint | Source |
|---|---|---|---|
| `EDT-HINT-KEY-WHITESPACE` | Warning | A key of a semantic id or supplemental semantic id has whitespace | F-EDT-06 AC9 |
| `EDT-HINT-CATEGORY` | Info | A category is deprecated | F-EDT-06 AC16 |
| `EDT-HINT-COPY-NAME` | Warning | An idShort has three dashes, as a copy of the original names it | F-EDT-06 |
| `EDT-HINT-ASSET-ID-EMPTY` | Warning | The global asset id of a shell is blank | F-EDT-02 AC9 |
| `EDT-HINT-ASSET-ID-DUPLICATE` | Warning | Two shells share a global asset id | F-EDT-02 AC9 |
| `EDT-HINT-NO-DATA-SPEC` | Warning | A concept description has no data specification. One with a SAMM element is left out | F-EDT-05 AC18 |

The tab shows the findings and hints whose anchor is its object. The create dialogs show `field_problem` for the idShort, the value of a key, and the global asset id while the user types: the idShort check is the one of AASd-002, so a field and the rule give one message. The notices of Package Explorer about missing descriptions, display names and semantic ids are not done.

## The rules on the 132 templates

`tests/medium/test_validation_corpus.py` validates every template and pins these counts.
A template is opened as the editor opens it, so a package that needed the failsafe branch is missing the objects the SDK dropped.

| Rule | Findings | Templates |
|---|---|---|
| `EDT-DANGLING-REFERENCE` | 569 | 56 |
| `AASd-002` | 120 | 6 |
| `EDT-MISSING-FILE` | 60 | 13 |
| `EDT-VALUE-TYPE` | 1 | 1 |
| All other rules | 0 | 0 |

**`EDT-DANGLING-REFERENCE`, 569, is the template and not the rule.**
381 of the 569 references point at placeholder ids (`https://example.com/ids/...`, `www.vendor.com/...`), and the other 188 point at objects that the template package does not carry.

| Where | Findings | Templates | Points at |
|---|---|---|---|
| `first` of a RelationshipElement | 195 | 6 | A submodel with an example id |
| `second` of a RelationshipElement | 162 | 3 | The same |
| `semantic_id`, key type ConceptDescription | 102 | 4 | A description that the package does not carry |
| `semantic_id`, key type Submodel | 52 | 43 | The id of the submodel template, which the package does not carry |
| `value` of a ReferenceElement | 41 | 9 | A submodel with an example id, or a path that does not exist |
| `is_case_of` | 11 | 7 | An ECLASS IRDI, typed as a Submodel key (10), or a description (1) |
| `creator` | 3 | 3 | A submodel the package does not carry |
| `derived_from` | 3 | 3 | A shell with an example id |

The rule is right to report them, because each reference is broken inside the package, and the severity is a warning because the specification lets a model reference point into another package.
No rule drops the check: the dock can filter by severity.

**`AASd-002`, 120 in 6 templates, is a defect of the templates and the SDK is too lenient.**
IDTA 02026 (Provision of 3D models) and IDTA 02045 (Data model for asset location), in each of their versions, use one-letter idShorts such as `X`, `Y` and `Z` for properties and concept descriptions.
Four sources agree that the pattern needs two characters: the V3.1 verifier of `aas-core-meta` that the Package Explorer uses (`AasCore.Aas3_1/verification.cs`), the JSON schema and the XSD of the local specification folder (V3.2, with the same pattern), and the changelog of Part 1, which says V3.2 only rewrote the description to match the pattern.
The SDK docstring writes `^[a-zA-Z]|[a-zA-Z][a-zA-Z0-9_-]*[a-zA-Z0-9_]$`, which allows one letter by an alternative that the specification does not have.

**`EDT-MISSING-FILE`, 60 in 13 templates, is the known defect.**
These are the 13 templates of ADR 0006 whose File elements point at a part that is not in the package.
They are the only findings that block a save.

**`EDT-VALUE-TYPE`, 1: Software Nameplate.**
`InstallationPath` is an `xs:anyURI` with the value `C:\Windows\Program Files\Demo\Firmware`.
XSD 1.0 lets an anyURI hold any string, and the SDK reads and writes it, so this is a warning.
The editor still refuses to type such a value (ADR 0008).

No template has a template qualifier in an instance submodel, a coded value that disagrees with its list, a duplicate id (the SDK dropped them on read, see below), or a case-only language duplicate.

### Speed

`validate` takes 0.043 s for Purchase Order, the largest template (836 elements and 306 objects), and 0.66 s for all 132 templates together.
A synthetic package grows linearly: 2000 elements take 0.08 s, 16000 take 0.67 s, 32000 take 1.9 s.
`tests/medium/test_validation_corpus.py` only guards against a rule that turns quadratic, with a limit of 2 s.

## Why 49 of the 132 templates open only in failsafe mode

The editor reads a package strictly and offers the failsafe branch when that raises (D6).
Since the tolerant reader of WP2, the 13 templates with missing files open strictly.
Reading all 132 templates strictly, 83 open and 49 raise.
The work package statement said 53, which I could not reproduce at this commit.
`tests/medium/test_failsafe_causes.py` pins the table below by reading each of the 49 in both modes.

The strict read stops at the first error, so a package that has several causes is counted once, by its first.
Failsafe mode logs every object it drops, so the second table counts all of them.

| First strict error | Templates |
|---|---|
| Objects share an id | 30 |
| AASd-022, equal idShort in one namespace | 4 |
| AASd-014, self-managed entity without asset id | 4 |
| AASd-021, equal qualifier type | 4 |
| AASd-123, model reference whose first key is not an identifiable | 2 |
| AASd-131, asset information without asset id | 1 |
| AASd-109, list of properties without value type | 1 |
| AASd-002, invalid idShort | 1 |
| Invalid enumeration text (`Identifiable` as a key type) | 1 |
| A text element with no text | 1 |

| What failsafe mode drops | Templates | Objects or parts |
|---|---|---|
| A second object with the same id | 30 | 83 |
| AASd-022, an element with an idShort that a sibling has | 5 | 5 |
| AASd-109, a list of properties or ranges with no `valueTypeListElement` | 4 | 9 |
| AASd-014, an entity | 4 | 4 |
| AASd-021, a qualifier | 4 | 4 |
| A text with no text | 3 | 16 |
| AASd-118, an object with a supplemental id and no semantic id | 3 | 3 |
| AASd-123, a reference | 2 | 17 |
| A reference with no keys | 2 | 2 |
| AASd-127, a fragment reference that no File or Blob key precedes | 1 | 43 |
| AASd-131, a shell without an asset id | 1 | 1 |
| A key type that is no key type | 1 | 1 |
| A short name over 18 characters (IEC 61360) | 1 | 2 |
| A missing mandatory child | 1 | 2 |
| A Property value that is no number | 1 | 2 |
| AASd-002, an invalid idShort | 1 | 6 |

### Decision: D6 stays as it is

I found no cause for which failsafe mode loses nothing, so no package leaves the Save As rule.

- **Objects that share an id (30 of 49).** The only candidate for a lossless read. The SDK drops the second object of an id before the caller sees it, so a decoder was passed through the `decoder` option of the reader to see both. Over the 30 packages there are 81 groups of objects with a shared id: 32 are equal concept descriptions, 24 are concept descriptions with different content, and 25 are a concept description that has the id of the submodel it describes. The 32 equal copies, which a reader could drop without a loss, appear only in packages that also lose a different object, so **no package loses only equal copies**. A concept description with the id of its submodel cannot be kept next to it, because the store holds one object for each id, and giving it a new id would change what a semantic id means. `reader options only` allows nothing else: `ignore_existing` and `replace_existing` apply to objects already in the store, not to the second copy in one document.
- **Everything else** drops an element, entity, qualifier, reference or list that breaks a constraint that the SDK enforces on construction (AASd-002, 014, 021, 022, 109, 118, 123, 127, 131), or a text that V3.1 forbids (an empty text, a key type that does not exist, an IEC 61360 short name above 18 characters). These are defects of the templates, and the SDK is right to refuse them. Keeping the content needs a repair that chooses a value, which is Fix, not a reader option.

Two quieter findings make D6 safer, and are not a reduction:

- The SDK logs every object it drops at warning or error level. A later change can use those records to tell the user what is missing, instead of saying that something may be.
- An AASX with two parts that hold the same id skips the second object **without a log line**, in strict mode as well. This is from reading `_read_aas_part_into`, which does `continue` for an id already read. It was not probed, and the editor cannot see this loss.

| | Strict | Failsafe |
|---|---|---|
| Before | 83 | 49 |
| After | 83 | 49 |

## Limits

- Language tags: no registry, so `zz` passes. A malformed tag cannot arise in memory.
- `AASd-006` and `AASd-007` need the value list in the package. A `valueId` that points to ECLASS or IEC CDD is not checked.
- `AASd-012` and `AASd-115` have no check.
- Dangling references cannot tell an error from a reference into another package, so they are warnings.
- A rule sees the objects the SDK could read. A failsafe package is checked without what it dropped.
- Validation runs on a save, and in the dock and hints after a pause of 250 ms in the changes. It runs in the thread of the UI.
- The order of findings within a severity follows the order of an unordered set for shells, submodels and descriptions.
