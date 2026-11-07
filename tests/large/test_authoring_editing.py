"""A person edits the package they built: rename, retype, move, paste, convert.

The package comes from `build_everything`, which builds it through the dialogs
from an empty window. Every edit here goes through the context menu actions,
the Edit menu, the cells and the attribute tabs. Each one must be a step that
undo takes back and redo gives again, the references must follow, and the
package saved and opened again must hold what the editor showed.
"""

from pathlib import Path

from basyx.aas.model import datatypes
import pytest
from tests.authoring import Author
from tests.authoring_builders import EVERYTHING
from tests.authoring_builders import SUBMODEL
from tests.authoring_builders import build_everything
from tests.authoring_builders import everything
from tests.authoring_builders import findings
from tests.authoring_builders import reopened
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


def test_renaming_an_id_and_an_idshort_updates_the_references_that_name_them(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.reference_dialogs import RenameDialog

    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    held = everything(author)
    alarm = held.get_referable("Alarm")
    voltage = held.get_referable("Voltage")
    shell = author.package.objStore.get_item("urn:example:aas:pump")

    # The id of a submodel: the shell and the event refer to it.
    author.select_path(*SUBMODEL)
    with author.answering(
        RenameDialog, lambda d: d.edit.setText("urn:example:sm:everything-v2")
    ) as answer:
        assert author.act("references.rename_id")
    author.assert_accepted(answer)
    assert held.id == "urn:example:sm:everything-v2"
    assert "urn:example:sm:everything-v2" in [
        r.key[0].value for r in shell.submodel
    ]
    assert "urn:example:sm:everything" not in [
        r.key[0].value for r in shell.submodel
    ]
    assert alarm.observed.key[0].value == "urn:example:sm:everything-v2"

    # The id of the concept description that Voltage has as its semantic id.
    author.select_path("concept_descriptions", "Speed")
    with author.answering(
        RenameDialog, lambda d: d.edit.setText("urn:example:cd:speed-v2")
    ) as answer:
        assert author.act("references.rename_id")
    author.assert_accepted(answer)
    assert voltage.semantic_id.key[0].value == "urn:example:cd:speed-v2"

    # The idShort of an element that the event observes.
    author.select_path(*SUBMODEL, "Voltage")
    with author.answering(
        RenameDialog, lambda d: d.edit.setText("Supply")
    ) as answer:
        assert author.act("references.rename_id_short")
    author.assert_accepted(answer)
    assert voltage.id_short == "Supply"
    assert [k.value for k in alarm.observed.key] == [
        "urn:example:sm:everything-v2",
        "Supply",
    ]
    assert "Supply" in author.names(*SUBMODEL)

    assert findings(author) == []
    renamed = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == renamed
    assert author.undo_to_saved() == 3
    assert snapshot(author.package.objStore) == before
    assert alarm.observed.key[0].value == EVERYTHING
    assert author.redo_all() == 3
    assert snapshot(author.package.objStore) == renamed


def test_a_value_type_changes_through_its_dialog_and_a_value_that_does_not_fit_is_refused(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    author.stack.mark_saved()
    voltage = everything(author).get_referable("Voltage")
    tab = author.open_tab(*SUBMODEL, "Voltage")

    def choose(type_: type) -> None:
        def fill(dialog) -> None:
            box = dialog.inputWidget.widget
            box.setCurrentIndex(box.findData(type_))

        answer = author.edit_attribute_in_dialog(tab, "value_type", fill)
        author.assert_accepted(answer)

    choose(datatypes.Decimal)
    assert voltage.value_type is datatypes.Decimal
    assert voltage.value == 230
    assert author.edit_attribute(tab, "value", "12.5")
    assert voltage.value == datatypes.Decimal("12.5")

    # 12.5 is no whole number, so the value type Int is refused, with a reason.
    author.errors.clear()
    choose(datatypes.Int)
    assert voltage.value_type is datatypes.Decimal
    assert voltage.value == datatypes.Decimal("12.5")
    assert author.errors
    assert "xs:int" in author.errors[0]

    # Text that is no value of the type is refused, and the value stays.
    author.errors.clear()
    assert not author.edit_attribute(tab, "value", "twelve")
    assert voltage.value == datatypes.Decimal("12.5")
    assert "not a valid xs:decimal" in author.errors[0]

    changed = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == changed
    assert author.undo_to_saved() == 2
    assert voltage.value_type is datatypes.Int
    assert voltage.value == 230
    assert author.redo_all() == 2
    assert snapshot(author.package.objStore) == changed


def _group(author: Author) -> list[str]:
    """The names of the children of the collection Group, in the tree."""
    return author.names(*SUBMODEL, "Group")


def _group_objects(author: Author) -> list[str]:
    group = everything(author).get_referable("Group")
    return [element.id_short for element in group.value]


def test_elements_are_moved_and_the_tree_the_objects_and_the_file_keep_one_order(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    assert _group(author) == ["Speed", "Inner", "Readings", "Rows"]

    author.select_path(*SUBMODEL, "Group", "Rows")
    assert author.act("structure.move_top")
    assert _group(author) == _group_objects(author)
    assert _group(author) == ["Rows", "Speed", "Inner", "Readings"]

    author.select_path(*SUBMODEL, "Group", "Speed")
    assert author.act("structure.move_end")
    author.select_path(*SUBMODEL, "Group", "Inner")
    assert author.act("structure.move_down")
    author.select_path(*SUBMODEL, "Group", "Readings")
    assert author.act("structure.move_up")

    assert _group(author) == _group_objects(author)
    assert _group(author) == ["Readings", "Rows", "Inner", "Speed"]
    moved = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == moved
    assert author.undo_to_saved() == 4
    assert _group(author) == ["Speed", "Inner", "Readings", "Rows"]
    assert snapshot(author.package.objStore) == before
    assert author.redo_all() == 4
    assert _group(author) == _group_objects(author)
    assert snapshot(author.package.objStore) == moved


def test_elements_are_copied_cut_and_pasted_above_below_and_into(
    author: Author, tmp_path: Path
) -> None:
    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    top = [e.id_short for e in everything(author).submodel_element]

    # Copy Speed, and paste it below Rows: a copy with a new idShort.
    author.select_path(*SUBMODEL, "Group", "Speed")
    assert author.edit_menu("copy")
    author.select_path(*SUBMODEL, "Group", "Rows")
    assert author.edit_menu("paste_below")
    assert _group(author) == _group_objects(author)
    assert _group(author)[-2] == "Rows"
    assert _group(author)[-1].startswith("Speed")
    copy_name = _group(author)[-1]
    assert copy_name != "Speed"
    group = everything(author).get_referable("Group")
    assert group.get_referable(copy_name).value == 1500

    # Paste the same copy above Speed.
    author.select_path(*SUBMODEL, "Group", "Speed")
    assert author.edit_menu("paste_above")
    assert _group(author) == _group_objects(author)
    assert _group(author)[0].startswith("Speed")
    assert _group(author)[0] != "Speed"
    assert _group(author)[1] == "Speed"

    # Cut Limits from the top of the submodel, and paste it into Inner.
    author.select_path(*SUBMODEL, "Limits")
    assert author.edit_menu("cut")
    assert "Limits" not in [
        e.id_short for e in everything(author).submodel_element
    ]
    author.select_path(*SUBMODEL, "Group", "Inner")
    assert author.edit_menu("paste_into")
    inner = group.get_referable("Inner")
    assert "Limits" in [e.id_short for e in inner.value]
    assert inner.get_referable("Limits").max == 10
    assert [e.id_short for e in everything(author).submodel_element] == [
        name for name in top if name != "Limits"
    ]

    assert findings(author) == []
    pasted = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == pasted
    assert author.undo_to_saved() == 4
    assert snapshot(author.package.objStore) == before
    assert author.redo_all() == 4
    assert snapshot(author.package.objStore) == pasted
