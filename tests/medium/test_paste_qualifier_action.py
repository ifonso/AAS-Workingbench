"""Paste into an existing qualifier, in a tab (F-EDT-07 AC4 and AC5)."""

import json
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication
import pytest
from tests.factories import make_property
from tests.serialization import snapshot

from aas_workingbench.application.editing import edit_mode

CLIPBOARD_KIND = "ConceptQualifier"


@pytest.fixture
def pasting(lab_class, monkeypatch: pytest.MonkeyPatch):
    from aas_workingbench.ui import bulk_dialogs
    from aas_workingbench.ui.preset_actions import register_preset_actions

    register_preset_actions()
    prop = make_property("Element")
    prop.qualifier.add(
        model.Qualifier(
            "Cardinality",
            model.datatypes.String,
            "One",
            kind=model.QualifierKind.TEMPLATE_QUALIFIER,
        )
    )
    prop.qualifier.add(model.Qualifier("Other", model.datatypes.String, "o"))
    lab = lab_class(prop)
    problems: list[str] = []
    monkeypatch.setattr(
        bulk_dialogs,
        "show_problem",
        lambda title, message, parent=None: problems.append(message),
    )

    class Pasting:
        attrs = lab.attrs()
        problems_ = problems
        stack = lab.stack
        package = lab.package
        element = lab.element()

        @staticmethod
        def select(position: int) -> None:
            proxy = Pasting.attrs.model()
            parent = lab.row(Pasting.attrs, "qualifier").siblingAtColumn(0)
            index = proxy.index(position, 0, parent)
            selection = Pasting.attrs.selectionModel()
            selection.clear()
            selection.select(index, QItemSelectionModel.SelectionFlag.Select)

        @staticmethod
        def action() -> Any:
            return Pasting.attrs.registeredActions.find(
                "clipboard.paste_qualifier"
            )

        @staticmethod
        def qualifier(type_: str) -> model.Qualifier:
            return next(q for q in Pasting.element.qualifier if q.type == type_)

    return Pasting


def _clip(text: str) -> None:
    QApplication.clipboard().setText(text)  # pyright: ignore[reportOptionalMemberAccess]


def test_the_content_is_pasted_and_the_kind_stays(pasting) -> None:
    before = snapshot(pasting.package.objStore)
    pasting.select(0)
    _clip(
        json.dumps(
            {
                "type": "Mark",
                "valueType": "xs:int",
                "value": "5",
                "kind": CLIPBOARD_KIND,
            }
        )
    )

    enabled = pasting.action().isEnabled()
    pasting.action().trigger()
    pasted = pasting.qualifier("Mark")
    after = (pasted.value, pasted.kind)
    pasting.stack.undo()

    assert enabled
    assert after == (5, model.QualifierKind.TEMPLATE_QUALIFIER)
    assert snapshot(pasting.package.objStore) == before
    assert not pasting.stack.can_undo
    assert pasting.problems_ == []


def test_text_that_is_no_qualifier_changes_nothing_and_says_why(
    pasting,
) -> None:
    before = snapshot(pasting.package.objStore)
    pasting.select(0)
    _clip("this is not json")

    pasting.action().trigger()

    assert snapshot(pasting.package.objStore) == before
    assert not pasting.stack.can_undo
    assert len(pasting.problems_) == 1


def test_a_type_that_another_qualifier_has_is_refused_with_the_reason(
    pasting,
) -> None:
    before = snapshot(pasting.package.objStore)
    pasting.select(0)
    _clip(json.dumps({"type": "Other", "valueType": "xs:string"}))

    pasting.action().trigger()

    assert snapshot(pasting.package.objStore) == before
    assert len(pasting.problems_) == 1
    assert "AASd-021" in pasting.problems_[0]


def test_several_qualifiers_on_the_clipboard_are_refused(pasting) -> None:
    pasting.select(0)
    _clip(
        json.dumps(
            [
                {"type": "A", "valueType": "xs:string"},
                {"type": "B", "valueType": "xs:string"},
            ]
        )
    )

    pasting.action().trigger()

    assert not pasting.stack.can_undo
    assert "takes one" in pasting.problems_[0]


def test_the_action_is_for_a_qualifier_row_in_edit_mode(pasting) -> None:
    pasting.select(1)
    on_qualifier = pasting.action().isEnabled()
    selection = pasting.attrs.selectionModel()
    selection.clear()
    on_nothing = pasting.action().isEnabled()
    pasting.select(1)
    edit_mode().set_editing(False)
    pasting.select(1)

    assert on_qualifier
    assert not on_nothing
    assert not pasting.action().isEnabled()
