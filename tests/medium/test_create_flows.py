"""Creating shells and submodels, linking them, and removing attributes in bulk.

Every flow goes through the tree view and its registered action, with the
dialog answered the way a user would. Each one is a single undo step, and its
result survives a save and a reload.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_asset_information
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.medium.forms import answering
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode
from aas_editor.application.operations.bulk import RemovableAttribute
from aas_editor.domain.asset_information import ASSET_KINDS


@pytest.fixture
def creating(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A package with a shell and two submodels, and ways to create in it."""
    from aas_editor.ui import create_actions
    from aas_editor.ui.bulk_actions import register_bulk_actions
    from aas_editor.ui.bulk_actions import RemoveAttributesDialog
    from aas_editor.ui.create_actions import register_create_actions
    from aas_editor.ui.create_dialogs import CreateShellDialog
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog
    from aas_editor.ui.create_dialogs import LinkSubmodelsDialog
    from aas_editor.ui.create_dialogs import SpecificAssetIdDialog

    register_create_actions()
    register_bulk_actions()
    problems: list[str] = []
    monkeypatch.setattr(
        create_actions,
        "show_problem",
        lambda message, parent=None: problems.append(message),
    )

    class Creating:
        shell_dialog = CreateShellDialog
        submodel_dialog = CreateSubmodelDialog
        link_dialog = LinkSubmodelsDialog
        specific_dialog = SpecificAssetIdDialog
        remove_dialog = RemoveAttributesDialog

        def __init__(self, *extra: model.Identifiable) -> None:
            self.problems = problems
            self.monkeypatch = monkeypatch
            self.shown = views()
            self.view = self.shown.view
            self.first = make_submodel(id_="urn:sm:1", id_short="First")
            self.second = make_submodel(id_="urn:sm:2", id_short="Second")
            self.shell = make_shell(
                id_="urn:shell:a",
                id_short="Shell",
                submodels=[self.first],
                asset_information=make_asset_information("urn:asset:a"),
            )
            self.package = self.shown.open_package(
                self.shell, self.first, self.second, *extra
            )
            self.stack = self.package.commandStack
            self.objects = self.package.objStore

        def select(self, *path: str) -> None:
            self.shown.select(self.shown.index(*path))

        def run(self, action_id: str, dialog_class: type, script: Any) -> bool:
            """Triggers an action and answers its dialog. Tells if it was on."""
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            if enabled:
                with answering(self.monkeypatch, dialog_class, script):
                    action.trigger()
            return enabled

        def enabled(self, action_id: str) -> bool:
            return self.view.registeredActions.find(action_id).isEnabled()

        def reloaded(self) -> Any:
            from aas_editor.package import Package

            path = tmp_path / "created.aasx"
            self.package.write(path)
            return Package(path).objStore

        def new_objects(self, kind: type, known: set[str]) -> list[Any]:
            return [
                o
                for o in self.objects
                if isinstance(o, kind) and o.id not in known
            ]

    return Creating


def _ids(objects: Any) -> set[str]:
    return {o.id for o in objects}


