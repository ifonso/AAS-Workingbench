"""Copy, cut and paste above, below and into, through the tree view."""

from pathlib import Path

from basyx.aas import model
import pytest
from PyQt6.QtWidgets import QApplication
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.forms import answering

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.domain.clipboard_json import dump_objects

SUBMODEL = ("submodels", "Submodel")


def _ids(container: object) -> list[str | None]:
    return [m.id_short for m in container]  # type: ignore[attr-defined]


@pytest.fixture
def pasting(views, monkeypatch: pytest.MonkeyPatch):
    """Packages with a submodel, and ways to copy and paste in the tree."""
    from aas_workingbench.package import Package
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.ui import paste_dialogs
    from aas_workingbench.ui.move_actions import register_move_actions
    from aas_workingbench.ui.paste_actions import register_paste_actions

    register_move_actions()
    register_paste_actions()
    problems: list[str] = []
    monkeypatch.setattr(
        paste_dialogs,
        "show_problem",
        lambda message, parent=None: problems.append(message),
    )
    QApplication.clipboard().clear()

    class Pasting:
        def __init__(self, *elements: model.SubmodelElement) -> None:
            self.monkeypatch = monkeypatch
            self.problems = problems
            self.shown = views()
            self.view = self.shown.view
            self.view.treeClipboard.clear()
            self.submodel = make_submodel(elements=elements)
            self.package = self.shown.open_package(self.submodel)

        def open_other(self, *objects: model.Identifiable) -> object:
            return self.shown.open_package(*objects)

        def path(self, *names: str, package: int = 0):
            return self.shown.index(*names, package=package)

        def select(self, *paths: tuple[str, ...], package: int = 0) -> None:
            self.shown.select(
                *(self.shown.index(*p, package=package) for p in paths)
            )

        def element_path(self, *names: str) -> tuple[str, ...]:
            return (*SUBMODEL, *names)

        def copy(self) -> None:
            self.view.onCopy()

        def cut(self) -> None:
            self.view.onCut()

        def act(self, action_id: str) -> bool:
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            action.trigger()
            return enabled

        def enabled(self, action_id: str) -> bool:
            return self.view.registeredActions.find(action_id).isEnabled()

        def rows(self, *path: str) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(*SUBMODEL, *path)
            return [
                proxy.index(row, 0, parent).data(NAME_ROLE)
                for row in range(proxy.rowCount(parent))
            ]

        def saved(self, tmp_path: Path) -> model.Submodel:
            path = tmp_path / "pasted.aasx"
            self.package.write(path)
            return Package(path).objStore.get_item(self.submodel.id)

    return Pasting


def test_copy_then_paste_below_adds_a_numbered_duplicate_after_it(
    pasting, tmp_path
) -> None:
    lab = pasting(make_property("Name"), make_property("Other"))
    lab.select(lab.element_path("Name"))
    original = next(iter(lab.submodel.submodel_element))
    value = original.value  # type: ignore[attr-defined]

    lab.copy()
    lab.act("structure.paste_below")

    assert _ids(lab.submodel.submodel_element) == ["Name", "Name_1", "Other"]
    assert lab.rows() == ["Name", "Name_1", "Other"]
    assert original.value == value  # type: ignore[attr-defined]
    assert _ids(lab.saved(tmp_path).submodel_element) == [
        "Name",
        "Name_1",
        "Other",
    ]


def test_paste_above_inserts_before_the_selected_element(pasting) -> None:
    lab = pasting(make_property("A"), make_property("B"))
    lab.select(lab.element_path("B"))
    lab.copy()
    lab.select(lab.element_path("A"))

    lab.act("structure.paste_above")

    assert lab.rows() == ["B_1", "A", "B"]


def test_a_second_paste_gives_a_further_duplicate(pasting) -> None:
    lab = pasting(make_property("Name"))
    lab.select(lab.element_path("Name"))
    lab.copy()

    lab.act("structure.paste_below")
    lab.act("structure.paste_below")

    assert len(_ids(lab.submodel.submodel_element)) == 3
    assert len(set(_ids(lab.submodel.submodel_element))) == 3


