# ADR 0012: Replacing an element builds a new one, shows what is lost, and keeps the references

**Status:** Accepted

## Context

Package Explorer converts an element to another type ("Refactor"), and the SDK has no setter for the type of the items of a `SubmodelElementList`, its `order_relevant`, its semantic id, or its value type ([ADR 0008](0008-values-follow-their-type.md) left both to this work). Probes against the pinned SDK (ADR 0004) found:

| Finding | Consequence |
|---|---|
| No element can change its class. The only way is a new object from the constructor. | A conversion and a list rebuild both swap an old element for a new one. |
| `copy.deepcopy` of an element copies its parent, so the whole submodel. With `{id(parent): None}` as the memo it stops at the parent. | Items are copied with that memo. A copy shares nothing with the original. |
| An element cannot be added to a second namespace while it has a parent (`ValueError`). | The items cannot move to the new element, and the old element could not be brought back by undo. They are copied, and the old element keeps its own. |
| `SubmodelElementList` accepts a child that has an idShort, keeps it in memory, and does not write it. | Items made from a collection lose their idShorts when saved, so the plan reports that. |
| A list item needs `type(child) is type_value_list_element`, the value type of a Property or Range item (AASd-109), and the same semantic id (AASd-107, 114). The SDK raises `AASConstraintViolation` at the add. | The SDK decides which items fit a list. The editor adds them one by one and reports the ones it refuses. |
| `type_value_list_element` accepts `SubmodelElement` and `DataElement`, but no real item has exactly that type. | Those are not offered. |
| `AnnotatedRelationshipElement.annotation` accepts any element, though the specification allows data elements only. | The annotations of a relationship convert only to data elements. |
| An `Entity` without an entity type is written without `entityType`. | A conversion to an Entity sets `CoManagedEntity`, which needs no asset id. |
| A reference to an element names its class in the last key, and in `ModelReference.type`. After a conversion `resolve` raises `UnexpectedTypeError`. A reference to an item resolves by idShort through any container but a list, which wants a position. | References through the element change with it. |
| The original editor drops `extensions`, the second end of a relationship, and all variables of an Operation without a message. | None of these is lost silently here. |

## Decision

- **Both features build a new element and swap it in place.** `domain/conversion.py` and `domain/list_settings.py` make a `ReplacementPlan` without changing anything. The plan holds the new element, the list of losses, notes, and where each direct item of the old element went. `application/operations/replace.py` has the command, `ReplaceElement`, which uses `containers.replace_member` and so keeps the position, and `replacement_command`, which makes one undo step of the swap and the updates to the references.
- **A loss is anything the old element has that the new one does not.** The plan names each one with its value. The editor shows them in a table and asks, with Cancel as the default. A conversion without a loss asks nothing. Information that the reverse conversion would set by default is no loss: the `CoManagedEntity` of an entity, the `xs:string` of a Property, the input direction of an Operation variable.
- **The conversion groups are these.** Inside a group the values carry over. Between groups, and to a Capability, only the attributes all elements share carry over, and everything else is a loss.

  | Group | Types | What carries over |
  |---|---|---|
  | Value elements | Property, Range, MultiLanguageProperty, File, Blob | The value as text. Property and Range keep the value type for each other. Range uses `min`, and a Property fills `min` and `max`. A MultiLanguageProperty uses one text, in English if there is one, and a Property or File gives it the language `en`. A File's path is the text of a Blob, or the stored content if the user chooses. Bytes of a Blob that are text become text. |
  | Reference elements | ReferenceElement, RelationshipElement, AnnotatedRelationshipElement | `first`, and `second` between relationships. A relationship that becomes a ReferenceElement loses `second`, and an annotated one that loses its annotations names them. |
  | Containers | SubmodelElementCollection, SubmodelElementList, Entity, Operation | The items. Items without an idShort get `Item_<position>`. A list takes the most common type of the items, and keeps those that fit. An Operation takes all items as input variables, and gives all of them back, with the direction as a loss. |
  | Capability | Capability | Nothing specific. It converts to every type without a loss, and every type converts to it with a list of what is lost. |
  | BasicEventElement | BasicEventElement | It converts to every other type, losing what is its own. No type converts to it, because `observed` is mandatory and no other element has one. |

  Common to all: `idShort`, `displayName`, `category`, `description`, `semanticId`, supplemental semantic ids, qualifiers, extensions, and embedded data specifications. The original loses extensions.
- **An item of a list is not converted.** The list fixes its type (AASd-108). The error says to change the list.
- **References are rewritten, not just reported.** `plan_reference_updates` finds the references through the element with the `ReferenceIndex` of [ADR 0009](0009-reference-integrity.md). A reference gets the key type and `ModelReference.type` of the new element, and the key of an item gets its new idShort or position. References stored in the old element are updated first, so the copies of the items carry the new ones, and undo reverts in the reverse order. References into items that are gone stay, and the dialog lists them before the user agrees.
- **The new element is built when the command is applied.** The plan builds one for the preview. The command builds another, after the references were rewritten, and redo reuses it.
- **A list rebuild is a replacement of a list by a list.** The user chooses the four settings. The items that the SDK refuses are listed. Property and Range items change their value type with `typed_values.type_change_values`, and an item whose value does not fit is dropped and named. "Detect from the items" takes the most common semantic id, with the type and value type the items have. It starts from the type the SDK enforces already, so only the semantic id of a list that states none can be new.
- **The model refuses a cell edit of what a list fixes with a message that names the action.**
- **An item of a list shows its position in a read-only `index` row** in place of the generated idShort (F-EDT-04 AC13).

## Consequences

- A conversion of a File to a path or a text to a File can give a path that no stored file has. Saving reports it (D5). The conversion does not check.
- The new element has new identity. A tab that shows the old element closes, as for a delete, and the new row is selected.
- Items are copied, so a conversion of a collection with large Blobs copies them twice while the history holds both.
- AASd-107 and AASd-114 make the order of items matter in a rebuild: the most common semantic id wins, and the others are dropped.
- The conversion table is part of the behavior. A change to it is a change to this record or to a later one.
- A new SDK version that adds a setter for the list attributes makes the rebuild unnecessary, but not wrong.

## Alternatives considered

- **Move the items to the new element instead of copying them.** Rejected: the SDK allows one parent, and undo would have to rebuild the old element.
- **Copy the common attributes only, as the original does for some pairs.** Rejected: it loses data without a word.
- **Refuse a conversion that loses anything.** Rejected: the user wants to fix a wrong type, and a short list of what goes is enough.
- **Update only the references in the confirmation text.** Rejected: a package whose references stop resolving after a conversion is damaged.
- **Convert an item of a list by rebuilding the list around it.** Rejected for now: the user can change the type of the list, and the items that do not fit are named.
