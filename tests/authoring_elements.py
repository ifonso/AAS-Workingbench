"""Adds every kind of submodel element through its Add dialog.

The dialogs are the ones the editor generates from the SDK classes. Each
function fills the fields of one dialog as a person does, and the element is
looked up again in the package for the test to read.
"""

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import QDateTime
from PyQt6.QtWidgets import QPushButton
from tests.authoring import Author
from tests.authoring_builders import SUBMODEL
from tests.authoring_builders import add_item
from tests.medium.forms import Form


def external(value: str) -> list[tuple[model.KeyTypes, str]]:
    """Keys of an external reference to a global thing."""
    return [(model.KeyTypes.GLOBAL_REFERENCE, value)]


def pick_semantic_id(
    author: Author, form: Form, target: model.Referable
) -> None:
    """Presses Choose from package on the semantic id, and picks a target."""
    from aas_editor.ui.reference_fields import CHOOSE_TEXT
    from aas_editor.ui.reference_picker import ReferencePickerDialog

    box = form.widget("semantic_id").widget
    (button,) = [
        b for b in box.findChildren(QPushButton) if b.text() == CHOOSE_TEXT
    ]
    with author.answering(
        ReferencePickerDialog, lambda picker: picker.select(target)
    ) as answer:
        button.click()
    author.assert_accepted(answer)


def add_qualifier_and_extension(form: Form) -> None:
    """Gives the element a qualifier, an extension and a supplemental id."""
    entry = add_item(form.widget("qualifier"))
    entry.paramWidgets["type_"].widget.setText("Cardinality")
    value_type = entry.paramWidgets["value_type"].widget
    value_type.setCurrentIndex(value_type.findData(datatypes.String))
    kind = entry.paramWidgets["kind"].widget
    kind.setCurrentIndex(kind.findData(model.QualifierKind.VALUE_QUALIFIER))
    value_button = Form._create_button(entry, "value")
    assert value_button is not None
    value_button.click()
    entry.paramWidgets["value"].widget.set_text("One")

    extension = add_item(form.widget("extension"))
    extension.paramWidgets["name"].widget.setText("origin")

    supplemental = add_item(form.widget("supplemental_semantic_id"))
    Form(None).fill_reference_box(
        supplemental.widget, external("urn:example:supplemental")
    )


def add_voltage(author: Author, concept: model.ConceptDescription) -> None:
    """An Int Property with every common attribute and a picked semantic id."""

    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("value", "230")
        form.type_text("category", "PARAMETER")
        form.add_language("display_name", "en", "Voltage")
        form.add_language("display_name", "de", "Spannung")
        form.add_language("description", "en", "The supply voltage")
        form.add_language("description", "de", "Die Versorgungsspannung")
        pick_semantic_id(author, form, concept)
        add_qualifier_and_extension(form)

    answer = author.add_element(SUBMODEL, model.Property, "Voltage", fill)
    author.assert_accepted(answer)


def add_language_property(author: Author) -> None:
    """A MultiLanguageProperty with two languages."""

    def fill(form: Form) -> None:
        form.add_language("value", "en", "Main pump")
        form.add_language("value", "de", "Hauptpumpe")

    answer = author.add_element(
        SUBMODEL, model.MultiLanguageProperty, "Label", fill
    )
    author.assert_accepted(answer)


def add_range(author: Author) -> None:
    """A Range of Int."""

    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("min", "1")
        form.type_text("max", "10")

    answer = author.add_element(SUBMODEL, model.Range, "Limits", fill)
    author.assert_accepted(answer)


def add_blob(author: Author, path: tuple[str, ...], name: str) -> None:
    """A Blob with a text content type and a short text."""

    def fill(form: Form) -> None:
        form.type_text("content_type", "text/plain")
        form.widget("value").widget.editor.setPlainText("hello")

    answer = author.add_element(path, model.Blob, name, fill)
    author.assert_accepted(answer)


def add_file(author: Author, path: tuple[str, ...], name: str) -> None:
    """A File element that refers to nothing yet."""

    def fill(form: Form) -> None:
        form.type_text("content_type", "text/plain")

    answer = author.add_element(path, model.File, name, fill)
    author.assert_accepted(answer)


def add_reference_element(author: Author, target: str) -> None:
    """A ReferenceElement to a global thing."""
    answer = author.add_element(
        SUBMODEL,
        model.ReferenceElement,
        "Ref",
        lambda form: form.fill_reference("value", external(target)),
    )
    author.assert_accepted(answer)