class TestCreateShell:
    def test_the_action_makes_a_shell_with_valid_asset_information(
        self, creating, tmp_path: Path
    ) -> None:
        lab = creating()
        known = _ids(lab.objects)
        before = snapshot(lab.objects)
        lab.select("shells")

        def script(dialog: Any) -> None:
            dialog.id_short_edit.setText("Pump")

        enabled = lab.run("create.shell", lab.shell_dialog, script)
        (shell,) = lab.new_objects(model.AssetAdministrationShell, known)

        assert enabled
        assert shell.id_short == "Pump"
        assert shell.id.startswith("urn:uuid:")
        # Instance, where Package Explorer makes NotApplicable (ADR 0019).
        assert shell.asset_information.asset_kind is model.AssetKind.INSTANCE
        from aas_editor.settings.app_settings import OBJECT_ROLE

        assert lab.view.currentIndex().data(OBJECT_ROLE) is shell
        assert shell.asset_information.global_asset_id.startswith("urn:uuid:")
        reloaded = lab.reloaded()
        assert reloaded.get_item(
            shell.id
        ).asset_information.global_asset_id == (
            shell.asset_information.global_asset_id
        )
        after = snapshot(lab.objects)
        lab.stack.undo()
        undone = snapshot(lab.objects)
        lab.stack.redo()
        assert undone == before
        assert snapshot(lab.objects) == after
        assert not lab.stack.can_redo

    def test_add_on_the_shells_node_uses_the_dialog_and_no_longer_fails(
        self, creating
    ) -> None:
        # The generated form could not make AssetInformation: AASd-131.
        lab = creating()
        known = _ids(lab.objects)
        node = lab.shown.index("shells")
        lab.shown.select(node)

        with answering(
            lab.monkeypatch, lab.shell_dialog, lambda dialog: None
        ) as opened:
            lab.view.onAddAct(node)

        (shell,) = lab.new_objects(model.AssetAdministrationShell, known)
        assert len(opened) == 1
        assert shell.asset_information.global_asset_id is not None
        assert lab.shown.shown_errors == []

    def test_asset_kind_and_specific_asset_ids_are_kept(self, creating) -> None:
        lab = creating()
        known = _ids(lab.objects)
        lab.select("shells")

        def script(dialog: Any) -> None:
            dialog.global_id_edit.setText("")
            dialog.kind_box.setCurrentIndex(
                dialog.kind_box.findData(model.AssetKind.TYPE)
            )
            dialog.add_specific_row("serialNumber", "4711")
            dialog.asset_type_edit.setText("urn:type:pump")

        lab.run("create.shell", lab.shell_dialog, script)

        (shell,) = lab.new_objects(model.AssetAdministrationShell, known)
        information = shell.asset_information
        assert information.asset_kind is model.AssetKind.TYPE
        assert information.global_asset_id is None
        assert [(s.name, s.value) for s in information.specific_asset_id] == [
            ("serialNumber", "4711")
        ]
        assert information.asset_type == "urn:type:pump"

    def test_every_asset_kind_of_v3_1_is_offered(self, creating) -> None:
        lab = creating()
        offered: list[Any] = []
        lab.select("shells")

        def script(dialog: Any) -> None:
            offered.extend(
                dialog.kind_box.itemData(i)
                for i in range(dialog.kind_box.count())
            )

        lab.run("create.shell", lab.shell_dialog, script)

        assert offered == list(ASSET_KINDS)

    def test_the_dialog_explains_a_missing_asset_id_and_blocks_ok(
        self, creating
    ) -> None:
        lab = creating()
        seen: list[Any] = []
        lab.select("shells")

        def script(dialog: Any) -> None:
            dialog.global_id_edit.setText("")
            seen.append((dialog.problem, dialog.ok_button.isEnabled()))
            dialog.add_specific_row("serialNumber", "1")
            seen.append((dialog.problem, dialog.ok_button.isEnabled()))

        lab.run("create.shell", lab.shell_dialog, script)

        assert "AASd-131" in seen[0][0]
        assert seen[0][1] is False
        assert seen[1] == ("", True)

    def test_the_dialog_refuses_an_id_that_another_object_has(
        self, creating
    ) -> None:
        lab = creating()
        seen: list[Any] = []
        lab.select("shells")

        def script(dialog: Any) -> None:
            dialog.id_edit.setText(lab.first.id)
            seen.append((dialog.problem, dialog.ok_button.isEnabled()))
            dialog.id_edit.setText("urn:shell:new")

        lab.run("create.shell", lab.shell_dialog, script)

        assert "belongs to another" in seen[0][0]
        assert seen[0][1] is False
        assert lab.objects.get_item("urn:shell:new") is not None

    def test_cancelling_changes_nothing(self, creating) -> None:
        lab = creating()
        before = snapshot(lab.objects)
        lab.select("shells")
        action = lab.view.registeredActions.find("create.shell")

        def reject(dialog: Any) -> int:
            from PyQt6.QtWidgets import QDialog

            return QDialog.DialogCode.Rejected

        lab.monkeypatch.setattr(lab.shell_dialog, "exec", reject)
        action.trigger()

        assert snapshot(lab.objects) == before
        assert not lab.stack.can_undo

    def test_read_mode_turns_the_action_off(self, creating) -> None:
        lab = creating()
        lab.select("shells")
        edit_mode().set_editing(False)
        try:
            lab.view.updateActions(lab.view.currentIndex())
            enabled = lab.enabled("create.shell")
        finally:
            edit_mode().set_editing(True)

        assert not enabled


