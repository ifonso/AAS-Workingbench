"""Entering the languages of multi-language texts, through the item models."""

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_multi_language_property
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def texts(model_support):
    """Edits the language entries of an element that has descriptions."""

    class Texts:
        def __init__(self, element: model.SubmodelElement) -> None:
            self.table = model_support.pack_table(
                make_submodel(elements=[element])
            )
            self.package = model_support.package_of(self.table)
            self.details = model_support.detail_table(
                self.table, *SUBMODEL, element.id_short
            )

        def row(self, *names: str) -> QModelIndex:
            index = QModelIndex()
            for name in names:
                index = model_support.find(self.details, name, index)
            return index

        def replace(self, row: QModelIndex, language: str, text: str) -> bool:
            from aas_editor.additional.classes import DictItem

            return self.details.setData(
                row, DictItem(language, text), Qt.ItemDataRole.EditRole
            )

        def message(self, row: QModelIndex) -> str:
            from aas_editor.settings.app_settings import DATA_CHANGE_FAILED_ROLE

            return self.details.data(row, DATA_CHANGE_FAILED_ROLE)

    return Texts


def _prop_with_description() -> model.Property:
    prop = make_property("p")
    prop.description = model.MultiLanguageTextType({"en": "a", "de": "b"})
    return prop


def test_a_language_with_an_underscore_is_refused_with_the_reason(
    texts,
) -> None:
    prop = _prop_with_description()
    shown = texts(prop)
    row = shown.row("description", "DictItem 0")
    before = snapshot(shown.package.objStore)

    edited = shown.replace(row, "en_US", "a")

    assert not edited
    assert shown.message(row) == (
        "'en_US' is not a language tag: use a hyphen, not an underscore, "
        "as in en-US"
    )
    assert snapshot(shown.package.objStore) == before
    assert not shown.package.commandStack.can_undo


def test_a_well_formed_language_is_accepted_and_can_be_undone(texts) -> None:
    prop = _prop_with_description()
    shown = texts(prop)
    row = shown.row("description", "DictItem 0")
    before = snapshot(shown.package.objStore)

    edited = shown.replace(row, "en-GB", "a")
    after_edit = dict(prop.description)
    shown.package.commandStack.undo()

    assert edited
    assert after_edit == {"en-GB": "a", "de": "b"}
    assert snapshot(shown.package.objStore) == before


def test_an_empty_language_is_refused(texts) -> None:
    prop = _prop_with_description()
    shown = texts(prop)

    edited = shown.replace(shown.row("description", "DictItem 0"), "", "a")

    assert not edited
    assert dict(prop.description) == {"en": "a", "de": "b"}


def test_a_language_of_the_value_of_a_multi_language_property_is_checked(
    texts,
) -> None:
    mlp = make_multi_language_property("m", {"en": "a", "de": "b"})
    shown = texts(mlp)
    row = shown.row("value", "DictItem 1")

    edited = shown.replace(row, "de_DE", "b")

    assert not edited
    assert "use a hyphen" in shown.message(row)
    assert dict(mlp.value) == {"en": "a", "de": "b"}


def test_a_language_of_a_display_name_is_checked(texts) -> None:
    prop = make_property("p")
    prop.display_name = model.MultiLanguageNameType({"en": "Name"})
    shown = texts(prop)
    row = shown.row("display_name", "DictItem 0")

    edited = shown.replace(row, "e n", "Name")

    assert not edited
    assert "must not contain spaces" in shown.message(row)


def test_a_text_that_is_empty_is_refused_and_the_entry_stays(texts) -> None:
    prop = _prop_with_description()
    shown = texts(prop)

    row = shown.row("description", "DictItem 0")

    edited = shown.replace(row, "fr", "")

    assert not edited
    assert (
        shown.message(row) == "The text for the language 'fr' cannot be empty"
    )
    assert dict(prop.description) == {"en": "a", "de": "b"}
