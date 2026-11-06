"""Entering values in the dialogs and cells of the views."""

import datetime
import decimal
import json

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtWidgets import QStyleOptionViewItem
from PyQt6.QtWidgets import QWidget
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.medium.forms import Form
from tests.serialization import snapshot


def _property(value_type: type, value: object = None) -> model.Property:
    return model.Property(ELEMENT_ID, value_type=value_type, value=value)  # pyright: ignore[reportArgumentType]


class TestAddDialog:
    def test_text_that_is_no_integer_is_refused_with_the_message(
        self, lab
    ) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Int)
            form.type_text("value", "twelve")

        lab.add(fill, refused=True)

        assert lab.shown.shown_errors == [
            "'twelve' is not a valid xs:int: it must be a whole number "
            "such as 12 or -3"
        ]
        assert len(lab.submodel.submodel_element) == 0
        assert not lab.stack.can_undo

    def test_the_value_is_checked_for_the_type_chosen_last(self, lab) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.type_text("value", "300")
            form.choose("value_type", datatypes.Byte)

        lab.add(fill, refused=True)

        assert "out of the range of xs:byte" in lab.shown.shown_errors[0]

    def test_a_big_integer_is_taken_when_the_type_is_xs_integer(
        self, lab
    ) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Integer)
            form.type_text("value", "123456789012345678901234567890")

        lab.add(fill)

        assert lab.element().value == 123456789012345678901234567890

    def test_a_date_is_typed_as_text(self, lab) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Date)
            form.type_text("value", "2024-05-31")

        lab.add(fill)

        assert lab.element().value == datatypes.Date(2024, 5, 31)

    def test_a_value_is_optional_and_stays_missing_when_not_created(
        self, lab
    ) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Double)

        lab.add(fill)

        assert lab.element().value is None
        assert lab.element().value_type is datatypes.Double

    def test_a_range_with_the_minimum_above_the_maximum_is_refused(
        self, lab
    ) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Range)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Int)
            form.type_text("min", "10")
            form.type_text("max", "1")

        lab.add(fill, refused=True)

        assert lab.shown.shown_errors == [
            "The minimum 10 is more than the maximum 1"
        ]
        assert len(lab.submodel.submodel_element) == 0

    def test_a_range_with_equal_limits_is_made(self, lab) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Range)
            form.type_text("id_short", ELEMENT_ID)
            form.choose("value_type", datatypes.Int)
            form.type_text("min", "5")
            form.type_text("max", "5")

        lab.add(fill)

        assert (lab.element().min, lab.element().max) == (5, 5)

    def test_a_language_that_is_no_language_tag_is_refused_with_the_reason(
        self, lab
    ) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.MultiLanguageProperty)
            form.type_text("id_short", ELEMENT_ID)
            form.add_language("value", "en_US", "Hello")

        lab.add(fill, refused=True)

        assert lab.shown.shown_errors == [
            "'en_US' is not a language tag: use a hyphen, not an underscore, "
            "as in en-US"
        ]
        assert len(lab.submodel.submodel_element) == 0

    def test_a_description_with_a_language_tag_is_made(self, lab) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.add_language("description", "de-DE", "Beschreibung")

        lab.add(fill)

        assert dict(lab.element().description) == {"de-DE": "Beschreibung"}

    def test_a_language_used_twice_is_refused(self, lab) -> None:
        def fill(form: Form) -> None:
            form.choose_type(model.Property)
            form.type_text("id_short", ELEMENT_ID)
            form.add_language("display_name", "en", "Name")
            form.add_language("display_name", "EN", "Other")

        lab.add(fill, refused=True)

        assert lab.shown.shown_errors == [
            "The language 'EN' is used more than once"
        ]


