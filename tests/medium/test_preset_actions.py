"""Presets and the clipboard through the tree view: do, undo, redo, save, reload."""

import json
from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QDialog
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.domain.member_json import MemberKind
from aas_workingbench.domain.presets import FILE_NAMES

SUBMODEL = ("submodels", "Submodel")
CARDINALITY = "Submodel templates | Cardinality = One"


@pytest.fixture
def presets(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """A package that the preset and clipboard actions work on."""
    from aas_workingbench.package import Package
    from aas_workingbench.ui import bulk_dialogs
    from aas_workingbench.ui import preset_actions
    from aas_workingbench.ui.preset_actions import register_preset_actions
    from aas_workingbench.ui.preset_dialogs import PresetDialog

    register_preset_actions()
    user_dir = tmp_path / "user-presets"
    monkeypatch.setattr(preset_actions, "user_presets_dir", lambda: user_dir)

    class Presets:
        problems: list[str]
        confirmations: list[Any]
        dialogs: list[Any]

        def __init__(self, *elements: model.SubmodelElement, shells=()):
            self.shown = views()
            self.submodel = make_submodel(elements=elements)
            self.package = self.shown.open_package(self.submodel, *shells)
            self.view = self.shown.view
            self.stack = self.package.commandStack
            self.user_dir = user_dir
            self.problems = []
            self.confirmations = []
            self.dialogs = []
            self.answer = True
            monkeypatch.setattr(
                bulk_dialogs,
                "show_problem",
                lambda title, message, parent=None: self.problems.append(
                    message
                ),
            )

            def confirm(plan, parent=None) -> bool:
                self.confirmations.append(plan)
                return self.answer

            monkeypatch.setattr(bulk_dialogs, "confirm_attach", confirm)

        def select_elements(self, *names: str) -> None:
            self.shown.select(
                *(self.shown.index(*SUBMODEL, name) for name in names)
            )

        def action(self, action_id: str):
            return self.view.registeredActions.find(action_id)

        def use_preset(
            self, action_id: str, name: str, value: str | None = None
        ) -> None:
            def fake_exec(dialog: PresetDialog) -> int:
                self.dialogs.append(dialog)
                dialog.choose(name)
                if value is not None:
                    dialog.valueEdit.setText(value)
                return QDialog.DialogCode.Accepted

            monkeypatch.setattr(PresetDialog, "exec", fake_exec)
            self.action(action_id).trigger()

        def write_user_file(self, kind: MemberKind, content: object) -> None:
            self.user_dir.mkdir(exist_ok=True)
            text = content if isinstance(content, str) else json.dumps(content)
            (self.user_dir / FILE_NAMES[kind]).write_text(text, "utf-8")

        def reloaded(self, tmp_path: Path) -> tuple[str, str]:
            path = tmp_path / "presets.aasx"
            self.package.write(path)
            return snapshot(self.package.objStore), snapshot(
                Package(path).objStore
            )

    return Presets


def _types(prop: Any) -> list[str]:
    return [q.type for q in prop.qualifier]


def test_a_qualifier_preset_is_added_to_every_selected_element(
    presets, tmp_path
) -> None:
    props = [make_property(n) for n in "ABC"]
    lab = presets(*props)
    lab.select_elements("A", "B")

    lab.use_preset("preset.add_qualifier", CARDINALITY)
    after = [_types(p) for p in props]
    live, reread = lab.reloaded(tmp_path)
    qualifier = next(iter(props[0].qualifier))
    lab.view.onUndo()
    undone = [_types(p) for p in props]
    lab.view.onRedo()

    assert after == [["SMT/Cardinality"], ["SMT/Cardinality"], []]
    assert (qualifier.value, qualifier.kind) == (
        "One",
        model.QualifierKind.TEMPLATE_QUALIFIER,
    )
    assert live == reread
    assert undone == [[], [], []]
    assert [_types(p) for p in props] == after
    assert lab.problems == []


def test_each_element_has_a_qualifier_of_its_own(presets) -> None:
    props = [make_property(n) for n in "AB"]
    lab = presets(*props)
    lab.select_elements("A", "B")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    first, second = (next(iter(p.qualifier)) for p in props)
    assert first is not second
    assert first.parent is props[0]
    assert second.parent is props[1]


def test_an_element_that_has_the_type_is_skipped_after_a_question(
    presets,
) -> None:
    has, lacks = make_property("A"), make_property("B")
    has.qualifier.add(
        model.Qualifier(
            "SMT/Cardinality", value_type=model.datatypes.String, value="mine"
        )
    )
    lab = presets(has, lacks)
    lab.select_elements("A", "B")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    (plan,) = lab.confirmations
    assert plan.skipped_count == 1
    assert next(iter(has.qualifier)).value == "mine"
    assert _types(lacks) == ["SMT/Cardinality"]


def test_cancelling_the_question_adds_nothing(presets) -> None:
    has, lacks = make_property("A"), make_property("B")
    has.qualifier.add(
        model.Qualifier("SMT/Cardinality", value_type=model.datatypes.String)
    )
    lab = presets(has, lacks)
    lab.answer = False
    lab.select_elements("A", "B")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    assert _types(lacks) == []
    assert not lab.stack.can_undo


def test_when_nothing_can_be_added_the_reasons_are_shown(presets) -> None:
    has = make_property("A")
    has.qualifier.add(
        model.Qualifier("SMT/Cardinality", value_type=model.datatypes.String)
    )
    lab = presets(has)
    lab.select_elements("A")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    assert "Nothing can be added" in lab.problems[0]
    assert "AASd-021" in lab.problems[0]
    assert not lab.stack.can_undo


def test_a_preset_of_the_user_replaces_the_shipped_one_and_adds_its_own(
    presets,
) -> None:
    lab = presets(make_property("A"))
    lab.write_user_file(
        MemberKind.QUALIFIER,
        [
            {
                "name": CARDINALITY,
                "qualifier": {
                    "type": "SMT/Cardinality",
                    "valueType": "xs:string",
                    "value": "Mine",
                },
            },
            {
                "name": "Mine | Own",
                "qualifier": {"type": "Own", "valueType": "xs:string"},
            },
        ],
    )
    lab.select_elements("A")

    lab.use_preset("preset.add_qualifier", CARDINALITY)
    shown = lab.dialogs[0]
    names = [preset.name for preset in shown._loaded.presets]

    assert next(iter(lab.submodel.get_referable("A").qualifier)).value == "Mine"
    assert "Mine | Own" in names
    assert shown._loaded.problems == ()


def test_a_broken_user_file_still_lets_the_dialog_open(presets) -> None:
    lab = presets(make_property("A"))
    lab.write_user_file(MemberKind.QUALIFIER, "{ this is not json")
    lab.select_elements("A")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    dialog = lab.dialogs[0]
    assert len(dialog._loaded.problems) == 1
    assert "not valid JSON" in str(dialog._loaded.problems[0])
    assert dialog.problemLabel.text() == "1 problem in the preset files"
    assert _types(lab.submodel.get_referable("A")) == ["SMT/Cardinality"]


def test_an_entry_with_a_wrong_value_is_refused_and_the_rest_are_listed(
    presets,
) -> None:
    lab = presets(make_property("A"))
    lab.write_user_file(
        MemberKind.EXTENSION,
        [
            {
                "name": "Bad",
                "extension": {
                    "name": "E",
                    "value": "1",
                    "valueType": "xs:int",
                    "x": 1,
                },
            },
            {
                "name": "Worse",
                "extension": {
                    "name": "E",
                    "valueType": "xs:int",
                    "value": "abc",
                },
            },
            {"name": "Fine", "extension": {"name": "Fine"}},
        ],
    )
    lab.select_elements("A")

    lab.use_preset("preset.add_extension", "Fine")

    dialog = lab.dialogs[0]
    assert [p.problem.where for p in dialog._loaded.problems] == [
        "Entry 2 ('Worse')"
    ]
    assert [e.name for e in lab.submodel.get_referable("A").extension] == [
        "Fine"
    ]


def test_an_extension_preset_is_added_and_survives_save_and_reload(
    presets, tmp_path
) -> None:
    props = [make_property("A"), make_property("B")]
    lab = presets(*props)
    lab.select_elements("A", "B")

    lab.use_preset("preset.add_extension", "BOM Plugin | Formatting arguments")
    live, reread = lab.reloaded(tmp_path)

    assert [[e.name for e in p.extension] for p in props] == [["BOM.Args"]] * 2
    assert live == reread


def test_a_data_specification_preset_is_added(presets, tmp_path) -> None:
    prop = make_property("A")
    lab = presets(prop)
    lab.select_elements("A")

    lab.use_preset("preset.add_data_specification", "IEC 61360")
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()

    assert live == reread
    assert prop.embedded_data_specifications == []


def test_a_data_specification_preset_gives_one_record_and_no_blank_one(
    presets,
) -> None:
    """F-EDT-05 AC16 and F-EDT-06 AC14, end state.

    Package Explorer creates a blank record, and the preset replaces it. The
    SDK cannot hold a blank record (tests/small/test_blank_member_probes), so
    the list has the one record of the preset and nothing else.
    """
    prop = make_property("A")
    lab = presets(prop)
    lab.select_elements("A")

    lab.use_preset("preset.add_data_specification", "IEC 61360")

    (record,) = prop.embedded_data_specifications
    assert [k.value for k in record.data_specification.key] == [
        "https://admin-shell.io/DataSpecificationTemplates/"
        "DataSpecificationIec61360/3/0"
    ]
    content = record.data_specification_content
    assert isinstance(content, model.DataSpecificationIEC61360)
    assert dict(content.preferred_name) == {"en": "Preferred name"}


def test_a_qualifier_preset_gives_one_qualifier_with_its_semantic_id(
    presets,
) -> None:
    """F-EDT-07 AC1, end state: type, value, kind, semantic id, and no other."""
    prop = make_property("A")
    lab = presets(prop)
    lab.select_elements("A")

    lab.use_preset("preset.add_qualifier", CARDINALITY)

    (qualifier,) = prop.qualifier
    assert (qualifier.type, qualifier.value) == ("SMT/Cardinality", "One")
    assert qualifier.kind is model.QualifierKind.TEMPLATE_QUALIFIER
    assert qualifier.semantic_id is not None
    assert len(qualifier.semantic_id.key) == 1


def test_a_specific_asset_id_preset_asks_for_the_value(
    presets, tmp_path
) -> None:
    information = model.AssetInformation(model.AssetKind.INSTANCE, "urn:asset")
    shell = model.AssetAdministrationShell(
        information, "urn:test:shell", id_short="Shell"
    )
    lab = presets(make_property("A"), shells=(shell,))
    lab.shown.select(lab.shown.index("shells", "Shell"))

    lab.use_preset("preset.add_specific_asset_id", "Catena-X BPN", "BPNL0001")
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()

    dialog = lab.dialogs[0]
    assert dialog.chosen.value_required
    assert live == reread
    assert list(information.specific_asset_id) == []


def test_the_add_button_waits_for_the_value(presets, monkeypatch) -> None:
    information = model.AssetInformation(model.AssetKind.INSTANCE, "urn:asset")
    shell = model.AssetAdministrationShell(
        information, "urn:test:shell", id_short="Shell"
    )
    lab = presets(make_property("A"), shells=(shell,))
    lab.shown.select(lab.shown.index("shells", "Shell"))
    seen: dict[str, bool] = {}

    from aas_workingbench.ui.preset_dialogs import PresetDialog

    def fake_exec(dialog: PresetDialog) -> int:
        dialog.choose("Catena-X BPN")
        seen["before"] = dialog.addButton.isEnabled()
        dialog.valueEdit.setText("BPNL1")
        seen["after"] = dialog.addButton.isEnabled()
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(PresetDialog, "exec", fake_exec)
    lab.action("preset.add_specific_asset_id").trigger()

    assert seen == {"before": False, "after": True}
    assert list(information.specific_asset_id) == []


def test_the_actions_are_off_for_objects_that_cannot_have_the_kind(
    presets,
) -> None:
    lab = presets(make_property("A"))
    lab.select_elements("A")

    assert lab.action("preset.add_qualifier").isEnabled()
    assert not lab.action("preset.add_specific_asset_id").isEnabled()
    assert not lab.action("clipboard.add_specific_asset_id").isEnabled()


def test_read_mode_disables_the_actions(presets) -> None:
    lab = presets(make_property("A"))
    lab.select_elements("A")
    edit_mode().set_editing(False)
    lab.view.updateActions(lab.view.currentIndex())

    assert not lab.action("preset.add_qualifier").isEnabled()
    assert not lab.action("clipboard.add_qualifier").isEnabled()


def _clip(text: str) -> None:
    QApplication.clipboard().setText(text)


def test_a_qualifier_on_the_clipboard_is_added(presets, tmp_path) -> None:
    props = [make_property("A"), make_property("B")]
    lab = presets(*props)
    lab.select_elements("A", "B")
    _clip(
        json.dumps(
            {
                "type": "Mark",
                "valueType": "xs:int",
                "value": "5",
                "kind": "ConceptQualifier",
            }
        )
    )

    lab.action("clipboard.add_qualifier").trigger()
    live, reread = lab.reloaded(tmp_path)
    lab.view.onUndo()
    undone = [_types(p) for p in props]
    lab.view.onRedo()

    qualifier = next(iter(props[0].qualifier))
    assert (qualifier.type, qualifier.value) == ("Mark", 5)
    assert qualifier.value_type is model.datatypes.Int
    assert live == reread
    assert undone == [[], []]
    assert [_types(p) for p in props] == [["Mark"], ["Mark"]]


def test_an_extension_on_the_clipboard_is_added(presets) -> None:
    prop = make_property("A")
    lab = presets(prop)
    lab.select_elements("A")
    _clip(
        json.dumps(
            [
                {"name": "One"},
                {"name": "Two", "valueType": "xs:string", "value": "v"},
            ]
        )
    )

    lab.action("clipboard.add_extension").trigger()

    assert [e.name for e in prop.extension] == ["One", "Two"]
    assert lab.stack.undo_description == "Add extension to A"


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("just some text", "does not hold AAS JSON"),
        ("{ broken", "not valid JSON"),
        ("[]", "holds no object"),
        ('{"type": "T"}', "valueType"),
        (
            '{"modelType": "Property", "idShort": "P", "valueType": "xs:string"}',
            "is a Property, not a Qualifier",
        ),
        (
            '{"type": "T", "valueType": "xs:int", "value": "x"}',
            "not a valid xs:int",
        ),
    ],
)
def test_bad_clipboard_content_is_refused_with_a_message(
    presets, text: str, fragment: str
) -> None:
    prop = make_property("A")
    lab = presets(prop)
    lab.select_elements("A")
    _clip(text)

    lab.action("clipboard.add_qualifier").trigger()

    assert fragment in lab.problems[0]
    assert _types(prop) == []
    assert not lab.stack.can_undo


