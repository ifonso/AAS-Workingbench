# ADR 0014: Reference fields wrap the generated forms, and creation has its own dialogs

**Status:** Accepted

## Context

Probes of the pinned SDK and of the editor before work package 7 showed:

- `AssetInformation()` raises AASd-131 without a global or a specific asset id, an empty id raises `ValueError`, and `AssetKind` has no `Batch`. The generated form for a shell shows no required field of the AssetInformation, so Add on the shells node always failed with a traceback.
- A `Reference` is entered through `ExternalReference` and `ModelReference` forms made from type hints. Only `ModelReference[...]` had a chooser, which listed every referable and did not derive a key type. The SDK refuses wrong keys when the reference is made (AASd-122 to 128) but allows a `ModelReference` whose target type does not match its keys.
- The tree of the packages shows shells, submodels and elements, not the references. References are rows of the tabs.
- A tab already keeps a history, so opening the target in the same tab gives Back for free.

## Decision

- **The picker wraps the generated form.** `ui/reference_fields.py` has `ReferenceGroupBox`, `ModelReferenceField`, and `ExternalReferenceField`. They subclass the existing group boxes, so the keys stay editable, free entry of external references is kept, and the objects the form makes are unchanged. `widgetUtil` picks them by the type hint, so every field of the SDK that holds a reference gets them, and a test lists those fields.
- **The rules are in the domain.** `domain/reference_picker.py` reads the hint into a rule (kinds and target classes), lists candidates, derives keys, and says whether a reference resolves, resolves in part, dangles, or is outside. No Qt.
- **An element gets a model reference.** An external reference points at an id, so choosing an element in the external kind gives a model reference. A concept description gets an external reference to its id by default, and a model reference when asked.
- **The SDK is the judge of the keys.** The form builds the reference as it is typed and shows the message of the SDK, with the rule number, and keeps OK off. It does not repeat the rules.
- **Creation has dialogs of its own.** `application/operations/create.py` makes valid objects or refuses with a message, and `ui/create_dialogs.py` asks. A Submodel and the reference to it are one step.
- **Paste into an AAS plans first.** `plan_paste_into_shell` copies Submodels as `plan_paste` does, skips references that are held, and reports dangling ones. Files and concept descriptions come along as in any other paste.
- **Jump opens in the current tab.** No new history is written.

## Consequences

- A new SDK reference field is found by the type hint, with no list of fields to keep.
- The status line builds an index of the package a moment after the user types, which costs about 20 ms for the largest template.
- A form that is opened without a tree view has no package, so it shows no status, and the picker lists nothing.

## Alternatives considered

- **A new reference widget in place of the group boxes.** Rejected: the tests and the other forms depend on the structure of the group boxes, and nothing would have gained.
- **Checking AASd-121 to 128 in our own code.** Rejected: the SDK enforces them, and a copy would drift.
- **A jump that opens a new tab.** Rejected: Back would have nothing to return to.
