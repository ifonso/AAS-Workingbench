"""The view orders of concept descriptions (F-EDT-05 AC10, AC12)."""

from basyx.aas import model
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_samm_concept
from tests.factories import make_store
from tests.factories import make_submodel

from aas_editor.domain.concept_order import CANNOT_SORT
from aas_editor.domain.concept_order import ConceptOrder
from aas_editor.domain.concept_order import can_sort_permanently
from aas_editor.domain.concept_order import ranks_for
from aas_editor.domain.concept_order import sort_key


def _used(prop: model.Property, concept_id: str) -> model.Property:
    prop.semantic_id = make_external_reference(concept_id)
    return prop


def _listed(
    order: ConceptOrder, store: model.SetIdentifiableStore
) -> list[str]:
    concepts = [o for o in store if isinstance(o, model.ConceptDescription)]
    ranks = ranks_for(order, store)
    return [
        c.id for c in sorted(concepts, key=lambda c: sort_key(order, c, ranks))
    ]


class TestListIndex:
    def test_the_view_lists_the_descriptions_in_the_order_of_the_store(
        self,
    ) -> None:
        store = make_store(
            make_concept_description("urn:cd:zebra", "Zebra"),
            make_concept_description("urn:cd:apple", "Apple"),
            make_concept_description("urn:cd:mango", "Mango"),
        )

        assert _listed(ConceptOrder.LIST_INDEX, store) == [
            "urn:cd:zebra",
            "urn:cd:apple",
            "urn:cd:mango",
        ]

    def test_the_name_order_is_another_order_than_the_list_index(self) -> None:
        store = make_store(
            make_concept_description("urn:cd:zebra", "Zebra"),
            make_concept_description("urn:cd:apple", "Apple"),
        )

        assert _listed(ConceptOrder.NAME, store) == [
            "urn:cd:apple",
            "urn:cd:zebra",
        ]
        assert _listed(ConceptOrder.LIST_INDEX, store) == [
            "urn:cd:zebra",
            "urn:cd:apple",
        ]

    def test_a_description_added_later_comes_last(self) -> None:
        store = make_store(
            make_concept_description("urn:cd:b", "B"),
            make_concept_description("urn:cd:c", "C"),
        )
        ranks = ranks_for(ConceptOrder.LIST_INDEX, store)
        late = make_concept_description("urn:cd:a", "A")

        keys = sorted(
            [
                *(o for o in store if isinstance(o, model.ConceptDescription)),
                late,
            ],
            key=lambda c: sort_key(ConceptOrder.LIST_INDEX, c, ranks),
        )

        assert [c.id for c in keys] == ["urn:cd:b", "urn:cd:c", "urn:cd:a"]


class TestByElements:
    def _store(self) -> model.SetIdentifiableStore:
        submodel = make_submodel("urn:sm", "Sm")
        submodel.semantic_id = make_external_reference("urn:cd:only-submodel")
        submodel.submodel_element.add(
            make_collection(
                "Group",
                [
                    _used(make_property("One"), "urn:cd:second"),
                    _used(make_property("Two"), "urn:cd:first"),
                ],
            )
        )
        return make_store(
            submodel,
            make_concept_description("urn:cd:first", "First"),
            make_concept_description("urn:cd:second", "Second"),
            make_concept_description("urn:cd:only-submodel", "OnlySubmodel"),
            make_concept_description("urn:cd:unused", "Unused"),
        )

    def test_descriptions_of_elements_come_first_in_the_saved_order(
        self,
    ) -> None:
        assert _listed(ConceptOrder.BY_ELEMENTS, self._store())[:2] == [
            "urn:cd:second",
            "urn:cd:first",
        ]

    def test_a_description_that_only_the_submodel_uses_is_not_by_elements(
        self,
    ) -> None:
        listed = _listed(ConceptOrder.BY_ELEMENTS, self._store())

        # Not referenced by an element, so it is listed with the rest by name.
        assert listed[2:] == ["urn:cd:only-submodel", "urn:cd:unused"]

    def test_the_first_use_order_counts_the_semantic_id_of_the_submodel(
        self,
    ) -> None:
        listed = _listed(ConceptOrder.FIRST_USE, self._store())

        assert listed[0] == "urn:cd:only-submodel"