def test_a_qualifier_that_the_element_has_already_is_not_added_from_the_clipboard(
    presets,
) -> None:
    prop = make_property("A")
    prop.qualifier.add(
        model.Qualifier("Mark", value_type=model.datatypes.String, value="old")
    )
    lab = presets(prop)
    lab.select_elements("A")
    _clip('{"type": "Mark", "valueType": "xs:string", "value": "new"}')

    lab.action("clipboard.add_qualifier").trigger()

    assert "AASd-021" in lab.problems[0]
    assert next(iter(prop.qualifier)).value == "old"


def test_the_clipboard_text_of_a_copied_element_is_not_a_qualifier(
    presets,
) -> None:
    prop = make_property("A")
    lab = presets(prop, make_property("B"))
    lab.select_elements("B")
    lab.shown.select(lab.shown.index(*SUBMODEL, "A"))
    lab.view.onCopy()
    lab.select_elements("B")

    lab.action("clipboard.add_qualifier").trigger()

    assert "is a Property, not a Qualifier" in lab.problems[0]


def test_shells_take_extensions_like_any_referable(presets) -> None:
    shell = make_shell()
    lab = presets(make_property("A"), shells=(shell,))
    lab.shown.select(lab.shown.index("shells", "Shell"))
    _clip('{"name": "Note", "valueType": "xs:string", "value": "x"}')

    lab.action("clipboard.add_extension").trigger()

    assert [e.name for e in shell.extension] == ["Note"]


