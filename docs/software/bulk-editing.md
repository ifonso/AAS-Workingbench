# Bulk editing and presets

This guide describes the actions that change many selected objects at once, the pattern language of "Change attribute with a pattern...", and the preset files.
The design decisions are in [ADR 0017](adr/0017-presets-and-the-pattern-language.md).

All actions are in the context menu of the package tree.
Each one is a single undo step, is disabled in Read mode, and either changes everything or nothing.

## Actions

| Action | What it does |
|---|---|
| Change attribute with a pattern... | Changes the idShort, description, display name, or text value of the selected objects. A table shows the result for every object before anything changes. |
| Remove extensions... | Lists the extensions of the selected objects by name or by semantic id, with counts, and removes the chosen group. |
| Add qualifier, extension, specific asset id, or data specification from preset... | Adds a member from a list of presets to every selected object that can have it. |
| Add qualifier, extension, or specific asset id from clipboard | Adds the member (or members) that the system clipboard holds as JSON. |
| Move up, down, to top, to end | Moves the selected rows. A selection across several collections, lists, or submodels moves in each container. |

### Concept descriptions for a selection

The actions of the concept description tools work on every selected submodel or element, so no separate bulk action exists:

| Action | For a selection |
|---|---|
| Assign concept description... | Gives all selected elements the chosen description as semantic id. A semantic id that is set is replaced only after a list of the old and the new ones was confirmed. |
| Auto-detect concept descriptions... | Gives each selected element, and everything below it, that has no semantic id the description with its idShort, after a preview. It never replaces a semantic id. |
| Create concept descriptions from all semantic ids... | Adds a description for each semantic id below the selection that has none. |
| Fix data specification keys... | Looks at the selected descriptions, or at all of them when none is selected. |

Each is one undo step. See ADR 0014 for how a description is found.

### Which objects take what

| Kind | Objects |
|---|---|
| Qualifier | A submodel and every submodel element |
| Extension | Every shell, submodel, concept description, and submodel element |
| Specific asset id | The asset information of a shell (select the shell), and a self-managed entity |
| Data specification | Every shell, submodel, concept description, and submodel element |

A selected object that cannot have the kind is skipped.
So is an object that has the member already: a qualifier of the same type (AASd-021), an extension of the same name (AASd-077), an equal specific asset id, or the same data specification.
The others still get theirs, and the dialog names each skipped object with the reason.
Nothing is replaced.

### What is refused

A change of an attribute shows one of four results for each object:

| Result | Meaning |
|---|---|
| Changes | The attribute gets the new text. |
| Unchanged | The pattern gives the text it has. |
| Skipped | The object has nothing to change: no text in the chosen language, no text value, or an item of a list, which has no idShort. The others still change. |
| Refused | The new text is not allowed. The reason is shown, and **nothing can be applied** until the pattern or the selection changes. |

A new idShort is refused when it is not valid (AASd-002), or when a sibling has it.
Siblings are compared after the whole change, so two elements can swap names.
A text is refused when it is empty or longer than the metamodel allows (1023 characters for a description, 128 for a display name).
A value is refused when it does not fit the value type of the Property.

A rename of an idShort updates every reference through the renamed elements in the same step, as the single rename does.
The table says how many references change.

## The pattern language

A pattern is text with fields in braces.
The text is copied as it is, and each field is replaced by a value.
Filters after a bar change the value on its way.
Nothing is evaluated: there are no variables, loops, or regular expressions, and a pattern that is not in this language is refused with the place of the problem.

```text
pattern  := ( text | '{{' | '}}' | field )*
field    := '{' name ( '|' filter )* '}'
filter   := name [ '(' argument ( ',' argument )* ')' ]
argument := whole number | "text in double quotes"
```

`{{` and `}}` are a literal brace.
In a text in double quotes, `\"` is a quote and `\\` is a backslash.
Spaces around names, bars, commas, and parentheses are ignored.
A pattern has at most 1000 characters, and a result at most 10000.

### Fields

| Field | Value |
|---|---|
| `old` | The current value of the attribute that is changed |
| `idShort` | The idShort of the object |
| `parent` | The idShort of its parent, or empty |
| `type` | The class of the object, such as `Property` |
| `number` | The position of the object among the selected ones, from 1, in the order of the tree |
| `count` | How many objects are selected |

### Filters

| Filter | Effect |
|---|---|
| `upper`, `lower` | Letter case of the whole text |
| `capitalize` | The first character in upper case, the rest unchanged |
| `trim` | Drops spaces at both ends |
| `reverse` | Reverses the characters |
| `slice(a)`, `slice(a,b)` | The characters from `a` up to `b`, counted from 0. A negative number counts from the end. |
| `replace("x","y")` | Replaces every `x` by `y`. `x` must not be empty. |
| `remove("x")` | Drops every `x` |
| `strip_prefix("x")`, `strip_suffix("x")` | Drops `x` from the start or the end, if it is there |
| `default("x")` | Gives `x` when the text is empty |
| `pad(n)`, `pad(n,"c")` | Puts `c` (default `0`) at the start up to `n` characters |
| `add(n)` | Adds the whole number `n` to a text that is a number |
| `to_id_short` | Repairs the text into a valid idShort |

### Examples

