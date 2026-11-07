"""Converting an element to another type through the context menu action."""

from collections.abc import Callable
import io
from itertools import permutations
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_blob
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_external_reference
from tests.factories import make_file_element
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_operation
from tests.factories import make_property
from tests.medium.conftest import ELEMENT_ID
from tests.medium.conftest import ELEMENT_PATH
from tests.medium.conftest import SUBMODEL_PATH
from tests.serialization import snapshot

from aas_workingbench.domain.replacement import ReplacementPlan

CONVERT = "conversion.convert"
STRING = model.datatypes.String
# A text that becomes the path of a File must not be a path into the package.
DOCUMENT_URL = "https://example.com/doc.pdf"


def _event() -> model.BasicEventElement:
    return model.BasicEventElement(
        ELEMENT_ID,
        model.ModelReference(
            (model.Key(model.KeyTypes.SUBMODEL, "urn:example:observed"),),
            model.Submodel,
        ),
        model.Direction.OUTPUT,
        model.StateOfEvent.ON,
        message_topic="topic/one",
    )


def _relationship(
    cls: type[model.RelationshipElement],
) -> model.RelationshipElement:
    return cls(
        ELEMENT_ID,
        make_external_reference("urn:example:first"),
        make_external_reference("urn:example:second"),
    )


# One filled element of each type, named like the element that tests convert.
SOURCES: dict[str, Callable[[], model.SubmodelElement]] = {
    "Property": lambda: make_property(ELEMENT_ID, DOCUMENT_URL),
    "Range": lambda: model.Range(ELEMENT_ID, STRING, DOCUMENT_URL, "z"),
    "MultiLanguageProperty": lambda: make_multi_language_property(
        ELEMENT_ID, {"en": DOCUMENT_URL, "de": "Hallo"}
    ),
    "File": lambda: make_file_element(ELEMENT_ID, "/aasx/files/sheet.pdf"),
    "Blob": lambda: make_blob(ELEMENT_ID, DOCUMENT_URL.encode(), "text/plain"),
    "ReferenceElement": lambda: model.ReferenceElement(
        ELEMENT_ID, make_external_reference("urn:example:target")
    ),
    "RelationshipElement": lambda: _relationship(model.RelationshipElement),
    "AnnotatedRelationshipElement": lambda: model.AnnotatedRelationshipElement(
        ELEMENT_ID,
        make_external_reference("urn:example:first"),
        make_external_reference("urn:example:second"),
        annotation=[model.Property("Note", STRING, "n")],
    ),
    "SubmodelElementCollection": lambda: make_collection(
        ELEMENT_ID, [make_property("A", "1"), make_property("B", "2")]
    ),
    "SubmodelElementList": lambda: make_list(
        ELEMENT_ID,
        [model.Property(None, STRING, "x"), model.Property(None, STRING, "y")],
    ),
    "Entity": lambda: make_entity(ELEMENT_ID, [make_property("S", "1")]),
    "Operation": lambda: make_operation(
        ELEMENT_ID,
        [make_property("In", "1")],
        [make_property("Out", "2")],
    ),
    "Capability": lambda: model.Capability(ELEMENT_ID),
    "BasicEventElement": _event,
}
TARGETS: dict[str, type[model.SubmodelElement]] = {
    name: getattr(model, name)
    for name in SOURCES
    if name != "BasicEventElement"
}

VALUES = ["Property", "Range", "MultiLanguageProperty", "File", "Blob"]
REFERENCES = [
    "ReferenceElement",
    "RelationshipElement",
    "AnnotatedRelationshipElement",
]
CONTAINERS = [
    "SubmodelElementCollection",
    "SubmodelElementList",
    "Entity",
    "Operation",
]
PAIRS = [
    *permutations(VALUES, 2),
    *permutations(REFERENCES, 2),
    *permutations(CONTAINERS, 2),
    *[(name, "Capability") for name in [*VALUES, *REFERENCES, *CONTAINERS]],
    *[("Capability", name) for name in [*VALUES, *REFERENCES, *CONTAINERS]],
    ("BasicEventElement", "Capability"),
    ("BasicEventElement", "Property"),
    ("Property", "Entity"),
    ("Entity", "File"),
    ("ReferenceElement", "Blob"),
    ("SubmodelElementList", "Range"),
]


