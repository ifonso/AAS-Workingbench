# ruff: noqa: F811
"""F-EDT-08 criteria that the first audit found open."""

from PyQt6.QtWidgets import QApplication
from tests.factories import make_property
from tests.medium.test_paste_actions import pasting  # noqa: F401

from aas_editor.domain.clipboard_json import dump_objects


def _ids(container: object) -> list[str | None]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


def test_json_with_the_name_of_a_sibling_is_added_with_a_numbered_name(
    pasting,
) -> None:
    # F-EDT-08 AC6: the element comes from the clipboard alone, the name is
    # checked for uniqueness, and nothing else is touched.
    lab = pasting(make_property("A", "1"), make_property("B"))
    lab.act("structure.clear_buffer")
    QApplication.clipboard().setText(dump_objects([make_property("A", "2")]))
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("B"))

    lab.act("structure.paste_below")

    assert _ids(lab.submodel.submodel_element) == ["A", "B", "A_1"]
    original = lab.submodel.get_referable("A")
    assert original.value == "1"  # type: ignore[attr-defined]
    pasted = lab.submodel.get_referable("A_1")
    assert pasted.value == "2"  # type: ignore[attr-defined]
    lab.view.onUndo()
    assert _ids(lab.submodel.submodel_element) == ["A", "B"]
    assert not lab.package.commandStack.can_undo


def test_copied_elements_paste_in_the_order_of_the_tree_not_of_the_clicks(
    pasting,
) -> None:
    # F-EDT-08 AC9: three elements, selected in the order C, A, B.
    lab = pasting(*(make_property(n) for n in "ABC"), make_property("Z"))
    lab.select(
        lab.element_path("C"), lab.element_path("A"), lab.element_path("B")
    )
    lab.copy()
    lab.select(lab.element_path("Z"))

    lab.act("structure.paste_below")

    assert _ids(lab.submodel.submodel_element) == [
        "A",
        "B",
        "C",
        "Z",
        "A_1",
        "B_1",
        "C_1",
    ]
    assert lab.package.commandStack.undo_description
    lab.view.onUndo()
    assert _ids(lab.submodel.submodel_element) == ["A", "B", "C", "Z"]
