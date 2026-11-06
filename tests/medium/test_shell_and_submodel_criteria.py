"""F-EDT-02 and F-EDT-03 criteria that the first audit found open.

The flows go through the tree view and the tabs, as a user does, and each
test asserts what the criterion says: what the objects are afterwards, what the
file holds, and what one undo gives back.
"""

import json
from pathlib import Path
import re
from typing import Any

from basyx.aas import model
from basyx.aas.adapter.json import AASToJsonEncoder
from PyQt6.QtCore import QModelIndex
import pytest
from tests.factories import make_asset_information
from tests.factories import make_property
from tests.factories import make_reference_to
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.medium.test_create_flows import creating  # noqa: F401
from tests.medium.test_reference_integrity import Answers  # noqa: F401
from tests.medium.test_reference_integrity import answers  # noqa: F401
from tests.medium.test_user_defaults import settings  # noqa: F401
from tests.reference_factories import make_linked
from tests.serialization import snapshot

from aas_editor.domain.asset_information import ASSET_KINDS
from aas_editor.settings.app_settings import NAME_ROLE
from aas_editor.settings.app_settings import OBJECT_ROLE

# -- F-EDT-02 AC2 ------------------------------------------------------------


def test_a_template_submodel_is_free_and_becomes_the_current_row(
    creating,  # noqa: F811
) -> None:
    lab = creating()
    known = {o.id for o in lab.objects}
    lab.select("submodels")

    def script(dialog: Any) -> None:
        dialog.kind_box.setCurrentIndex(
            dialog.kind_box.findData(model.ModellingKind.TEMPLATE)
        )
        dialog.shell_box.setCurrentIndex(0)

    lab.run("create.submodel", lab.submodel_dialog, script)
    (submodel,) = lab.new_objects(model.Submodel, known)

    assert submodel.kind is model.ModellingKind.TEMPLATE
    assert lab.view.currentIndex().data(OBJECT_ROLE) is submodel
    shells = [
        o for o in lab.objects if isinstance(o, model.AssetAdministrationShell)
    ]
    for shell in shells:
        keys = {key.value for ref in shell.submodel for key in ref.key}
        assert submodel.id not in keys


# -- F-EDT-03 AC2 ------------------------------------------------------------


def test_a_template_submodel_is_made_with_the_id_of_the_template_pattern(
    creating,  # noqa: F811
    settings,  # noqa: F811
) -> None:
    from aas_editor.settings.app_settings import AppSettings

    settings(AppSettings.ID_TEMPLATE_SUBMODEL_INSTANCE, "urn:inst:DDDD")
    settings(AppSettings.ID_TEMPLATE_SUBMODEL_TEMPLATE, "urn:tmpl:DDDD")
    lab = creating()
    known = {o.id for o in lab.objects}
    lab.select("submodels")

    lab.run(
        "create.submodel",
        lab.submodel_dialog,
        lambda dialog: dialog.kind_box.setCurrentIndex(
            dialog.kind_box.findData(model.ModellingKind.TEMPLATE)
        ),
    )
    (submodel,) = lab.new_objects(model.Submodel, known)

    assert submodel.kind is model.ModellingKind.TEMPLATE
    assert re.fullmatch(r"urn:tmpl:\d{4}", submodel.id)
    assert re.fullmatch(
        r"urn:tmpl:\d{4}", lab.reloaded().get_item(submodel.id).id
    )


# -- F-EDT-02 AC6 ------------------------------------------------------------


def test_deleting_a_shell_is_one_step_and_undo_brings_it_back_with_its_submodels(
    views,
    answers,  # noqa: F811
) -> None:
    linked = make_linked()
    shown = views()
    package = shown.open_package(*linked.store)
    before = snapshot(package.objStore)
    shown.select(shown.index("shells", "Shell"))
    answers.box_button = "Delete"

    shown.view.onDelClear()
    gone = linked.shell not in package.objStore
    stay = linked.main in package.objStore and linked.other in package.objStore
    shown.view.onUndo()

    assert gone
    assert stay
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_declining_the_question_keeps_the_shell(
    views,
    answers,  # noqa: F811
) -> None:
    linked = make_linked()
    shown = views()
    package = shown.open_package(*linked.store)
    shown.select(shown.index("shells", "Shell"))
    answers.box_button = "Cancel"

    shown.view.onDelClear()

    assert linked.shell in package.objStore
    assert not package.commandStack.can_undo


