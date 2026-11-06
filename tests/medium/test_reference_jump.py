"""Jumping from a reference to its target, and back (F-EDT-11 AC19 to AC21).

The jump runs from the row of a reference in a tab. A
target that is missing gets a message, and a reference that resolves in part
opens the closest object and says what was not found.
"""

from typing import Any

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

K = model.KeyTypes


@pytest.fixture
def jumping(views, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch):
    """A package whose property refers to other objects, and a tab to jump in."""
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.ui import reference_jump
    from aas_editor.ui.reference_jump import register_jump_actions
    from aas_editor.widgets.tab import TabWidget

    register_jump_actions()
    notices: list[str] = []
    monkeypatch.setattr(
        reference_jump,
        "show_notice",
        lambda text, parent=None: notices.append(text),
    )

    class Jumping:
        def __init__(self, semantic_id: Any) -> None:
            self.concept = make_concept_description()
            self.target = make_property("Target")
            self.inner = make_collection("Inner", [self.target])
            self.start = make_property("Start")
            self.submodel = make_submodel(elements=[self.start, self.inner])
            self.shell = make_shell(submodels=[self.submodel])
            self.start.semantic_id = semantic_id(self)
            self.shown = views()
            self.package = self.shown.open_package(
                self.shell, self.submodel, self.concept
            )
            self.notices = notices
            self.tabs = TabWidget(unclosable=True)
            qtbot.addWidget(self.tabs)
            self.tabs.addTab(self.tabs.tabCls(parent=self.tabs), "Welcome")
            self.tabs.openItemInNewTab(
                self.shown.index("submodels", "Submodel", "Start")
            )

        @property
        def tab(self) -> Any:
            return self.tabs.currentWidget()

        def select_attribute(self, name: str) -> Any:
            attrs = self.tab.attrsTreeView
            proxy = attrs.model()
            for row in range(proxy.rowCount()):
                index = proxy.index(row, 0)
                if index.data(NAME_ROLE) == name:
                    attrs.setCurrentIndex(index.siblingAtColumn(1))
                    return attrs
            raise LookupError(name)

        def jump(self) -> bool:
            action = self.tab.attrsTreeView.registeredActions.find(
                "reference.jump"
            )
            enabled = action.isEnabled()
            action.trigger()
            return enabled

    return Jumping


def test_jump_opens_a_resolving_model_reference_in_the_same_tab(
    jumping,
) -> None:
    jump = jumping(lambda world: make_reference_to(world.concept))
    jump.select_attribute("semantic_id")

    enabled = jump.jump()

    assert enabled
    assert jump.tab.packItemObj is jump.concept
    assert jump.notices == []


def test_back_returns_to_the_object_that_was_being_edited(jumping) -> None:
    jump = jumping(lambda world: make_reference_to(world.concept))
    jump.select_attribute("semantic_id")

    jump.jump()
    on_target = jump.tab.packItemObj
    jump.tab.backAct.trigger()

    assert on_target is jump.concept
    assert jump.tab.packItemObj is jump.start
    assert jump.tab.forwardAct.isEnabled()


def test_an_external_reference_to_an_id_of_the_package_jumps_to_it(
    jumping,
) -> None:
    jump = jumping(lambda world: make_external_reference(world.concept.id))
    jump.select_attribute("semantic_id")

    jump.jump()

    assert jump.tab.packItemObj is jump.concept


def test_a_reference_to_an_unknown_id_says_the_target_is_missing(
    jumping,
) -> None:
    jump = jumping(
        lambda world: model.ModelReference(
            (model.Key(K.CONCEPT_DESCRIPTION, "urn:example:nowhere"),),
            ConceptDescription,
        )
    )
    jump.select_attribute("semantic_id")

    jump.jump()

    assert jump.tab.packItemObj is jump.start
    (message,) = jump.notices
    assert "Target not found" in message
    assert "urn:example:nowhere" in message


def test_a_reference_that_resolves_in_part_opens_the_closest_object(
    jumping,
) -> None:
    jump = jumping(
        lambda world: model.ModelReference(
            (
                model.Key(K.SUBMODEL, world.submodel.id),
                model.Key(K.SUBMODEL_ELEMENT_COLLECTION, "Inner"),
                model.Key(K.PROPERTY, "Missing"),
            ),
            model.Property,
        )
    )
    jump.select_attribute("semantic_id")

    jump.jump()

    assert jump.tab.packItemObj is jump.inner
    (message,) = jump.notices
    assert "Missing" in message
    assert "Inner" in message


def test_an_external_reference_outside_the_package_has_nothing_to_open(
    jumping,
) -> None:
    jump = jumping(
        lambda world: make_external_reference("urn:example:elsewhere")
    )
    jump.select_attribute("semantic_id")

    jump.jump()

    assert jump.tab.packItemObj is jump.start
    (message,) = jump.notices
    assert "outside" in message


def test_the_jump_is_not_offered_on_a_row_without_a_reference(jumping) -> None:
    jump = jumping(
        lambda world: make_external_reference("urn:example:elsewhere")
    )
    jump.select_attribute("id_short")

    action = jump.tab.attrsTreeView.registeredActions.find("reference.jump")

    assert not action.isEnabled()


def test_the_jump_works_in_read_mode(jumping) -> None:
    from aas_editor.application.editing import edit_mode

    jump = jumping(lambda world: make_reference_to(world.concept))
    edit_mode().set_editing(False)
    try:
        jump.select_attribute("semantic_id")
        enabled = jump.jump()
    finally:
        edit_mode().set_editing(True)

    assert enabled
    assert jump.tab.packItemObj is jump.concept
