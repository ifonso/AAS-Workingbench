"""A tab names attributes, types, and entries in words of the AAS, not Python.

What the editor edits stays the attribute of the SDK. These tests look at what
a person reads, and at the places that find a row by its name.
"""

from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtCore import Qt
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID

DISPLAY = Qt.ItemDataRole.DisplayRole


def _rich_property() -> model.Property:
    element = make_property(ELEMENT_ID, 7.5, datatypes.Double)
    element.display_name = model.MultiLanguageNameType(
        {"en": "Rated power", "de": "Nennleistung"}
    )
    element.semantic_id = make_external_reference("0173-1#02-AAZ715#006")
    element.qualifier.add(
        model.Qualifier("Cardinality", datatypes.String, "One")
    )
    element.extension.add(model.Extension("Origin", datatypes.String, "sheet"))
    return element


@pytest.fixture
def tab(lab_class: Any) -> Any:
    """The attributes of a property that has most of what a tab shows."""
    return lab_class(_rich_property()).attrs()


def _texts(attrs: Any) -> dict[str, tuple[str, str, str]]:
    """What each row reads, by the attribute of the SDK that it shows."""
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = attrs.model()
    return {
        proxy.index(row, 0).data(NAME_ROLE): (
            proxy.index(row, 0).data(DISPLAY),
            proxy.index(row, 1).data(DISPLAY),
            proxy.index(row, 2).data(DISPLAY),
        )
        for row in range(proxy.rowCount())
    }


def _index(attrs: Any, sdk_name: str, column: int = 0) -> Any:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = attrs.model()
    for row in range(proxy.rowCount()):
        if proxy.index(row, 0).data(NAME_ROLE) == sdk_name:
            return proxy.index(row, column)
    raise LookupError(sdk_name)


def test_the_attributes_are_named_as_the_metamodel_names_them(tab: Any) -> None:
    names = {sdk: texts[0] for sdk, texts in _texts(tab).items()}

    assert names["id_short"] == "idShort"
    assert names["display_name"] == "displayName"
    assert names["value_type"] == "valueType"
    assert names["semantic_id"] == "semanticId"
    assert names["supplemental_semantic_id"] == "supplementalSemanticId"
    assert names["embedded_data_specifications"] == "embeddedDataSpecifications"
    assert "_" not in "".join(names.values())


def test_the_type_column_names_the_type_of_the_aas(tab: Any) -> None:
    types = {sdk: texts[2] for sdk, texts in _texts(tab).items()}

    assert types["id_short"] == "xs:string"
    assert types["value"] == "xs:double"
    assert types["value_type"] == "DataTypeDefXsd"
    assert types["display_name"] == "MultiLanguageNameType"
    assert types["semantic_id"] == "ExternalReference"
    assert types["qualifier"] == "list of Qualifier"
    assert types["extension"] == "list of Extension"


def test_no_type_reads_like_python(tab: Any) -> None:
    types = " ".join(texts[2] for texts in _texts(tab).values())

    for python in ("NoneType", "Optional", "Union", "Iterable", "typing"):
        assert python not in types


def test_a_null_attribute_reads_as_not_set_and_has_the_type_it_would_have(
    tab: Any,
) -> None:
    _, value, type_ = _texts(tab)["value_id"]

    assert value == "(not set)"
    assert type_ == "Reference"


def test_an_empty_list_does_not_read_like_python(tab: Any) -> None:
    _, value, _ = _texts(tab)["supplemental_semantic_id"]

    assert value == "(empty)"


def test_the_value_type_reads_as_an_xsd_type(tab: Any) -> None:
    _, value, _ = _texts(tab)["value_type"]

    assert value == "xs:double"


def test_the_rows_keep_the_order_of_the_attributes(tab: Any) -> None:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = tab.model()
    names = [proxy.index(row, 0).data(NAME_ROLE) for row in range(5)]

    assert names == [
        "id_short",
        "category",
        "value",
        "value_type",
        "description",
    ]


def test_the_name_that_editing_uses_is_the_attribute_of_the_sdk(
    tab: Any,
) -> None:
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.settings.app_settings import PARENT_OBJ_ROLE

    index = _index(tab, "display_name")

    assert index.data(DISPLAY) == "displayName"
    assert index.data(NAME_ROLE) == "display_name"
    assert hasattr(index.data(PARENT_OBJ_ROLE), index.data(NAME_ROLE))


def test_a_value_is_still_edited_through_the_row_of_its_attribute(
    lab_class: Any,
) -> None:
    lab = lab_class(_rich_property())
    attrs = lab.attrs()

    edited = lab.set(attrs, "category", "PARAMETER")

    assert edited
    assert lab.element().category == "PARAMETER"