# -- F-EDT-02 AC8 ------------------------------------------------------------


@pytest.fixture
def two_shells(views, answers):  # noqa: F811
    from aas_editor.ui.reference_actions import register_reference_actions

    register_reference_actions()
    first = make_shell("urn:shell:a", "First")
    second = make_shell("urn:shell:b", "Second")
    second.derived_from = make_reference_to(first)
    shown = views()
    package = shown.open_package(first, second)

    class Two:
        pass

    two = Two()
    two.first, two.second, two.shown, two.package = (
        first,
        second,
        shown,
        package,
    )
    two.answers = answers
    return two


def test_renaming_a_shell_updates_the_references_to_it(two_shells) -> None:
    lab = two_shells
    before = snapshot(lab.package.objStore)
    lab.shown.select(lab.shown.index("shells", "First"))
    lab.shown.view.updateActions(lab.shown.view.currentIndex())

    def type_new_id(dialog: Any) -> None:
        dialog.edit.setText("urn:shell:renamed")
        dialog.accept()

    lab.answers.dialog_action = type_new_id
    lab.shown.view.registeredActions.find("references.rename_id").trigger()

    assert lab.first.id == "urn:shell:renamed"
    assert [k.value for k in lab.second.derived_from.key] == [
        "urn:shell:renamed"
    ]
    lab.shown.view.onUndo()
    assert snapshot(lab.package.objStore) == before


def test_a_rename_that_cannot_be_done_says_why_and_changes_nothing(
    two_shells,
) -> None:
    lab = two_shells
    before = snapshot(lab.package.objStore)
    lab.shown.select(lab.shown.index("shells", "First"))
    lab.shown.view.updateActions(lab.shown.view.currentIndex())
    seen: list[tuple[str, bool]] = []

    def try_a_taken_id(dialog: Any) -> None:
        dialog.edit.setText("urn:shell:b")
        seen.append(
            (dialog.error_label.text(), dialog.accept_button.isEnabled())
        )
        dialog.reject()

    lab.answers.dialog_action = try_a_taken_id
    lab.shown.view.registeredActions.find("references.rename_id").trigger()

    (message, accept_enabled) = seen[0]
    assert "urn:shell:b" in message
    assert not accept_enabled
    assert lab.first.id == "urn:shell:a"
    assert snapshot(lab.package.objStore) == before


# -- F-EDT-02 AC9 ------------------------------------------------------------


@pytest.fixture
def bar(qapp, qtbot):
    from aas_editor.ui.hints_bar import HintsBar

    widget = HintsBar()
    qtbot.addWidget(widget)
    return widget


def test_the_tab_of_a_shell_with_a_blank_global_asset_id_shows_the_advisory(
    views, bar
) -> None:
    shell = make_shell(
        "urn:shell:s", "Blank", asset_information=make_asset_information(" ")
    )
    other = make_shell("urn:shell:o", "Fine")
    package = views().open_package(shell, other)

    bar.set_target(package, shell)
    blank = list(bar.lines)
    bar.set_target(package, other)
    fine = list(bar.lines)

    assert any("global asset id is empty" in line for line in blank)
    assert not any("global asset id is empty" in line for line in fine)


def test_the_tab_of_two_shells_with_one_global_asset_id_shows_the_duplicate(
    views, bar
) -> None:
    first = make_shell(
        "urn:shell:1",
        "One",
        asset_information=make_asset_information("urn:asset:x"),
    )
    second = make_shell(
        "urn:shell:2",
        "Two",
        asset_information=make_asset_information("urn:asset:x"),
    )
    third = make_shell(
        "urn:shell:3",
        "Three",
        asset_information=make_asset_information("urn:asset:y"),
    )
    package = views().open_package(first, second, third)

    bar.set_target(package, first)
    duplicate_for_first = list(bar.lines)
    bar.set_target(package, third)
    duplicate_for_third = list(bar.lines)

    assert any("urn:asset:x" in line for line in duplicate_for_first)
    assert not any("urn:asset:x" in line for line in duplicate_for_third)


# -- F-EDT-02 AC10 -----------------------------------------------------------

_LITERALS = {
    "INSTANCE": "Instance",
    "TYPE": "Type",
    "NOT_APPLICABLE": "NotApplicable",
    "ROLE": "Role",
}