def test_a_paste_is_one_undo_step(pasting) -> None:
    lab = pasting(make_property("A"), make_property("B"))
    lab.select(lab.element_path("A"), lab.element_path("B"))
    lab.copy()
    lab.select(lab.element_path("B"))

    lab.act("structure.paste_below")
    after = _ids(lab.submodel.submodel_element)
    lab.view.onUndo()
    undone = _ids(lab.submodel.submodel_element)
    lab.view.onRedo()

    assert after == ["A", "B", "A_1", "B_1"]
    assert undone == ["A", "B"]
    assert _ids(lab.submodel.submodel_element) == after
    assert lab.rows() == after


def test_several_copied_elements_paste_below_in_their_order(pasting) -> None:
    lab = pasting(*(make_property(n) for n in "ABC"), make_property("Z"))
    lab.select(
        lab.element_path("A"), lab.element_path("B"), lab.element_path("C")
    )
    lab.copy()
    lab.select(lab.element_path("Z"))

    lab.act("structure.paste_below")

    assert _ids(lab.submodel.submodel_element)[-3:] == ["A_1", "B_1", "C_1"]


def test_cut_then_paste_above_keeps_the_name_and_removes_the_source(
    pasting,
) -> None:
    lab = pasting(
        make_collection("From", [make_property("Item")]),
        make_collection("To", [make_property("Other")]),
    )
    lab.select(lab.element_path("From", "Item"))
    lab.cut()
    lab.select(lab.element_path("To", "Other"))

    lab.act("structure.paste_above")

    assert _ids(lab.submodel.get_referable("From").value) == []  # type: ignore[attr-defined]
    assert _ids(lab.submodel.get_referable("To").value) == ["Item", "Other"]  # type: ignore[attr-defined]


def test_annotations_can_be_pasted_above(pasting) -> None:
    lab = pasting(
        make_annotated_relationship(
            annotations=[make_property("N1"), make_property("N2")]
        )
    )
    lab.select(lab.element_path("Relationship", "N2"))
    lab.copy()

    lab.act("structure.paste_above")

    relationship = lab.submodel.get_referable("Relationship")
    assert _ids(relationship.annotation) == ["N1", "N2_1", "N2"]  # type: ignore[attr-defined]


def test_paste_into_adds_at_the_end(pasting) -> None:
    lab = pasting(
        make_collection("C", [make_property("a")]), make_property("p")
    )
    lab.select(lab.element_path("p"))
    lab.copy()
    lab.select(lab.element_path("C"))

    enabled = lab.enabled("structure.paste_into")
    lab.act("structure.paste_into")

    assert enabled
    assert _ids(lab.submodel.get_referable("C").value) == ["a", "p"]  # type: ignore[attr-defined]


def test_paste_into_is_disabled_on_a_property(pasting) -> None:
    lab = pasting(make_property("p"))
    lab.select(lab.element_path("p"))
    lab.copy()

    assert not lab.enabled("structure.paste_into")
    assert lab.enabled("structure.paste_below")


def test_copy_puts_json_on_the_system_clipboard(pasting) -> None:
    import json

    lab = pasting(make_property("Voltage", "230"))
    lab.select(lab.element_path("Voltage"))

    lab.copy()

    text = QApplication.clipboard().text()
    entry = json.loads(text)[0]
    assert (entry["modelType"], entry["idShort"]) == ("Property", "Voltage")


def test_json_from_another_program_pastes_after_the_buffer_is_cleared(
    pasting,
) -> None:
    lab = pasting(make_property("A"))
    lab.select(lab.element_path("A"))
    lab.copy()
    lab.act("structure.clear_buffer")
    emptied = lab.view.treeClipboard.isEmpty()
    QApplication.clipboard().setText(
        dump_objects([make_property("External", "1")])
    )
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("A"))

    lab.act("structure.paste_below")

    assert emptied
    assert _ids(lab.submodel.submodel_element) == ["A", "External"]


def test_clear_buffer_also_empties_the_system_clipboard(pasting) -> None:
    lab = pasting(make_property("A"))
    lab.select(lab.element_path("A"))
    lab.copy()

    lab.act("structure.clear_buffer")

    assert lab.view.treeClipboard.isEmpty()
    assert QApplication.clipboard().text() == ""


@pytest.mark.parametrize(
    "text",
    ["hello", "[1, 2", '{"modelType": "Nonsense"}', '[{"a": 1}]'],
)
def test_bad_clipboard_text_is_refused_with_a_message(
    pasting, text: str
) -> None:
    lab = pasting(make_property("A"))
    lab.view.treeClipboard.clear()
    QApplication.clipboard().setText(text)
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("A"))

    lab.act("structure.paste_below")

    assert len(lab.problems) == 1
    assert lab.problems[0]
    assert _ids(lab.submodel.submodel_element) == ["A"]
    assert not lab.package.commandStack.can_undo


