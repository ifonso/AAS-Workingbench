"""All 14 submodel element types: create, edit, undo, save, and reload.

Each case makes the element through the real add dialog, which is generated
from the constructor of the BaSyx class. `exec` of the dialog is replaced, so
that the test fills the widgets as a user would and accepts. The edit goes
through the models and dialogs of the views. After the edit the package is
saved as AASX and read again, and compared with the SDK serialization.

A second test compares the form and the attribute list of each class with the
constructor of the class, so that an attribute that a new SDK adds fails it.
"""

from collections.abc import Callable
from dataclasses import dataclass
import datetime
import inspect
from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import QDateTime
import pytest
from tests.medium.forms import Form
from tests.serialization import snapshot

from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH

URL = "https://example.com/files/data.txt"


@dataclass
class Case:
    """How to make, change, and check one type of element."""

    element_type: type
    fill: Callable[[Form], None]
    check_created: Callable[[Any], None]
    edit: Callable[[Any, Any], None]
    check_edited: Callable[[Any], None]
    # How many edits the editor refuses with a message while editing.
    refusals: int = 0


def _global(value: str) -> list[tuple[model.KeyTypes, str]]:
    return [(model.KeyTypes.GLOBAL_REFERENCE, value)]


def _property() -> Case:
    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("value", "7")

    def created(element: model.Property) -> None:
        assert element.value_type is datatypes.Int
        assert element.value == 7
        assert isinstance(element.value, datatypes.Int)

    def edit(lab: Any, attrs: Any) -> None:
        assert lab.set(attrs, "value", "12")

    def edited(element: model.Property) -> None:
        assert element.value == 12
        assert isinstance(element.value, datatypes.Int)

    return Case(model.Property, fill, created, edit, edited)


def _multi_language_property() -> Case:
    def fill(form: Form) -> None:
        form.add_language("value", "en", "Hello")
        form.add_language("value", "de", "Hallo")

    def created(element: model.MultiLanguageProperty) -> None:
        assert dict(element.value or {}) == {"en": "Hello", "de": "Hallo"}

    def edit(lab: Any, attrs: Any) -> None:
        from aas_editor.additional.classes import DictItem

        assert lab.set(attrs, "value", DictItem("en", "Hi"), "DictItem 0"), (
            lab.refusal
        )

    def edited(element: model.MultiLanguageProperty) -> None:
        assert dict(element.value or {}) == {"en": "Hi", "de": "Hallo"}

    return Case(model.MultiLanguageProperty, fill, created, edit, edited)


def _range() -> Case:
    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("min", "1")
        form.type_text("max", "10")

    def created(element: model.Range) -> None:
        assert (element.min, element.max) == (1, 10)
        assert isinstance(element.max, datatypes.Int)

    def edit(lab: Any, attrs: Any) -> None:
        assert lab.set(attrs, "max", "20")
        assert not lab.set(attrs, "min", "30")

    def edited(element: model.Range) -> None:
        assert (element.min, element.max) == (1, 20)

    return Case(model.Range, fill, created, edit, edited, refusals=1)


def _file() -> Case:
    def fill(form: Form) -> None:
        form.type_text("content_type", "text/plain")
        form.type_text("value", URL)

    def created(element: model.File) -> None:
        assert (element.content_type, element.value) == ("text/plain", URL)

    def edit(lab: Any, attrs: Any) -> None:
        assert lab.set(attrs, "content_type", "application/json")

    def edited(element: model.File) -> None:
        assert element.content_type == "application/json"

    return Case(model.File, fill, created, edit, edited)


def _blob() -> Case:
    def fill(form: Form) -> None:
        form.type_text("content_type", "text/plain")
        form.widget("value").widget.editor.setPlainText("hello")

    def created(element: model.Blob) -> None:
        assert (element.content_type, element.value) == ("text/plain", b"hello")

    def edit(lab: Any, attrs: Any) -> None:
        def fill_value(dialog: Any) -> None:
            dialog.binary_edit.set_data(b"\x00\xff\x10binary")

        lab.edit_in_dialog(attrs, "value", fill_value, lab.value_dialog)

    def edited(element: model.Blob) -> None:
        assert element.value == b"\x00\xff\x10binary"

    return Case(model.Blob, fill, created, edit, edited)


