# Architecture decision records

An architecture decision record (ADR) captures one significant decision, why we made it, and what it costs.
ADRs are immutable: to change a decision, add a new ADR that supersedes the old one.

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-project-layout.md) | `src/` layout and tests organized by size | Accepted |
| [0002](0002-layered-architecture.md) | Layered architecture, adopted incrementally | Accepted |
| [0003](0003-python-style.md) | Google Python style, with legacy code exempted | Accepted |
| [0004](0004-basyx-sdk-pin.md) | Pin the BaSyx SDK fork to a commit | Accepted |
| [0005](0005-metamodel-and-validation.md) | Target metamodel V3.1.x, with validation built on BaSyx | Accepted |
| [0006](0006-safe-save.md) | Write packages atomically, and keep three isolated workarounds for the SDK | Accepted |
| [0007](0007-command-stack-and-change-observer.md) | Edits as commands on AAS objects, reported to an observer | Accepted |
| [0008](0008-values-follow-their-type.md) | Values follow their value type, and a change of the type converts or refuses | Accepted |
| [0009](0009-reference-integrity.md) | Find references by walking the SDK objects, and index them for each operation | Accepted |
| [0010](0010-validation-findings.md) | Validation rules report findings, and a partial load stays partial | Accepted |
| [0011](0011-natural-order-in-trees.md) | Trees show the saved order, and the others are sorted by name | Accepted |
| [0012](0012-replacing-an-element-shows-what-is-lost.md) | Replacing an element builds a new one, shows what is lost, and keeps the references | Accepted |
| [0013](0013-supplementary-files.md) | Stored files change with their references, and never overwrite | Accepted |
| [0014](0014-concept-descriptions-and-iec-61360.md) | Concept descriptions follow the semantic id by id, and IEC 61360 records are built from a checked draft | Accepted |
| [0015](0015-validation-in-the-editor.md) | The rules run in the dock, in hints, and in the save gate, and the marker follows the stack | Accepted |
| [0016](0016-reference-fields-and-creation-dialogs.md) | Reference fields wrap the generated forms, and creation has its own dialogs | Accepted |
| [0017](0017-presets-and-the-pattern-language.md) | Presets are SDK JSON files, and bulk changes use a small pattern language | Accepted |
| [0018](0018-load-report.md) | A package that opens in failsafe mode lists what the SDK left out | Accepted |
| [0019](0019-defaults-and-notices-of-new-objects.md) | New objects start with the defaults of the user, and the editor says what the SDK refuses | Accepted |
| [0020](0020-selection-locations-and-clipboard.md) | A selection moves as a block, and the panel, locations, and clipboard fallback that go with it | Accepted |
| [0021](0021-order-of-the-file-and-concept-description-gaps.md) | The package keeps the order of the file, and the concept description gaps close in the view | Accepted |
| [0022](0022-attribute-vocabulary.md) | Tabs name attributes with a vocabulary of the metamodel, and show what the editor edits unchanged | Accepted |
| [0023](0023-actions-on-the-whole-selection.md) | Delete, cut and copy act on the whole selection, or refuse | Accepted |
| [0024](0024-package-tree-vocabulary-and-layout.md) | The package tree and the cells read in words of the AAS, and a layout that fits the screen | Accepted |
| [0025](0025-design-tokens-and-theme-architecture.md) | One table of design tokens makes the style sheet, the palette, and the colors of text | Accepted |

| [0026](0026-forms-read-in-words-of-the-metamodel.md) | Forms read in the words of the metamodel, and adding to a list starts with its entry | Accepted |
| [0027](0027-bundled-font-and-themed-icons.md) | Inter is bundled, and icons are SVG files that an engine colors by token | Accepted |

To add one, copy the structure of an existing ADR, use the next number, and add it to this table.
Write an ADR for a decision that is expensive to reverse: a new dependency with wide reach, a change to layer boundaries, or a metamodel target.
