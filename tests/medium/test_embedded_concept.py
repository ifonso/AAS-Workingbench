"""The concept description in the tab of the object that refers to it.

F-EDT-03 AC15: a submodel with a semantic id that names a description shows it,
and one that names nothing shows the notice of the original. F-EDT-05 AC14:
the same for an element, read-only, and with no move panel.
"""

from typing import Any

from basyx.aas import model
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.domain.concept_summary import NOT_FOUND
from aas_editor.domain.data_specifications import IEC_61360_TEMPLATE_KEY

CONCEPT_ID = "0173-1#02-BAA120#008"


def _concept() -> model.ConceptDescription:
    concept = make_concept_description(CONCEPT_ID, "MaxSpeed")
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            make_external_reference(IEC_61360_TEMPLATE_KEY),
            model.DataSpecificationIEC61360(
                model.PreferredNameTypeIEC61360({"en": "Maximum speed"}),
                unit="m/s",
                symbol="v",
                data_type=model.DataTypeIEC61360.REAL_MEASURE,
            ),
        )
    )
    return concept


@pytest.fixture
def panel_for(views, qtbot: QtBot):
    from aas_editor.ui.embedded_concept import EmbeddedConceptPanel

    def make(target: Any, *others: model.Identifiable) -> Any:
        shown = views()
        package = shown.open_package(*others)
        panel = EmbeddedConceptPanel()
        qtbot.addWidget(panel)
        panel.set_target(package, target)
        return panel, package

    return make


def _speed(semantic: str | None = CONCEPT_ID) -> model.Property:
    prop = make_property("Speed")
    if semantic is not None:
        prop.semantic_id = make_external_reference(semantic)
    return prop