| Pattern | Applied to | Gives |
|---|---|---|
| `ABC_{old}` | `Foo` | `ABC_Foo` |
| `{old}_XYZ` | `Foo` | `Foo_XYZ` |
| `{old\|upper}` | `foo` | `FOO` |
| `{old\|slice(0,1)\|upper}{old\|slice(1)}` | `foo` | `Foo` |
| `{old\|slice(1)}` | `foo` | `oo` |
| `__{old\|slice(0,3)}__{old\|slice(3)}` | `abcdef` | `__abc__def` |
| `{old\|reverse}` | `abc` | `cba` |
| `{old\|replace("Temp","Temperature")}` | `TempMax` | `TemperatureMax` |
| `Item{number\|pad(3)}` | the 7th object | `Item007` |
| `{parent}_{old}` | `Inner` in `Group` | `Group_Inner` |
| `Item{old\|strip_prefix("Item")\|add(1)}` | `Item2` | `Item3` |

### Differences from Package Explorer

Package Explorer has a language of single characters (`*`, `?`, `^`, `§`, `~`, `<`).
This editor does not use it, because it has defects that cannot be kept for parity, and because the result of a pattern should be readable.
A pattern is never half applied, it is previewed, and a result that is invalid or duplicates a name is refused with a reason.
The tokens map like this:

| Package Explorer | Here |
|---|---|
| `*` (the whole value) | `{old}` |
| `ABC_*` | `ABC_{old}` |
| `^` or `§` followed by `>` (all upper or lower case) | `{old\|upper}`, `{old\|lower}` |
| `?` (the next character) | `{old\|slice(0,1)}` and `{old\|slice(1)}` |
| `~` (skip a character) | `{old\|slice(1)}` |
| `<` (reverse, broken in the original) | `{old\|reverse}` |

## Presets

A preset is a named qualifier, extension, specific asset id, or data specification.
Presets are JSON files, one for each kind.
The files that come with the app are in `src/aas_workingbench/presets/`.
The files of the user have the same names, and are in the `presets` folder next to `settings.ini` (`src/aas_workingbench/settings/presets/`, which is not tracked by Git).
The dialog has a button that opens this folder.

| File | Key of the member in an entry |
|---|---|
| `qualifiers.json` | `qualifier` |
| `extensions.json` | `extension` |
| `specific-asset-ids.json` | `specificAssetId` |
| `data-specifications.json` | `embeddedDataSpecification` |

The files are read each time the dialog opens, so an edit applies at once.
A preset of the user with the name of a shipped preset replaces it.
Names with a bar, such as `Submodel templates | Cardinality = One`, show the text before the bar as a group, and the dialog's filter searches the whole name.

A file is an array of entries.
Each entry has a `name` and the member in the JSON of the metamodel, so the SDK reads it:

```json
[
  {
    "name": "Submodel templates | Cardinality = One",
    "qualifier": {
      "kind": "TemplateQualifier",
      "type": "SMT/Cardinality",
      "valueType": "xs:string",
      "value": "One",
      "semanticId": {
        "type": "ExternalReference",
        "keys": [
          {
            "type": "GlobalReference",
            "value": "https://admin-shell.io/SubmodelTemplates/Cardinality/1/0"
          }
        ]
      }
    }
  }
]
```

A `null` in an object is the same as leaving the attribute out.
Whole lines that start with `//` are comments.

### A specific asset id without a value

The SDK refuses a specific asset id with an empty value.
A preset with `"value": ""` (or no value) asks for the value when it is used, and the dialog's Add button waits for it.

### Data specifications

The SDK has a content class for IEC 61360 only.
A preset of a data specification must therefore have IEC 61360 content, and needs at least one preferred name.
The shipped preset uses the placeholder "Preferred name", which the user then edits.

### Files from Package Explorer

The files of Package Explorer can be copied into the presets folder of the user, with the names above.
They are read as they are, except that `upgradeFrom` is ignored and `pair` is read as `specificAssetId`.
A qualifier without `valueType`, and an extension with a value and no `valueType`, are `xs:string`.
A data specification entry `{"name": ..., "value": <url>}` is read for the IEC 61360 template, and refused for any other.

### Bad files

A preset file is treated as untrusted data.
A file that is missing is fine for the user, a file that is not UTF-8 text, is not JSON, is not an array, is nested too deeply, or has more than 2 million characters or 5000 entries is refused as a whole.
An entry that is not valid is refused alone, with its number, its name, and the reason, such as `Entry 2 ('Worse'): The value: '7x' is not a valid xs:int`.
The dialog shows how many problems there are and lists them.
The other entries still work, and the editor does not stop.

### What the shipped files leave out

The shipped files are those of Package Explorer, without these entries:

| Entry | Reason |
|---|---|
| `Submodel templates \| EitherOr` | It had the semantic id of Cardinality, which cannot be right |
| `Catena-X ManufacturerID` (the second copy) | A duplicate |
| `Predicate relation \| Requirement`, `Expression semantic \| Actual value` | Copies of other entries with a wrong value |
| `GenericForms plugin \| ...` | Entries for a plugin that this editor does not have. Add them to the user file if they are needed. |
| `ISO 13584` | The SDK has no content class for it |

The extension "Main app | Submodel template attribute set" has no value, because the value of the original was animation arguments.

## Qualifiers and extensions from the clipboard

The clipboard text is JSON: one object, or an array of objects, in the serialization of the metamodel.
An object may carry `"modelType": "Qualifier"`, `"Extension"`, or `"SpecificAssetId"`.
One that names something else is refused: `This is a Property, not a Qualifier`.
Text that is not JSON, that has an attribute missing, or whose value does not fit its value type is refused with the reason.
Unknown attributes are ignored, as the SDK ignores them.
Every selected object gets its own copy.
