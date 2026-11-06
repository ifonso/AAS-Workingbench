"""Forms for the other owners of values, and for editing a whole element."""

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.medium.forms import answering
from tests.medium.forms import Form


def _form(owner: type, qtbot) -> Form:
    from aas_editor.dialogs import EditObjDialog

    dialog = EditObjDialog(owner, parent=None, rmDefParams=False)
    qtbot.addWidget(dialog)
    return Form(dialog)


class TestQualifierAndExtension:
    """A Qualifier and an Extension have a value type and a value too."""

    def test_a_qualifier_takes_a_value_for_its_type(self, qapp, qtbot) -> None:
        form = _form(model.Qualifier, qtbot)

        form.type_text("type_", "Cardinality")
        form.choose("value_type", datatypes.Int)
        form.type_text("value", "5")
        qualifier = form.dialog.inputWidget.getObj2add()

        assert qualifier.type == "Cardinality"
        assert qualifier.value_type is datatypes.Int
        assert qualifier.value == 5
        assert isinstance(qualifier.value, datatypes.Int)

    def test_a_qualifier_refuses_a_value_that_does_not_fit_its_type(
        self, qapp, qtbot
    ) -> None:
        form = _form(model.Qualifier, qtbot)
        form.type_text("type_", "Cardinality")
        form.choose("value_type", datatypes.Boolean)
        form.type_text("value", "maybe")

        with pytest.raises(ValueError, match="xs:boolean"):
            form.dialog.inputWidget.getObj2add()

    def test_an_extension_takes_a_value_when_it_has_a_type(
        self, qapp, qtbot
    ) -> None:
        form = _form(model.Extension, qtbot)

        form.type_text("name", "Source")
        form.choose("value_type", datatypes.Date)
        form.type_text("value", "2024-05-31")
        extension = form.dialog.inputWidget.getObj2add()

        assert extension.value == datatypes.Date(2024, 5, 31)

    def test_an_extension_without_a_type_refuses_a_value(
        self, qapp, qtbot
    ) -> None:
        form = _form(model.Extension, qtbot)
        form.type_text("name", "Source")
        form.type_text("value", "text")

        with pytest.raises(ValueError):
            form.dialog.inputWidget.getObj2add()


class TestWholeElement:
    def test_a_property_is_edited_as_a_whole_with_its_type_and_value_shown(
        self, lab_class
    ) -> None:
        from aas_editor.dialogs import EditObjDialog

        lab = lab_class(
            model.Property(
                ELEMENT_ID,
                value_type=datatypes.Date,
                value=datatypes.Date(2024, 1, 1),
            )
        )
        shown = lab.shown
        index = shown.index(*ELEMENT_PATH)
        shown.select(index)

        def fill(dialog) -> None:
            form = Form(dialog)
            assert (
                form.widget("value_type").widget.value_type() is datatypes.Date
            )
            assert form.widget("value").widget.text() == "2024-01-01"
            form.type_text("value", "2024-12-31")

        with answering(
            lab.monkeypatch, EditObjDialog, fill, shown.shown_errors
        ):
            shown.view.onEditCreate(None, index)

        assert lab.element().value == datatypes.Date(2024, 12, 31)
        assert lab.element().value_type is datatypes.Date


def test_the_completer_of_languages_offers_the_common_codes(
    qapp: object,
) -> None:
    from aas_editor.additional.classes import DictItem
    from aas_editor.settings.defaults import DEFAULT_COMPLETIONS

    assert DEFAULT_COMPLETIONS[DictItem]["key"] == [
        "de",
        "en",
        "es",
        "fi",
        "fr",
        "it",
        "ja",
        "ko",
        "nl",
        "no",
        "pt",
        "sv",
        "zh",
    ]
