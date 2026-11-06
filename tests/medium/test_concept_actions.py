"""The concept description actions, through the tree view of a package.

Each flow is done, undone, redone, saved and read again. The dialogs are
replaced by answers, except where the test is about a dialog: then the real
dialog is filled in through its widgets.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QApplication
import pytest
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.application.editing import edit_mode
from aas_editor.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_editor.domain.data_specifications import TemplateMatch
from aas_editor.domain.data_specifications import match_template

CONCEPTS = "concept_descriptions"
SUBMODEL = ("submodels", "Submodel")


def _record(
    key: str = IEC_61360_TEMPLATE_KEY, **kwargs: Any
) -> model.EmbeddedDataSpecification:
    return model.EmbeddedDataSpecification(
        make_external_reference(key),
        model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360({"en": "Name"}), **kwargs
        ),
    )


def _concept(
    id_: str,
    id_short: str | None = None,
    *records: model.EmbeddedDataSpecification,
) -> model.ConceptDescription:
    return model.ConceptDescription(
        id_, id_short=id_short, embedded_data_specifications=list(records)
    )


def _prop(id_short: str, semantic: str | None = None) -> model.Property:
    prop = make_property(id_short)
    if semantic is not None:
        prop.semantic_id = make_external_reference(semantic)
    return prop


def _concept_ids(store: Any) -> list[str]:
    return sorted(
        o.id for o in store if isinstance(o, model.ConceptDescription)
    )


@pytest.fixture
def concepts(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Packages with objects, and ways to select, act and look at the result."""
    from aas_editor.package import Package
    from aas_editor.settings.app_settings import NAME_ROLE
    from aas_editor.ui import concept_dialogs
    from aas_editor.ui import reference_dialogs
    from aas_editor.ui.concept_actions import register_concept_actions

    register_concept_actions()

    class Lab:
        def __init__(self, *objects: model.Identifiable) -> None:
            self.monkeypatch = monkeypatch
            self.shown = views()
            self.view = self.shown.view
            self.package = self.shown.open_package(*objects)
            self.stack = self.package.commandStack
            self.store = self.package.objStore
            self.messages: list[str] = []
            self.asked: list[Any] = []
            monkeypatch.setattr(
                reference_dialogs,
                "show_message",
                lambda title, text, parent=None: self.messages.append(text),
            )

        def select(self, *paths: tuple[str, ...]) -> None:
            self.shown.select(*(self.shown.index(*p) for p in paths))
            self.view.updateActions(self.view.currentIndex())

        def act(self, action_id: str) -> bool:
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            action.trigger()
            return enabled

        def enabled(self, action_id: str) -> bool:
            return self.view.registeredActions.find(action_id).isEnabled()

        def rows(self, *path: str) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(*path)
            return [
                proxy.index(row, 0, parent).data(NAME_ROLE)
                for row in range(proxy.rowCount(parent))
            ]

        def answer(self, name: str, value: Any) -> None:
            """Replaces a question of the concept dialogs by an answer."""

            def respond(*args: Any, **kwargs: Any) -> Any:
                self.asked.append((args, kwargs))
                return value

            monkeypatch.setattr(concept_dialogs, name, respond)

        def fill(self, dialog_class: type, fill: Callable[[Any], None]) -> None:
            """Makes the real dialog fill itself and accept, instead of exec."""

            def run(dialog: Any) -> None:
                fill(dialog)
                dialog.accept()

            monkeypatch.setattr(dialog_class, "exec", run)

        def saved(self) -> str:
            path = tmp_path / "saved.aasx"
            self.package.write(path)
            return snapshot(Package(path).objStore)

        def concept(self, id_: str) -> model.ConceptDescription:
            found = self.store.get_item(id_)
            assert isinstance(found, model.ConceptDescription)
            return found

    return Lab