class TestCreateSubmodel:
    def test_with_a_shell_the_submodel_and_its_reference_are_one_step(
        self, creating
    ) -> None:
        lab = creating()
        known = _ids(lab.objects)
        before = snapshot(lab.objects)
        lab.select("shells", "Shell")
        seen: list[Any] = []

        def script(dialog: Any) -> None:
            seen.append(dialog.selected_shell())
            dialog.id_short_edit.setText("Nameplate")

        lab.run("create.submodel", lab.submodel_dialog, script)
        (submodel,) = lab.new_objects(model.Submodel, known)

        assert seen == [lab.shell]
        assert submodel.id_short == "Nameplate"
        assert submodel.kind is model.ModellingKind.INSTANCE
        from aas_editor.settings.app_settings import OBJECT_ROLE

        assert lab.view.currentIndex().data(OBJECT_ROLE) is submodel
        assert len(lab.shell.submodel) == 2
        assert (
            lab.reloaded().get_item(lab.shell.id).submodel == lab.shell.submodel
        )
        after = snapshot(lab.objects)
        lab.stack.undo()
        undone = snapshot(lab.objects)
        lab.stack.redo()
        assert undone == before
        assert snapshot(lab.objects) == after

    def test_template_kind_and_no_shell_make_a_free_submodel(
        self, creating
    ) -> None:
        lab = creating()
        known = _ids(lab.objects)
        lab.select("submodels")

        def script(dialog: Any) -> None:
            dialog.kind_box.setCurrentIndex(
                dialog.kind_box.findData(model.ModellingKind.TEMPLATE)
            )
            dialog.shell_box.setCurrentIndex(0)

        lab.run("create.submodel", lab.submodel_dialog, script)

        (submodel,) = lab.new_objects(model.Submodel, known)
        assert submodel.kind is model.ModellingKind.TEMPLATE
        assert len(lab.shell.submodel) == 1

    def test_a_duplicate_id_is_refused_in_the_dialog(self, creating) -> None:
        lab = creating()
        seen: list[str] = []
        lab.select("submodels")

        def script(dialog: Any) -> None:
            dialog.id_edit.setText(lab.first.id)
            seen.append(dialog.problem)
            dialog.id_edit.setText("urn:sm:fresh")

        lab.run("create.submodel", lab.submodel_dialog, script)

        assert "belongs to another" in seen[0]