def _edit_first_key(name: str) -> Callable[[Any, Any], None]:
    def edit(lab: Any, attrs: Any) -> None:
        def fill_key(dialog: Any) -> None:
            keys = Form(dialog).group.paramWidgets["key"]
            keys.inputWidgets[0].paramWidgets["value"].widget.setText(
                "urn:example:other"
            )

        lab.edit_in_dialog(attrs, name, fill_key)

    return edit


def _reference_element() -> Case:
    def fill(form: Form) -> None:
        form.fill_reference("value", _global("urn:example:target"))

    def created(element: model.ReferenceElement) -> None:
        assert element.value is not None
        assert element.value.key[0].value == "urn:example:target"

    def edited(element: model.ReferenceElement) -> None:
        assert element.value is not None
        assert element.value.key[0].value == "urn:example:other"

    return Case(
        model.ReferenceElement,
        fill,
        created,
        _edit_first_key("value"),
        edited,
    )


def _relationship(element_type: type) -> Case:
    def fill(form: Form) -> None:
        form.fill_reference("first", _global("urn:example:a"))
        form.fill_reference("second", _global("urn:example:b"))

    def created(element: model.RelationshipElement) -> None:
        assert element.first is not None and element.second is not None
        assert element.first.key[0].value == "urn:example:a"
        assert element.second.key[0].value == "urn:example:b"

    def edited(element: model.RelationshipElement) -> None:
        assert element.first is not None
        assert element.first.key[0].value == "urn:example:other"

    if element_type is model.AnnotatedRelationshipElement:

        def edit(lab: Any, attrs: Any) -> None:
            _edit_first_key("first")(lab, attrs)
            lab.add(_add_note, *ELEMENT_PATH)

        def edited_with_note(
            element: model.AnnotatedRelationshipElement,
        ) -> None:
            edited(element)
            assert [note.id_short for note in element.annotation] == ["Note"]

        return Case(element_type, fill, created, edit, edited_with_note)
    return Case(element_type, fill, created, _edit_first_key("first"), edited)


def _add_note(form: Form) -> None:
    form.choose_type(model.Property)
    form.type_text("id_short", "Note")
    form.type_text("value", "text")


def _collection() -> Case:
    def edit(lab: Any, attrs: Any) -> None:
        lab.add(_add_note, *ELEMENT_PATH)

    def edited(element: model.SubmodelElementCollection) -> None:
        assert [child.id_short for child in element.value] == ["Note"]

    return Case(
        model.SubmodelElementCollection,
        lambda form: None,
        lambda element: None,
        edit,
        edited,
    )


LIST_SEMANTIC_ID = "urn:example:number"


def _list() -> Case:
    def fill(form: Form) -> None:
        # The SDK default is that the order matters.
        assert form.checked("order_relevant") is True
        form.check("order_relevant", False)
        form.choose("type_value_list_element", model.Property)
        form.choose("value_type_list_element", datatypes.Int)
        form.fill_reference(
            "semantic_id_list_element", _global(LIST_SEMANTIC_ID)
        )

    def created(element: model.SubmodelElementList) -> None:
        assert element.order_relevant is False
        assert element.type_value_list_element is model.Property
        assert element.value_type_list_element is datatypes.Int
        assert element.semantic_id_list_element is not None
        assert element.semantic_id_list_element.key[0].value == LIST_SEMANTIC_ID

    def add_child(form: Form) -> None:
        # The dialog is made for the type the list allows, with what the list
        # fixes already set, so the type and the value type are not asked.
        assert not form.has("value_type")
        semantic_id = form.widget("semantic_id")
        keys = semantic_id.widget.paramWidgets["key"]
        assert keys.inputWidgets[0].paramWidgets["value"].widget.text() == (
            LIST_SEMANTIC_ID
        )
        form.type_text("value", "5")

    def edit(lab: Any, attrs: Any) -> None:
        lab.add(add_child, *ELEMENT_PATH)

    def edited(element: model.SubmodelElementList) -> None:
        (child,) = element.value
        assert isinstance(child, model.Property)
        assert child.value_type is datatypes.Int
        assert child.value == 5
        assert child.semantic_id == element.semantic_id_list_element

    return Case(model.SubmodelElementList, fill, created, edit, edited)


