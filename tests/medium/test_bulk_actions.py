"""The bulk actions through the tree view: do, undo, redo, save, and reload."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QDialog
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode

SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def bulk(views, monkeypatch: pytest.MonkeyPatch):
    """A package that the bulk actions work on, and ways to drive them."""
    from aas_editor.package import Package
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.ui import bulk_dialogs
    from aas_editor.ui.bulk_dialogs import ChangeAttributeDialog
    from aas_editor.ui.bulk_dialogs import RemoveExtensionsDialog
    from aas_editor.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_editor.ui.move_actions import register_move_actions

    register_bulk_edit_actions()
    register_move_actions()

    class Bulk:
        problems: list[str]

        def __init__(self, *elements: model.SubmodelElement, extra=()):
            self.shown = views()
            self.submodel = make_submodel(elements=elements)
            self.package = self.shown.open_package(self.submodel, *extra)
            self.view = self.shown.view
            self.stack = self.package.commandStack
            self.problems = []
            monkeypatch.setattr(
                bulk_dialogs,
                "show_problem",
                lambda title, message, parent=None: self.problems.append(
                    message
                ),
            )

        def select(self, *paths: tuple[str, ...]) -> None:
            self.shown.select(*(self.shown.index(*SUBMODEL, *p) for p in paths))

        def action(self, action_id: str):
            return self.view.registeredActions.find(action_id)

        def change(self, fill: Callable[[Any], None]) -> None:
            """Triggers the change action and fills its dialog."""

            def fake_exec(dialog: ChangeAttributeDialog) -> int:
                fill(dialog)
                return QDialog.DialogCode.Accepted

            monkeypatch.setattr(ChangeAttributeDialog, "exec", fake_exec)
            self.action("bulk.change_attribute").trigger()

        def remove_extensions(self, label: str, by_semantic_id=False) -> None:
            def fake_exec(dialog: RemoveExtensionsDialog) -> int:
                if by_semantic_id:
                    dialog.bySemanticId.setChecked(True)
                dialog.choose(label)
                return QDialog.DialogCode.Accepted

            monkeypatch.setattr(RemoveExtensionsDialog, "exec", fake_exec)
            self.action("bulk.remove_extensions").trigger()

        def rows(self, *path: str) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(*SUBMODEL, *path)
            return [
                proxy.index(row, 0, parent).data(NAME_ROLE)
                for row in range(proxy.rowCount(parent))
            ]

        def reloaded(self, tmp_path: Path) -> tuple[str, str]:
            """Saves, reads the file again, and returns both snapshots."""
            path = tmp_path / "bulk.aasx"
            self.package.write(path)
            return snapshot(self.package.objStore), snapshot(
                Package(path).objStore
            )

    return Bulk


def _names(container: Any) -> list[str]:
    return [m.id_short for m in container]


def test_a_pattern_renames_the_selected_elements_and_the_tree_follows(
    bulk, tmp_path
) -> None:
    lab = bulk(*(make_property(n) for n in ("Foo", "Bar", "Baz")))
    lab.select(("Foo",), ("Bar",))

    lab.change(lambda d: d.set_pattern("ABC_{old}"))
    after = (_names(lab.submodel.submodel_element), lab.rows())
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()
    undone = (_names(lab.submodel.submodel_element), lab.rows())
    lab.view.onRedo()
    redone = _names(lab.submodel.submodel_element)

    expected = ["ABC_Foo", "ABC_Bar", "Baz"]
    assert after == (expected, expected)
    assert live == reread
    assert undone == (["Foo", "Bar", "Baz"], ["Foo", "Bar", "Baz"])
    assert redone == expected
    assert lab.problems == []


def test_the_rename_is_one_undo_step(bulk) -> None:
    lab = bulk(make_property("A"), make_property("B"))
    lab.select(("A",), ("B",))

    lab.change(lambda d: d.set_pattern("{old|lower}"))

    assert lab.stack.undo_description == "Change idShort of 2 items"
    lab.view.onUndo()
    assert not lab.stack.can_undo


def test_references_follow_a_bulk_rename_and_come_back_on_undo(
    bulk, tmp_path
) -> None:
    target = make_property("Target")
    holder = model.ReferenceElement(id_short="Pointer")
    lab = bulk(target, holder)
    # A reference to an element needs the element to be in its submodel.
    holder.value = model.ModelReference.from_referable(target)
    lab.select(("Target",))

    lab.change(lambda d: d.set_pattern("Renamed"))
    keys = [k.value for k in holder.value.key]
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()

    assert keys[-1] == "Renamed"
    assert live == reread
    assert [k.value for k in holder.value.key][-1] == "Target"


def test_a_refused_result_applies_nothing(bulk) -> None:
    lab = bulk(make_property("A"), make_property("Taken"))
    lab.select(("A",))
    seen: dict[str, Any] = {}

    def fill(dialog) -> None:
        dialog.set_pattern("Taken")
        seen["apply_enabled"] = dialog.applyButton.isEnabled()
        seen["reason"] = dialog.plan.entries[0].reason

    lab.change(fill)

    assert not seen["apply_enabled"]
    assert "sibling" in seen["reason"]
    assert _names(lab.submodel.submodel_element) == ["A", "Taken"]
    assert not lab.stack.can_undo


def test_a_pattern_with_an_error_cannot_be_applied(bulk) -> None:
    lab = bulk(make_property("A"))
    lab.select(("A",))
    seen: dict[str, Any] = {}

    def fill(dialog) -> None:
        dialog.set_pattern("{nope}")
        seen["summary"] = dialog.summary.text()
        seen["enabled"] = dialog.applyButton.isEnabled()

    lab.change(fill)

    assert "Unknown field" in seen["summary"]
    assert not seen["enabled"]
    assert not lab.stack.can_undo


def test_the_preview_lists_every_object_with_its_result(bulk) -> None:
    lab = bulk(make_property("A"), make_collection("C"), make_property("B"))
    lab.select(("A",), ("C",))
    seen: dict[str, Any] = {}

    def fill(dialog) -> None:
        dialog.set_attribute(dialog.attribute.__class__.VALUE)
        dialog.set_pattern("x{old}")
        table = dialog.table
        seen["rows"] = [
            [table.item(r, c).text() for c in range(4)]
            for r in range(table.rowCount())
        ]

    lab.change(fill)

    assert [row[3].split(":")[0] for row in seen["rows"]] == [
        "Changes",
        "Skipped",
    ]
    assert seen["rows"][0][1:3] == ["text", "xtext"]


def test_a_text_in_the_chosen_language_changes(bulk, tmp_path) -> None:
    first, second = make_property("A"), make_property("B")
    first.description = model.MultiLanguageTextType({"en": "one", "de": "eins"})
    second.description = model.MultiLanguageTextType({"de": "zwei"})
    lab = bulk(first, second)
    lab.select(("A",), ("B",))

    def fill(dialog) -> None:
        dialog.set_attribute(dialog.attribute.__class__.DESCRIPTION)
        dialog.set_language("de")
        dialog.set_pattern("{old|upper}")

    lab.change(fill)
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()

    assert live == reread
    assert dict(first.description) == {"en": "one", "de": "eins"}
    assert dict(second.description) == {"de": "zwei"}


def test_a_failure_while_applying_leaves_the_package_as_it_was(bulk) -> None:
    lab = bulk(make_property("A"), make_property("B"))
    lab.select(("A",), ("B",))

    def fill(dialog) -> None:
        dialog.set_pattern("N_{old}")
        # The package changes while the dialog is open.
        lab.submodel.submodel_element.add(make_property("N_B"))

    lab.change(fill)

    assert _names(lab.submodel.submodel_element) == ["A", "B", "N_B"]
    assert not lab.stack.can_undo
    assert "nothing was changed" in lab.problems[0]


def test_read_mode_disables_the_bulk_actions(bulk) -> None:
    lab = bulk(make_property("A"))
    lab.select(("A",))
    enabled = lab.action("bulk.change_attribute").isEnabled()
    edit_mode().set_editing(False)
    lab.view.updateActions(lab.view.currentIndex())

    assert enabled
    assert not lab.action("bulk.change_attribute").isEnabled()
    assert not lab.action("bulk.remove_extensions").isEnabled()


def test_extensions_with_a_name_are_removed_in_one_step(bulk, tmp_path) -> None:
    props = [make_property(n) for n in ("A", "B", "C")]
    for prop, name in zip(props, ("Alpha", "Alpha", "Beta"), strict=True):
        prop.extension.add(model.Extension(name))
    lab = bulk(*props)
    lab.select(("A",), ("B",), ("C",))

    lab.remove_extensions("Alpha (2)")
    left = [[e.name for e in p.extension] for p in props]
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()
    again = [[e.name for e in p.extension] for p in props]
    lab.view.onRedo()

    assert left == [[], [], ["Beta"]]
    assert live == reread
    assert again == [["Alpha"], ["Alpha"], ["Beta"]]
    assert [[e.name for e in p.extension] for p in props] == left


def test_the_removal_is_off_when_nothing_has_an_extension(bulk) -> None:
    lab = bulk(make_property("A"))
    lab.select(("A",))

    assert not lab.action("bulk.remove_extensions").isEnabled()


def test_a_selection_across_collections_moves_in_each_collection(
    bulk, tmp_path
) -> None:
    first = make_collection("First", [make_property(n) for n in "ABC"])
    second = make_collection("Second", [make_property(n) for n in "XYZ"])
    lab = bulk(first, second)
    lab.shown.view.expandAll()
    lab.select(("First", "B"), ("Second", "Z"))
    move_up = lab.action("structure.move_up")
    enabled = move_up.isEnabled()

    move_up.trigger()
    after = (_names(first.value), _names(second.value))
    live, reread = lab.reloaded(tmp_path)
    steps = lab.stack.undo_description
    lab.view.onUndo()
    undone = (_names(first.value), _names(second.value))
    lab.view.onRedo()

    assert enabled
    assert after == (["B", "A", "C"], ["X", "Z", "Y"])
    assert live == reread
    assert steps == "Move 2 items up"
    assert undone == (list("ABC"), list("XYZ"))
    assert (_names(first.value), _names(second.value)) == after
    assert lab.rows("First") == ["B", "A", "C"]


def test_a_selection_across_containers_is_off_when_none_can_move(bulk) -> None:
    first = make_collection("First", [make_property(n) for n in "AB"])
    second = make_collection("Second", [make_property(n) for n in "XY"])
    lab = bulk(first, second)
    lab.shown.view.expandAll()
    lab.select(("First", "A"), ("Second", "X"))

    assert not lab.action("structure.move_up").isEnabled()
    assert lab.action("structure.move_down").isEnabled()
