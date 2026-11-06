# ruff: noqa: F811
"""F-EDT-11 criteria that the first audit found open."""

from typing import Any

from basyx.aas import model
from tests.factories import make_external_reference
from tests.medium.conftest import ELEMENT_ID
from tests.medium.test_reference_picker_fields import picking  # noqa: F401
from tests.serialization import snapshot

K = model.KeyTypes


def test_picking_for_a_supplemental_semantic_id_appends_a_reference(
    picking,
) -> None:
    element = model.Property(
        ELEMENT_ID,
        value_type=str,
        value="x",
        semantic_id=make_external_reference("urn:example:main"),
        supplemental_semantic_id=[make_external_reference("urn:example:first")],
    )
    flow = picking(element)
    lab = flow.lab
    before = snapshot(lab.package.objStore)
    attrs = lab.attrs()

    def fill(dialog: Any) -> None:
        box = dialog.inputWidget
        box._addInputWidget()  # What the Add Item button does.
        added = box.inputWidgets[-1]
        field = getattr(added, "widget", added)
        flow.pick(field, lambda picker: picker.select(flow.concept))

    lab.edit_in_dialog(attrs, "supplemental_semantic_id", fill)

    keys = [
        [key.value for key in ref.key]
        for ref in element.supplemental_semantic_id
    ]
    assert keys == [["urn:example:first"], [flow.concept.id]]
    assert [key.value for key in element.semantic_id.key] == [
        "urn:example:main"
    ]
    assert element.supplemental_semantic_id[1].key[0].type is K.GLOBAL_REFERENCE
    assert lab.shown.shown_errors == []
    assert lab.stack.can_undo
    lab.stack.undo()
    assert snapshot(lab.package.objStore) == before