def add_relationships(author: Author) -> None:
    """A RelationshipElement and an AnnotatedRelationshipElement."""

    def fill(form: Form) -> None:
        form.fill_reference("first", external("urn:example:a"))
        form.fill_reference("second", external("urn:example:b"))

    answer = author.add_element(
        SUBMODEL, model.RelationshipElement, "Rel", fill
    )
    author.assert_accepted(answer)
    answer = author.add_element(
        SUBMODEL, model.AnnotatedRelationshipElement, "Annotated", fill
    )
    author.assert_accepted(answer)
    answer = author.add_element(
        (*SUBMODEL, "Annotated"),
        model.Property,
        "Note",
        lambda form: form.type_text("value", "checked"),
    )
    author.assert_accepted(answer)


def add_entity(author: Author) -> None:
    """A self-managed Entity with a statement."""

    def fill(form: Form) -> None:
        form.choose("entity_type", model.EntityType.SELF_MANAGED_ENTITY)
        form.type_text("global_asset_id", "urn:example:asset:machine")

    answer = author.add_element(SUBMODEL, model.Entity, "Machine", fill)
    author.assert_accepted(answer)
    answer = author.add_element(
        (*SUBMODEL, "Machine"),
        model.Property,
        "Role",
        lambda form: form.type_text("value", "pump"),
    )
    author.assert_accepted(answer)


def add_operation(author: Author) -> None:
    """An Operation with an input and an output variable."""
    answer = author.add_element(SUBMODEL, model.Operation, "Start")
    author.assert_accepted(answer)
    for variable, name in (
        ("input_variable", "Speed"),
        ("output_variable", "Done"),
    ):
        answer = author.add_element(
            (*SUBMODEL, "Start", variable),
            model.Property,
            name,
            lambda form: form.type_text("value", "1"),
        )
        author.assert_accepted(answer)


def add_capability(author: Author) -> None:
    answer = author.add_element(SUBMODEL, model.Capability, "CanStart")
    author.assert_accepted(answer)


def add_event(author: Author) -> None:
    """A BasicEventElement that observes the Voltage."""

    def fill(form: Form) -> None:
        form.fill_model_reference(
            "observed",
            [
                (model.KeyTypes.SUBMODEL, "urn:example:sm:everything"),
                (model.KeyTypes.PROPERTY, "Voltage"),
            ],
            model.Property,
        )
        form.choose("direction", model.Direction.OUTPUT)
        form.choose("state", model.StateOfEvent.ON)
        form.type_text("message_topic", "plant/voltage")
        moment = form.widget("last_update").widget
        moment.dateTimeEdit.setDateTime(QDateTime(2024, 5, 31, 13, 45, 0))
        zone = moment.tzinfoEdit.widget
        zone.setCurrentIndex(zone.findData("UTC"))

    answer = author.add_element(
        SUBMODEL, model.BasicEventElement, "Alarm", fill
    )
    author.assert_accepted(answer)


def add_collections_and_lists(author: Author) -> None:
    """A collection that holds a collection, a list of numbers, and a list of collections."""
    answer = author.add_element(
        SUBMODEL, model.SubmodelElementCollection, "Group"
    )
    author.assert_accepted(answer)
    group = (*SUBMODEL, "Group")
    answer = author.add_element(
        group,
        model.Property,
        "Speed",
        lambda form: (
            form.choose("value_type", datatypes.Int),
            form.type_text("value", "1500"),
        ),
    )
    author.assert_accepted(answer)
    answer = author.add_element(group, model.SubmodelElementCollection, "Inner")
    author.assert_accepted(answer)
    add_file(author, (*group, "Inner"), "Manual")
    add_blob(author, (*group, "Inner"), "Certificate")

    def numbers(form: Form) -> None:
        form.choose("type_value_list_element", model.Property)
        form.choose("value_type_list_element", datatypes.Int)

    answer = author.add_element(
        group, model.SubmodelElementList, "Readings", numbers
    )
    author.assert_accepted(answer)
    for number in ("11", "12"):
        answer = author.add_element(
            (*group, "Readings"),
            model.Property,
            None,
            lambda form, number=number: form.type_text("value", number),
        )
        author.assert_accepted(answer)

    answer = author.add_element(
        group,
        model.SubmodelElementList,
        "Rows",
        lambda form: form.choose(
            "type_value_list_element", model.SubmodelElementCollection
        ),
    )
    author.assert_accepted(answer)
    answer = author.add_element(
        (*group, "Rows"), model.SubmodelElementCollection, None
    )
    author.assert_accepted(answer)
