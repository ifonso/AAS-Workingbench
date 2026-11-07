# ADR 0026: Forms read in the words of the metamodel, and adding to a list starts with its entry

**Status:** Accepted

## Context

[ADR 0022](0022-attribute-vocabulary.md) gave the tabs the names of the metamodel and left the generated forms alone. The forms are built from the constructor of a class of the SDK, so a form for a qualifier read:

- `type*`, `value_type*`, `value`, `value_id`, `kind`, `semantic_id`, `supplemental_semantic_id`: the Python names that the tab beside it no longer shows,
- a "Create" button for each optional attribute,
- under `supplemental_semantic_id`, a box with an "Add Item" button and nothing else.

Adding a qualifier from the tab took four actions before the first field: select the element, select the `qualifier` row, press `+`, and press "Add Item" in a dialog that held only that button ([UI and UX plan](../../planning/ui-ux-plan.md), problem U2).

A probe of what finds a field of a form found these places:

- `ObjGroupBox.paramWidgets` maps the **name of the parameter of the SDK** to its widget, and `CreateOptionalParamBtn.paramName` holds the same name. Creating, filling, and reading an object use these, and so does `tests/medium/forms.py` and every test that uses it.
- `_rowOfParam` looked for the row of the global asset id of an entity by the **text of its label**. This was the only place that did.
- The label was made by `QFormLayout.addRow(str, widget)`, which sets a buddy but gives the code no hook for a tooltip.
- `IterableGroupBox` is the box of any list or set. It is also the top-level widget of the dialog that adds to a list attribute (`onAddAct` of a tab, with the type hint of the attribute). Inside another form it is one field of many.

## Decision

- **The label of a field is the name of the metamodel, from the vocabulary of ADR 0022.** `domain/form_labels.py` (no Qt) gives `field_label(owner, param, attribute, required)`: the name, the mark for a required field (`*`, as before), and the description. The attribute is the one that holds the parameter (`type` for `type_`, `id` for `id_`), which `ObjGroupBox` already knew through `paramsToAttrs`. A parameter that the vocabulary has no entry for keeps its name without the trailing underscore. A test walks every class that a form is made for and fails for a field that is shown in Python.
- **The description is the tooltip** of the label and of the field, when the field has none of its own.
- **A field is found by the name of the SDK, never by its label.** The label is a `QLabel` with the dynamic property `sdkName` and a buddy (the field), so a screen reader names the field. `ObjGroupBox.labelOf(param)` returns it, and `_rowOfParam` finds a row by its widget, not by text. `paramWidgets`, `paramName`, and `tests/medium/forms.py` are unchanged, and `Form.label` and `Form.tooltip` give tests the words a user reads.
- **The add dialog of a list starts with one empty entry.** `addItemWithDialog` asks `EditObjDialog` for `firstEntry`, and the dialog calls `IterableGroupBox.startWithEntry` once the form is in it. The entry is made by the code of "Add Item", so the same fields, defaults and checks apply, and the focus goes to its first field (`type` for a qualifier). "Add Item" stays for a second entry. The rule is for a new object (`objVal is None`) of an add. Editing, pasting, and the lists inside a form do not start with an entry.
- **The dialog is titled with the name of the metamodel**: `Add supplementalSemanticId element`, not `Add supplemental_semantic_id element`.
- **The "Create" button keeps its text.** It stands for "give this optional attribute a value", and is not changed here. The "More" section that the plan describes is not built.

## Consequences

- A form for a qualifier reads `type*`, `valueType*`, `value`, `valueId`, `kind`, `semanticId`, `supplementalSemanticId`, with a hover that says what each is. Adding one takes the select of the row, the `+`, and typing in `type`.
- An OK on a new entry that is left empty is refused with the message of the SDK, as an empty `type` always was, and the dialog stays open. To add nothing the user presses Cancel.
- A test that pressed "Add Item" in the first step of an add dialog for a list (the submodel references of a shell) was changed: the entry is there already.
- A later class or attribute that the vocabulary lacks fails the walk of the forms, as it fails the walk of the tabs.
- The class name that titles an entry (`Qualifier 1`) and the labels `key` and `value` of a language entry are not translated by this change. The first is the class of the SDK, and the second is what the vocabulary says for `DictItem`.
  - *Settled in phase K:* an entry is titled by `entry_title` (`Text 1` for a language entry, `Reference 1` for a model or external reference), a language entry reads `language` and `text` in a form only, and a box no longer hands its title to the list or reference inside it, which showed `Qualifier 1` over the supplemental semantic ids.
- The buttons "Create", "Add Item" and "Choose from local", and the styling of the forms, are for later phases.

## Alternatives considered

- **Find the field by its label and keep the Python label.** Rejected: it fixes nothing the user sees.
- **Rename the key of `paramWidgets` to the metamodel name.** Rejected: ADR 0022 refused to rename what editing reads, and the keys are what the SDK constructor takes.
- **Add the entry in every `IterableGroupBox`.** Rejected: a list inside a form is optional, and an empty entry would be refused at OK, which makes each such form fail until the user finds the X.
- **Add the entry in the tab and pass it to the dialog.** Rejected: the dialog already owns the form and its focus.
- **Give a `QLabel` subclass with its own tooltip logic.** Rejected: a property and a tooltip on a plain label are enough.
