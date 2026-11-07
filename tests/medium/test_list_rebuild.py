"""Changing what a SubmodelElementList fixes, through the context menu action."""

from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.serialization import snapshot

from aas_workingbench.domain.list_settings import ListSettings
from aas_workingbench.domain.replacement import ReplacementPlan

ACTION = "conversion.list_settings"
STRING = model.datatypes.String
INT = model.datatypes.Int
SEMANTIC_ID = make_external_reference("urn:example:item")


def _texts(*values: str) -> list[model.SubmodelElement]:
    return [model.Property(None, STRING, value) for value in values]


class Rebuilds:
    """Runs the action on the list of a lab, with the dialogs stubbed."""

    def __init__(self, lab: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        from aas_workingbench.ui import reference_dialogs
        from aas_workingbench.ui import replacement_dialogs

        self.lab = lab
        self.settings: ListSettings | None = None
        self.asked: list[ReplacementPlan] = []
        self.answer = True
        self.messages: list[str] = []
        monkeypatch.setattr(
            replacement_dialogs,
            "ask_list_settings",
            lambda item_list, parent=None: self.settings,
        )

        def confirm(title, intro, plan, updates, accept_text, parent=None):
            self.asked.append(plan)
            return self.answer

        monkeypatch.setattr(replacement_dialogs, "confirm_replacement", confirm)
        monkeypatch.setattr(
            reference_dialogs,
            "show_message",
            lambda title, text, parent=None: self.messages.append(text),
        )

    def run(self, settings: ListSettings | None) -> None:
        self.settings = settings
        shown = self.lab.shown
        index = shown.index(*ELEMENT_PATH)
        shown.select(index)
        shown.view.updateActions(index)
        shown.view.registeredActions.find(ACTION).trigger()


@pytest.fixture
def registered(qapp: object) -> None:
    from aas_workingbench.ui.conversion_actions import (
        register_conversion_actions,
    )

    register_conversion_actions()


def _lab(lab_class: Any, items: list[model.SubmodelElement]) -> Any:
    return lab_class(
        make_property("Before"),
        make_list(ELEMENT_ID, items),
        make_property("After"),
    )


def test_the_order_of_a_list_can_be_changed_and_undone(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a", "b"))
    rebuilds = Rebuilds(lab, monkeypatch)
    before = snapshot(lab.package.objStore)

    rebuilds.run(ListSettings(model.Property, STRING, None, False))
    changed = snapshot(lab.package.objStore)
    order = lab.element().order_relevant
    lab.stack.undo()
    undone_order = lab.element().order_relevant
    undone = snapshot(lab.package.objStore)
    lab.stack.redo()
    reloaded = lab.save_and_reload()

    assert order is False
    assert undone_order is True
    assert undone == before
    assert reloaded == changed
    assert [e.id_short for e in lab.submodel.submodel_element] == [
        "Before",
        ELEMENT_ID,
        "After",
    ]
    assert rebuilds.asked == []


def test_a_new_value_type_keeps_the_items_that_convert_and_names_the_rest(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("12", "abc", "7"))
    rebuilds = Rebuilds(lab, monkeypatch)
    before = snapshot(lab.package.objStore)

    rebuilds.run(ListSettings(model.Property, INT, None, True))
    values = [item.value for item in lab.element().value]
    reloaded = lab.save_and_reload()
    changed = snapshot(lab.package.objStore)
    lab.stack.undo()

    assert values == [12, 7]
    assert reloaded == changed
    assert [str(loss.what) for loss in rebuilds.asked[0].losses] == [
        "item not kept"
    ]
    assert "abc" in rebuilds.asked[0].losses[0].detail
    assert snapshot(lab.package.objStore) == before
    assert [item.value for item in lab.element().value] == ["12", "abc", "7"]


def test_declining_the_dropped_items_changes_nothing(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a", "b"))
    rebuilds = Rebuilds(lab, monkeypatch)
    rebuilds.answer = False
    before = snapshot(lab.package.objStore)

    rebuilds.run(ListSettings(model.File, None, None, True))

    assert snapshot(lab.package.objStore) == before
    assert not lab.stack.can_undo


def test_a_new_item_type_empties_the_list_after_the_user_agreed(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a", "b"))
    rebuilds = Rebuilds(lab, monkeypatch)

    rebuilds.run(ListSettings(model.File, None, None, True))
    new = lab.element()
    reloaded = lab.save_and_reload()
    changed = snapshot(lab.package.objStore)

    assert new.type_value_list_element is model.File
    assert len(new.value) == 0
    assert len(rebuilds.asked[0].losses) == 2
    assert reloaded == changed


def test_a_semantic_id_for_the_items_is_set_by_a_rebuild(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a"))
    rebuilds = Rebuilds(lab, monkeypatch)

    rebuilds.run(ListSettings(model.Property, STRING, SEMANTIC_ID, True))

    assert lab.element().semantic_id_list_element == SEMANTIC_ID
    assert lab.save_and_reload() == snapshot(lab.package.objStore)


def test_settings_the_list_has_already_are_refused_with_a_message(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a"))
    rebuilds = Rebuilds(lab, monkeypatch)

    rebuilds.run(ListSettings(model.Property, STRING, None, True))

    assert rebuilds.messages == ["The list has these settings already."]
    assert not lab.stack.can_undo


def test_cancelling_the_dialog_changes_nothing(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a"))
    rebuilds = Rebuilds(lab, monkeypatch)

    rebuilds.run(None)

    assert not lab.stack.can_undo
    assert rebuilds.messages == []


def test_a_reference_to_an_item_keeps_pointing_at_it(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("1", "abc", "3"))
    third = list(lab.element().value)[2]
    pointer = model.ReferenceElement(
        "Pointer", model.ModelReference.from_referable(third)
    )
    lab.submodel.submodel_element.add(pointer)
    rebuilds = Rebuilds(lab, monkeypatch)

    rebuilds.run(ListSettings(model.Property, INT, None, True))

    target = pointer.value.resolve(lab.package.objStore)  # type: ignore[union-attr]
    assert target.value == 3
    assert [key.value for key in pointer.value.key][1:] == [ELEMENT_ID, "1"]  # type: ignore[union-attr]


def test_the_action_is_for_lists_only(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, _texts("a"))
    Rebuilds(lab, monkeypatch)
    shown = lab.shown
    action = shown.view.registeredActions.find(ACTION)

    on_property = shown.index("submodels", "Submodel", "Before")
    shown.select(on_property)
    shown.view.updateActions(on_property)
    off = action.isEnabled()
    on_list = shown.index(*ELEMENT_PATH)
    shown.select(on_list)
    shown.view.updateActions(on_list)

    assert (off, action.isEnabled()) == (False, True)


def test_the_edit_of_a_fixed_attribute_points_to_the_action(
    lab_class: Any,
) -> None:
    lab = lab_class(make_list(ELEMENT_ID, _texts("a")))
    attrs = lab.attrs()

    edited = lab.set(attrs, "order_relevant", False)

    assert not edited
    assert lab.refusal == (
        "'order_relevant' cannot be changed after the SubmodelElementList is "
        "made. Choose 'Change list settings...' in the context menu of the "
        "list to rebuild it"
    )


def test_the_dialog_starts_with_the_settings_of_the_list(qapp: object) -> None:
    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        semantic_id_list_element=SEMANTIC_ID,
        value_type_list_element=INT,
        order_relevant=False,
    )

    dialog = ListSettingsDialog(item_list)

    assert dialog.settings() == ListSettings(
        model.Property, INT, SEMANTIC_ID, False
    )


def test_the_dialog_gives_a_global_id_as_an_external_reference(
    qapp: object,
) -> None:
    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    item_list = model.SubmodelElementList(
        "Items", model.Property, value_type_list_element=STRING
    )
    dialog = ListSettingsDialog(item_list)

    dialog.semantic_box.setCurrentIndex(dialog.semantic_box.findData("global"))
    dialog.semantic_edit.setText("0173-1#02-AAO677#002")

    assert dialog.settings().semantic_id == make_external_reference(
        "0173-1#02-AAO677#002"
    )


def test_the_value_type_applies_to_property_and_range_items_only(
    qapp: object,
) -> None:
    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    item_list = model.SubmodelElementList(
        "Items", model.Property, value_type_list_element=INT
    )
    dialog = ListSettingsDialog(item_list)

    dialog.type_box.setCurrentIndex(dialog.type_box.findData(model.File))

    assert not dialog.value_type_box.isEnabled()
    assert dialog.settings().value_type is None


def test_detecting_takes_the_settings_the_items_share(qapp: object) -> None:
    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    item_list = model.SubmodelElementList(
        "Items",
        model.Property,
        [model.Property(None, INT, 5, semantic_id=SEMANTIC_ID)],
        value_type_list_element=INT,
    )
    dialog = ListSettingsDialog(item_list)

    dialog.detect_button.click()

    assert dialog.settings() == ListSettings(
        model.Property, INT, SEMANTIC_ID, True
    )


def test_detecting_is_off_for_a_list_without_items(qapp: object) -> None:
    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    item_list = model.SubmodelElementList(
        "Items", model.Property, value_type_list_element=INT
    )

    assert not ListSettingsDialog(item_list).detect_button.isEnabled()
