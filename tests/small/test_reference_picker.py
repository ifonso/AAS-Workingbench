"""Tests for the rules behind the reference picker (F-EDT-11)."""

from typing import Any

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_list
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_workingbench.domain.reference_picker import ANYTHING
from aas_workingbench.domain.reference_picker import ReferenceState
from aas_workingbench.domain.reference_picker import ReferenceTargetError
from aas_workingbench.domain.reference_picker import candidates
from aas_workingbench.domain.reference_picker import class_for_key_type
from aas_workingbench.domain.reference_picker import explain
from aas_workingbench.domain.reference_picker import key_type_of
from aas_workingbench.domain.reference_picker import reference_to
from aas_workingbench.domain.reference_picker import rule_for_hint
from aas_workingbench.domain.reference_picker import status_of
from aas_workingbench.domain.references import ReferenceIndex

K = model.KeyTypes


def _objects() -> tuple[Any, ...]:
    pump = make_property("Pump")
    inner = make_collection("Inner", [make_property("Deep")])
    items = make_list("Items", [make_property("ignored")])
    submodel = make_submodel(elements=[pump, inner, items])
    shell = make_shell(submodels=[submodel])
    concept = make_concept_description()
    return shell, submodel, concept, pump, inner


class TestRuleForHint:
    def test_reference_accepts_both_kinds_and_any_target(self) -> None:
        rule = rule_for_hint(model.Reference)

        assert rule.allows_model and rule.allows_external
        assert rule.targets == ANYTHING

    def test_external_reference_accepts_only_external(self) -> None:
        rule = rule_for_hint(model.ExternalReference)

        assert rule.allows_external and not rule.allows_model

    def test_model_reference_of_submodel_limits_the_targets(self) -> None:
        rule = rule_for_hint(model.ModelReference[model.Submodel])

        assert rule.allows_model and not rule.allows_external
        assert rule.targets == (model.Submodel,)

    def test_model_reference_of_a_union_keeps_each_class(self) -> None:
        hint: Any = model.ModelReference[
            model.AssetAdministrationShell | model.Submodel
        ]

        assert set(rule_for_hint(hint).targets) == {
            model.AssetAdministrationShell,
            model.Submodel,
        }

    def test_bare_model_reference_accepts_any_target(self) -> None:
        assert rule_for_hint(model.ModelReference).targets == ANYTHING

    def test_filters_for_submodel_reference_offer_submodels_only(self) -> None:
        names = [
            f.name
            for f in rule_for_hint(
                model.ModelReference[model.Submodel]
            ).filters()
        ]

        assert names == ["Anything", "Submodels"]


class TestCandidates:
    def test_lists_identifiables_and_elements_in_document_order(self) -> None:
        shell, submodel, concept, *_ = _objects()

        found = candidates([shell, submodel, concept])

        assert [c.label for c in found] == [
            "Shell",
            "Submodel",
            "Pump",
            "Inner",
            "Inner/Deep",
            "Items",
            "Items/0",
            "Concept",
        ]

    def test_filter_by_class_keeps_only_that_target_type(self) -> None:
        objects = _objects()[:3]

        found = candidates(objects, (model.ConceptDescription,))

        assert [c.target for c in found] == [objects[2]]

    def test_filter_by_submodel_element_skips_identifiables(self) -> None:
        shell, submodel, concept, *_ = _objects()

        found = candidates([shell, submodel, concept], (model.SubmodelElement,))

        assert all(isinstance(c.target, model.SubmodelElement) for c in found)
        assert len(found) == 5

    def test_text_search_matches_path_class_and_id(self) -> None:
        objects = _objects()[:3]

        assert [c.label for c in candidates(objects, text="deep")] == [
            "Inner/Deep"
        ]
        assert [c.kind for c in candidates(objects, text="conceptdescr")] == [
            "ConceptDescription"
        ]
        assert [c.label for c in candidates(objects, text=objects[1].id)] == [
            "Submodel"
        ]

    def test_an_element_names_the_identifiable_it_belongs_to(self) -> None:
        shell, submodel, *_ = _objects()

        (found,) = candidates([shell, submodel], text="pump")

        assert "Submodel" in found.owner


class TestReferenceTo:
    def test_external_reference_to_a_concept_description_holds_its_id(
        self,
    ) -> None:
        concept = make_concept_description()

        reference = reference_to(concept, as_model=False)

        assert isinstance(reference, model.ExternalReference)
        assert reference.key == (model.Key(K.GLOBAL_REFERENCE, concept.id),)

    def test_model_reference_to_a_concept_description_keeps_the_key_type(
        self,
    ) -> None:
        concept = make_concept_description()

        reference = reference_to(concept, as_model=True)

        assert isinstance(reference, model.ModelReference)
        assert reference.key == (model.Key(K.CONCEPT_DESCRIPTION, concept.id),)

    def test_model_reference_to_an_element_goes_through_its_path(self) -> None:
        _, submodel, _, _, inner = _objects()
        deep = inner.get_referable("Deep")

        reference = reference_to(deep, as_model=True)

        assert [key.type for key in reference.key] == [
            K.SUBMODEL,
            K.SUBMODEL_ELEMENT_COLLECTION,
            K.PROPERTY,
        ]
        assert [key.value for key in reference.key] == [
            submodel.id,
            "Inner",
            "Deep",
        ]

    def test_external_reference_to_an_element_is_refused_with_advice(
        self,
    ) -> None:
        pump = _objects()[3]

        with pytest.raises(ReferenceTargetError, match="model reference"):
            reference_to(pump, as_model=False)

    def test_model_reference_to_a_detached_element_is_refused(self) -> None:
        with pytest.raises(ReferenceTargetError, match="not part of"):
            reference_to(make_property("Loose"), as_model=True)

    def test_a_list_item_is_referred_to_by_position(self) -> None:
        submodel = make_submodel(
            elements=[make_list("Items", [make_property("x")])]
        )
        item = submodel.get_referable("Items").value[0]

        reference = reference_to(item, as_model=True)

        assert [key.value for key in reference.key][-1] == "0"