class TestCreateFromSemanticId:
    def _lab(self, concepts):
        prop = _prop("MaxSpeed", "urn:cd:speed")
        prop.description = model.MultiLanguageTextType({"en": "How fast"})
        submodel = make_submodel(elements=[prop, _prop("Plain")])
        lab = concepts(submodel)
        lab.select((*SUBMODEL, "MaxSpeed"))
        return lab

    def test_it_adds_the_description_and_the_row(
        self, concepts, tmp_path
    ) -> None:
        lab = self._lab(concepts)

        enabled = lab.act("concepts.create")

        assert enabled
        concept = lab.concept("urn:cd:speed")
        assert concept.id_short == "MaxSpeed"
        (record,) = concept.embedded_data_specifications
        assert (
            match_template(record.data_specification) is TemplateMatch.CURRENT
        )
        assert lab.rows(CONCEPTS) == ["MaxSpeed"]

    def test_undo_removes_it_again_and_redo_brings_it_back(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        before = snapshot(lab.store)

        lab.act("concepts.create")
        created = snapshot(lab.store)
        lab.stack.undo()

        assert snapshot(lab.store) == before
        assert lab.rows(CONCEPTS) == []
        lab.stack.redo()
        assert snapshot(lab.store) == created
        assert lab.rows(CONCEPTS) == ["MaxSpeed"]

    def test_the_description_survives_a_save_and_a_reload(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)

        lab.act("concepts.create")

        assert lab.saved() == snapshot(lab.store)
        assert "urn:cd:speed" in lab.saved()

    def test_it_is_one_undo_step(self, concepts) -> None:
        lab = self._lab(concepts)

        lab.act("concepts.create")
        lab.stack.undo()

        assert not lab.stack.can_undo

    def test_an_existing_description_gets_a_message_and_no_step(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.act("concepts.create")
        lab.select((*SUBMODEL, "MaxSpeed"))
        lab.stack.undo()
        lab.stack.redo()
        before = snapshot(lab.store)

        lab.act("concepts.create")

        assert "has already" in lab.messages[-1]
        assert snapshot(lab.store) == before
        lab.stack.undo()
        assert _concept_ids(lab.store) == []

    def test_an_element_without_semantic_id_says_why_nothing_is_created(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.select((*SUBMODEL, "Plain"))

        enabled = lab.act("concepts.create")

        assert enabled
        assert lab.messages[-1].startswith(
            "Cannot create a concept description because no valid semantic "
            "id is present in"
        )
        assert "Plain" in lab.messages[-1]
        assert _concept_ids(lab.store) == []
        assert not lab.stack.can_undo

    def test_an_id_of_another_kind_of_object_is_explained(
        self, concepts
    ) -> None:
        other = make_submodel("urn:cd:clash", "Other")
        submodel = make_submodel(elements=[_prop("A", "urn:cd:clash")])
        lab = concepts(submodel, other)
        lab.select((*SUBMODEL, "A"))

        lab.act("concepts.create")

        assert "not a concept description" in lab.messages[-1]
        assert _concept_ids(lab.store) == []

    def test_read_mode_disables_it(self, concepts) -> None:
        lab = self._lab(concepts)
        edit_mode().set_editing(False)
        lab.view.updateActions(lab.view.currentIndex())

        assert not lab.enabled("concepts.create")
        assert _concept_ids(lab.store) == []


class TestCreateFromAll:
    def _lab(self, concepts):
        submodel = make_submodel(
            elements=[
                _prop("A", "urn:cd:a"),
                make_collection("C", [_prop("B", "urn:cd:b")]),
                _prop("Plain"),
            ]
        )
        lab = concepts(submodel)
        lab.select(SUBMODEL)
        return lab

    def test_all_new_descriptions_are_one_undo_step(self, concepts) -> None:
        lab = self._lab(concepts)
        before = snapshot(lab.store)
        lab.answer("ask_create_kind", True)

        lab.act("concepts.create_all")
        created = snapshot(lab.store)

        assert _concept_ids(lab.store) == ["urn:cd:a", "urn:cd:b"]
        assert lab.rows(CONCEPTS) == ["A", "B"]
        assert "2 concept descriptions will be added" in lab.asked[0][0][0]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        assert lab.rows(CONCEPTS) == []
        assert not lab.stack.can_undo
        lab.stack.redo()
        assert snapshot(lab.store) == created
        assert lab.saved() == created

    def test_with_records_the_names_come_from_the_idshort(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.answer("ask_create_kind", True)

        lab.act("concepts.create_all")

        record = lab.concept("urn:cd:b").embedded_data_specifications[0]
        content = record.data_specification_content
        assert dict(content.preferred_name) == {"en": "B"}  # type: ignore[attr-defined]

    def test_plain_descriptions_have_no_record(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.answer("ask_create_kind", False)

        lab.act("concepts.create_all")

        assert lab.concept("urn:cd:a").embedded_data_specifications == []

    def test_cancel_changes_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        before = snapshot(lab.store)
        lab.answer("ask_create_kind", None)

        lab.act("concepts.create_all")

        assert snapshot(lab.store) == before
        assert not lab.stack.can_undo

    def test_nothing_to_create_is_explained(self, concepts) -> None:
        lab = concepts(make_submodel(elements=[_prop("Plain")]))
        lab.select(SUBMODEL)
        lab.answer("ask_create_kind", True)

        lab.act("concepts.create_all")

        assert lab.messages[-1].startswith("Nothing to create.")
        assert lab.asked == []


class TestAssign:
    def _lab(self, concepts, semantic: str | None = None):
        submodel = make_submodel(elements=[_prop("A", semantic), _prop("B")])
        speed = _concept("urn:cd:speed", "Speed")
        lab = concepts(submodel, speed, _concept("urn:cd:weight", "Weight"))
        lab.select((*SUBMODEL, "A"))
        return lab, speed

    def test_the_chosen_description_becomes_the_semantic_id(
        self, concepts
    ) -> None:
        lab, speed = self._lab(concepts)
        lab.answer("ask_concept", speed)
        before = snapshot(lab.store)

        lab.act("concepts.assign")
        assigned = snapshot(lab.store)

        element = lab.package.submodels.__next__().get_referable("A")
        assert element.semantic_id == make_external_reference("urn:cd:speed")
        assert [c.id for c in lab.asked[0][0][0]] == [
            "urn:cd:speed",
            "urn:cd:weight",
        ]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert snapshot(lab.store) == assigned
        assert lab.saved() == assigned

    def test_an_existing_semantic_id_is_not_replaced_without_asking(
        self, concepts
    ) -> None:
        lab, speed = self._lab(concepts, "urn:cd:old")
        lab.answer("ask_concept", speed)
        lab.answer("confirm_replace_semantic_ids", False)
        before = snapshot(lab.store)

        lab.act("concepts.assign")

        assert snapshot(lab.store) == before
        assert "urn:cd:old" in lab.asked[1][0][0][0]
        assert "urn:cd:speed" in lab.asked[1][0][0][0]

    def test_a_confirmed_replacement_is_one_undo_step(self, concepts) -> None:
        lab, speed = self._lab(concepts, "urn:cd:old")
        lab.answer("ask_concept", speed)
        lab.answer("confirm_replace_semantic_ids", True)
        before = snapshot(lab.store)

        lab.act("concepts.assign")

        element = next(iter(lab.package.submodels)).get_referable("A")
        assert element.semantic_id == make_external_reference("urn:cd:speed")
        lab.stack.undo()
        assert snapshot(lab.store) == before
        assert element.semantic_id == make_external_reference("urn:cd:old")

    def test_a_cancelled_choice_changes_nothing(self, concepts) -> None:
        lab, _ = self._lab(concepts)
        lab.answer("ask_concept", None)

        lab.act("concepts.assign")

        assert not lab.stack.can_undo

    def test_assigning_what_the_element_has_says_so(self, concepts) -> None:
        lab, speed = self._lab(concepts, "urn:cd:speed")
        lab.answer("ask_concept", speed)

        lab.act("concepts.assign")

        assert "this semantic id already" in lab.messages[-1]
        assert not lab.stack.can_undo

    def test_a_package_without_descriptions_says_what_to_do(
        self, concepts
    ) -> None:
        lab = concepts(make_submodel(elements=[_prop("A")]))
        lab.select((*SUBMODEL, "A"))

        lab.act("concepts.assign")

        assert "no concept descriptions" in lab.messages[-1]

    def test_several_elements_get_the_same_description_in_one_step(
        self, concepts
    ) -> None:
        lab, speed = self._lab(concepts)
        lab.answer("ask_concept", speed)
        lab.select((*SUBMODEL, "A"), (*SUBMODEL, "B"))

        lab.act("concepts.assign")

        submodel = next(iter(lab.package.submodels))
        assert [e.semantic_id for e in submodel.submodel_element] == [
            make_external_reference("urn:cd:speed")
        ] * 2
        lab.stack.undo()
        assert [e.semantic_id for e in submodel.submodel_element] == [
            None,
            None,
        ]

    def test_the_element_keeps_its_row(self, concepts) -> None:
        lab, speed = self._lab(concepts)
        lab.answer("ask_concept", speed)

        lab.act("concepts.assign")

        assert lab.rows(*SUBMODEL) == ["A", "B"]


class TestAutoDetect:
    def _lab(self, concepts):
        submodel = make_submodel(
            elements=[
                _prop("Speed"),
                _prop("Weight", "urn:other:weight"),
                _prop("Colour"),
            ]
        )
        lab = concepts(
            submodel,
            _concept("urn:cd:speed", "Speed"),
            _concept("urn:cd:weight", "Weight"),
        )
        lab.select(SUBMODEL)
        return lab

    def test_an_element_without_semantic_id_gets_the_description_with_its_idshort(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.answer("confirm_preview", True)
        before = snapshot(lab.store)

        lab.act("concepts.auto_detect")
        done = snapshot(lab.store)

        submodel = next(iter(lab.package.submodels))
        by_name = {e.id_short: e.semantic_id for e in submodel.submodel_element}
        assert by_name["Speed"] == make_external_reference("urn:cd:speed")
        # A semantic id that is set is never replaced, even if the idShort matches.
        assert by_name["Weight"] == make_external_reference("urn:other:weight")
        assert by_name["Colour"] is None
        rows = lab.asked[0][0][3]
        assert rows == [
            ["Property 'Speed' of Submodel 'Submodel'", "Speed", "urn:cd:speed"]
        ]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert lab.saved() == done

    def test_declining_the_preview_changes_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.answer("confirm_preview", False)

        lab.act("concepts.auto_detect")

        assert not lab.stack.can_undo

    def test_nothing_to_assign_says_why(self, concepts) -> None:
        lab = concepts(make_submodel(elements=[_prop("Colour")]))
        lab.select(SUBMODEL)
        lab.answer("confirm_preview", True)

        lab.act("concepts.auto_detect")

        assert lab.messages[-1].startswith("Nothing to assign.")
        assert lab.asked == []


class TestFromPairs:
    def _lab(self, concepts):
        pairs = {
            model.ValueReferencePair("Red", make_external_reference("urn:red")),
            model.ValueReferencePair(
                "Blue", make_external_reference("urn:blue")
            ),
            model.ValueReferencePair("Lonely"),
        }
        colours = _concept(
            "urn:cd:colours", "Colours", _record(value_list=pairs)
        )
        lab = concepts(colours)
        lab.select((CONCEPTS, "Colours"))
        return lab

    def test_each_pair_with_an_id_becomes_a_description(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.answer("confirm_preview", True)
        before = snapshot(lab.store)

        lab.act("concepts.from_pairs")
        done = snapshot(lab.store)

        assert _concept_ids(lab.store) == [
            "urn:blue",
            "urn:cd:colours",
            "urn:red",
        ]
        assert sorted(lab.rows(CONCEPTS)) == ["Blue", "Colours", "Red"]
        # The value list is unchanged.
        assert (
            len(
                lab.concept("urn:cd:colours")
                .embedded_data_specifications[0]
                .data_specification_content.value_list
            )
            == 3
        )  # type: ignore[attr-defined]
        assert "Skipped Lonely" in lab.asked[0][0][4][0]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert lab.saved() == done

    def test_declining_creates_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.answer("confirm_preview", False)

        lab.act("concepts.from_pairs")

        assert _concept_ids(lab.store) == ["urn:cd:colours"]
        assert not lab.stack.can_undo

    def test_it_is_disabled_without_a_value_list(self, concepts) -> None:
        lab = concepts(_concept("urn:cd:plain", "Plain"))
        lab.select((CONCEPTS, "Plain"))

        assert not lab.enabled("concepts.from_pairs")


class TestDeleteInvalid:
    def _lab(self, concepts):
        used = _concept("urn:cd:used", "Used")
        unused = _concept("urn:cd:unused", "Unused")
        full = _concept("urn:cd:full", "Full", _record())
        submodel = make_submodel(elements=[_prop("A", "urn:cd:used")])
        lab = concepts(submodel, used, unused, full)
        lab.select((CONCEPTS, "Full"))
        return lab

    def _answer_usages(self, lab, remove: bool | None) -> list[Any]:
        from aas_editor.ui import reference_dialogs

        plans: list[Any] = []

        def ask(plan: Any, parent: Any = None) -> bool | None:
            plans.append(plan)
            return remove

        lab.monkeypatch.setattr(reference_dialogs, "ask_delete", ask)
        return plans

    def test_the_delete_flow_shows_the_usages_of_what_is_deleted(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        plans = self._answer_usages(lab, True)
        lab.answer("choose_rows", [0, 1])

        lab.act("concepts.delete_invalid")

        (plan,) = plans
        assert [target.id for target in plan.targets] == [
            "urn:cd:unused",
            "urn:cd:used",
        ]
        assert [u.slot.location for u in plan.usages] == [
            "Property 'A' of Submodel 'Submodel' / semantic_id"
        ]

    def test_deleting_with_the_references_is_one_step_that_undo_restores(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        self._answer_usages(lab, True)
        lab.answer("choose_rows", [0, 1])
        before = snapshot(lab.store)

        lab.act("concepts.delete_invalid")
        done = snapshot(lab.store)

        assert _concept_ids(lab.store) == ["urn:cd:full"]
        assert lab.rows(CONCEPTS) == ["Full"]
        element = next(iter(lab.package.submodels)).get_referable("A")
        assert element.semantic_id is None
        lab.stack.undo()
        assert snapshot(lab.store) == before
        assert element.semantic_id == make_external_reference("urn:cd:used")
        assert sorted(lab.rows(CONCEPTS)) == ["Full", "Unused", "Used"]
        lab.stack.redo()
        assert lab.saved() == done

    def test_the_references_can_be_left_in_place(self, concepts) -> None:
        lab = self._lab(concepts)
        self._answer_usages(lab, False)
        lab.answer("choose_rows", [0, 1])

        lab.act("concepts.delete_invalid")

        element = next(iter(lab.package.submodels)).get_referable("A")
        assert _concept_ids(lab.store) == ["urn:cd:full"]
        assert element.semantic_id == make_external_reference("urn:cd:used")

    def test_cancelling_the_usages_deletes_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        self._answer_usages(lab, None)
        lab.answer("choose_rows", [0, 1])
        before = snapshot(lab.store)

        lab.act("concepts.delete_invalid")

        assert snapshot(lab.store) == before
        assert not lab.stack.can_undo

    def test_only_the_chosen_ones_are_deleted(self, concepts) -> None:
        lab = self._lab(concepts)
        self._answer_usages(lab, True)
        lab.answer("choose_rows", [0])

        lab.act("concepts.delete_invalid")

        assert _concept_ids(lab.store) == ["urn:cd:full", "urn:cd:used"]

    def test_the_list_names_the_descriptions_and_their_references(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.answer("choose_rows", None)

        lab.act("concepts.delete_invalid")

        rows = lab.asked[0][0][3]
        assert rows == [
            ["Unused", "urn:cd:unused", "0"],
            ["Used", "urn:cd:used", "1"],
        ]

    def test_without_invalid_descriptions_it_says_so(self, concepts) -> None:
        lab = concepts(_concept("urn:cd:full", "Full", _record()))
        lab.select((CONCEPTS, "Full"))

        lab.act("concepts.delete_invalid")

        assert "No concept description is invalid" in lab.messages[-1]


class TestRecords:
    def _lab(self, concepts):
        lab = concepts(_concept("urn:cd:speed", "Speed"))
        lab.select((CONCEPTS, "Speed"))
        return lab

    def _fill(self, lab, name: str = "Maximum speed") -> None:
        from aas_editor.ui.iec61360_dialog import Iec61360Dialog

        def fill(dialog: Any) -> None:
            dialog.preferred_name.set_rows([("en", name)])
            dialog.definition.add_row("en", "How fast")
            dialog.unit.setText("m/s")
            dialog.set_data_type(model.DataTypeIEC61360.REAL_MEASURE)

        lab.fill(Iec61360Dialog, fill)

    def test_the_dialog_starts_with_the_idshort_as_the_name(
        self, concepts
    ) -> None:
        from aas_editor.ui.iec61360_dialog import Iec61360Dialog

        lab = self._lab(concepts)
        starts: list[Any] = []
        lab.monkeypatch.setattr(
            Iec61360Dialog,
            "exec",
            lambda d: starts.append(d.preferred_name.rows()) or d.reject(),
        )

        lab.act("concepts.add_record")

        assert starts == [[("en", "Speed")]]
        assert not lab.stack.can_undo

    def test_adding_a_record_with_the_template_key(self, concepts) -> None:
        lab = self._lab(concepts)
        self._fill(lab)
        before = snapshot(lab.store)

        lab.act("concepts.add_record")
        done = snapshot(lab.store)

        (record,) = lab.concept("urn:cd:speed").embedded_data_specifications
        assert (
            match_template(record.data_specification) is TemplateMatch.CURRENT
        )
        content = record.data_specification_content
        assert isinstance(content, model.DataSpecificationIEC61360)
        assert dict(content.preferred_name) == {"en": "Maximum speed"}
        assert content.unit == "m/s"
        assert content.data_type is model.DataTypeIEC61360.REAL_MEASURE
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert snapshot(lab.store) == done
        assert lab.saved() == done

    def test_a_second_record_is_refused_with_a_pointer_to_edit(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        self._fill(lab)
        lab.act("concepts.add_record")
        before = snapshot(lab.store)

        lab.act("concepts.add_record")

        assert "Edit IEC 61360 record" in lab.messages[-1]
        assert snapshot(lab.store) == before

    def test_cancelling_the_dialog_adds_nothing(self, concepts) -> None:
        lab = self._lab(concepts)

        lab.act("concepts.add_record")

        assert lab.concept("urn:cd:speed").embedded_data_specifications == []

    def test_editing_changes_the_content_and_undo_gives_the_old_back(
        self, concepts
    ) -> None:
        from aas_editor.ui.iec61360_dialog import Iec61360Dialog

        lab = self._lab(concepts)
        self._fill(lab)
        lab.act("concepts.add_record")
        before = snapshot(lab.store)
        lab.select((CONCEPTS, "Speed"))
        lab.fill(
            Iec61360Dialog,
            lambda d: (
                d.preferred_name.set_rows(
                    [("en", "Top speed"), ("de", "Höchstgeschwindigkeit")]
                ),
                d.symbol.setText("v"),
            ),
        )

        lab.act("concepts.edit_record")
        done = snapshot(lab.store)

        content = (
            lab.concept("urn:cd:speed")
            .embedded_data_specifications[0]
            .data_specification_content
        )
        assert dict(content.preferred_name) == {  # type: ignore[attr-defined]
            "en": "Top speed",
            "de": "Höchstgeschwindigkeit",
        }
        assert content.symbol == "v"  # type: ignore[attr-defined]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert lab.saved() == done

    def test_editing_keeps_an_older_spelling_of_the_key(self, concepts) -> None:
        from aas_editor.ui.iec61360_dialog import Iec61360Dialog

        older = (
            "http://admin-shell.io/DataSpecificationTemplates/"
            "DataSpecificationIEC61360/3/0"
        )
        lab = concepts(_concept("urn:cd:old", "Old", _record(older)))
        lab.select((CONCEPTS, "Old"))
        lab.fill(Iec61360Dialog, lambda d: d.symbol.setText("v"))

        lab.act("concepts.edit_record")

        (record,) = lab.concept("urn:cd:old").embedded_data_specifications
        assert record.data_specification == make_external_reference(older)

    def test_edit_is_disabled_without_a_record(self, concepts) -> None:
        lab = self._lab(concepts)

        assert not lab.enabled("concepts.edit_record")
        assert lab.enabled("concepts.add_record")

    def test_empty_attributes_are_removed_in_one_step(self, concepts) -> None:
        lab = concepts(
            _concept(
                "urn:cd:e", "E", _record(unit="", symbol="", value_list=set())
            )
        )
        lab.select((CONCEPTS, "E"))
        before = snapshot(lab.store)

        enabled = lab.act("concepts.clear_empty")
        done = snapshot(lab.store)

        assert enabled
        content = (
            lab.concept("urn:cd:e")
            .embedded_data_specifications[0]
            .data_specification_content
        )
        assert content.unit is None  # type: ignore[attr-defined]
        assert content.value_list is None  # type: ignore[attr-defined]
        assert dict(content.preferred_name) == {"en": "Name"}  # type: ignore[attr-defined]
        assert done != before
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert lab.saved() == done

    def test_clean_content_leaves_the_action_disabled(self, concepts) -> None:
        lab = concepts(_concept("urn:cd:c", "C", _record(unit="m")))
        lab.select((CONCEPTS, "C"))

        assert not lab.enabled("concepts.clear_empty")


class TestFixKeys:
    OLDER = (
        "http://admin-shell.io/DataSpecificationTemplates/"
        "DataSpecificationIEC61360/3/0"
    )

    def _lab(self, concepts):
        lab = concepts(
            _concept("urn:cd:ok", "Ok", _record()),
            _concept(
                "urn:cd:wrong", "Wrong", _record("0112/2///62683#ACE053#001")
            ),
            _concept("urn:cd:older", "Older", _record(self.OLDER)),
            _concept("urn:cd:three", "Three", _record("a"), _record("b")),
        )
        lab.select((CONCEPTS, "Ok"))
        return lab

    def test_with_no_concept_selected_all_descriptions_are_fixed(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        lab.select((CONCEPTS,))
        lab.answer("ask_fix_keys", False)
        before = snapshot(lab.store)

        lab.act("concepts.fix_keys")
        done = snapshot(lab.store)

        def keys(id_: str) -> list[TemplateMatch]:
            return [
                match_template(r.data_specification)
                for r in lab.concept(id_).embedded_data_specifications
            ]

        assert keys("urn:cd:wrong") == [TemplateMatch.CURRENT]
        # Every record of a description is fixed in one run.
        assert keys("urn:cd:three") == [TemplateMatch.CURRENT] * 2
        # The other spelling stays unless the user asked.
        assert keys("urn:cd:older") == [TemplateMatch.OTHER_SPELLING]
        lab.stack.undo()
        assert snapshot(lab.store) == before
        lab.stack.redo()
        assert lab.saved() == done

    def test_the_user_can_include_other_spellings(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.select((CONCEPTS,))
        lab.answer("ask_fix_keys", True)

        lab.act("concepts.fix_keys")

        (record,) = lab.concept("urn:cd:older").embedded_data_specifications
        assert (
            match_template(record.data_specification) is TemplateMatch.CURRENT
        )

    def test_cancel_changes_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        lab.select((CONCEPTS,))
        lab.answer("ask_fix_keys", None)

        lab.act("concepts.fix_keys")

        assert not lab.stack.can_undo

    def test_a_package_with_correct_keys_says_so(self, concepts) -> None:
        lab = concepts(_concept("urn:cd:ok", "Ok", _record()))
        lab.select((CONCEPTS, "Ok"))

        lab.act("concepts.fix_keys")

        assert (
            lab.messages[-1]
            == "All 1 IEC 61360 records name the template already."
        )


class TestImportValueList:
    def _lab(self, concepts):
        lab = concepts(_concept("urn:cd:colours", "Colours", _record()))
        lab.select((CONCEPTS, "Colours"))
        return lab

    def _accept(self, lab) -> None:
        from aas_editor.ui.value_list_dialog import ValueListImportDialog

        lab.monkeypatch.setattr(
            ValueListImportDialog, "exec", lambda dialog: dialog.accept()
        )

    def _values(self, lab) -> dict[str, str]:
        content = (
            lab.concept("urn:cd:colours")
            .embedded_data_specifications[0]
            .data_specification_content
        )
        return {
            p.value: p.value_id.key[0].value  # type: ignore[union-attr]
            for p in content.value_list or ()  # type: ignore[attr-defined]
        }

    def test_the_clipboard_is_imported_after_the_preview(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)
        QApplication.clipboard().setText(
            "Red, 0173-1#07-AAA#001\nGreen\turn:green\n"
        )
        self._accept(lab)
        before = snapshot(lab.store)

        lab.act("concepts.import_value_list")
        done = snapshot(lab.store)

        assert self._values(lab) == {
            "Red": "0173-1#07-AAA#001",
            "Green": "urn:green",
        }
        lab.stack.undo()
        assert snapshot(lab.store) == before
        assert self._values(lab) == {}
        lab.stack.redo()
        assert snapshot(lab.store) == done
        assert lab.saved() == done

    def test_a_second_import_adds_only_what_is_new(self, concepts) -> None:
        lab = self._lab(concepts)
        self._accept(lab)
        QApplication.clipboard().setText("Red, urn:red")
        lab.act("concepts.import_value_list")
        QApplication.clipboard().setText("Red, urn:red\nBlue, urn:blue")

        lab.act("concepts.import_value_list")

        assert self._values(lab) == {"Red": "urn:red", "Blue": "urn:blue"}

    def test_text_that_cannot_be_read_imports_nothing(self, concepts) -> None:
        lab = self._lab(concepts)
        QApplication.clipboard().setText('[{"value": "x",')
        self._accept(lab)

        lab.act("concepts.import_value_list")

        assert self._values(lab) == {}
        assert not lab.stack.can_undo

    def test_code_on_the_clipboard_is_never_evaluated(
        self, concepts, tmp_path: Path
    ) -> None:
        lab = self._lab(concepts)
        marker = tmp_path / "owned"
        QApplication.clipboard().setText(
            f"__import__('pathlib').Path({str(marker)!r}).write_text('x')"
        )
        self._accept(lab)

        lab.act("concepts.import_value_list")

        assert not marker.exists()
        assert self._values(lab) == {}

    def test_it_is_disabled_without_a_record(self, concepts) -> None:
        lab = concepts(_concept("urn:cd:plain", "Plain"))
        lab.select((CONCEPTS, "Plain"))

        assert not lab.enabled("concepts.import_value_list")


class TestOrder:
    def _lab(self, concepts):
        submodel = make_submodel(
            elements=[_prop("First", "urn:cd:c"), _prop("Second", "urn:cd:a")]
        )
        lab = concepts(
            submodel,
            _concept("urn:cd:a", "alpha"),
            _concept("urn:cd:b", "Beta"),
            _concept("urn:cd:c", "gamma"),
            _concept("urn:cd:z", None),
            _concept("urn:cd:y", None),
        )
        lab.select((CONCEPTS,))
        return lab

    def _choose(self, lab, order) -> None:
        from aas_editor.ui import concept_actions

        lab.monkeypatch.setattr(
            concept_actions,
            "ask_concept_order",
            lambda current, parent=None: order,
        )
        lab.act("concepts.order")

    def _objects(self, lab) -> list[str]:
        from aas_editor.settings.app_settings import OBJECT_ROLE

        proxy = lab.view.model()
        parent = lab.shown.index(CONCEPTS)
        return [
            proxy.index(row, 0, parent).data(OBJECT_ROLE).id
            for row in range(proxy.rowCount(parent))
        ]

    def test_by_default_the_names_are_listed_without_regard_to_case(
        self, concepts
    ) -> None:
        lab = self._lab(concepts)

        # A capital C for ConceptDescription is shown for those without a name.
        assert self._objects(lab) == [
            "urn:cd:a",
            "urn:cd:b",
            "urn:cd:y",
            "urn:cd:z",
            "urn:cd:c",
        ]

    def test_idshort_lists_unnamed_descriptions_last(self, concepts) -> None:
        from aas_editor.domain.concept_order import ConceptOrder

        lab = self._lab(concepts)

        self._choose(lab, ConceptOrder.ID_SHORT)

        assert self._objects(lab) == [
            "urn:cd:a",
            "urn:cd:b",
            "urn:cd:c",
            "urn:cd:y",
            "urn:cd:z",
        ]

    def test_id_lists_by_the_id(self, concepts) -> None:
        from aas_editor.domain.concept_order import ConceptOrder

        lab = self._lab(concepts)

        self._choose(lab, ConceptOrder.ID)

        assert self._objects(lab) == [
            "urn:cd:a",
            "urn:cd:b",
            "urn:cd:c",
            "urn:cd:y",
            "urn:cd:z",
        ]

    def test_first_use_lists_the_used_descriptions_first(
        self, concepts
    ) -> None:
        from aas_editor.domain.concept_order import ConceptOrder

        lab = self._lab(concepts)

        self._choose(lab, ConceptOrder.FIRST_USE)

        # First (urn:cd:c) is used before Second (urn:cd:a).
        assert self._objects(lab)[:2] == ["urn:cd:c", "urn:cd:a"]

    def test_the_order_changes_the_view_and_never_the_package(
        self, concepts
    ) -> None:
        from aas_editor.domain.concept_order import ConceptOrder

        lab = self._lab(concepts)
        before = snapshot(lab.store)

        self._choose(lab, ConceptOrder.ID)

        assert snapshot(lab.store) == before
        assert not lab.stack.can_undo
        assert lab.stack.is_clean
        assert lab.saved() == before

    def test_the_order_is_available_in_read_mode(self, concepts) -> None:
        lab = self._lab(concepts)
        edit_mode().set_editing(False)
        lab.view.updateActions(lab.view.currentIndex())

        assert lab.enabled("concepts.order")

    def test_a_cancelled_choice_keeps_the_order(self, concepts) -> None:
        from aas_editor.domain.concept_order import ConceptOrder

        lab = self._lab(concepts)
        self._choose(lab, ConceptOrder.ID)
        order_before = self._objects(lab)

        self._choose(lab, None)

        assert self._objects(lab) == order_before
        assert lab.view.model().conceptOrder() is ConceptOrder.ID


def test_the_tools_for_descriptions_are_off_on_an_element(concepts) -> None:
    submodel = make_submodel(elements=[_prop("A", "urn:cd:a")])
    lab = concepts(submodel, model.ConceptDescription(id_="urn:cd:a"))
    ids = (
        "concepts.delete_invalid",
        "concepts.fix_keys",
        "concepts.order",
    )

    lab.select((*SUBMODEL, "A"))
    on_element = [lab.enabled(action_id) for action_id in ids]
    lab.select(("concept_descriptions",))
    on_the_node = [lab.enabled(action_id) for action_id in ids]

    # They were on for every row, so the menu of a Property listed them.
    assert on_element == [False, False, False]
    assert on_the_node == [True, True, True]