class TestEditDialog:
    def test_the_value_of_a_property_is_edited_for_its_type(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.Date, datatypes.Date(2024, 1, 1)))

        def fill(dialog) -> None:
            assert dialog.value_edit.text() == "2024-01-01"
            dialog.value_edit.set_text("2024-12-31")

        lab.edit_in_dialog(lab.attrs(), "value", fill, lab.value_dialog)

        assert lab.element().value == datatypes.Date(2024, 12, 31)

    def test_the_value_dialog_takes_a_missing_value(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.Int))

        def fill(dialog) -> None:
            assert dialog.value_edit.text() == ""
            dialog.value_edit.set_text("42")

        lab.edit_in_dialog(lab.attrs(), "value", fill, lab.value_dialog)

        assert lab.element().value == 42

    def test_the_value_dialog_clears_the_value(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.Int, 3))

        lab.edit_in_dialog(
            lab.attrs(),
            "value",
            lambda dialog: dialog.clear_button.click(),
            lab.value_dialog,
        )

        assert lab.element().value is None

    def test_a_limit_of_a_range_is_edited_for_its_type(self, lab_class) -> None:
        lab = lab_class(
            model.Range(
                ELEMENT_ID,
                value_type=datatypes.Decimal,
                min=decimal.Decimal(1),
                max=decimal.Decimal(9),
            )  # pyright: ignore[reportArgumentType]
        )

        lab.edit_in_dialog(
            lab.attrs(),
            "max",
            lambda dialog: dialog.value_edit.set_text("9.5"),
            lab.value_dialog,
        )

        assert str(lab.element().max) == "9.5"

    def test_the_value_type_is_chosen_by_name_and_converts_the_value(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.String, "12"))
        before = snapshot(lab.package.objStore)

        def fill(dialog) -> None:
            names = dialog.inputWidget.widget
            assert names.currentText() == "xs:string"
            names.setCurrentIndex(names.findData(datatypes.Int))

        lab.edit_in_dialog(lab.attrs(), "value_type", fill)
        converted = (lab.element().value_type, lab.element().value)
        lab.stack.undo()

        assert converted == (datatypes.Int, 12)
        assert snapshot(lab.package.objStore) == before

    def test_the_value_type_is_not_changed_when_the_value_does_not_fit(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.String, "not a number"))

        def fill(dialog) -> None:
            names = dialog.inputWidget.widget
            names.setCurrentIndex(names.findData(datatypes.Int))

        lab.edit_in_dialog(lab.attrs(), "value_type", fill, refused=True)

        assert lab.element().value_type is datatypes.String
        assert lab.shown.shown_errors == [
            "The value type cannot change to xs:int: the value 'not a number' "
            "is not a valid xs:int: it must be a whole number such as 12 or "
            "-3. Clear or change the value first"
        ]
        assert not lab.stack.can_undo

    def test_a_blob_is_edited_as_hex_when_it_is_binary(self, lab_class) -> None:
        blob = model.Blob(
            ELEMENT_ID, content_type="image/png", value=b"\x89PNG\x00\xff"
        )
        lab = lab_class(blob)

        def fill(dialog) -> None:
            assert dialog.binary_edit.mode() == "hex"
            assert (
                dialog.binary_edit.editor.toPlainText() == "89 50 4e 47 00 ff"
            )
            dialog.binary_edit.editor.setPlainText("89 50 4e 47 00 ff 01")

        lab.edit_in_dialog(lab.attrs(), "value", fill, lab.value_dialog)

        assert blob.value == b"\x89PNG\x00\xff\x01"

    def test_a_blob_with_text_is_shown_as_text_and_keeps_its_bytes(
        self, lab_class
    ) -> None:
        blob = model.Blob(ELEMENT_ID, "text/plain", "Größe\r\n".encode())
        lab = lab_class(blob)

        def fill(dialog) -> None:
            assert dialog.binary_edit.mode() == "text"
            assert dialog.binary_edit.editor.toPlainText() == "Größe\n"

        lab.edit_in_dialog(lab.attrs(), "value", fill, lab.value_dialog)

        assert blob.value == "Größe\r\n".encode()
        assert not lab.stack.can_undo


class TestCells:
    """The editor of a cell in the tab of an element."""

    def _edit(self, lab, attrs, name: str, text: str) -> bool:
        index = lab.row(attrs, name)
        delegate = attrs.itemDelegate()
        parent = QWidget()
        editor = delegate.createEditor(parent, QStyleOptionViewItem(), index)
        delegate.setEditorData(editor, index)
        editor.setText(text)
        delegate.setModelData(editor, attrs.model(), index)
        return True

    def test_a_cell_with_a_missing_value_is_edited_in_the_cell(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.Int))
        attrs = lab.attrs()

        assert attrs.isEditableInsideCell(lab.row(attrs, "value"))

    def test_the_cell_takes_text_for_the_value_type(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.Int))

        self._edit(lab, lab.attrs(), "value", "12")

        assert lab.element().value == 12
        assert isinstance(lab.element().value, datatypes.Int)

    def test_the_cell_takes_a_number_beyond_32_bits(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.Long))

        self._edit(lab, lab.attrs(), "value", "9000000000")

        assert lab.element().value == 9000000000

    def test_the_cell_takes_a_date_and_time(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.DateTime))

        self._edit(lab, lab.attrs(), "value", "2024-05-31T13:45:00Z")

        assert lab.element().value == datetime.datetime(
            2024, 5, 31, 13, 45, tzinfo=datetime.timezone.utc
        )

    def test_the_cell_refuses_text_that_is_no_value(self, lab_class) -> None:
        lab = lab_class(_property(datatypes.Int, 3))

        self._edit(lab, lab.attrs(), "value", "abc")

        assert lab.element().value == 3
        assert lab.shown.shown_errors == [
            "'abc' is not a valid xs:int: it must be a whole number "
            "such as 12 or -3"
        ]

    def test_the_cell_changes_nothing_when_the_text_is_left_as_it_was(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.String))

        self._edit(lab, lab.attrs(), "value", "")

        # A missing value does not become an empty string.
        assert lab.element().value is None
        assert not lab.stack.can_undo

    def test_the_cell_marks_a_wrong_text_before_it_is_accepted(
        self, lab_class
    ) -> None:
        lab = lab_class(_property(datatypes.Int))
        attrs = lab.attrs()
        index = lab.row(attrs, "value")
        parent = QWidget()
        editor = attrs.itemDelegate().createEditor(
            parent, QStyleOptionViewItem(), index
        )

        editor.setText("x1")

        assert editor.problem() == (
            "'x1' is not a valid xs:int: it must be a whole number "
            "such as 12 or -3"
        )
        assert editor.toolTip() == editor.problem()

    def test_a_cell_of_the_package_tree_takes_text_for_the_type(
        self, lab_class
    ) -> None:
        from aas_editor.settings.app_settings import (
            DEFAULT_COLUMNS_IN_PACKS_TABLE,
        )
        from aas_editor.settings import EXTENDED_COLUMNS_IN_PACK_TABLE

        lab = lab_class(_property(datatypes.Int, 3))
        view = lab.shown.view
        columns = list(DEFAULT_COLUMNS_IN_PACKS_TABLE) + list(
            EXTENDED_COLUMNS_IN_PACK_TABLE
        )
        column = columns.index("value")
        index = lab.shown.index(*ELEMENT_PATH).siblingAtColumn(column)
        delegate = view.itemDelegate()
        parent = QWidget()
        editor = delegate.createEditor(parent, QStyleOptionViewItem(), index)

        delegate.setEditorData(editor, index)
        editor.setText("8")
        delegate.setModelData(editor, view.model(), index)

        assert lab.element().value == 8