def _entity() -> Case:
    def fill(form: Form) -> None:
        form.choose("entity_type", model.EntityType.SELF_MANAGED_ENTITY)
        form.type_text("global_asset_id", "urn:asset:1")

    def created(element: model.Entity) -> None:
        assert element.entity_type is model.EntityType.SELF_MANAGED_ENTITY
        assert element.global_asset_id == "urn:asset:1"

    def edit(lab: Any, attrs: Any) -> None:
        assert lab.set(attrs, "global_asset_id", "urn:asset:2")

    def edited(element: model.Entity) -> None:
        assert element.global_asset_id == "urn:asset:2"

    return Case(model.Entity, fill, created, edit, edited)


def _operation() -> Case:
    def edit(lab: Any, attrs: Any) -> None:
        lab.add(_add_note, *ELEMENT_PATH, "input_variable")

    def edited(element: model.Operation) -> None:
        assert [v.id_short for v in element.input_variable] == ["Note"]
        assert len(element.output_variable) == 0

    return Case(
        model.Operation, lambda form: None, lambda element: None, edit, edited
    )


def _capability() -> Case:
    def edit(lab: Any, attrs: Any) -> None:
        # The category is read-only in a tab, so the edit is made as a command.
        from aas_editor.application.changes import observer_for
        from aas_editor.application.edits import SetAttribute

        lab.stack.push(
            SetAttribute(
                observer_for(lab.package),
                lab.element(),
                "category",
                "PARAMETER",
            )
        )

    def edited(element: model.Capability) -> None:
        assert element.category == "PARAMETER"

    return Case(
        model.Capability, lambda form: None, lambda element: None, edit, edited
    )


def _event() -> Case:
    def fill(form: Form) -> None:
        form.fill_model_reference(
            "observed",
            [
                (model.KeyTypes.SUBMODEL, "urn:example:submodel"),
                (model.KeyTypes.PROPERTY, "Temperature"),
            ],
            model.Property,
        )
        form.choose("direction", model.Direction.OUTPUT)
        form.choose("state", model.StateOfEvent.ON)
        form.type_text("message_topic", "plant/temperature")
        form.fill_model_reference(
            "message_broker",
            [(model.KeyTypes.SUBMODEL, "urn:example:broker")],
            model.Submodel,
        )
        moment = form.widget("last_update").widget
        moment.dateTimeEdit.setDateTime(QDateTime(2024, 5, 31, 13, 45, 0))
        zone = moment.tzinfoEdit.widget
        zone.setCurrentIndex(zone.findData("UTC"))
        minimum = form.widget("min_interval").widget
        minimum.secondsEdit.setText("30")
        maximum = form.widget("max_interval").widget
        maximum.hoursEdit.setText("1")

    def created(element: model.BasicEventElement) -> None:
        assert element.direction is model.Direction.OUTPUT
        assert element.state is model.StateOfEvent.ON
        assert element.message_topic == "plant/temperature"
        assert element.observed.key[-1].value == "Temperature"
        assert element.message_broker is not None
        assert element.message_broker.key[0].value == "urn:example:broker"
        assert element.last_update == datetime.datetime(
            2024, 5, 31, 13, 45, tzinfo=datetime.timezone.utc
        )
        assert element.min_interval is not None
        assert element.min_interval.seconds == 30
        assert element.max_interval is not None
        assert element.max_interval.hours == 1

    def edit(lab: Any, attrs: Any) -> None:
        assert lab.set(attrs, "message_topic", "plant/pressure")
        assert lab.set(attrs, "state", model.StateOfEvent.OFF)

        def fill_minimum(dialog: Any) -> None:
            # The dialog shows the interval that is set, 30 seconds.
            minimum = dialog.inputWidget.widget
            assert minimum.secondsEdit.text() == "30"
            minimum.secondsEdit.setText("45")

        lab.edit_in_dialog(attrs, "min_interval", fill_minimum)

    def edited(element: model.BasicEventElement) -> None:
        assert element.message_topic == "plant/pressure"
        assert element.state is model.StateOfEvent.OFF
        assert element.min_interval is not None
        assert element.min_interval.seconds == 45

    return Case(model.BasicEventElement, fill, created, edit, edited)


