# ADR 0019: New objects start with the defaults of the user, and the editor says what the SDK refuses

**Status:** Accepted

## Context

Package Explorer gives new objects defaults that differ by path, and it leaves some mistakes to a hint. Its specification (F-EDT-02, 04, 06 and 07, section 5 and 9) lists them, and asks the reimplementation to decide the cases that it calls open.
Probes against the pinned SDK (commit `412a53f`) found:

| Finding | Consequence |
|---|---|
| `AssetKind` has `Type`, `Instance`, `NotApplicable` and `Role`. `Batch` is a literal of metamodel V3.2 (`changelog.adoc` of Part 1, in the specification of the original). A file with `"assetKind": "Batch"` raises `KeyError` in strict mode, and in failsafe mode the whole shell is skipped. | `Batch` cannot be offered or read. The case is the one of the plan's "Metamodel V3.2" row. |
| `Add AAS` of the original makes `NotApplicable`, `Create data element` of AssetInformation makes `Type`, and its own notice says "'Instance' is the usual choice". | The default of the original is no one's decision. |
| A `LangStringSet` refuses an empty text (1..1023 characters, 1..128 for a display name) and an empty set. `Extension` and `SpecificAssetId` refuse an empty name. | The model cannot hold the empty row that "Create w/ default" and `DefaultLangs` make. |
| A self-managed `Entity` needs a global or a specific asset id (AASd-014). | A new entity must name its asset in the dialog that makes it. |
| A `Qualifier` accepts a new `type`, `value_type`, `value` and references in place, in the order value, value type, value. A type that a sibling has raises `KeyError`. | A paste into a qualifier is a group of commands, and the conflict is found before the first one. |
| `AssetInformation.specific_asset_id` is a list with no null. Removing the last one is refused when there is no global asset id (AASd-131), and the writers leave an empty list out. | "The list is absent" is true in the file, and the refusal is the SDK's. |

## Decision

- **A new AAS has the asset kind Instance.** The decision of the specification's D2 is open ("unify after a product decision, and document the choice"). Instance is the kind that the original's own notice names as usual, and the dialog lets the user choose any of the four kinds. A new submodel is an Instance too, as in the original.
- **`Batch` is not offered and not read.** The editor targets V3.1 (D1). A file with it is refused as a whole, and failsafe mode drops the shell and marks the package partial (D6), which the question at opening already says.
- **The category stays editable, with the deprecation hint.** The specification asks for a read-only row (F-EDT-06 AC16), as the original has. The metamodel V3.1 still has the attribute, the rules AASc-3a-004 to 007 tie the category of a concept description to its data type, so a user has to be able to correct it, and the editor could edit it before. A hint says that it is deprecated.
- **Default languages and id templates are settings, kept as texts.** `domain/default_languages.py` and `domain/id_templates.py` read and check the texts, and `ui/user_defaults.py` is the one place that reads `AppSettings`, so dialogs never ask the settings themselves. A text that cannot be read gives English or a `urn:uuid:` id, so a hand-edited file does no harm. The template format of the original is kept (`D`, `X` and `A`), with a backslash to make a character literal, which its specification recommends, and with the random digits from `secrets`. A template without a placeholder is refused in the settings dialog, because every id would be the same. D14 stays the default.
- **An empty language row is a row of the dialog, not of the model.** A new MultiLanguageProperty shows one row for each default language. A row that stays empty is left out when the element is made, and no row with a text gives no value.
- **Notices are hint rules.** A missing or one-language display name and description, and a self-managed entity without a global asset id, are `Info` findings of `domain/validation/rules/hints.py`. The form of a new entity shows the same sentence while the global asset id is empty, and the form of an extension says that a name is needed while it is blank. Hints mode switches them off, and they never block.
- **Base64 conversion is an action of the Blob, with no question.** The original asks "cannot be reverted", and the editor has undo. A text that is no Base64 is refused with the first wrong character or the length, and nothing changes. The conversion is about the content. The files store a Blob as Base64 either way.
- **A paste into a qualifier keeps its kind.** The specification asks for parity or a documented difference. The original keeps the kind, and a TemplateQualifier should not become another kind by text from somewhere else.
- **A language entry moves by its language.** A mapping holds no member objects, so `ReorderLanguages` names the keys, and the views read the set again after it.

## Consequences

- The Settings dialog has two more boxes, and scrolls on a small screen.
- Tests of hints must give their objects a display name and a description in two languages to expect no hint. The new notices appear in the bar of every plain element of a package.
- The default of Create AAS differs from Package Explorer's `Add AAS`. A user who wants NotApplicable chooses it in the dialog.
- `Batch` becomes possible with the SDK that implements V3.2, and the default kind and the list in `domain/asset_information.py` are the places to change.

## Alternatives considered

- **NotApplicable as the default, for parity.** Rejected: the original's own notice says that Instance is the usual choice, and a user would be asked to correct the default almost every time.
- **Creating the empty language entry anyway.** Rejected: the SDK refuses it, and a workaround would need a hand-made text that the model could not hold (D3).
- **Making the category read-only, as the specification says.** Tried and rejected: it removes an edit that users have, and with it a finding of AASc-3a-004 to 007 could be fixed only by changing the data type.
- **Asking before a Base64 conversion.** Rejected: the question exists in the original because nothing can be undone there.
- **One setting for all id templates.** Rejected: the original has one for each kind, and users write them for one kind at a time.
