# ADR 0015: Presets are SDK JSON files, and bulk changes use a small pattern language

**Status:** Accepted

## Context

Package Explorer adds qualifiers, extensions, specific asset ids, and data specifications from four JSON files whose paths come from startup options, and changes the idShort, description, or value of many selected elements with a pattern of single characters (`*`, `?`, `^`, `§`, `~`, `<`).
Probes against the pinned SDK (commit `412a53f`) and the original's documentation found:

| Finding | Consequence |
|---|---|
| The SDK's decoder reads a qualifier, extension, or specific asset id only inside its owner. `modelType: "Qualifier"` is refused, `"Extension"` and `"SpecificAssetId"` are accepted. | The JSON of one member is read by placing it in a holder that the SDK reads, and the holder is thrown away. No JSON of the metamodel is parsed by hand (D3). |
| The encoder writes a qualifier, extension, and specific asset id alone, but an `EmbeddedDataSpecification` only inside its owner. | The same holder trick writes a data specification. |
| A qualifier or extension belongs to one owner (`Object has already a parent`). A second qualifier type (AASd-021) or extension name (AASd-077) is refused on add, and a rename to a taken one raises `KeyError`. | Each owner gets a new member made from the preset, and a plan checks the conflicts before anything changes. |
| `SpecificAssetId` is immutable, and its value must not be empty. A co-managed entity refuses specific asset ids (AASd-014). | A preset without a value asks for it when it is used. |
| `DataSpecificationIEC61360` is the only data specification content class, and needs a preferred name. | Only the IEC 61360 template can be a preset. |
| Description texts are checked when a language entry is replaced (1..1023 characters, 1..128 for a display name). | A plan makes the text through the SDK's class first, so the dialog shows the reason. |
| The original's pattern language has defects: `<` (reverse) is broken, `^>` outputs the `>`, an element without the language throws, and nothing is checked or previewed. | A new language replaces it. |
| The original's qualifier presets file has `//` comments, which is not JSON, and lacks `valueType`. | Whole-line comments and a default value type are read for files made for Package Explorer. |

## Decision

- **Presets are JSON files, one for each kind**, with an array of `{"name", <kind key>}` entries, where the member is in the JSON of the metamodel. `domain/presets.py` parses a text, and `infrastructure/preset_files.py` reads the files. Both treat the content as untrusted: a bad entry or file is a `Problem` with a reason, never an exception.
- **Shipped files are package data** in `aas_editor/presets/`, listed in `aas_manager.spec`. **The user's files** have the same names in the `presets` folder next to `settings.ini`, the folder that holds the other state of the user (`recovery/`), and are not tracked by Git. A user preset with the name of a shipped one replaces it. The files are read each time the dialog opens, as in the original. A later change can move the folder with the rest of the settings.
- **The language is a template with fields and filters** (`domain/rename_pattern.py`), not single characters. It has no variables or loops, it is read by a small parser and run over whitelisted functions, and nothing is evaluated. [Bulk editing](../bulk-editing.md) documents it, with a table that maps the tokens of the original.
- **A bulk change is previewed and refused as a whole.** Each object is `CHANGE`, `UNCHANGED`, `SKIPPED` (nothing to change, which does not stop the others), or `REFUSED` (not allowed, which does). Nothing applies while one is refused, so the package never holds half of a rename. Names are checked against the names after the whole change, so two elements can swap, and an overlap is renamed through temporary names inside the same undo step.
- **An add to many skips what is there.** `plan_attach` skips an owner that cannot have the kind or has the member, names it with the reason, and adds the rest. Nothing is replaced, unlike the original, which removed a blank qualifier when a preset was added.
- **A move of a selection across containers moves in each container.** `plan_bulk_move` makes one plan, finds the new keys of references through moved list items once for all containers, and does not move an element to another parent, which would change its path.

## Consequences

- A preset is as valid as the element it makes, and an SDK that reads more or fewer attributes changes presets with no code of ours.
- Files of Package Explorer can be copied to the presets folder, with the changes the guide lists. Files of this editor are valid AAS JSON apart from the `name`.
- A pattern of the original must be rewritten once. The preview and the refusals replace its silent mistakes.
- Presets live inside the package folder, as the other state does. An installed copy would write there too, which is a known structural problem of the app (see the architecture guide).
- A data specification other than IEC 61360, and a unit-of-measure specification, cannot be a preset until the SDK has content classes for them.

## Alternatives considered

- **A regular expression for the rename.** Rejected: it is hard to write and read for the common cases, and a pattern from a file could cost much time. The filters cover find and replace.
- **Keeping the original's language and fixing it.** Rejected: its tokens depend on the position in a text that is consumed, which hides mistakes, and `§` is hard to type.
- **Applying what is allowed and reporting the rest.** Rejected for refusals: a rename of siblings that is half done is hard to understand and to undo by hand. Skips do not have this problem, so they stay.
- **One file with all kinds.** Rejected: users edit one kind at a time, and the files of Package Explorer are split the same way.