class Conversions:
    """Runs the action on the element of a lab, with the dialogs stubbed."""

    def __init__(self, lab: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        from aas_workingbench.ui import replacement_dialogs

        self.lab = lab
        self.asked: list[ReplacementPlan] = []
        self.answer = True
        self.messages: list[str] = []
        self.target: type[model.SubmodelElement] | None = None
        self.copy_file = False

        def choose(element: object, targets: object, parent: object) -> Any:
            return self.target

        def confirm(
            title: str,
            intro: str,
            plan: ReplacementPlan,
            updates: object,
            accept_text: str,
            parent: object = None,
        ) -> bool:
            self.asked.append(plan)
            return self.answer

        def use_content(path: str, size: int, parent: object = None) -> bool:
            return self.copy_file

        monkeypatch.setattr(replacement_dialogs, "choose_target", choose)
        monkeypatch.setattr(replacement_dialogs, "confirm_replacement", confirm)
        monkeypatch.setattr(
            replacement_dialogs, "ask_use_file_content", use_content
        )
        from aas_workingbench.ui import reference_dialogs

        monkeypatch.setattr(
            reference_dialogs,
            "show_message",
            lambda title, text, parent=None: self.messages.append(text),
        )

    def run(self, target: type[model.SubmodelElement], *path: str) -> None:
        self.target = target
        shown = self.lab.shown
        index = shown.index(*(path or ELEMENT_PATH))
        shown.select(index)
        shown.view.updateActions(index)
        shown.view.registeredActions.find(CONVERT).trigger()


@pytest.fixture
def registered(qapp: object) -> None:
    from aas_workingbench.ui.conversion_actions import (
        register_conversion_actions,
    )

    register_conversion_actions()


def _lab(lab_class: Any, source: str) -> Any:
    return lab_class(
        make_property("Before"), SOURCES[source](), make_property("After")
    )


@pytest.mark.parametrize(
    ("source", "target"),
    PAIRS,
    ids=[f"{source}-to-{target}" for source, target in PAIRS],
)
def test_a_conversion_can_be_undone_redone_saved_and_reloaded(
    lab_class: Any,
    registered: None,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    target: str,
) -> None:
    lab = _lab(lab_class, source)
    conversions = Conversions(lab, monkeypatch)
    before = snapshot(lab.package.objStore)

    conversions.run(TARGETS[target])
    converted = snapshot(lab.package.objStore)
    element_after = lab.submodel.get_referable(ELEMENT_ID)
    lab.stack.undo()
    undone = snapshot(lab.package.objStore)
    element_undone = lab.submodel.get_referable(ELEMENT_ID)
    lab.stack.redo()
    redone = snapshot(lab.package.objStore)
    reloaded = lab.save_and_reload()

    assert type(element_after) is TARGETS[target]
    assert type(element_undone).__name__ == source
    assert undone == before
    assert redone == converted
    assert reloaded == converted
    assert [e.id_short for e in lab.submodel.submodel_element] == [
        "Before",
        ELEMENT_ID,
        "After",
    ]
    assert not lab.stack.can_redo


def test_the_new_element_is_the_current_row(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    lab = _lab(lab_class, "Property")
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.Range)

    current = lab.shown.view.currentIndex().data(OBJECT_ROLE)
    assert current is lab.submodel.get_referable(ELEMENT_ID)
    assert isinstance(current, model.Range)


def test_a_conversion_without_a_loss_asks_nothing(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "Property")
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.Range)

    assert conversions.asked == []
    assert isinstance(lab.element(), model.Range)


def test_a_conversion_with_a_loss_shows_it_and_waits_for_the_answer(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "Range")
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.Property)

    assert [
        [str(loss) for loss in plan.losses] for plan in conversions.asked
    ] == [["maximum: 'z'"]]
    assert isinstance(lab.element(), model.Property)


def test_declining_the_loss_changes_nothing(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "Range")
    conversions = Conversions(lab, monkeypatch)
    conversions.answer = False
    before = snapshot(lab.package.objStore)

    conversions.run(model.Property)

    assert snapshot(lab.package.objStore) == before
    assert not lab.stack.can_undo
    assert isinstance(lab.element(), model.Range)


def test_cancelling_the_choice_of_a_type_changes_nothing(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "Property")
    conversions = Conversions(lab, monkeypatch)

    conversions.run(None)  # type: ignore[arg-type]

    assert not lab.stack.can_undo
    assert conversions.asked == []


def test_converting_a_container_names_the_items_it_cannot_keep(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = lab_class(
        make_collection(
            ELEMENT_ID,
            [make_property("A"), make_file_element("B"), make_property("C")],
        )
    )
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.SubmodelElementList, *ELEMENT_PATH)

    shown = [str(loss) for loss in conversions.asked[0].losses]
    assert any("B (File)" in line for line in shown)
    assert [item.value for item in lab.element().value] == [  # type: ignore[attr-defined]
        "text",
        "text",
    ]


