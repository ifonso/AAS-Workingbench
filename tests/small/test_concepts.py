"""Concept descriptions: new ones from semantic ids, matching, and order."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel

from aas_editor.domain.concept_order import ConceptOrder
from aas_editor.domain.concept_order import first_use_ranks
from aas_editor.domain.concept_order import sort_key
from aas_editor.domain.concepts import concept_for_pair
from aas_editor.domain.concepts import concept_reference
from aas_editor.domain.concepts import concepts_by_id_short
from aas_editor.domain.concepts import empty_concepts
from aas_editor.domain.concepts import holders_of
from aas_editor.domain.concepts import is_empty_concept
from aas_editor.domain.concepts import new_concept_for
from aas_editor.domain.data_specifications import TemplateMatch
from aas_editor.domain.data_specifications import iec_content_of
from aas_editor.domain.data_specifications import match_template


def _with_semantics(
    prop: model.Property, concept_id: str | None
) -> model.Property:
    if concept_id is not None:
        prop.semantic_id = make_external_reference(concept_id)
    return prop


def _content(
    concept: model.ConceptDescription,
) -> model.DataSpecificationIEC61360:
    (record,) = concept.embedded_data_specifications
    content = iec_content_of(record)
    assert content is not None
    return content


class TestHolders:
    def test_holders_cover_the_selection_and_everything_below(self) -> None:
        inner = make_property("Inner")
        outer = make_collection("Outer", [inner])
        submodel = make_submodel(elements=[outer, make_property("Other")])

        names = [h.owner.id_short for h in holders_of([submodel])]

        assert names == ["Submodel", "Outer", "Inner", "Other"]

    def test_without_below_only_the_selection_counts(self) -> None:
        outer = make_collection("Outer", [make_property("Inner")])

        assert [h.owner.id_short for h in holders_of([outer], below=False)] == [
            "Outer"
        ]

    def test_an_element_selected_twice_counts_once(self) -> None:
        inner = make_property("Inner")
        outer = make_collection("Outer", [inner])

        assert len(holders_of([outer, inner])) == 2

    def test_items_of_a_list_have_no_id_short(self) -> None:
        item = model.Property(None, model.datatypes.String)
        holder_list = make_list("List", [item])

        holders = holders_of([holder_list])

        assert [h.id_short for h in holders] == ["List", None]

    def test_annotations_and_entity_statements_are_found(self) -> None:
        annotated = model.AnnotatedRelationshipElement(
            "Annotated",
            first=make_external_reference("a"),
            second=make_external_reference("b"),
            annotation=[make_property("Note")],
        )
        entity = model.Entity(
            "Entity",
            model.EntityType.CO_MANAGED_ENTITY,
            statement=[make_property("Statement")],
        )

        names = {h.owner.id_short for h in holders_of([annotated, entity])}

        assert {"Note", "Statement"} <= names


class TestNewConcept:
    def test_the_id_is_the_first_key_and_the_names_come_from_the_element(
        self,
    ) -> None:
        prop = _with_semantics(make_property("MaxSpeed"), "0173-1#02-AAA#001")
        prop.description = model.MultiLanguageTextType({"en": "How fast"})
        (holder,) = holders_of([prop], below=False)

        concept = new_concept_for(holder, adaptive=False)

        assert concept.id == "0173-1#02-AAA#001"
        assert concept.id_short == "MaxSpeed"
        assert dict(concept.description or {}) == {"en": "How fast"}
        assert concept.embedded_data_specifications == []

    def test_the_first_key_of_several_is_the_id(self) -> None:
        prop = make_property("P")
        prop.semantic_id = model.ExternalReference(
            (
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "first"),
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "second"),
            )
        )
        (holder,) = holders_of([prop], below=False)

        assert new_concept_for(holder, adaptive=False).id == "first"

    def test_adaptive_gets_an_iec_record_with_name_and_definition(self) -> None:
        prop = _with_semantics(make_property("MaxSpeed"), "urn:cd:speed")
        prop.description = model.MultiLanguageTextType({"en": "How fast"})
        (holder,) = holders_of([prop], below=False)

        concept = new_concept_for(holder, adaptive=True)

        (record,) = concept.embedded_data_specifications
        assert (
            match_template(record.data_specification) is TemplateMatch.CURRENT
        )
        content = _content(concept)
        assert dict(content.preferred_name) == {"en": "MaxSpeed"}
        assert dict(content.definition or {}) == {"en": "How fast"}

    def test_the_display_name_is_the_preferred_name(self) -> None:
        prop = _with_semantics(make_property("MaxSpeed"), "urn:cd:speed")
        prop.display_name = model.MultiLanguageNameType(
            {"en": "Maximum speed", "de": "Höchstgeschwindigkeit"}
        )
        (holder,) = holders_of([prop], below=False)

        content = _content(new_concept_for(holder, adaptive=True))

        assert dict(content.preferred_name) == {
            "en": "Maximum speed",
            "de": "Höchstgeschwindigkeit",
        }

    def test_an_item_of_a_list_is_named_by_its_semantic_id(self) -> None:
        item = model.Property(
            None,
            model.datatypes.String,
            semantic_id=make_external_reference("urn:cd:item"),
        )
        make_list("List", [item])
        (holder,) = holders_of([item], below=False)

        concept = new_concept_for(holder, adaptive=True)

        assert concept.id_short is None
        assert dict(_content(concept).preferred_name) == {"en": "urn:cd:item"}

    @pytest.mark.parametrize(
        ("value_type", "expected"),
        [
            (model.datatypes.String, model.DataTypeIEC61360.STRING),
            (model.datatypes.Boolean, model.DataTypeIEC61360.BOOLEAN),
            (model.datatypes.Date, model.DataTypeIEC61360.DATE),
            (model.datatypes.DateTime, model.DataTypeIEC61360.TIMESTAMP),
            (model.datatypes.Int, None),
            (model.datatypes.Double, None),
        ],
    )
    def test_the_data_type_follows_the_value_type_only_where_it_is_clear(
        self, value_type: type, expected: model.DataTypeIEC61360 | None
    ) -> None:
        prop = model.Property(
            "P",
            value_type,
            semantic_id=make_external_reference("urn:cd:p"),
        )
        (holder,) = holders_of([prop], below=False)

        assert _content(new_concept_for(holder, True)).data_type is expected

    def test_a_multi_language_property_is_translatable(self) -> None:
        prop = model.MultiLanguageProperty(
            "Text", semantic_id=make_external_reference("urn:cd:text")
        )
        (holder,) = holders_of([prop], below=False)

        assert _content(new_concept_for(holder, True)).data_type is (
            model.DataTypeIEC61360.STRING_TRANSLATABLE
        )

    def test_a_holder_without_semantic_id_is_refused(self) -> None:
        (holder,) = holders_of([make_property("P")], below=False)

        with pytest.raises(ValueError, match="no semantic id"):
            new_concept_for(holder, adaptive=False)

    def test_the_new_description_does_not_share_texts_with_the_element(
        self,
    ) -> None:
        prop = _with_semantics(make_property("P"), "urn:cd:p")
        prop.description = model.MultiLanguageTextType({"en": "text"})
        (holder,) = holders_of([prop], below=False)

        concept = new_concept_for(holder, adaptive=False)
        concept.description["de"] = "Text"  # type: ignore[index]

        assert dict(prop.description) == {"en": "text"}


class TestConceptReference:
    def test_it_is_an_external_reference_with_a_global_key(self) -> None:
        concept = model.ConceptDescription("urn:cd:1")

        reference = concept_reference(concept)

        assert isinstance(reference, model.ExternalReference)
        assert [(k.type, k.value) for k in reference.key] == [
            (model.KeyTypes.GLOBAL_REFERENCE, "urn:cd:1")
        ]


class TestMatchByIdShort:
    def _concepts(self) -> list[model.ConceptDescription]:
        return [
            model.ConceptDescription("urn:cd:1", id_short="Speed"),
            model.ConceptDescription("urn:cd:2", id_short="speed"),
            model.ConceptDescription("urn:cd:3", id_short="Weight"),
            model.ConceptDescription("urn:cd:4"),
        ]

    def test_an_exact_match_wins_over_one_that_differs_in_case(self) -> None:
        found = concepts_by_id_short(self._concepts(), "Speed")

        assert [c.id for c in found] == ["urn:cd:1"]

    def test_a_match_that_differs_in_case_is_used_if_nothing_is_exact(
        self,
    ) -> None:
        found = concepts_by_id_short(self._concepts(), "WEIGHT")

        assert [c.id for c in found] == ["urn:cd:3"]

    def test_nothing_matches_an_unknown_name(self) -> None:
        assert concepts_by_id_short(self._concepts(), "Colour") == []

    def test_other_objects_and_unnamed_descriptions_are_ignored(self) -> None:
        objects = [*self._concepts(), make_submodel(id_short="Colour")]

        assert concepts_by_id_short(objects, "Colour") == []


class TestEmptyConcepts:
    def test_a_concept_with_nothing_but_an_id_is_empty(self) -> None:
        assert is_empty_concept(model.ConceptDescription("urn:cd:1"))

    def test_names_and_descriptions_do_not_define_a_concept(self) -> None:
        concept = model.ConceptDescription(
            "urn:cd:1",
            id_short="Name",
            description=model.MultiLanguageTextType({"en": "text"}),
        )

        assert is_empty_concept(concept)

    def test_a_record_a_case_of_or_an_extension_makes_it_not_empty(
        self,
    ) -> None:
        with_record = model.ConceptDescription(
            "urn:cd:1",
            embedded_data_specifications=[
                model.EmbeddedDataSpecification(
                    make_external_reference("k"),
                    model.DataSpecificationIEC61360(
                        model.PreferredNameTypeIEC61360({"en": "n"})
                    ),
                )
            ],
        )
        with_case_of = model.ConceptDescription(
            "urn:cd:2", is_case_of={make_external_reference("x")}
        )
        with_extension = model.ConceptDescription(
            "urn:cd:3", extension=[model.Extension("samm")]
        )

        assert not any(
            is_empty_concept(c)
            for c in (with_record, with_case_of, with_extension)
        )

    def test_the_empty_ones_of_a_package_come_in_a_stable_order(self) -> None:
        store = make_store(
            model.ConceptDescription("urn:cd:b"),
            model.ConceptDescription("urn:cd:a", id_short="Zed"),
            model.ConceptDescription("urn:cd:c"),
            make_submodel(),
        )

        assert [c.id for c in empty_concepts(store)] == [
            "urn:cd:b",
            "urn:cd:c",
            "urn:cd:a",
        ]


class TestConceptForPair:
    def _pair(
        self, value: str, id_: str = "urn:cd:red"
    ) -> model.ValueReferencePair:
        return model.ValueReferencePair(value, make_external_reference(id_))

    def test_a_pair_becomes_a_description_with_an_iec_record(self) -> None:
        concept = concept_for_pair(self._pair("Red"))

        assert concept.id == "urn:cd:red"
        assert concept.id_short == "Red"
        assert dict(concept.display_name or {}) == {"en": "Red"}
        content = _content(concept)
        assert dict(content.preferred_name) == {"en": "Red"}
        assert dict(content.short_name or {}) == {"en": "Red"}
        assert dict(content.definition or {}) == {"en": "Red"}
        assert content.data_type is model.DataTypeIEC61360.STRING_TRANSLATABLE

    def test_a_long_value_is_shortened_to_what_the_sdk_allows(self) -> None:
        concept = concept_for_pair(self._pair("v" * 2000))

        content = _content(concept)
        assert content.short_name is None
        assert len(content.preferred_name["en"]) == 255
        assert len((content.definition or {})["en"]) == 1023
        assert len((concept.display_name or {})["en"]) == 128

    def test_a_value_that_is_no_idshort_is_repaired(self) -> None:
        assert concept_for_pair(self._pair("dark red (RAL 3003)")).id_short == (
            "Dark_red_RAL_3003"
        )

    def test_a_pair_without_value_id_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no value id"):
            concept_for_pair(model.ValueReferencePair("Red"))


class TestOrder:
    def _concepts(self) -> list[model.ConceptDescription]:
        return [
            model.ConceptDescription("urn:cd:5", id_short="zeta"),
            model.ConceptDescription("urn:cd:3", id_short="Alpha"),
            model.ConceptDescription("urn:cd:1"),
            model.ConceptDescription("urn:cd:2"),
            model.ConceptDescription("urn:cd:4", id_short="beta"),
        ]

    def _ids(self, order: ConceptOrder, ranks: dict[str, int] | None = None):
        return [
            c.id
            for c in sorted(
                self._concepts(), key=lambda c: sort_key(order, c, ranks)
            )
        ]

    def test_name_ignores_case_and_breaks_ties_by_id(self) -> None:
        # The tree shows "ConceptDescription" for a description without an
        # idShort, and a capital C sorts before the lowercase names.
        assert self._ids(ConceptOrder.NAME) == [
            "urn:cd:3",
            "urn:cd:4",
            "urn:cd:1",
            "urn:cd:2",
            "urn:cd:5",
        ]

    def test_name_is_the_same_whatever_the_order_of_the_input(self) -> None:
        forward = self._ids(ConceptOrder.NAME)
        backwards = self._concepts()
        backwards.reverse()
        reverse = [
            c.id
            for c in sorted(
                backwards, key=lambda c: sort_key(ConceptOrder.NAME, c)
            )
        ]

        assert forward == reverse

    def test_id_short_puts_descriptions_without_one_last(self) -> None:
        assert self._ids(ConceptOrder.ID_SHORT) == [
            "urn:cd:3",
            "urn:cd:4",
            "urn:cd:5",
            "urn:cd:1",
            "urn:cd:2",
        ]

    def test_id_sorts_by_the_id(self) -> None:
        assert self._ids(ConceptOrder.ID) == [
            "urn:cd:1",
            "urn:cd:2",
            "urn:cd:3",
            "urn:cd:4",
            "urn:cd:5",
        ]

    def test_first_use_lists_used_descriptions_by_rank_then_the_rest(
        self,
    ) -> None:
        ranks = {"urn:cd:4": 0, "urn:cd:5": 1}

        assert self._ids(ConceptOrder.FIRST_USE, ranks) == [
            "urn:cd:4",
            "urn:cd:5",
            "urn:cd:3",
            "urn:cd:1",
            "urn:cd:2",
        ]

    def test_every_order_has_a_label(self) -> None:
        assert all(order.label for order in ConceptOrder)


class TestFirstUse:
    def test_ranks_follow_the_submodels_by_name_and_their_saved_order(
        self,
    ) -> None:
        first = make_submodel(
            "urn:sm:b",
            "Bravo",
            [
                _with_semantics(make_property("One"), "urn:cd:c"),
                make_collection(
                    "Group", [_with_semantics(make_property("Two"), "urn:cd:a")]
                ),
            ],
        )
        second = make_submodel(
            "urn:sm:a",
            "Alpha",
            [_with_semantics(make_property("Three"), "urn:cd:b")],
        )
        store = make_store(
            first,
            second,
            model.ConceptDescription("urn:cd:a"),
            model.ConceptDescription("urn:cd:b"),
            model.ConceptDescription("urn:cd:c"),
            model.ConceptDescription("urn:cd:unused"),
        )

        ranks = first_use_ranks(store)

        # Alpha comes first, then Bravo with its elements in saved order.
        assert ranks == {"urn:cd:b": 0, "urn:cd:c": 1, "urn:cd:a": 2}

    def test_a_semantic_id_without_a_description_has_no_rank(self) -> None:
        submodel = make_submodel(
            elements=[_with_semantics(make_property("P"), "urn:cd:missing")]
        )

        assert first_use_ranks(make_store(submodel)) == {}