class TestLinkExistingSubmodels:
    def test_the_dialog_lists_only_unlinked_submodels(self, creating) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        seen: list[Any] = []

        def script(dialog: Any) -> None:
            seen.append(dialog.names())
            dialog.check(lab.second)

        enabled = lab.run("create.link_submodels", lab.link_dialog, script)

        assert enabled
        assert len(seen[0]) == 1
        assert "Second" in seen[0][0]
        assert sorted(r.key[0].value for r in lab.shell.submodel) == [
            "urn:sm:1",
            "urn:sm:2",
        ]

    def test_linking_is_one_undoable_step_that_saves_and_reloads(
        self, creating
    ) -> None:
        lab = creating()
        third = make_submodel(id_="urn:sm:3", id_short="Third")
        lab.package.add(third)
        before = snapshot(lab.objects)
        lab.select("shells", "Shell")

        lab.run(
            "create.link_submodels",
            lab.link_dialog,
            lambda dialog: dialog.set_all_checked(True),
        )

        assert len(lab.shell.submodel) == 3
        saved = lab.reloaded().get_item(lab.shell.id)
        assert len(saved.submodel) == 3
        lab.stack.undo()
        assert snapshot(lab.objects) == before
        assert not lab.stack.can_undo

    def test_ok_needs_at_least_one_tick(self, creating) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        seen: list[bool] = []

        def script(dialog: Any) -> None:
            seen.append(dialog.ok_button.isEnabled())
            dialog.check(lab.second)

        lab.run("create.link_submodels", lab.link_dialog, script)

        assert seen == [False]

    def test_the_action_is_off_when_every_submodel_is_linked(
        self, creating
    ) -> None:
        lab = creating()
        lab.shell.submodel.add(model.ModelReference.from_referable(lab.second))
        lab.select("shells", "Shell")

        assert not lab.enabled("create.link_submodels")

    def test_the_action_is_off_on_a_submodel_row(self, creating) -> None:
        lab = creating()
        lab.select("submodels", "Second")

        assert not lab.enabled("create.link_submodels")


class TestAssetIds:
    def test_generate_gives_a_new_global_asset_id_in_one_step(
        self, creating
    ) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        action = lab.view.registeredActions.find("asset.generate_global_id")
        enabled = action.isEnabled()

        action.trigger()
        generated = lab.shell.asset_information.global_asset_id
        saved = lab.reloaded().get_item(lab.shell.id)
        lab.stack.undo()

        assert enabled
        assert generated is not None and generated.startswith("urn:uuid:")
        assert saved.asset_information.global_asset_id == generated
        assert lab.shell.asset_information.global_asset_id == "urn:asset:a"

    def test_add_specific_asset_id_is_one_step_that_saves_and_reloads(
        self, creating
    ) -> None:
        lab = creating()
        lab.select("shells", "Shell")

        def script(dialog: Any) -> None:
            dialog.name_edit.setText("serialNumber")
            dialog.value_edit.setText("4711")

        lab.run("asset.add_specific_id", lab.specific_dialog, script)

        added = [
            (s.name, s.value)
            for s in lab.shell.asset_information.specific_asset_id
        ]
        saved = lab.reloaded().get_item(lab.shell.id)
        assert added == [("serialNumber", "4711")]
        assert [
            (s.name, s.value) for s in saved.asset_information.specific_asset_id
        ] == added
        lab.stack.undo()
        assert list(lab.shell.asset_information.specific_asset_id) == []

    def test_the_dialog_needs_a_name_and_a_value(self, creating) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        seen: list[Any] = []

        def script(dialog: Any) -> None:
            seen.append((dialog.problem, dialog.ok_button.isEnabled()))
            dialog.name_edit.setText("n")
            seen.append((dialog.problem, dialog.ok_button.isEnabled()))
            dialog.value_edit.setText("v")

        lab.run("asset.add_specific_id", lab.specific_dialog, script)

        assert "needs a name" in seen[0][0]
        assert "needs a value" in seen[1][0]
        assert not seen[1][1]

    def test_the_helpers_are_off_in_read_mode(self, creating) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        edit_mode().set_editing(False)
        try:
            lab.view.updateActions(lab.view.currentIndex())
            off = not lab.enabled("asset.generate_global_id")
        finally:
            edit_mode().set_editing(True)

        assert off


