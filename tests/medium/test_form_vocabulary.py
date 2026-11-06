"""The generated forms name their fields as the tabs do, and adding is quick.

A form is made from the constructor of a BaSyx class. It labels each field with
the name of the metamodel (`valueType`, ADR 0022 and ADR 0026), but finds and
fills it by the name of the SDK, which is what these tests use. The adding of
one item to a list starts with that item.
"""

import inspect
from types import SimpleNamespace
from typing import Any

from basyx.aas import model
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID
from tests.medium.forms import answering
from tests.medium.forms import Form
from tests.serialization import snapshot


def _form_of(cls: type) -> Form:
    from aas_editor.dialogs import EditObjDialog

    return Form(EditObjDialog(cls, None, rmDefParams=False))


class TestLabels:
    def test_a_qualifier_form_reads_in_the_words_of_the_metamodel(
        self, qapp
    ) -> None:
        form = _form_of(model.Qualifier)

        assert form.label("type_") == "type*"
        assert form.label("value_type") == "valueType*"
        assert form.has("semantic_id")
        assert form.create("semantic_id") is not None
        assert form.label("semantic_id") == "semanticId"
        assert form.label("supplemental_semantic_id") == (
            "supplementalSemanticId"
        )
        assert form.label("value_id") == "valueId"

    def test_a_label_has_the_description_as_its_tooltip(self, qapp) -> None:
        form = _form_of(model.Qualifier)

        assert "XSD" in form.tooltip("value_type")
        assert (
            form.tooltip("value_type")
            == form.group.paramWidgets["value_type"].toolTip()
        )

    def test_a_label_names_its_field_for_a_screen_reader(self, qapp) -> None:
        form = _form_of(model.Qualifier)

        label = form.group.labelOf("value_type")

        assert label is not None
        assert label.buddy() is form.group.paramWidgets["value_type"]

    def test_a_label_is_there_for_an_optional_field_before_and_after_create(
        self, qapp
    ) -> None:
        form = _form_of(model.Qualifier)

        assert form.label("value_id") == "valueId"
        form.create("value_id")

        assert form.label("value_id") == "valueId"

    def test_a_field_is_found_by_its_sdk_name_whatever_it_is_called(
        self, qapp
    ) -> None:
        form = _form_of(model.Qualifier)

        form.type_text("type_", "Handle")
        form.choose("value_type", model.datatypes.Int)
        made = form.group.getObj2add()

        assert made.type == "Handle"
        assert made.value_type is model.datatypes.Int


def _concrete_model_classes() -> list[type]:
    from collections.abc import Mapping
    from collections.abc import Sequence
    from collections.abc import Set as AbstractSet
    from enum import Enum

    not_forms = (Enum, BaseException, Mapping, AbstractSet, Sequence)
    return [
        cls
        for _, cls in inspect.getmembers(model, inspect.isclass)
        if cls.__module__.startswith("basyx.aas.model")
        and not inspect.isabstract(cls)
        and not issubclass(cls, not_forms)
    ]


def test_no_field_of_any_form_is_shown_in_python(qapp) -> None:
    from aas_editor.domain.attribute_vocabulary import attribute_info
    from aas_editor.widgets.groupBoxes import ObjGroupBox

    unnamed: list[str] = []
    for cls in _concrete_model_classes():
        box = ObjGroupBox(cls)
        for param in box.reqParamsDict:
            attribute = box.paramsToAttrs.get(param, param)
            if attribute_info(cls, attribute) is None and (
                attribute_info(cls, param.strip("_")) is None
            ):
                unnamed.append(f"{cls.__name__}.{param}")
            label = box.labelOf(param)
            assert label is not None, f"{cls.__name__}.{param}"
            assert "_" not in label.text(), f"{cls.__name__}.{param}"

    assert unnamed == []