class TestListChildren:
    def test_a_child_added_without_an_id_short_keeps_a_hidden_name_that_is_never_saved(
        self, lab_class, tmp_path
    ) -> None:
        numbers = model.SubmodelElementList(
            ELEMENT_ID,
            type_value_list_element=model.Property,
            value_type_list_element=datatypes.Int,
        )
        lab = lab_class(numbers)

        def add_child(text: str):
            def fill(form: Form) -> None:
                form.type_text("value", text)

            return fill

        lab.add(add_child("1"), *ELEMENT_PATH)
        lab.add(add_child("2"), *ELEMENT_PATH)

        children = list(numbers.value)
        assert [child.value for child in children] == [1, 2]
        assert all(
            child.id_short.startswith("generated_submodel_list_hack_")
            for child in children
        )
        for suffix in (".json", ".aasx"):
            path = tmp_path / f"saved{suffix}"
            lab.package.write(path)
            if suffix == ".json":
                text = path.read_text(encoding="utf-8")
                assert "generated_submodel_list_hack_" not in text
                (saved,) = json.loads(text)["submodels"]
                (saved_list,) = saved["submodelElements"]
                assert [c["value"] for c in saved_list["value"]] == ["1", "2"]
                assert all("idShort" not in c for c in saved_list["value"])

    def test_the_tree_shows_the_type_of_a_child_that_has_no_id_short(
        self, lab_class
    ) -> None:
        from aas_editor.settings.app_settings import NAME_ROLE

        numbers = model.SubmodelElementList(
            ELEMENT_ID,
            type_value_list_element=model.Property,
            value_type_list_element=datatypes.Int,
        )
        lab = lab_class(numbers)

        lab.add(lambda form: form.type_text("value", "1"), *ELEMENT_PATH)

        proxy = lab.shown.view.model()
        parent = lab.shown.index(*ELEMENT_PATH)
        assert [
            proxy.index(row, 0, parent).data(NAME_ROLE)
            for row in range(proxy.rowCount(parent))
        ] == ["Property"]

    def test_a_list_of_ranges_asks_for_ranges_with_the_value_type_of_the_list(
        self, lab_class
    ) -> None:
        ranges = model.SubmodelElementList(
            ELEMENT_ID,
            type_value_list_element=model.Range,
            value_type_list_element=datatypes.Decimal,
        )
        lab = lab_class(ranges)

        def fill(form: Form) -> None:
            assert not form.has("value_type")
            form.type_text("min", "0.5")
            form.type_text("max", "2.5")

        lab.add(fill, *ELEMENT_PATH)

        (child,) = ranges.value
        assert isinstance(child, model.Range)
        assert (str(child.min), str(child.max)) == ("0.5", "2.5")
        assert child.value_type is datatypes.Decimal

    def test_a_list_cannot_get_a_child_of_another_type_through_the_dialog(
        self, lab_class
    ) -> None:
        files = model.SubmodelElementList(
            ELEMENT_ID, type_value_list_element=model.File
        )
        lab = lab_class(files)

        def fill(form: Form) -> None:
            # There is no chooser of the type: the list allows only files.
            assert not hasattr(form.dialog.inputWidget, "typeComboBox")
            form.type_text("content_type", "text/plain")

        lab.add(fill, *ELEMENT_PATH)

        (child,) = files.value
        assert isinstance(child, model.File)
        assert child.content_type == "text/plain"