def test_a_text_of_a_language_is_named_by_its_language(tab: Any) -> None:
    from PyQt6.QtCore import QModelIndex

    proxy = tab.model()
    entries = _index(tab, "display_name")
    tab.expand(entries)

    languages = {
        proxy.index(row, 0, entries).data(DISPLAY)
        for row in range(proxy.rowCount(entries))
    }

    assert languages == {"en", "de"}
    assert not any("DictItem" in language for language in languages)
    assert entries.parent() == QModelIndex()


def test_a_qualifier_and_an_extension_are_named_by_what_names_them(
    tab: Any,
) -> None:
    proxy = tab.model()
    qualifier = _index(tab, "qualifier")
    extension = _index(tab, "extension")

    assert proxy.index(0, 0, qualifier).data(DISPLAY) == "Cardinality"
    assert proxy.index(0, 0, extension).data(DISPLAY) == "Origin"


def test_an_entry_without_a_key_is_named_by_its_position(
    lab_class: Any,
) -> None:
    element = make_property(ELEMENT_ID)
    element.semantic_id = make_external_reference("urn:main")
    element.supplemental_semantic_id.append(make_external_reference("urn:a"))
    element.supplemental_semantic_id.append(make_external_reference("urn:b"))
    attrs = lab_class(element).attrs()
    proxy = attrs.model()
    references = _index(attrs, "supplemental_semantic_id")

    labels = [
        proxy.index(row, 0, references).data(DISPLAY)
        for row in range(proxy.rowCount(references))
    ]

    assert labels == ["[0]", "[1]"]


def test_the_keys_of_a_reference_are_named_by_their_position_and_type(
    tab: Any,
) -> None:
    proxy = tab.model()
    reference = _index(tab, "semantic_id")
    tab.expand(reference)
    keys = _index_of_child(proxy, reference, "key")
    tab.expand(keys)

    labels = [
        proxy.index(row, 0, keys).data(DISPLAY)
        for row in range(proxy.rowCount(keys))
    ]

    assert labels == ["[0] GLOBAL_REFERENCE"]


def _index_of_child(proxy: Any, parent: Any, sdk_name: str) -> Any:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    for row in range(proxy.rowCount(parent)):
        if proxy.index(row, 0, parent).data(NAME_ROLE) == sdk_name:
            return proxy.index(row, 0, parent)
    raise LookupError(sdk_name)


def test_hovering_an_attribute_shows_its_description(tab: Any) -> None:
    tooltip = _index(tab, "display_name").data(Qt.ItemDataRole.ToolTipRole)

    assert tooltip.startswith("displayName: MultiLanguageNameType")
    assert "several languages" in tooltip


def test_the_description_is_also_the_help_text_of_the_row(tab: Any) -> None:
    help_text = _index(tab, "id_short").data(Qt.ItemDataRole.WhatsThisRole)

    assert help_text.startswith("Short name of the element")


def test_the_type_hint_of_python_is_in_its_own_column_named_for_what_it_is(
    tab: Any,
) -> None:
    from aas_workingbench.settings.app_settings import TYPE_HINT_COLUMN

    proxy = tab.model()
    header = proxy.headerData(
        TYPE_HINT_COLUMN, Qt.Orientation.Horizontal, DISPLAY
    )

    assert header == "Python type"
    assert tab.header().isSectionHidden(TYPE_HINT_COLUMN)


def test_the_header_names_the_columns_for_a_person(tab: Any) -> None:
    proxy = tab.model()

    headers = [
        proxy.headerData(column, Qt.Orientation.Horizontal, DISPLAY)
        for column in range(3)
    ]

    assert headers == ["Attribute", "Value", "Type"]


def test_the_search_finds_an_attribute_by_the_name_that_is_shown(
    tab: Any,
) -> None:
    from aas_workingbench.settings.app_settings import ATTRIBUTE_COLUMN

    proxy = tab.model()

    found = proxy.search("displayName", [ATTRIBUTE_COLUMN], regExp=False)

    assert len(found) == 1
    assert found[0].data(DISPLAY) == "displayName"
    proxy.show_all_items()


def test_a_click_on_the_attribute_header_sorts_by_the_names_that_are_shown(
    tab: Any,
) -> None:
    from aas_workingbench.settings.app_settings import ATTRIBUTE_COLUMN

    proxy = tab.model()

    proxy.sort(ATTRIBUTE_COLUMN, Qt.SortOrder.AscendingOrder)
    shown = [
        proxy.index(row, 0).data(DISPLAY) for row in range(proxy.rowCount())
    ]
    proxy.sort(-1)

    assert shown == sorted(shown)


def test_the_rows_of_extensions_keep_their_order_though_named_by_key(
    lab_class: Any,
) -> None:
    element = make_property(ELEMENT_ID)
    for name in ("Two", "One", "Three"):
        element.extension.add(model.Extension(name))
    attrs = lab_class(element).attrs()
    proxy = attrs.model()
    extensions = _index(attrs, "extension")

    names = [
        proxy.index(row, 0, extensions).data(DISPLAY)
        for row in range(proxy.rowCount(extensions))
    ]

    assert names == ["Two", "One", "Three"]
