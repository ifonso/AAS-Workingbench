"""Copying a qualifier row puts JSON on the clipboard, which can be added back."""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtWidgets import QApplication
from tests.factories import make_property

from aas_workingbench.domain.clipboard_json import load_members
from aas_workingbench.domain.member_json import MemberKind


def _copy_first_qualifier(lab_class: Any) -> str:
    prop = make_property("Element")
    prop.qualifier.add(
        model.Qualifier("Cardinality", model.datatypes.String, "One")
    )
    lab = lab_class(prop)
    attrs = lab.attrs()
    parent = lab.row(attrs, "qualifier").siblingAtColumn(0)
    index = attrs.model().index(0, 0, parent)
    selection = attrs.selectionModel()
    selection.clear()
    selection.select(index, QItemSelectionModel.SelectionFlag.Select)
    attrs.onCopy()
    return QApplication.clipboard().text()


def test_a_copied_qualifier_row_reads_back_as_that_qualifier(
    lab_class: Any,
) -> None:
    text = _copy_first_qualifier(lab_class)

    (qualifier,) = load_members(text, MemberKind.QUALIFIER)

    assert isinstance(qualifier, model.Qualifier)
    assert (qualifier.type, qualifier.value) == ("Cardinality", "One")
