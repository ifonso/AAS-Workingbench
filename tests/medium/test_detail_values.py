"""What the detail of an element reads beside its values (proposals 3.4-3.7).

A text in languages reads in the language of the user with a badge, a semanticId
by the name of its concept with the id under it, and a value gets the unit that
its concept gives it, with a link to the concept. The concept description is
opened from those links, so the tab no longer has a panel for it below.
"""

from typing import Any

from basyx.aas import model
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY

CONCEPT_ID = "0173-1#02-BAA120#008"


def _concept() -> model.ConceptDescription:
    concept = make_concept_description(CONCEPT_ID, "MaxSpeed")
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            make_external_reference(IEC_61360_TEMPLATE_KEY),
            model.DataSpecificationIEC61360(
                model.PreferredNameTypeIEC61360({"en": "Maximum speed"}),
                unit="m/s",
            ),
        )
    )
    return concept


def _speed() -> model.Property:
    prop = make_property("Speed", value="2.0")
    prop.semantic_id = make_external_reference(CONCEPT_ID)
    prop.display_name = model.MultiLanguageNameType(
        {"en": "Speed", "de": "Geschwindigkeit", "pt": "Velocidade"}
    )
    return prop


@pytest.fixture
def tabs(views, qtbot: QtBot):
    from aas_workingbench.widgets.tab import TabWidget

    shown = views()
    shown.open_package(make_submodel(elements=[_speed()]), _concept())
    widget = TabWidget(unclosable=True)
    qtbot.addWidget(widget)
    widget.addTab(widget.tabCls(parent=widget), "Welcome")

    class Tabs:
        def open(self, *path: str) -> Any:
            widget.openItemInNewTab(shown.index(*path))
            return widget.currentWidget()

    return Tabs()


def _row(tab: Any, sdk_name: str):
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.settings.app_settings import VALUE_COLUMN

    proxy = tab.attrsTreeView.model()
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        if index.data(NAME_ROLE) == sdk_name:
            return index.siblingAtColumn(VALUE_COLUMN)
    raise LookupError(sdk_name)


def test_a_text_in_languages_reads_in_english_with_a_badge(tabs) -> None:
    from aas_workingbench.settings.app_settings import LANGUAGE_BADGE_ROLE

    tab = tabs.open("submodels", "Submodel", "Speed")
    value = _row(tab, "display_name")

    assert value.data() == "Speed"
    assert value.data(LANGUAGE_BADGE_ROLE) == "en +2"


def test_the_tooltip_of_a_text_in_languages_has_every_language(tabs) -> None:
    from PyQt6.QtCore import Qt

    tab = tabs.open("submodels", "Submodel", "Speed")

    tip = _row(tab, "display_name").data(Qt.ItemDataRole.ToolTipRole)

    assert "Geschwindigkeit" in tip and "Velocidade" in tip


def test_a_semantic_id_reads_the_name_of_its_concept_with_the_id_under_it(
    tabs,
) -> None:
    from aas_workingbench.settings.app_settings import IS_LINK_ROLE
    from aas_workingbench.settings.app_settings import SUBTEXT_ROLE

    tab = tabs.open("submodels", "Submodel", "Speed")
    value = _row(tab, "semantic_id")

    assert value.data() == "Maximum speed"
    assert value.data(SUBTEXT_ROLE) == CONCEPT_ID
    assert value.data(IS_LINK_ROLE)


def test_a_click_on_the_concept_opens_it_in_the_tab_and_back_returns(
    tabs,
) -> None:
    tab = tabs.open("submodels", "Submodel", "Speed")

    tab.attrsTreeView.clicked.emit(_row(tab, "semantic_id"))

    assert tab.packItemObj.id == CONCEPT_ID
    tab.openPrevItem()
    assert tab.packItemObj.id_short == "Speed"


def test_the_value_gets_the_unit_that_its_concept_gives(tabs) -> None:
    from aas_workingbench.settings.app_settings import UNIT_ROLE

    tab = tabs.open("submodels", "Submodel", "Speed")
    value = _row(tab, "value")

    assert value.data() == "2.0"
    assert value.data(UNIT_ROLE) == ("m/s", "MaxSpeed")


def test_a_click_on_the_value_does_not_open_the_concept(tabs) -> None:
    tab = tabs.open("submodels", "Submodel", "Speed")

    tab.attrsTreeView.clicked.emit(_row(tab, "value"))

    assert tab.packItemObj.id_short == "Speed"


def test_the_link_of_the_unit_opens_the_concept(tabs, qtbot: QtBot) -> None:
    from PyQt6.QtCore import Qt

    tab = tabs.open("submodels", "Submodel", "Speed")
    view = tab.attrsTreeView
    window = tab.window()
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    value = _row(tab, "value")
    view.viewport().grab()
    (link,) = view.itemDelegate().linkRects.values()

    qtbot.mouseClick(
        view.viewport(), Qt.MouseButton.LeftButton, pos=link.center()
    )

    assert value.isValid()
    assert tab.packItemObj.id == CONCEPT_ID


def test_the_tab_has_no_panel_of_the_concept_below_the_attributes(
    tabs,
) -> None:
    from aas_workingbench.ui.embedded_concept import EmbeddedConceptPanel

    tab = tabs.open("submodels", "Submodel", "Speed")

    assert tab.findChildren(EmbeddedConceptPanel) == []


def test_the_editor_of_a_value_says_its_type_inside(tabs, qtbot: QtBot) -> None:
    from PyQt6.QtWidgets import QStyleOptionViewItem
    from PyQt6.QtWidgets import QWidget

    tab = tabs.open("submodels", "Submodel", "Speed")
    value = _row(tab, "value")
    holder = QWidget()
    qtbot.addWidget(holder)

    editor = tab.attrsTreeView.itemDelegate().createEditor(
        holder, QStyleOptionViewItem(), value
    )

    assert editor.type_inside() == "xs:string"
