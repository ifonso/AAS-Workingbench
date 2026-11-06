"""Deleting a supplemental semantic id must not touch the semantic id.

The original editor has the defect that its "Delete supplementalSemanticId"
clears the `semanticId` and leaves the supplemental ids as they are
(KNOWN-DEFECTS, F-EDT-06). Here the delete goes through the views, as a user
presses it.
"""

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
import pytest
from tests.factories import make_external_reference
from tests.medium.conftest import ELEMENT_ID
from tests.serialization import snapshot


def _property_with_ids() -> model.Property:
    element = model.Property(ELEMENT_ID, value_type=str, value="x")
    element.semantic_id = make_external_reference("urn:example:main")
    element.supplemental_semantic_id.append(
        make_external_reference("urn:example:first")
    )
    element.supplemental_semantic_id.append(
        make_external_reference("urn:example:second")
    )
    return element


def _select_row(lab, attrs, name: str, child: str) -> None:
    # The tab selects whole rows, as it does when the user clicks a row.
    attrs.setCurrentIndex(lab.row(attrs, name, child).siblingAtColumn(0))


def _child_names(lab, attrs, name: str) -> list[str]:
    proxy = attrs.model()
    parent: QModelIndex = lab.row(attrs, name).siblingAtColumn(0)
    from aas_editor.settings.app_settings import NAME_ROLE

    return [
        proxy.index(row, 0, parent).data(NAME_ROLE)
        for row in range(proxy.rowCount(parent))
    ]


def test_deleting_a_supplemental_semantic_id_keeps_the_semantic_id(
    lab_class,
) -> None:
    element = _property_with_ids()
    lab = lab_class(element)
    attrs = lab.attrs()
    first = "ExternalReference 0"

    _select_row(lab, attrs, "supplemental_semantic_id", first)
    attrs.onDelClear()

    assert element.semantic_id is not None
    assert element.semantic_id.key[0].value == "urn:example:main"
    assert [ref.key[0].value for ref in element.supplemental_semantic_id] == [
        "urn:example:second"
    ]


def test_deleting_the_last_supplemental_semantic_id_leaves_an_empty_list(
    lab_class,
) -> None:
    element = _property_with_ids()
    del element.supplemental_semantic_id[1]
    lab = lab_class(element)
    attrs = lab.attrs()
    (only,) = _child_names(lab, attrs, "supplemental_semantic_id")

    _select_row(lab, attrs, "supplemental_semantic_id", only)
    attrs.onDelClear()

    assert len(element.supplemental_semantic_id) == 0
    assert element.semantic_id is not None
    assert "supplementalSemanticIds" not in snapshot(lab.package.objStore)


def test_undo_gives_back_the_supplemental_semantic_id(lab_class) -> None:
    element = _property_with_ids()
    lab = lab_class(element)
    attrs = lab.attrs()
    before = snapshot(lab.package.objStore)
    first = "ExternalReference 0"

    _select_row(lab, attrs, "supplemental_semantic_id", first)
    attrs.onDelClear()
    lab.stack.undo()

    assert snapshot(lab.package.objStore) == before


def test_clearing_the_semantic_id_is_refused_while_supplemental_ids_exist(
    lab_class,
) -> None:
    element = _property_with_ids()
    lab = lab_class(element)
    attrs = lab.attrs()
    attrs.setCurrentIndex(lab.row(attrs, "semantic_id").siblingAtColumn(0))

    attrs.onDelClear()

    # The SDK refuses (AASd-118), and nothing changes.
    assert element.semantic_id is not None
    assert len(element.supplemental_semantic_id) == 2
    assert lab.shown.shown_errors[0].endswith("(Constraint AASd-118)")
    assert not lab.stack.can_undo


def test_the_semantic_id_can_be_cleared_once_no_supplemental_id_is_left(
    lab_class,
) -> None:
    element = _property_with_ids()
    del element.supplemental_semantic_id[:]
    lab = lab_class(element)
    attrs = lab.attrs()
    attrs.setCurrentIndex(lab.row(attrs, "semantic_id").siblingAtColumn(0))

    attrs.onDelClear()

    assert element.semantic_id is None


@pytest.mark.parametrize("which", [0, 1])
def test_each_supplemental_semantic_id_can_be_deleted_on_its_own(
    lab_class, which: int
) -> None:
    element = _property_with_ids()
    lab = lab_class(element)
    attrs = lab.attrs()
    kept = element.supplemental_semantic_id[1 - which].key[0].value

    _select_row(
        lab, attrs, "supplemental_semantic_id", f"ExternalReference {which}"
    )
    attrs.onDelClear()

    assert [ref.key[0].value for ref in element.supplemental_semantic_id] == [
        kept
    ]
