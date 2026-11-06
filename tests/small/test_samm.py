"""Recognizing a concept description that carries a SAMM element (F-EDT-05 AC18)."""

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_samm_concept
from tests.factories import samm_type_urn

from aas_editor.domain.samm import attribute_order
from aas_editor.domain.samm import is_samm
from aas_editor.domain.samm import samm_element_of
from aas_editor.domain.samm import samm_elements_of
from aas_editor.domain.samm import samm_links


class TestRecognition:
    @pytest.mark.parametrize(
        ("type_name", "version"),
        [
            ("Aspect", "2.1.0"),
            ("Property", "2.0.0"),
            ("Aspect", "1.0.0"),
            ("Trait", "2.1.0"),
            ("RangeConstraint", "1.0.0"),
            ("Unit", "2.0.0"),
        ],
    )
    def test_the_urn_of_a_known_type_and_version_is_recognized(
        self, type_name: str, version: str
    ) -> None:
        element = samm_element_of(
            make_samm_concept("urn:cd", type_name, version=version)
        )

        assert element is not None
        assert (element.type_name, element.version) == (type_name, version)

    def test_a_description_without_extension_is_no_samm(self) -> None:
        assert not is_samm(make_concept_description())

    @pytest.mark.parametrize(
        "urn",
        [
            # A version that the original does not know.
            "urn:samm:org.eclipse.esmf.samm:meta-model:2.2.0#Aspect",
            # The prefix and the version do not go together.
            "urn:bamm:io.openmanufacturing:meta-model:2.1.0#Aspect",
            "urn:samm:org.eclipse.esmf.samm:meta-model:1.0.0#Aspect",
            # A type that is not a SAMM element, or in the wrong namespace.
            "urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#Operation",
            "urn:samm:org.eclipse.esmf.samm:meta-model:2.1.0#Trait",
            "https://example.com/samm#Aspect",
        ],
    )
    def test_other_urns_are_no_samm(self, urn: str) -> None:
        concept = model.ConceptDescription(
            "urn:cd",
            extension=[
                model.Extension(
                    "x",
                    semantic_id=make_external_reference(urn),
                    value_type=model.datatypes.String,
                    value="{}",
                )
            ],
        )

        assert not is_samm(concept)

    def test_an_extension_with_two_keys_is_no_samm(self) -> None:
        reference = model.ExternalReference(
            (
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:other"),
                model.Key(
                    model.KeyTypes.GLOBAL_REFERENCE, samm_type_urn("Aspect")
                ),
            )
        )
        concept = model.ConceptDescription(
            "urn:cd", extension=[model.Extension("x", semantic_id=reference)]
        )

        assert not is_samm(concept)

    def test_every_samm_extension_is_listed_in_order(self) -> None:
        concept = make_samm_concept("urn:cd", "Property")
        concept.extension.add(
            model.Extension(
                "other-name",
                semantic_id=make_external_reference(samm_type_urn("Entity")),
            )
        )

        names = [e.type_name for e in samm_elements_of(concept)]

        assert names == ["Property", "Entity"]


class TestLinks:
    def test_an_aspect_points_at_its_properties(self) -> None:
        concept = make_samm_concept(
            "urn:a",
            "Aspect",
            '{"Properties": [{"Value": "urn:p1"}, '
            '{"Value": "urn:p2", "Optional": true}]}',
        )

        element = samm_element_of(concept)
        assert element is not None
        assert samm_links(element) == ("urn:p1", "urn:p2")

    def test_a_property_points_at_its_characteristic(self) -> None:
        concept = make_samm_concept(
            "urn:p", "Property", '{"Characteristic": {"Value": "urn:c"}}'
        )

        element = samm_element_of(concept)
        assert element is not None
        assert samm_links(element) == ("urn:c",)

    def test_a_trait_points_at_its_base_and_its_constraints(self) -> None:
        concept = make_samm_concept(
            "urn:t",
            "Trait",
            '{"BaseCharacteristic": {"Value": "urn:b"}, '
            '"Constraint": [{"Value": "urn:k1"}, {"Value": "urn:k2"}]}',
        )

        element = samm_element_of(concept)
        assert element is not None
        assert samm_links(element) == ("urn:b", "urn:k1", "urn:k2")

    def test_another_characteristic_points_at_its_data_type(self) -> None:
        concept = make_samm_concept(
            "urn:c", "Measurement", '{"DataType": {"Value": "xsd:float"}}'
        )

        element = samm_element_of(concept)
        assert element is not None
        assert samm_links(element) == ("xsd:float",)

    @pytest.mark.parametrize("value", [None, "", "not json", "[1, 2]", "{}"])
    def test_a_value_without_links_gives_none_and_raises_nothing(
        self, value: str | None
    ) -> None:
        element = samm_element_of(make_samm_concept("urn:a", "Aspect", value))

        assert element is not None
        assert samm_links(element) == ()

    def test_a_constraint_points_at_nothing(self) -> None:
        concept = make_samm_concept(
            "urn:k", "RangeConstraint", '{"DataType": {"Value": "urn:x"}}'
        )

        element = samm_element_of(concept)
        assert element is not None
        assert samm_links(element) == ()


class TestAttributeOrder:
    USUAL = ["id_short", "display_name", "description", "administration", "id"]

    def test_identifiable_comes_before_referable_for_a_samm_description(
        self,
    ) -> None:
        concept = make_samm_concept("urn:cd")

        assert attribute_order(concept, self.USUAL) == [
            "id",
            "administration",
            "id_short",
            "display_name",
            "description",
        ]

    def test_another_description_keeps_the_usual_order(self) -> None:
        assert (
            attribute_order(make_concept_description(), self.USUAL)
            == self.USUAL
        )

    def test_an_object_that_is_no_description_keeps_the_usual_order(
        self,
    ) -> None:
        assert (
            attribute_order(model.Submodel("urn:s"), self.USUAL) == self.USUAL
        )