def test_json_that_is_newer_on_the_clipboard_replaces_the_buffer(
    pasting,
) -> None:
    """F-EDT-08 AC5 differs on purpose (ADR 0020): the buffer is the clipboard."""
    lab = pasting(make_property("A"), make_property("B"))
    lab.select(lab.element_path("A"))
    lab.copy()
    QApplication.clipboard().setText(
        dump_objects([make_property("Other", "9")])
    )
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("B"))

    lab.act("structure.paste_below")

    assert _ids(lab.submodel.submodel_element) == ["A", "B", "Other"]


def test_a_submodel_cannot_be_pasted_among_elements(pasting) -> None:
    lab = pasting(make_property("A"))
    lab.view.treeClipboard.clear()
    QApplication.clipboard().setText(
        dump_objects([make_submodel(id_="urn:other")])
    )
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("A"))

    lab.act("structure.paste_below")

    assert lab.problems
    assert _ids(lab.submodel.submodel_element) == ["A"]


def test_a_refused_object_leaves_the_package_as_it_was(pasting) -> None:
    from tests.factories import make_list

    lab = pasting(make_list("L", [make_property("x", "1")]))
    # A list of strings refuses a range.
    lab.view.treeClipboard.clear()
    QApplication.clipboard().setText(
        dump_objects([model.Range("r", model.datatypes.Int, 1, 2)])
    )
    lab.view.updateTreeClipboard()
    lab.select(lab.element_path("L", "x"))

    lab.act("structure.paste_below")

    assert lab.problems
    assert len(lab.submodel.get_referable("L").value) == 1  # type: ignore[attr-defined]
    assert not lab.package.commandStack.can_undo


def test_read_mode_disables_pasting(pasting) -> None:
    lab = pasting(make_property("A"))
    lab.select(lab.element_path("A"))
    lab.copy()
    edit_mode().set_editing(False)
    lab.view.updateActions(lab.view.currentIndex())

    assert not lab.enabled("structure.paste_below")


def test_a_cut_from_a_list_pasted_into_a_collection_leaves_the_list_without_it(
    pasting, tmp_path
) -> None:
    from tests.factories import make_list

    lab = pasting(
        make_list("L", [make_property("x", "1"), make_property("y", "2")]),
        make_collection("To", [make_property("Other")]),
    )
    lab.select(lab.element_path("L", "x"))

    lab.cut()
    list_after_cut = [m.value for m in lab.submodel.get_referable("L").value]  # type: ignore[attr-defined]
    lab.select(lab.element_path("To", "Other"))
    lab.act("structure.paste_above")

    saved = lab.saved(tmp_path)
    assert list_after_cut == ["2"]
    assert [m.value for m in lab.submodel.get_referable("L").value] == ["2"]  # type: ignore[attr-defined]
    assert _ids(lab.submodel.get_referable("To").value) == ["x", "Other"]  # type: ignore[attr-defined]
    assert [m.value for m in saved.get_referable("L").value] == ["2"]  # type: ignore[attr-defined]
    assert _ids(saved.get_referable("To").value) == ["x", "Other"]  # type: ignore[attr-defined]
    lab.view.onUndo()
    lab.view.onUndo()
    assert [m.value for m in lab.submodel.get_referable("L").value] == [  # type: ignore[attr-defined]
        "1",
        "2",
    ]


