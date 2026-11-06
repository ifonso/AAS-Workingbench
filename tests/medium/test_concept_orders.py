"""The six view orders and the permanent sort of concept descriptions.

F-EDT-05 AC10 (the tree lists the descriptions as each order says, and the
package is not changed), AC11 (a permanent sort writes the order, and the view
goes back to the list index) and AC12 (an order that cannot sort says so and
changes nothing).
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_samm_concept
from tests.factories import make_submodel
from tests.serialization import snapshot

from aas_editor.domain.concept_order import ConceptOrder

CONCEPTS = "concept_descriptions"


def _concept(id_: str, id_short: str) -> model.ConceptDescription:
    return model.ConceptDescription(id_, id_short=id_short)


def _prop(id_short: str, semantic: str) -> model.Property:
    prop = make_property(id_short)
    prop.semantic_id = make_external_reference(semantic)
    return prop


@pytest.fixture
def lab(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from aas_editor.package import Package
    from aas_editor.settings.app_settings import OBJECT_ROLE
    from aas_editor.ui import concept_actions
    from aas_editor.ui import concept_dialogs
    from aas_editor.ui import reference_dialogs
    from aas_editor.ui.concept_actions import register_concept_actions

    register_concept_actions()

    class Lab:
        def __init__(self, *objects: model.Identifiable) -> None:
            self.shown = views()
            self.view = self.shown.view
            self.package = self.shown.open_package(*objects)
            self.stack = self.package.commandStack
            self.messages: list[str] = []
            self.previews: list[list[list[str]]] = []
            self.confirm = True
            monkeypatch.setattr(
                reference_dialogs,
                "show_message",
                lambda title, text, parent=None: self.messages.append(text),
            )

            def confirm_preview(*args: Any, **kwargs: Any) -> bool:
                self.previews.append([list(row) for row in args[3]])
                return self.confirm

            monkeypatch.setattr(
                concept_dialogs, "confirm_preview", confirm_preview
            )
            self.shown.select(self.shown.index(CONCEPTS))
            self.view.updateActions(self.view.currentIndex())

        def choose(self, order: ConceptOrder) -> None:
            monkeypatch.setattr(
                concept_actions,
                "ask_concept_order",
                lambda current, parent=None: order,
            )
            self.view.registeredActions.find("concepts.order").trigger()

        def sort(self) -> None:
            self.view.registeredActions.find("concepts.sort").trigger()

        def listed(self) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(CONCEPTS)
            return [
                proxy.index(row, 0, parent).data(OBJECT_ROLE).id
                for row in range(proxy.rowCount(parent))
            ]

        def stored(self) -> list[str]:
            return [
                o.id
                for o in self.package.objStore
                if isinstance(o, model.ConceptDescription)
            ]

        def saved_order(self) -> list[str]:
            path = tmp_path / "saved.aasx"
            self.package.write(path)
            return [
                o.id
                for o in Package(path).objStore
                if isinstance(o, model.ConceptDescription)
            ]

    return Lab


def _plain(lab_class) -> Any:
    submodel = make_submodel(
        elements=[
            _prop("First", "urn:cd:c"),
            make_collection("Group", [_prop("Second", "urn:cd:a")]),
        ]
    )
    return lab_class(
        submodel,
        _concept("urn:cd:c", "Charlie"),
        _concept("urn:cd:z", "zulu"),
        _concept("urn:cd:a", "alpha"),
        _concept("urn:cd:b", "Bravo"),
    )


class TestOrders:
    def test_the_list_index_lists_the_descriptions_as_the_file_does(
        self, lab
    ) -> None:
        lab = _plain(lab)

        lab.choose(ConceptOrder.LIST_INDEX)

        assert lab.listed() == ["urn:cd:c", "urn:cd:z", "urn:cd:a", "urn:cd:b"]

    def test_by_default_the_names_are_listed_without_regard_to_case(
        self, lab
    ) -> None:
        assert _plain(lab).listed() == [
            "urn:cd:a",
            "urn:cd:b",
            "urn:cd:c",
            "urn:cd:z",
        ]

    def test_by_submodel_elements_lists_the_used_descriptions_first(
        self, lab
    ) -> None:
        lab = _plain(lab)

        lab.choose(ConceptOrder.BY_ELEMENTS)

        assert lab.listed()[:2] == ["urn:cd:c", "urn:cd:a"]

    def test_structured_lists_an_aspect_with_what_it_reaches_first(
        self, lab
    ) -> None:
        lab = lab(
            _concept("urn:cd:plain", "Aaa"),
            make_samm_concept(
                "urn:samm:property",
                "Property",
                '{"Characteristic": {"Value": "urn:samm:measure"}}',
                "Zeta",
            ),
            make_samm_concept(
                "urn:samm:measure", "Measurement", "{}", "Yankee"
            ),
            make_samm_concept(
                "urn:samm:aspect",
                "Aspect",
                '{"Properties": [{"Value": "urn:samm:property"}]}',
                "Xray",
            ),
        )

        lab.choose(ConceptOrder.STRUCTURED)

        assert lab.listed() == [
            "urn:samm:aspect",
            "urn:samm:property",
            "urn:samm:measure",
            "urn:cd:plain",
        ]

    @pytest.mark.parametrize("order", list(ConceptOrder))
    def test_no_order_changes_the_package(
        self, lab, order: ConceptOrder
    ) -> None:
        lab = _plain(lab)
        before = snapshot(lab.package.objStore)
        stored = lab.stored()

        lab.choose(order)

        assert lab.stored() == stored
        assert snapshot(lab.package.objStore) == before
        assert not lab.stack.can_undo


class TestSort:
    def test_sorting_by_id_short_writes_the_order_and_goes_back_to_the_list_index(
        self, lab
    ) -> None:
        lab = _plain(lab)
        lab.choose(ConceptOrder.ID_SHORT)

        lab.sort()

        expected = ["urn:cd:a", "urn:cd:b", "urn:cd:c", "urn:cd:z"]
        assert lab.stored() == expected
        assert lab.view.model().conceptOrder() is ConceptOrder.LIST_INDEX
        assert lab.listed() == expected
        assert lab.saved_order() == expected

    def test_the_question_lists_the_new_order(self, lab) -> None:
        lab = _plain(lab)
        lab.choose(ConceptOrder.ID)

        lab.sort()

        assert [row[2] for row in lab.previews[0]] == [
            "urn:cd:a",
            "urn:cd:b",
            "urn:cd:c",
            "urn:cd:z",
        ]

    def test_one_undo_gives_the_old_order_of_the_file_back(self, lab) -> None:
        lab = _plain(lab)
        lab.choose(ConceptOrder.ID)
        lab.sort()

        lab.stack.undo()

        assert lab.stored() == ["urn:cd:c", "urn:cd:z", "urn:cd:a", "urn:cd:b"]
        assert lab.stack.is_clean

    def test_declining_the_question_changes_nothing(self, lab) -> None:
        lab = _plain(lab)
        lab.choose(ConceptOrder.ID)
        lab.confirm = False

        lab.sort()

        assert lab.stored() == ["urn:cd:c", "urn:cd:z", "urn:cd:a", "urn:cd:b"]
        assert not lab.stack.can_undo

    @pytest.mark.parametrize(
        "order",
        [
            ConceptOrder.LIST_INDEX,
            ConceptOrder.BY_ELEMENTS,
            ConceptOrder.STRUCTURED,
        ],
    )
    def test_an_order_that_cannot_sort_gives_the_message_and_changes_nothing(
        self, lab, order: ConceptOrder
    ) -> None:
        lab = _plain(lab)
        lab.choose(order)
        before = lab.stored()

        lab.sort()

        assert lab.messages == ["Cannot apply selected sort order!"]
        assert lab.stored() == before
        assert lab.previews == []
        assert not lab.stack.can_undo

    def test_a_file_that_has_the_order_already_says_so(self, lab) -> None:
        lab = lab(_concept("urn:cd:a", "Alpha"), _concept("urn:cd:b", "Beta"))
        lab.choose(ConceptOrder.ID)

        lab.sort()

        assert "already" in lab.messages[0]
        assert not lab.stack.can_undo

    def test_it_is_refused_in_read_mode(self, lab) -> None:
        from aas_editor.application.editing import edit_mode

        lab = _plain(lab)
        lab.choose(ConceptOrder.ID)
        edit_mode().set_editing(False)
        try:
            lab.view.updateActions(lab.view.currentIndex())
            enabled = lab.view.registeredActions.find(
                "concepts.sort"
            ).isEnabled()
        finally:
            edit_mode().set_editing(True)

        assert not enabled
