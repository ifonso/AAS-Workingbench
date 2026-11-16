# ADR 0035: The icons of the kinds of elements are colored by family

**Status:** Accepted. Changes a point of [ADR 0027](0027-bundled-font-and-themed-icons.md).

## Context

ADR 0027 drew the 24 icons of the kinds of elements in the accent of the application, so every icon of a tree was the same blue, and only the shape and the letters told a property from an operation.

The UI proposals (`design/ui-proposals.md`, 1.4) give each family of kinds a color of its own, in the light and the dark theme, and ask to measure their contrast against the surfaces before they enter the tokens.

## Decision

- Five color tokens, in both themes, `kind_structure`, `kind_container`, `kind_data`, `kind_behavior` and `kind_relation`, with the values of the proposal:

  | Token | Kinds | Light | Dark |
  |---|---|---|---|
  | `kind_structure` | Shell, Submodel, Concept description, Asset information, Submodel reference | `#0f6cbd` | `#479ef5` |
  | `kind_container` | Collection, List, Entity | `#00727a` | `#4cc2c8` |
  | `kind_data` | Property, Range, MultiLanguageProperty, File, Blob | `#6b3fa0` | `#b696e0` |
  | `kind_behavior` | Capability, Operation, BasicEventElement | `#a3247c` | `#e58bc9` |
  | `kind_relation` | Relationship, AnnotatedRelationship, ReferenceElement | `#4f52b2` | `#9ea2f2` |

- The colors avoid red, orange and green, which already say error, warning and success.
- Each is an icon pair of `CONTRAST_PAIRS` on every surface of a tree, at 3 to 1 at least, which a test checks in both themes. The lowest measured is 3.69, `kind_structure` on `bg_pressed` in the dark theme.
- `kind_icons.KIND_ROLES` gives each file of `icons/kinds/` the role of its family. The annotations (qualifier, extension, specific asset id, reference, data specification) keep the accent, as before.

## Consequences

- A tree tells the families apart at a glance. The shape, the letters and the tooltip still say the kind, so the color is never alone.
- A new kind needs a family, or it is drawn in the accent.
- A switch of theme recolors the icons, because `ThemedIconEngine` reads the token when it draws (ADR 0027).