class TestPasteFromText:
    """F-EDT-08 AC8: a text box when the clipboard cannot be read."""

    @pytest.fixture
    def typed(self, monkeypatch: pytest.MonkeyPatch):
        from aas_workingbench.ui import paste_dialogs

        answer: dict[str, object] = {"value": None, "places": None}

        def ask(places, parent=None):
            answer["places"] = [key for key, _ in places]
            return answer["value"]

        monkeypatch.setattr(paste_dialogs, "ask_paste_text", ask)
        return answer

    def test_text_is_pasted_with_an_empty_clipboard_and_buffer(
        self, pasting, typed
    ) -> None:
        lab = pasting(make_property("A"), make_property("B"))
        lab.select(lab.element_path("A"))
        typed["value"] = (dump_objects([make_property("Typed", "7")]), "below")

        enabled = lab.act("structure.paste_text")

        assert enabled
        assert lab.view.treeClipboard.isEmpty()
        assert _ids(lab.submodel.submodel_element) == ["A", "Typed", "B"]
        assert lab.rows() == ["A", "Typed", "B"]
        lab.view.onUndo()
        assert _ids(lab.submodel.submodel_element) == ["A", "B"]

    def test_text_is_pasted_into_a_collection(self, pasting, typed) -> None:
        lab = pasting(make_collection("C", [make_property("In")]))
        lab.select(lab.element_path("C"))
        typed["value"] = (dump_objects([make_property("Typed")]), "into")

        lab.act("structure.paste_text")

        assert _ids(lab.submodel.get_referable("C").value) == ["In", "Typed"]  # type: ignore[attr-defined]

    def test_text_that_is_no_aas_object_is_refused_with_a_message(
        self, pasting, typed
    ) -> None:
        lab = pasting(make_property("A"))
        lab.select(lab.element_path("A"))
        typed["value"] = ("hello", "below")

        lab.act("structure.paste_text")

        assert lab.problems
        assert _ids(lab.submodel.submodel_element) == ["A"]
        assert not lab.package.commandStack.can_undo

    def test_cancelling_the_box_changes_nothing(self, pasting, typed) -> None:
        lab = pasting(make_property("A"))
        lab.select(lab.element_path("A"))
        typed["value"] = None

        lab.act("structure.paste_text")

        assert _ids(lab.submodel.submodel_element) == ["A"]
        assert not lab.problems

    def test_the_box_offers_the_places_that_fit_the_row(
        self, pasting, typed
    ) -> None:
        lab = pasting(make_property("A"), make_collection("C"))
        lab.select(lab.element_path("A"))
        lab.act("structure.paste_text")
        on_property = typed["places"]
        lab.select(lab.element_path("C"))
        lab.act("structure.paste_text")

        assert on_property == ["below", "above"]
        assert typed["places"] == ["below", "above", "into"]

    def test_a_pending_cut_is_not_taken_by_a_paste_from_text(
        self, pasting, typed
    ) -> None:
        lab = pasting(make_property("A"), make_property("B"))
        lab.select(lab.element_path("A"))
        lab.cut()
        lab.select(lab.element_path("B"))
        typed["value"] = (dump_objects([make_property("A")]), "below")

        lab.act("structure.paste_text")

        assert lab.view.treeClipboard.cut
        assert _ids(lab.submodel.submodel_element) == ["B", "A"]

    def test_it_is_off_in_read_mode(self, pasting, typed) -> None:
        lab = pasting(make_property("A"))
        lab.select(lab.element_path("A"))
        edit_mode().set_editing(False)
        lab.view.updateActions(lab.view.currentIndex())

        assert not lab.enabled("structure.paste_text")


def test_the_existing_paste_into_a_submodel_gives_the_copy_a_free_name(
    pasting,
) -> None:
    from aas_workingbench.dialogs import EditObjDialog

    lab = pasting(make_property("P"))
    lab.select(lab.element_path("P"))
    lab.copy()
    lab.select(SUBMODEL)
    lab.view.setCurrentIndex(lab.shown.index(*SUBMODEL))

    with answering(
        lab.monkeypatch,
        EditObjDialog,
        lambda dialog: None,
        lab.shown.shown_errors,
    ):
        lab.view.onPaste()

    assert _ids(lab.submodel.submodel_element) == ["P", "P_1"]