class TestRemoveAttributes:
    def _submodel_with_qualifiers(self) -> model.Submodel:
        top = make_property("Top")
        top.qualifier.add(model.Qualifier("Q1", model.datatypes.String, "v"))
        inner = model.SubmodelElementCollection("Inner")
        deep = make_property("Deep")
        deep.qualifier.add(model.Qualifier("Q2", model.datatypes.String, "v"))
        deep.extension.add(model.Extension("E1", model.datatypes.String, "v"))
        inner.value.add(deep)
        submodel = make_submodel(
            id_="urn:sm:q", id_short="Qualified", elements=[top, inner]
        )
        submodel.qualifier.add(
            model.Qualifier("Q0", model.datatypes.String, "v")
        )
        return submodel

    def test_all_qualifiers_go_in_one_step_and_the_question_names_them(
        self, creating
    ) -> None:
        submodel = self._submodel_with_qualifiers()
        lab = creating(submodel)
        before = snapshot(lab.objects)
        lab.select("submodels", "Qualified")
        questions: list[str] = []
        counts: list[str] = []

        def script(dialog: Any) -> None:
            counts.append(dialog.boxes[RemovableAttribute.QUALIFIERS].text())
            dialog.check(RemovableAttribute.QUALIFIERS)
            questions.append(dialog.question.text())

        enabled = lab.run("bulk.remove_attributes", lab.remove_dialog, script)

        from aas_editor.domain.walking import descendants

        assert enabled
        assert counts == ["All qualifiers (3)"]
        assert "3 qualifiers" in questions[0]
        assert "Qualified" in questions[0]
        assert len(submodel.qualifier) == 0
        assert all(len(e.qualifier) == 0 for e in descendants(submodel))
        assert len(list(submodel.get_referable("Inner").value)) == 1
        reloaded = lab.reloaded().get_item("urn:sm:q")
        assert all(len(e.qualifier) == 0 for e in descendants(reloaded))
        assert len(reloaded.qualifier) == 0
        after = snapshot(lab.objects)
        lab.stack.undo()
        undone = snapshot(lab.objects)
        lab.stack.redo()
        assert undone == before
        assert snapshot(lab.objects) == after

    def test_extensions_stay_when_only_qualifiers_are_chosen(
        self, creating
    ) -> None:
        submodel = self._submodel_with_qualifiers()
        lab = creating(submodel)
        lab.select("submodels", "Qualified")

        lab.run(
            "bulk.remove_attributes",
            lab.remove_dialog,
            lambda dialog: dialog.check(RemovableAttribute.QUALIFIERS),
        )

        deep = submodel.get_referable("Inner").get_referable("Deep")
        assert len(deep.extension) == 1

    def test_ok_needs_a_tick_and_an_empty_attribute_cannot_be_ticked(
        self, creating
    ) -> None:
        lab = creating(self._submodel_with_qualifiers())
        lab.select("submodels", "Qualified")
        seen: list[Any] = []

        def script(dialog: Any) -> None:
            seen.append(dialog.ok_button.isEnabled())
            seen.append(dialog.boxes[RemovableAttribute.CATEGORIES].isEnabled())
            dialog.check(RemovableAttribute.EXTENSIONS)

        lab.run("bulk.remove_attributes", lab.remove_dialog, script)

        assert seen == [False, False]

    def test_cancelling_removes_nothing(self, creating) -> None:
        lab = creating(self._submodel_with_qualifiers())
        before = snapshot(lab.objects)
        lab.select("submodels", "Qualified")
        action = lab.view.registeredActions.find("bulk.remove_attributes")

        def reject(dialog: Any) -> int:
            from PyQt6.QtWidgets import QDialog

            return QDialog.DialogCode.Rejected

        lab.monkeypatch.setattr(lab.remove_dialog, "exec", reject)
        action.trigger()

        assert snapshot(lab.objects) == before
        assert not lab.stack.can_undo

    def test_the_action_is_only_for_a_submodel_and_off_in_read_mode(
        self, creating
    ) -> None:
        lab = creating()
        lab.select("shells", "Shell")
        on_shell = lab.enabled("bulk.remove_attributes")
        lab.select("submodels", "First")
        on_submodel = lab.enabled("bulk.remove_attributes")
        edit_mode().set_editing(False)
        try:
            lab.view.updateActions(lab.view.currentIndex())
            in_read_mode = lab.enabled("bulk.remove_attributes")
        finally:
            edit_mode().set_editing(True)

        assert (on_shell, on_submodel, in_read_mode) == (False, True, False)
