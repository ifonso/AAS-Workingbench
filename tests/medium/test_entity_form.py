"""The form of a new Entity (F-EDT-04 AC17) and of an extension (F-EDT-07 AC12)."""

from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QLabel
from tests.medium.forms import Form

from aas_workingbench.application.hints import hints_mode

NOTICE = (
    "Enter the global asset id of the asset that this self-managed entity "
    "stands for"
)


def _notice(form: Form) -> QLabel:
    label = form.group.noticeLabel
    assert isinstance(label, QLabel)
    return label


def test_a_new_entity_is_self_managed_and_asks_for_the_global_asset_id(
    lab,
) -> None:
    seen: list[Any] = []

    def fill(form: Form) -> None:
        form.choose_type(model.Entity)
        form.type_text("id_short", "Element")
        combo = form.widget("entity_type").widget
        seen.append(combo.currentData())
        seen.append(((not _notice(form).isHidden()), _notice(form).text()))
        form.type_text("global_asset_id", "urn:asset:1")
        seen.append((not _notice(form).isHidden()))

    lab.add(fill)

    assert seen == [
        model.EntityType.SELF_MANAGED_ENTITY,
        (True, NOTICE),
        False,
    ]
    assert lab.element().entity_type is model.EntityType.SELF_MANAGED_ENTITY
    assert lab.element().global_asset_id == "urn:asset:1"


def test_the_notice_comes_back_when_the_global_asset_id_is_cleared(
    lab,
) -> None:
    seen: list[bool] = []

    def fill(form: Form) -> None:
        form.choose_type(model.Entity)
        form.type_text("id_short", "Element")
        form.type_text("global_asset_id", "urn:asset:1")
        seen.append((not _notice(form).isHidden()))
        form.type_text("global_asset_id", "")
        seen.append((not _notice(form).isHidden()))
        form.type_text("global_asset_id", "urn:asset:2")

    lab.add(fill)

    assert seen == [False, True]


def test_a_co_managed_entity_gets_no_notice(lab) -> None:
    seen: list[bool] = []

    def fill(form: Form) -> None:
        form.choose_type(model.Entity)
        form.type_text("id_short", "Element")
        form.choose("entity_type", model.EntityType.CO_MANAGED_ENTITY)
        seen.append((not _notice(form).isHidden()))

    lab.add(fill)

    assert seen == [False]
    assert lab.element().entity_type is model.EntityType.CO_MANAGED_ENTITY


def test_hints_mode_off_hides_the_notice(lab) -> None:
    hints_mode().set_on(False)
    seen: list[bool] = []

    def fill(form: Form) -> None:
        form.choose_type(model.Entity)
        form.type_text("id_short", "Element")
        form.choose("entity_type", model.EntityType.SELF_MANAGED_ENTITY)
        seen.append((not _notice(form).isHidden()))
        form.type_text("global_asset_id", "urn:asset:1")

    lab.add(fill)

    assert seen == [False]


def test_a_blank_name_of_an_extension_shows_the_hint_in_its_form(
    qapp: object,
) -> None:
    from aas_workingbench.ui.inline_hints import InlineHint
    from aas_workingbench.widgets.groupBoxes import ObjGroupBox

    box = ObjGroupBox(model.Extension, rmDefParams=True)
    field = box.paramWidgets["name"].widget
    hint = field.findChild(InlineHint)
    assert hint is not None
    blank = hint.text

    field.setText("BOM.Args")

    assert blank.startswith("An extension needs a name")
    assert hint.text == ""