class TestPanel:
    def test_an_element_with_a_description_shows_it_collapsed(
        self, panel_for
    ) -> None:
        speed = _speed()
        panel, _ = panel_for(speed, make_submodel(elements=[speed]), _concept())

        assert not panel.isHidden()
        assert (
            panel.header == "Concept description MaxSpeed - en: Maximum speed"
        )
        assert not panel.is_expanded
        assert panel.details.isHidden()

    def test_expanding_lists_the_attributes_that_have_a_value(
        self, panel_for
    ) -> None:
        speed = _speed()
        panel, _ = panel_for(speed, make_submodel(elements=[speed]), _concept())

        panel.toggle.setChecked(True)

        rows = dict(panel.shown_rows)
        assert rows["Id:"] == CONCEPT_ID
        assert rows["Preferred name:"] == "en: Maximum speed"
        assert rows["Unit:"] == "m/s"
        assert rows["Data type:"] == "REAL_MEASURE"
        assert "Definition:" not in rows
        assert not panel.details.isHidden()

    def test_a_submodel_shows_its_description_too(self, panel_for) -> None:
        submodel = make_submodel()
        submodel.semantic_id = make_external_reference(CONCEPT_ID)
        panel, _ = panel_for(submodel, submodel, _concept())

        assert panel.concept is not None
        assert panel.concept.id == CONCEPT_ID

    def test_a_semantic_id_that_names_nothing_shows_the_notice(
        self, panel_for
    ) -> None:
        speed = _speed("urn:no:such:concept")
        panel, _ = panel_for(speed, make_submodel(elements=[speed]))

        assert not panel.isHidden()
        assert panel.concept is None
        assert panel.notice_text.startswith(NOT_FOUND)
        assert "urn:no:such:concept" in panel.notice_text
        assert panel.header == ""

    def test_an_element_without_a_semantic_id_shows_nothing(
        self, panel_for
    ) -> None:
        speed = _speed(None)
        panel, _ = panel_for(speed, make_submodel(elements=[speed]), _concept())

        assert panel.isHidden()
        assert panel.notice_text == ""

    @pytest.mark.parametrize(
        "make",
        [
            lambda concept: concept,
            lambda concept: model.AssetAdministrationShell(
                model.AssetInformation(global_asset_id="urn:asset"),
                "urn:shell",
            ),
        ],
        ids=["a concept description", "a shell"],
    )
    def test_other_objects_show_nothing(self, panel_for, make: Any) -> None:
        concept = _concept()
        panel, _ = panel_for(make(concept), concept)

        assert panel.isHidden()

    def test_the_panel_is_read_only(self, panel_for) -> None:
        from PyQt6.QtWidgets import QLineEdit
        from PyQt6.QtWidgets import QPlainTextEdit

        speed = _speed()
        panel, _ = panel_for(speed, make_submodel(elements=[speed]), _concept())
        panel.toggle.setChecked(True)

        assert panel.findChildren(QLineEdit) == []
        assert panel.findChildren(QPlainTextEdit) == []

    def test_it_follows_a_change_of_the_semantic_id(
        self, panel_for, qtbot: QtBot
    ) -> None:
        speed = _speed()
        panel, package = panel_for(
            speed, make_submodel(elements=[speed]), _concept()
        )

        package.commandStack.push(
            SetAttribute(
                observer_for(package),
                speed,
                "semantic_id",
                make_external_reference("urn:other"),
            )
        )
        qtbot.waitUntil(lambda: panel.concept is None)

        assert panel.notice_text.startswith(NOT_FOUND)

    def test_it_follows_an_edit_of_the_description(
        self, panel_for, qtbot: QtBot
    ) -> None:
        speed = _speed()
        concept = _concept()
        panel, package = panel_for(
            speed, make_submodel(elements=[speed]), concept
        )
        panel.toggle.setChecked(True)

        package.commandStack.push(
            SetAttribute(observer_for(package), concept, "id_short", "Renamed")
        )
        qtbot.waitUntil(lambda: "Renamed" in panel.header)

        assert panel.header.startswith("Concept description Renamed")

    def test_the_open_button_opens_the_description(self, panel_for) -> None:
        from aas_editor.ui.embedded_concept import EmbeddedConceptPanel

        speed = _speed()
        opened: list[model.ConceptDescription] = []
        panel, package = panel_for(
            speed, make_submodel(elements=[speed]), _concept()
        )
        other = EmbeddedConceptPanel(None, opened.append)
        other.set_target(package, speed)
        other.toggle.setChecked(True)

        other.open_button.click()

        assert [c.id for c in opened] == [CONCEPT_ID]


class TestInATab:
    @pytest.fixture
    def tabs(self, views, qtbot: QtBot):
        from aas_editor.widgets.tab import TabWidget

        speed = _speed()
        shown = views()
        shown.open_package(
            make_submodel(elements=[speed]),
            _concept(),
            make_submodel("urn:sm2", "Other"),
        )
        widget = TabWidget(unclosable=True)
        qtbot.addWidget(widget)
        widget.addTab(widget.tabCls(parent=widget), "Welcome")

        class Tabs:
            def open(self, *path: str) -> Any:
                widget.openItemInNewTab(shown.index(*path))
                return widget.currentWidget()

        return Tabs()

    def test_the_tab_of_an_element_has_the_panel_below_the_attributes(
        self, tabs
    ) -> None:
        tab = tabs.open("submodels", "Submodel", "Speed")

        assert tab.embeddedConcept.concept is not None
        assert tab.embeddedConcept.header.startswith("Concept description")

    def test_the_tab_of_the_description_itself_has_no_panel(self, tabs) -> None:
        tab = tabs.open("concept_descriptions", "MaxSpeed")

        assert tab.embeddedConcept.isHidden()

    def test_the_open_button_opens_the_description_and_back_returns(
        self, tabs
    ) -> None:
        tab = tabs.open("submodels", "Submodel", "Speed")
        tab.embeddedConcept.toggle.setChecked(True)

        tab.embeddedConcept.open_button.click()

        assert tab.packItemObj.id == CONCEPT_ID
        tab.openPrevItem()
        assert tab.packItemObj.id_short == "Speed"