class TestKeyTypes:
    def test_key_type_of_uses_the_class_of_the_object(self) -> None:
        assert key_type_of(make_property()) is K.PROPERTY
        assert key_type_of(make_concept_description()) is K.CONCEPT_DESCRIPTION

    def test_class_for_key_type_is_the_inverse(self) -> None:
        assert class_for_key_type(K.SUBMODEL) is model.Submodel
        assert class_for_key_type(K.GLOBAL_REFERENCE) is None


class TestStatus:
    def test_model_reference_to_an_element_resolves(self) -> None:
        shell, submodel, concept, pump, _ = _objects()
        index = ReferenceIndex([shell, submodel, concept])

        status = status_of(index, reference_to(pump, as_model=True))

        assert status.state is ReferenceState.RESOLVED
        assert status.target is pump
        assert not status.is_dangling

    def test_model_reference_to_an_unknown_id_is_dangling_with_the_reason(
        self,
    ) -> None:
        index = ReferenceIndex([make_submodel()])
        reference = model.ModelReference(
            (model.Key(K.SUBMODEL, "urn:missing"),), model.Submodel
        )

        status = status_of(index, reference)

        assert status.state is ReferenceState.DANGLING
        assert status.is_dangling
        assert "urn:missing" in status.text
        assert status.reached is None

    def test_a_missing_element_below_a_submodel_is_partial(self) -> None:
        submodel = make_submodel(elements=[make_collection("Inner")])
        index = ReferenceIndex([submodel])
        reference = model.ModelReference(
            (
                model.Key(K.SUBMODEL, submodel.id),
                model.Key(K.SUBMODEL_ELEMENT_COLLECTION, "Inner"),
                model.Key(K.PROPERTY, "Gone"),
            ),
            model.Property,
        )

        status = status_of(index, reference)

        assert status.state is ReferenceState.PARTIAL
        assert status.reached is submodel.get_referable("Inner")
        assert status.missing == ("Gone",)
        assert "Gone" in status.text

    def test_external_reference_to_an_id_of_the_package_resolves_to_it(
        self,
    ) -> None:
        concept = make_concept_description()
        index = ReferenceIndex([concept])

        status = status_of(index, reference_to(concept, as_model=False))

        assert status.state is ReferenceState.RESOLVED
        assert status.target is concept

    def test_external_reference_to_something_else_is_outside_not_dangling(
        self,
    ) -> None:
        index = ReferenceIndex([make_concept_description()])

        status = status_of(index, make_external_reference("urn:elsewhere"))

        assert status.state is ReferenceState.OUTSIDE
        assert not status.is_dangling

    def test_a_trailing_fragment_key_is_ignored(self) -> None:
        file_element = model.File(
            "Doc", "application/pdf", "/aasx/files/doc.pdf"
        )
        submodel = make_submodel(elements=[file_element])
        reference = model.ModelReference(
            (
                model.Key(K.SUBMODEL, submodel.id),
                model.Key(K.FILE, "Doc"),
                model.Key(K.FRAGMENT_REFERENCE, "page=2"),
            ),
            model.File,
        )

        status = status_of(ReferenceIndex([submodel]), reference)

        assert status.state is ReferenceState.RESOLVED
        assert status.target is file_element


class TestExplain:
    @pytest.mark.parametrize(
        ("keys", "rule"),
        [
            ([model.Key(K.SUBMODEL, "x")], "AASd-122"),
            (
                [
                    model.Key(K.GLOBAL_REFERENCE, "x"),
                    model.Key(K.PROPERTY, "y"),
                ],
                "AASd-124",
            ),
        ],
    )
    def test_the_sdk_refusal_of_an_external_reference_names_the_rule(
        self, keys: list[model.Key], rule: str
    ) -> None:
        with pytest.raises(model.AASConstraintViolation) as error:
            model.ExternalReference(tuple(keys))

        assert rule in explain(error.value)

    @pytest.mark.parametrize(
        ("keys", "rule"),
        [
            ([model.Key(K.PROPERTY, "x")], "AASd-123"),
            (
                [model.Key(K.SUBMODEL, "x"), model.Key(K.SUBMODEL, "y")],
                "AASd-125",
            ),
            (
                [
                    model.Key(K.SUBMODEL, "x"),
                    model.Key(K.SUBMODEL_ELEMENT_LIST, "l"),
                    model.Key(K.PROPERTY, "y"),
                ],
                "AASd-128",
            ),
            (
                [
                    model.Key(K.SUBMODEL, "x"),
                    model.Key(K.PROPERTY, "p"),
                    model.Key(K.FRAGMENT_REFERENCE, "f"),
                ],
                "AASd-127",
            ),
        ],
    )
    def test_the_sdk_refusal_of_a_model_reference_names_the_rule(
        self, keys: list[model.Key], rule: str
    ) -> None:
        with pytest.raises(model.AASConstraintViolation) as error:
            model.ModelReference(tuple(keys), model.Referable)

        assert rule in explain(error.value)
        assert "\n" not in explain(error.value)


class TestExplainEmptyReference:
    def test_a_reference_without_keys_says_what_to_do(self) -> None:
        with pytest.raises(ValueError) as error:
            model.ExternalReference(())

        text = explain(error.value)

        assert "at least one key" in text
        assert "choose the target" in text