class TestAddingOneItem:
    def _qualifier_row(self, lab: Any, attrs: Any) -> Any:
        return lab.row(attrs, "qualifier")

    def _add_qualifier(self, lab: Any, fill: Any) -> None:
        attrs = lab.attrs()
        parent = self._qualifier_row(lab, attrs)
        attrs.setCurrentIndex(parent)
        from aas_editor.dialogs import EditObjDialog

        with answering(lab.monkeypatch, EditObjDialog, fill):
            attrs.onAddAct(parent)

    def test_a_qualifier_is_added_without_the_add_item_step(
        self, lab_class
    ) -> None:
        lab = lab_class(make_property(ELEMENT_ID))
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            box = dialog.inputWidget
            seen.append(len(box.inputWidgets))
            # The entry is a form of its own, filled like any other.
            entry = Form(SimpleNamespace(inputWidget=box.inputWidgets[0]))
            entry.type_text("type_", "Handle")
            entry.choose("value_type", model.datatypes.Int)
            entry.type_text("value", "7")

        before = snapshot(lab.package.objStore)
        self._add_qualifier(lab, fill)

        assert lab.shown.shown_errors == []
        qualifiers = list(lab.element().qualifier)
        assert seen == [1]
        assert [(q.type, q.value_type, q.value) for q in qualifiers] == [
            ("Handle", model.datatypes.Int, 7)
        ]
        lab.stack.undo()
        assert snapshot(lab.package.objStore) == before

    def test_the_type_of_the_new_entry_has_the_focus(self, lab_class) -> None:
        lab = lab_class(make_property(ELEMENT_ID))
        focused: list[Any] = []

        def fill(dialog: Any) -> None:
            entry = dialog.inputWidget.inputWidgets[0]
            focused.append(
                (
                    dialog.focusWidget(),
                    entry.paramWidgets["type_"].widget,
                )
            )
            entry.paramWidgets["type_"].widget.setText("Handle")

        self._add_qualifier(lab, fill)

        assert focused[0][0] is focused[0][1]

    def test_add_item_still_adds_a_second_entry(self, lab_class) -> None:
        from PyQt6.QtWidgets import QPushButton

        lab = lab_class(make_property(ELEMENT_ID))

        def fill(dialog: Any) -> None:
            box = dialog.inputWidget
            box.findChild(QPushButton).click()
            assert len(box.inputWidgets) == 2
            for entry, name in zip(box.inputWidgets, ("A", "B")):
                entry.paramWidgets["type_"].widget.setText(name)

        self._add_qualifier(lab, fill)

        assert [q.type for q in lab.element().qualifier] == ["A", "B"]

    def test_an_entry_that_is_left_empty_is_refused_with_a_message(
        self, lab_class
    ) -> None:
        lab = lab_class(make_property(ELEMENT_ID))
        from aas_editor.dialogs import EditObjDialog

        attrs = lab.attrs()
        parent = self._qualifier_row(lab, attrs)
        attrs.setCurrentIndex(parent)
        with answering(
            lab.monkeypatch,
            EditObjDialog,
            lambda dialog: None,
            lab.shown.shown_errors,
            cancel_when_asked_again=True,
        ):
            attrs.onAddAct(parent)

        assert lab.shown.shown_errors != []
        assert list(lab.element().qualifier) == []
        assert not lab.stack.can_undo

    def test_editing_a_list_does_not_add_an_entry(self, lab_class) -> None:
        lab = lab_class(make_property(ELEMENT_ID))
        seen: list[int] = []

        def fill(dialog: Any) -> None:
            seen.append(len(dialog.inputWidget.inputWidgets))

        lab.edit_in_dialog(lab.attrs(), "qualifier", fill)

        assert seen == [0]

    def test_a_list_in_an_entry_does_not_take_the_title_of_its_owner(
        self, lab_class
    ) -> None:
        lab = lab_class(make_property(ELEMENT_ID))
        titles: list[tuple[str, str]] = []

        def fill(dialog: Any) -> None:
            entry = dialog.inputWidget.inputWidgets[0]
            titles.append(
                (
                    entry.title(),
                    entry.paramWidgets["supplemental_semantic_id"].title(),
                )
            )
            entry.paramWidgets["type_"].widget.setText("Handle")

        self._add_qualifier(lab, fill)

        assert titles == [("Qualifier 1", "")]

    def test_a_form_in_a_form_does_not_start_with_an_entry(self, qapp) -> None:
        form = _form_of(model.Qualifier)

        keys = form.widget("supplemental_semantic_id")

        assert keys.inputWidgets == []


def test_a_language_entry_is_titled_text_and_has_a_language_and_a_text(
    qapp,
) -> None:
    form = _form_of(model.MultiLanguageProperty)

    texts = form.widget("value")
    entry = texts.inputWidgets[0]

    assert entry.title() == "Text 1"
    assert [entry.labelOf(param).text() for param in entry.paramWidgets] == [
        "language*",
        "text*",
    ]


def test_the_dialog_is_titled_with_the_name_of_the_metamodel(
    lab_class,
) -> None:
    from aas_editor.dialogs import EditObjDialog

    lab = lab_class(make_property(ELEMENT_ID))
    titles: list[str] = []
    attrs = lab.attrs()
    parent = lab.row(attrs, "supplemental_semantic_id")
    attrs.setCurrentIndex(parent)

    with answering(
        lab.monkeypatch,
        EditObjDialog,
        lambda dialog: titles.append(dialog.windowTitle()),
        lab.shown.shown_errors,
        cancel_when_asked_again=True,
    ):
        attrs.onAddAct(parent)

    assert titles == ["Add supplementalSemanticId element"]