class TestStructured:
    def _store(self) -> model.SetIdentifiableStore:
        submodel = make_submodel("urn:sm", "Sm")
        submodel.submodel_element.add(
            _used(make_property("P"), "urn:cd:used-by-submodel")
        )
        return make_store(
            submodel,
            make_concept_description("urn:cd:zzz-other", "ZzzOther"),
            make_concept_description("urn:cd:used-by-submodel", "UsedBySm"),
            make_samm_concept(
                "urn:samm:characteristic",
                "Measurement",
                '{"DataType": {"Value": "urn:samm:float"}}',
                "Char",
            ),
            make_samm_concept(
                "urn:samm:property",
                "Property",
                '{"Characteristic": {"Value": "urn:samm:characteristic"}}',
                "Prop",
            ),
            make_samm_concept(
                "urn:samm:aspect",
                "Aspect",
                '{"Properties": [{"Value": "urn:samm:property"}]}',
                "Asp",
            ),
            make_samm_concept("urn:samm:orphan", "Property", "{}", "Orphan"),
        )

    def test_the_aspect_comes_first_with_what_it_reaches_below_it(self) -> None:
        listed = _listed(ConceptOrder.STRUCTURED, self._store())

        assert listed[:3] == [
            "urn:samm:aspect",
            "urn:samm:property",
            "urn:samm:characteristic",
        ]

    def test_descriptions_of_submodels_come_before_the_rest(self) -> None:
        listed = _listed(ConceptOrder.STRUCTURED, self._store())

        assert listed[3] == "urn:cd:used-by-submodel"

    def test_a_samm_description_that_no_aspect_reaches_is_in_the_rest(
        self,
    ) -> None:
        listed = _listed(ConceptOrder.STRUCTURED, self._store())

        assert listed[4:] == ["urn:samm:orphan", "urn:cd:zzz-other"]

    def test_a_cycle_between_elements_ends(self) -> None:
        store = make_store(
            make_samm_concept(
                "urn:a",
                "Entity",
                '{"Properties": [{"Value": "urn:b"}]}',
                "A",
            ),
            make_samm_concept(
                "urn:aspect",
                "Aspect",
                '{"Properties": [{"Value": "urn:a"}]}',
                "Asp",
            ),
            make_samm_concept(
                "urn:b",
                "Property",
                '{"Characteristic": {"Value": "urn:a"}}',
                "B",
            ),
        )

        assert _listed(ConceptOrder.STRUCTURED, store) == [
            "urn:aspect",
            "urn:a",
            "urn:b",
        ]


class TestPermanentSort:
    def test_the_three_orders_of_the_original_that_it_refuses_are_refused(
        self,
    ) -> None:
        assert not can_sort_permanently(ConceptOrder.LIST_INDEX)
        assert not can_sort_permanently(ConceptOrder.BY_ELEMENTS)
        assert not can_sort_permanently(ConceptOrder.STRUCTURED)

    def test_the_orders_that_name_one_place_for_each_description_sort(
        self,
    ) -> None:
        assert can_sort_permanently(ConceptOrder.ID_SHORT)
        assert can_sort_permanently(ConceptOrder.ID)
        assert can_sort_permanently(ConceptOrder.FIRST_USE)

    def test_the_message_says_that_nothing_was_sorted(self) -> None:
        assert CANNOT_SORT == (
            "The file cannot keep this order, so nothing was sorted"
        )

    def test_every_order_has_a_label(self) -> None:
        assert all(order.label for order in ConceptOrder)
        assert len({order.label for order in ConceptOrder}) == len(ConceptOrder)