class TestBetweenPackages:
    def _two_packages(
        self, pasting, concept_for_source, concept_in_target=None
    ):
        element = model.Property(
            id_short="Temp",
            value_type=model.datatypes.String,
            semantic_id=make_external_reference("urn:cd:temp"),
        )
        lab = pasting(element, make_property("Plain"))
        lab.package.add(concept_for_source)
        target = make_submodel(id_="urn:target", id_short="Target")
        objects = [target]
        if concept_in_target is not None:
            objects.append(concept_in_target)
        other = lab.open_other(*objects)
        lab.view.expandAll()
        lab.select(lab.element_path("Temp"))
        lab.copy()
        lab.select(("submodels", "Target"), package=1)
        return lab, other, target

    def _concept(self, category: str | None = None) -> model.ConceptDescription:
        return model.ConceptDescription(
            id_="urn:cd:temp", id_short="Temp", category=category
        )

    def test_asking_to_copy_adds_the_concept_description(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", lambda *a: True)
        lab, other, target = self._two_packages(pasting, self._concept())

        lab.act("structure.paste_into")

        assert _ids(target.submodel_element) == ["Temp"]
        assert [c.id for c in other.concept_descriptions] == ["urn:cd:temp"]
        lab.shown.view.setCurrentIndex(lab.shown.index("shells", package=1))
        lab.view.onUndo()
        assert list(other.concept_descriptions) == []

    def test_several_copied_elements_bring_their_concept_descriptions(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", lambda *a: True)
        lab, other, target = self._two_packages(pasting, self._concept())
        lab.select(lab.element_path("Temp"), lab.element_path("Plain"))
        lab.copy()
        lab.select(("submodels", "Target"), package=1)

        lab.act("structure.paste_into")

        assert _ids(target.submodel_element) == ["Temp", "Plain"]
        assert [c.id for c in other.concept_descriptions] == ["urn:cd:temp"]

    def test_declining_pastes_the_element_alone(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(
            paste_dialogs, "ask_copy_concepts", lambda *a: False
        )
        lab, other, target = self._two_packages(pasting, self._concept())

        lab.act("structure.paste_into")

        assert _ids(target.submodel_element) == ["Temp"]
        assert list(other.concept_descriptions) == []

    def test_cancelling_pastes_nothing(self, pasting, monkeypatch) -> None:
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", lambda *a: None)
        lab, other, target = self._two_packages(pasting, self._concept())

        lab.act("structure.paste_into")

        assert _ids(target.submodel_element) == []
        assert list(other.concept_descriptions) == []

    def test_an_identical_description_is_reused_without_a_question(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.ui import paste_dialogs

        def fail(*args: object) -> bool:
            raise AssertionError("Nothing should be asked")

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", fail)
        lab, other, target = self._two_packages(
            pasting, self._concept(), self._concept()
        )

        lab.act("structure.paste_into")

        assert _ids(target.submodel_element) == ["Temp"]
        assert len(list(other.concept_descriptions)) == 1

    def test_a_different_description_asks_and_can_be_added_as_new(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.application.operations.companions import (
            ConceptChoice,
        )
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", lambda *a: True)
        monkeypatch.setattr(
            paste_dialogs,
            "ask_concept_conflict",
            lambda *a: ConceptChoice.ADD_WITH_NEW_ID,
        )
        lab, other, target = self._two_packages(
            pasting, self._concept("VALUE"), self._concept("PROPERTY")
        )

        lab.act("structure.paste_into")

        concepts = {c.id: c for c in other.concept_descriptions}
        pasted = target.get_referable("Temp")
        new_id = pasted.semantic_id.key[0].value  # type: ignore[attr-defined]
        assert len(concepts) == 2
        assert new_id != "urn:cd:temp"
        assert concepts[new_id].category == "VALUE"
        assert concepts["urn:cd:temp"].category == "PROPERTY"

    def test_a_different_description_can_stay_as_the_target_has_it(
        self, pasting, monkeypatch
    ) -> None:
        from aas_workingbench.application.operations.companions import (
            ConceptChoice,
        )
        from aas_workingbench.ui import paste_dialogs

        monkeypatch.setattr(paste_dialogs, "ask_copy_concepts", lambda *a: True)
        monkeypatch.setattr(
            paste_dialogs,
            "ask_concept_conflict",
            lambda *a: ConceptChoice.KEEP_EXISTING,
        )
        lab, other, target = self._two_packages(
            pasting, self._concept("VALUE"), self._concept("PROPERTY")
        )

        lab.act("structure.paste_into")

        pasted = target.get_referable("Temp")
        assert pasted.semantic_id.key[0].value == "urn:cd:temp"  # type: ignore[attr-defined]
        assert len(list(other.concept_descriptions)) == 1


def test_copying_several_elements_puts_their_json_on_the_clipboard(
    pasting,
) -> None:
    from aas_workingbench.domain.clipboard_json import load_objects

    lab = pasting(*(make_property(n) for n in "ABC"))
    lab.select(lab.element_path("A"), lab.element_path("B"))

    lab.copy()

    text = QApplication.clipboard().text()
    assert [o.id_short for o in load_objects(text)] == ["A", "B"]