CASES = {
    "Property": _property,
    "MultiLanguageProperty": _multi_language_property,
    "Range": _range,
    "File": _file,
    "Blob": _blob,
    "ReferenceElement": _reference_element,
    "RelationshipElement": lambda: _relationship(model.RelationshipElement),
    "AnnotatedRelationshipElement": lambda: _relationship(
        model.AnnotatedRelationshipElement
    ),
    "SubmodelElementCollection": _collection,
    "SubmodelElementList": _list,
    "Entity": _entity,
    "Operation": _operation,
    "Capability": _capability,
    "BasicEventElement": _event,
}


def _fill_with_id(case: Case) -> Callable[[Form], None]:
    def fill(form: Form) -> None:
        form.choose_type(case.element_type)
        form.type_text("id_short", ELEMENT_ID)
        case.fill(form)

    return fill


@pytest.mark.parametrize("name", CASES)
def test_element_is_made_edited_undone_saved_and_read_again(
    lab, name: str
) -> None:
    case = CASES[name]()
    empty = snapshot(lab.package.objStore)

    lab.add(_fill_with_id(case))
    element = lab.element()
    case.check_created(element)
    assert type(element) is case.element_type
    created = snapshot(lab.package.objStore)
    lab.stack.mark_saved()

    case.edit(lab, lab.attrs())
    assert len(lab.shown.shown_errors) == case.refusals, lab.shown.shown_errors
    case.check_edited(lab.element())
    edited = snapshot(lab.package.objStore)

    while not lab.stack.is_clean:
        lab.stack.undo()
    assert snapshot(lab.package.objStore) == created
    while lab.stack.can_redo:
        lab.stack.redo()
    assert snapshot(lab.package.objStore) == edited
    assert lab.save_and_reload() == edited

    while lab.stack.can_undo:
        lab.stack.undo()
    assert snapshot(lab.package.objStore) == empty
    assert "generated_submodel_list_hack_" not in edited


def _constructor_parameters(element_type: type) -> list[str]:
    parameters = inspect.signature(element_type.__init__).parameters
    return [name for name in parameters if name not in ("self", "parent")]


@pytest.mark.parametrize("name", CASES)
def test_form_and_attributes_have_every_attribute_of_the_class(
    lab, name: str
) -> None:
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.utils.util_classes import ClassesInfo

    case = CASES[name]()
    element_type = case.element_type
    parameters = _constructor_parameters(element_type)
    # The elements below an element are added to it in the tree, and not set in
    # the form of the element.
    children = set(ClassesInfo.iterAttrs(element_type))
    without_widget: list[str] = []

    def fill(form: Form) -> None:
        form.choose_type(element_type)
        without_widget.extend(
            p for p in parameters if p not in children and not form.has(p)
        )
        form.type_text("id_short", ELEMENT_ID)
        case.fill(form)

    lab.add(fill)

    assert without_widget == [], "no widget or Create button in the form"
    proxy = lab.attrs().model()
    rows = {
        proxy.index(number, 0).data(NAME_ROLE)
        for number in range(proxy.rowCount())
    }
    for parameter in parameters:
        attribute = ClassesInfo.paramsToAttrs(element_type).get(
            parameter, parameter
        )
        if attribute in children:
            assert ClassesInfo.addType(
                element_type, attribute
            ) or ClassesInfo.addType(element_type), (
                f"{element_type.__name__}.{attribute} cannot be added to"
            )
        elif attribute == "category":
            # Deprecated: a row only for a category that has content, and
            # never in an element that was just made (F-EDT-06 AC16).
            assert attribute not in rows
        else:
            assert attribute in rows, (
                f"{element_type.__name__}.{attribute} is not in the attributes"
            )
