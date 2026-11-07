# ADR 0009: Find references by walking the SDK objects, and index them for each operation

**Status:** Accepted

## Context

An AAS reference is immutable and holds the ids and idShorts of its path as keys. Nothing in the SDK tells where references are stored or who refers to an object, and the editor kept no such knowledge:

- Renaming an id or an idShort left every reference through it pointing at nothing.
- Deleting an object left its references behind without a word.
- An edit of the `id` attribute skipped the duplicate check that the object store does only when an object is added.
- The add dialogs proposed the fixed id `https://www.example.com/`, so the second new object failed with a `KeyError`.

References are stored in many fields: semantic ids, supplemental semantic ids, value ids, `refers_to`, the references of a shell, relationship ends, data specifications, `unit_id`, `creator`, `external_subject_id`, and others. A list that is kept by hand would miss the fields of the next SDK version.

Probing the pinned SDK showed three more facts that shape the design:

- Setting `semantic_id` makes the SDK take an element out of its namespace and add it again, which moves it to the end, as renaming an idShort does.
- A `SpecificAssetId` cannot be changed after it is made, and its references can only be replaced with the whole object.
- The SDK requires a non-empty preferred name for an IEC 61360 data specification, so "fill an empty preferred name", which the original does for Sync, cannot happen.

## Decision

- **A generic walk finds the references.** `aas_workingbench.domain.references.iter_slots` reads the attributes of the SDK objects and yields a `ReferenceSlot` for every reference with the object, the attribute, the list or set that holds it, and the element and identifiable it belongs to. No field is listed. A small test reads the constructor of every class of the SDK, builds an object with every reference parameter set, and fails when a field is not found or has no builder, so an SDK upgrade cannot silently lose one.
- **What counts as a reference to an object.** A reference points at an identifiable if its first key (model references) or any key (external references) holds the id, so the semantic id that points at a concept description counts. It points at an element if the path of keys begins with the path of the element, so a reference through a collection counts too. A reference that is stored inside the target is not a usage of it, except for a rename, which must update it.
- **The index is built for one operation and dropped.** `ReferenceIndex` maps ids to objects when it is made and collects the references on first use. It never follows changes, so it cannot be stale. The walk costs about 17 ms for the Purchase Order template (836 elements, 304 concept descriptions) and 0.4 s for 50000 elements, measured. That is linear and below what a user notices for a delete. The alternative, an index kept up to date by subscribing to the change observer, was rejected: it would have to understand every command, and a missed report would silently break renames.
- **Changes replace stored references.** A reference is replaced in place by the existing commands: `SetAttribute` for an attribute, `ReplaceMember` for a member of a list or set, and a replacement of the whole object for a `SpecificAssetId`. A new reference equal to one that a set holds already removes the old one instead.
- **Rename is a plan, then one step.** `plan_rename_id` and `plan_rename_id_short` find the references without changing anything. They refuse a duplicate id and an invalid idShort, and suggest a valid one. `RenameCommand` is a group: the rename first, so a refused value changes nothing, then the replacements. Renaming an idShort changes the key at that position of every model reference through the element, and keys that name a list position stay (AASd-128).
- **Delete asks, and lists the usages.** `plan_delete` finds the usages and splits them into those that can be taken away (members of lists and sets, optional attributes, a cut `referred_semantic_id`) and those that must stay because the attribute is required, such as the ends of a relationship. The user chooses between removing and leaving the references. A semantic id stays while a supplemental one stays (AASd-118). Deleting a child of a `SubmodelElementList` always moves the references to the items behind it up by one.
- **Which deletes ask.** A delete with usages shows them. A delete of a shell, submodel or concept description, or of an element with elements below it, asks for confirmation. Other deletes ask nothing, because undo brings them back. Shift skips the confirmation but not the usages. A cut asks nothing and leaves the references, because the object comes back with the paste (D12, D13).
- **Fix References is a repair, not a search.** It replaces the idShort that stands in the first key by the id when exactly one identifiable has it, and corrects key types that name another class than the object has. A general type such as `SubmodelElement` is correct. What it cannot resolve is listed, not guessed.
- **Sync idShort copies to the concept description.** It fills the idShort and the short name of the concept description that a semantic id names, never overwriting. A short name has at most 18 characters.
- **The dialogs are in `ui/`, and the plans are Qt-free.** The plans, texts about them and the question to ask are in `application/operations`. `ui/reference_dialogs.py` shows them, and `ui/reference_actions.py` and `ui/delete_flow.py` connect them to the actions and the views. The item models ask through `ui.reference_actions.rename_command`, so an id typed in a cell takes the same path as the Rename action.
- **`SetAttribute` keeps the position for every attribute**, not only the idShort, because the semantic id moved elements too.
- **New ids are `urn:uuid:` URNs** made when a dialog opens, in `GENERATED_DEFAULTS`, so each new object gets its own.

## Consequences

- A rename touches only references that the walk finds. A reference that the SDK keeps in a new kind of field is found without a change here, and the test says when a builder is missing.
- A global reference whose value happens to equal the id of an object of the package counts as a reference to it. It is one by the definition of the id.
- `AssetInformation.global_asset_id` and `SpecificAssetId.value` are strings, not references, and a rename does not touch them.
- Fix References repairs nothing that needs a choice. A reference through a list that names an item by its idShort is reported, not repaired.
- Moving list items, which work package 6 adds, must give the references the new positions the way delete does. `aas_workingbench.application.operations.references.rewrite_keys` is the function for that.
- A package of 50000 elements spends about half a second planning each delete or rename. If that becomes a problem, the walk can be cached per identifiable and invalidated by the change observer, without changing the plans.
- A reference to an object in another package is not seen. Copying between packages is work package 6.

## Alternatives considered

- **A list of reference fields.** Rejected because it needs upkeep with the SDK and fails silently.
- **An index that follows the change observer.** Rejected for the reasons above.
- **Making the SDK references mutable.** Not possible: the SDK forbids it, and the editor only uses BaSyx.
- **Asking inside the models.** The models call one function, and the dialogs stay in `ui/`, which keeps the plans testable without Qt.
