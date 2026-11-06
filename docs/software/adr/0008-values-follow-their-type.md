# ADR 0008: Values follow their value type, and a change of the type converts or refuses

**Status:** Accepted

## Context

A Property, a Range, a Qualifier, and an Extension hold a value of the type that their `value_type` names.
Probes against the pinned SDK (ADR 0004) and the editor found:

| Finding | Consequence |
|---|---|
| `Property.value` is typed as a union of 30 XSD classes, and the forms are generated from type hints. | The form asked the user to choose a Python class for the value, and offered a text line only after that. |
| The `value` setter casts only trivially (`trivial_cast`). Text for an `xs:int` is refused with `TypeError`, and a Property with no value could not get one by typing. | The editor must parse text itself. |
| `value_type` is a plain attribute. Setting it leaves the value in the old type. | A saved package can hold `xs:int` with the value `abc`. The SDK writes it, and then cannot read the file back (`ValueError: invalid literal for int()`). |
| `from_xsd` is the SDK's parser, but Python's `int`, `float`, and `bytes.fromhex` behind it accept `1_000`, ` 12`, `infinity`, `nan`, and hex with spaces. It does not check the alphabet of `base64Binary`, `anyURI`, or the day of a `gMonthDay`, and a `float` or `double` that is too large becomes infinity. | A typo can turn into a different value without a message. |
| `SubmodelElementList` has no setters for `type_value_list_element`, `order_relevant`, `semantic_id_list_element`, and `value_type_list_element`, and it refuses a wrong child (AASd-107, 108, 109, 114). | These attributes are set when the list is made. A new child has one possible type. |
| `LangStringSet` refuses a language tag that is not well-formed BCP 47, but only when the object is built, with one sentence and a traceback in the editor. | The user learns the reason too late, and the legacy forms showed it as an error with a traceback. |
| `ConstrainedList` (supplemental semantic ids) is no `list`, and a selected row of a tab lists one index for each cell. | Deleting a supplemental semantic id failed, and when it worked it deleted once for each column. |

## Decision

- **Parsing and formatting live in `domain/value_types.py`.** It delegates to `from_xsd` and `xsd_repr`, adds the checks above, collapses whitespace as XSD says (not for `string` and `normalizedString`), and raises `InvalidValueError` with a message that names the text, the type, and the reason.
- **Text is parsed in one place: the item model.** `StandardTable.attributeCommand` calls `domain/typed_values.prepare_edit` for the value attributes of the four classes. The cell editor (`ValueLineEdit`), the dialog for one value (`ValueEditDialog`), and the forms (`TypedValueInputWidget`) pass text or a typed value, and all of them check against the same function. An empty text clears a value, except for `string` and `normalizedString`, where it is an empty value.
- **A Range keeps its minimum at or below its maximum** for the types that have an order (numbers, `date`, `dateTime`, `time`). It is checked in the cell, the dialog, and the add dialog.
- **A change of the value type converts the values through their text, in one undoable step (`SetValueType`), or is refused and changes nothing.** `"12"` as `xs:string` becomes the `xs:int` 12, and `"abc"` does not. The message names the value and says to clear or change it first. A Property or Range in a list that fixes the value type cannot leave it (AASd-109).
  The editor never clears or keeps a value without telling.
- **The Blob editor shows text when the bytes are valid UTF-8 without control characters other than tab and line breaks, and one kind of line break, and hex otherwise.** It returns the exact bytes while the user changes nothing, keeps `\r\n` as it was, and does not show content above 1 MiB. Files are loaded and saved from the editor and from two context menu actions. The user never types a Python literal.
- **Language tags are checked for being well-formed (RFC 5646), with the syntax of the SDK and no registry.** `domain/language_tags.py` uses the standard library only. A registry check would need the IANA subtag registry as data, which is a dependency for little gain. The editor also refuses an empty text and a language that another entry uses.
- **A new child of a list gets a dialog made for the type of the list**, with the value type hidden and fixed, and the semantic id filled in. There is no type chooser, because the SDK allows no other type. The attributes of the list itself can be chosen when the list is made, and cannot be changed afterwards.
- **A list of members includes the SDK's `ConstrainedList`**, through `domain.containers.is_list_like`, and a selected row is one item however many cells it lists.

## Consequences

- The legacy forms show `xs:` names for value types, and one line for a value. Strings with line breaks cannot be typed in the line. They are shown and kept, and edited in a later multi-line editor.
- A conversion goes through the lexical form, so `xs:double` 3.5 does not become `xs:int`, and an `xs:int` 300 does not become `xs:byte`. `xs:string` to `xs:date` works only when the text is a date.
- Changing the order, the semantic id, or the child type of an existing list needs a new list. That belongs to the conversion work package (WP8b).
- A language registry check, if the validation rules want one, is added to `language_tags.py` with its data, and nothing else changes.
- The tests that exercise the dialogs replace `exec` and fill the generated widgets (`tests/medium/forms.py`), so they follow the generated forms and need a change when those change.

## Alternatives considered

- **Keep editable lists of types, as the original does.** Rejected because a typo then silently changes a type or throws, and the original's list accepts text that is no type.
- **Clear the value when the type changes.** Rejected because it loses data without asking. The user can clear it on purpose before the change.
- **Keep the value in the old type when the type changes.** Rejected because the file can then be written but not read again.
- **Parse in the widgets.** Rejected because the model is the one place all edits pass, including programmatic ones, and the widgets would repeat the rules.
- **A BCP 47 library such as `langcodes`.** Rejected for now: it brings a registry as a dependency, and the SDK already decides what is accepted.