def test_each_asset_kind_is_written_as_its_literal_and_read_back(
    creating,  # noqa: F811
) -> None:
    from aas_editor.package import Package

    lab = creating()
    created: dict[model.AssetKind, model.AssetAdministrationShell] = {}
    for kind in ASSET_KINDS:
        known = {o.id for o in lab.objects}
        lab.select("shells")

        def script(dialog: Any, kind: model.AssetKind = kind) -> None:
            dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(kind))

        lab.run("create.shell", lab.shell_dialog, script)
        (created[kind],) = lab.new_objects(
            model.AssetAdministrationShell, known
        )

    for kind, shell in created.items():
        text = json.dumps(shell.asset_information, cls=AASToJsonEncoder)
        assert f'"assetKind": "{_LITERALS[kind.name]}"' in text
    reloaded = lab.reloaded()
    for kind, shell in created.items():
        assert reloaded.get_item(shell.id).asset_information.asset_kind is kind
    assert Package is not None


# -- F-EDT-03 AC3 ------------------------------------------------------------


def test_linking_an_existing_submodel_adds_a_reference_and_no_copy(
    creating,  # noqa: F811
) -> None:
    lab = creating()
    count = len(list(lab.objects))
    lab.select("shells", "Shell")

    lab.run(
        "create.link_submodels",
        lab.link_dialog,
        lambda dialog: dialog.check(lab.second),
    )

    assert len(list(lab.objects)) == count
    added = [
        ref for ref in lab.shell.submodel if ref.key[0].value == lab.second.id
    ]
    (reference,) = added
    assert reference.resolve(lab.objects) is lab.second
    assert [
        o.id_short for o in lab.objects if isinstance(o, model.Submodel)
    ] == [
        "First",
        "Second",
    ] or len([o for o in lab.objects if isinstance(o, model.Submodel)]) == 2


# -- F-EDT-03 AC4 ------------------------------------------------------------


def test_a_copy_of_a_submodel_within_a_package_is_deep(
    views, monkeypatch
) -> None:
    from PyQt6.QtWidgets import QApplication

    from aas_editor.ui import paste_dialogs
    from aas_editor.ui.paste_actions import register_paste_actions

    register_paste_actions()
    monkeypatch.setattr(
        paste_dialogs, "ask_copy_concepts", lambda plan, parent=None: False
    )
    QApplication.clipboard().clear()
    inner = make_property("Inner")
    box = model.SubmodelElementCollection("Box", value=[inner])
    first = make_submodel("urn:sm:1", "First", [box])
    shell = make_shell("urn:shell:a", "Shell")
    shown = views()
    package = shown.open_package(shell, first)
    shown.view.treeClipboard.clear()
    shown.select(shown.index("submodels", "First"))
    shown.view.onCopy()
    shown.select(shown.index("shells", "Shell"))

    shown.view.registeredActions.find("structure.paste_into").trigger()

    (reference,) = shell.submodel
    copy = reference.resolve(package.objStore)
    assert copy.id != first.id
    copied_box = copy.get_referable("Box")
    assert copied_box is not box
    assert copied_box.get_referable("Inner") is not inner
    assert copied_box.get_referable("Inner").parent is copied_box
    assert box.get_referable("Inner") is inner


# -- F-EDT-03 AC5 ------------------------------------------------------------


def test_a_submodel_copied_to_another_package_brings_its_concept_descriptions(
    views, monkeypatch
) -> None:
    from PyQt6.QtWidgets import QApplication

    from aas_editor.ui import paste_dialogs
    from aas_editor.ui.paste_actions import register_paste_actions

    register_paste_actions()
    monkeypatch.setattr(
        paste_dialogs, "ask_copy_concepts", lambda plan, parent=None: True
    )
    QApplication.clipboard().clear()
    element = model.Property(
        id_short="Temp",
        value_type=model.datatypes.String,
        semantic_id=model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:cd:temp"),)
        ),
    )
    source = make_submodel("urn:sm:1", "First", [element])
    concept = model.ConceptDescription(id_="urn:cd:temp", id_short="Temp")
    shown = views()
    first = shown.open_package(source, concept)
    target_shell = make_shell("urn:shell:t", "Target")
    other = shown.open_package(target_shell)
    shown.view.treeClipboard.clear()
    shown.select(shown.index("submodels", "First", package=0))
    shown.view.onCopy()
    shown.select(shown.index("shells", "Target", package=1))

    shown.view.registeredActions.find("structure.paste_into").trigger()

    (reference,) = target_shell.submodel
    pasted = reference.resolve(other.objStore)
    assert pasted is not source
    assert [e.id_short for e in pasted.submodel_element] == ["Temp"]
    assert [
        c.id for c in other.objStore if isinstance(c, model.ConceptDescription)
    ] == ["urn:cd:temp"]
    assert source.id in {o.id for o in first.objStore}