def test_in_a_tab_the_row_of_the_asset_information_takes_a_specific_asset_id(
    presets, monkeypatch, tmp_path
) -> None:
    from PyQt6.QtCore import QItemSelectionModel

    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.ui.preset_dialogs import PresetDialog

    information = model.AssetInformation(model.AssetKind.INSTANCE, "urn:asset")
    shell = model.AssetAdministrationShell(
        information, "urn:test:shell", id_short="Shell"
    )
    lab = presets(make_property("A"), shells=(shell,))
    attrs = lab.shown.attrs_view("shells", "Shell")
    proxy = attrs.model()
    row = next(
        proxy.index(r, 0)
        for r in range(proxy.rowCount())
        if proxy.index(r, 0).data(NAME_ROLE) == "asset_information"
    )
    attrs.selectionModel().select(
        row, QItemSelectionModel.SelectionFlag.ClearAndSelect
    )
    attrs.setCurrentIndex(row)
    monkeypatch.setattr(
        PresetDialog,
        "exec",
        lambda dialog: (
            dialog.choose("Catena-X BPN"),
            dialog.valueEdit.setText("BPNL2"),
            QDialog.DialogCode.Accepted,
        )[-1],
    )

    attrs.registeredActions.find("preset.add_specific_asset_id").trigger()
    live, reread = lab.reloaded(tmp_path)

    assert [(s.name, s.value) for s in information.specific_asset_id] == [
        ("BPN", "BPNL2")
    ]
    assert live == reread