def test_an_item_of_a_list_cannot_be_converted(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = lab_class(make_list(ELEMENT_ID, [model.Property(None, STRING, "x")]))
    conversions = Conversions(lab, monkeypatch)
    item_list = lab.element()
    list_index = lab.shown.index(*ELEMENT_PATH)
    first = lab.shown.view.model().index(0, 0, list_index)
    before = snapshot(lab.package.objStore)
    conversions.target = model.Range
    lab.shown.select(first)
    lab.shown.view.updateActions(first)

    lab.shown.view.registeredActions.find(CONVERT).trigger()

    assert "AASd-108" in conversions.messages[0]
    assert snapshot(lab.package.objStore) == before
    assert item_list is lab.element()


def test_the_action_is_off_in_read_mode_and_for_what_is_no_element(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.application.editing import edit_mode

    lab = _lab(lab_class, "Property")
    Conversions(lab, monkeypatch)
    shown = lab.shown
    action = shown.view.registeredActions.find(CONVERT)

    shown.select(shown.index("submodels", "Submodel"))
    shown.view.updateActions(shown.index("submodels", "Submodel"))
    on_submodel = action.isEnabled()
    shown.select(shown.index(*ELEMENT_PATH))
    shown.view.updateActions(shown.index(*ELEMENT_PATH))
    on_element = action.isEnabled()
    edit_mode().set_editing(False)
    shown.view.updateActions(shown.index(*ELEMENT_PATH))
    in_read_mode = action.isEnabled()

    assert (on_submodel, on_element, in_read_mode) == (False, True, False)


def test_a_file_becomes_a_blob_with_the_content_of_the_stored_file(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "File")
    lab.package.fileStore.add_file(
        "/aasx/files/sheet.pdf", io.BytesIO(b"%PDF content"), "application/pdf"
    )
    conversions = Conversions(lab, monkeypatch)
    conversions.copy_file = True

    conversions.run(model.Blob)
    copied = lab.element().value
    lab.stack.undo()
    lab.stack.redo()
    redone = lab.element().value

    assert copied == b"%PDF content"
    assert redone == b"%PDF content"
    assert [str(loss) for loss in conversions.asked[0].losses] == [
        "path: '/aasx/files/sheet.pdf'"
    ]


def test_a_file_becomes_a_blob_with_its_path_when_the_content_is_declined(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "File")
    lab.package.fileStore.add_file(
        "/aasx/files/sheet.pdf", io.BytesIO(b"%PDF content"), "application/pdf"
    )
    conversions = Conversions(lab, monkeypatch)
    conversions.copy_file = False

    conversions.run(model.Blob)

    assert lab.element().value == b"/aasx/files/sheet.pdf"
    assert conversions.asked == []


def test_references_to_the_element_follow_and_one_undo_restores_them(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = _lab(lab_class, "Property")
    pointer = model.ReferenceElement(
        "Pointer", model.ModelReference.from_referable(lab.element())
    )
    lab.submodel.submodel_element.add(pointer)
    before = snapshot(lab.package.objStore)
    conversions = Conversions(lab, monkeypatch)

    conversions.run(model.Range)
    resolved = pointer.value.resolve(lab.package.objStore)  # type: ignore[union-attr]
    lab.stack.undo()
    restored = pointer.value.resolve(lab.package.objStore)  # type: ignore[union-attr]

    assert isinstance(resolved, model.Range)
    assert isinstance(restored, model.Property)
    assert snapshot(lab.package.objStore) == before


def test_references_into_lost_items_are_shown_before_they_dangle(
    lab_class: Any, registered: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = lab_class(make_collection(ELEMENT_ID, [make_property("A")]))
    pointer = model.ReferenceElement(
        "Pointer",
        model.ModelReference.from_referable(lab.element().get_referable("A")),
    )
    lab.submodel.submodel_element.add(pointer)
    shown_updates: list[Any] = []
    from aas_workingbench.ui import replacement_dialogs

    def confirm(title, intro, plan, updates, accept_text, parent=None) -> bool:
        shown_updates.append(updates)
        return False

    monkeypatch.setattr(replacement_dialogs, "confirm_replacement", confirm)
    conversions = Conversions(lab, monkeypatch)
    monkeypatch.setattr(replacement_dialogs, "confirm_replacement", confirm)

    conversions.run(model.Capability, *ELEMENT_PATH)

    assert len(shown_updates[0].orphaned) == 1
    assert isinstance(lab.element(), model.SubmodelElementCollection)


def test_the_tab_of_the_old_element_closes_and_other_tabs_stay(
    lab_class: Any,
    registered: None,
    monkeypatch: pytest.MonkeyPatch,
    qtbot: Any,
) -> None:
    pytest.importorskip("PyQt6.QtWebEngineWidgets")
    from aas_workingbench.widgets.tab import TabWidget

    lab = _lab(lab_class, "Property")
    conversions = Conversions(lab, monkeypatch)
    tab_widget = TabWidget(unclosable=True)
    qtbot.addWidget(tab_widget)
    tab_widget.addTab(tab_widget.tabCls(parent=tab_widget), "Welcome")
    tab_widget.openItemInNewTab(lab.shown.index(*ELEMENT_PATH))
    tab_widget.openItemInNewTab(lab.shown.index(*SUBMODEL_PATH, "After"))
    titles_before = [tab_widget.tabText(i) for i in range(tab_widget.count())]

    conversions.run(model.Range)
    qtbot.wait(5)

    titles_after = [tab_widget.tabText(i) for i in range(tab_widget.count())]
    assert ELEMENT_ID in titles_before
    assert ELEMENT_ID not in titles_after
    assert "After" in titles_after