# -- F-EDT-03 AC7, AC8 -------------------------------------------------------


def test_deleting_a_free_submodel_removes_it_from_the_package(
    views,
    answers,  # noqa: F811
) -> None:
    free = make_submodel("urn:sm:free", "Free", [make_property("P")])
    shown = views()
    package = shown.open_package(free)
    before = snapshot(package.objStore)
    shown.select(shown.index("submodels", "Free"))
    answers.box_button = "Delete"

    shown.view.onDelClear()
    removed = free not in package.objStore
    shown.view.onUndo()

    assert removed
    assert snapshot(package.objStore) == before


def test_deleting_a_submodel_also_removes_the_references_of_every_shell(
    views,
    answers,  # noqa: F811
) -> None:
    shared = make_submodel("urn:sm:shared", "Shared")
    one = make_shell("urn:shell:1", "One", submodels=[shared])
    two = make_shell("urn:shell:2", "Two", submodels=[shared])
    shown = views()
    package = shown.open_package(one, two, shared)
    before = snapshot(package.objStore)
    shown.select(shown.index("submodels", "Shared"))
    answers.box_button = "Delete"
    answers.dialog_action = lambda dialog: dialog.accept()

    shown.view.onDelClear()
    after = (len(one.submodel), len(two.submodel), shared in package.objStore)
    shown.view.onUndo()

    assert after == (0, 0, False)
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


# -- F-EDT-03 AC9 ------------------------------------------------------------


def _row(proxy: Any, parent: QModelIndex, name: str) -> QModelIndex:
    for number in range(proxy.rowCount(parent)):
        index = proxy.index(number, 0, parent)
        if index.data(NAME_ROLE) == name:
            return index
    raise LookupError(name)


@pytest.fixture
def dangling(views):
    """A shell with a reference to a Submodel that the package does not have."""
    shell = make_shell("urn:shell:d", "Dangling")
    shell.submodel.add(
        model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:sm:missing"),),
            model.Submodel,
        )
    )
    shown = views()
    package = shown.open_package(shell)
    attrs = shown.attrs_view("shells", "Dangling")
    attrs.expandAll()

    class Dangling:
        pass

    lab = Dangling()
    lab.shell, lab.shown, lab.package, lab.attrs = shell, shown, package, attrs
    return lab


def test_a_reference_to_no_submodel_can_be_edited(
    dangling, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_editor.dialogs import EditObjDialog
    from tests.medium.forms import Form
    from tests.medium.forms import answering

    attrs = dangling.attrs
    proxy = attrs.model()
    submodel = _row(proxy, QModelIndex(), "submodel")
    reference = _row(proxy, submodel, "ModelReference 0")

    def fill_key(dialog: Any) -> None:
        keys = Form(dialog).group.paramWidgets["key"]
        keys.inputWidgets[0].paramWidgets["value"].widget.setText(
            "urn:sm:other"
        )

    attrs.setCurrentIndex(reference)
    with answering(
        monkeypatch, EditObjDialog, fill_key, dangling.shown.shown_errors
    ):
        attrs.onEditCreate(None, reference.siblingAtColumn(1))

    (changed,) = dangling.shell.submodel
    assert [k.value for k in changed.key] == ["urn:sm:other"]
    assert dangling.shown.shown_errors == []
    dangling.package.commandStack.undo()
    (restored,) = dangling.shell.submodel
    assert [k.value for k in restored.key] == ["urn:sm:missing"]


def test_a_reference_to_no_submodel_can_be_removed_and_is_not_written(
    dangling, tmp_path: Path
) -> None:
    from aas_editor.package import Package

    attrs = dangling.attrs
    proxy = attrs.model()
    submodel = _row(proxy, QModelIndex(), "submodel")
    reference = _row(proxy, submodel, "ModelReference 0")
    attrs.setCurrentIndex(reference)
    attrs.selectionModel().select(
        reference, attrs.selectionModel().SelectionFlag.ClearAndSelect
    )

    attrs.onDelClear()

    assert len(dangling.shell.submodel) == 0
    path = tmp_path / "out.aasx"
    dangling.package.write(path)
    assert len(Package(path).objStore.get_item("urn:shell:d").submodel) == 0
