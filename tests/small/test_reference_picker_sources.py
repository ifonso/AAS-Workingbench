"""Listing the targets of several packages (F-EDT-11 AC1)."""

from basyx.aas import model
from tests.factories import make_concept_description
from tests.factories import make_property
from tests.factories import make_submodel

from aas_workingbench.domain.reference_picker import PickerSource
from aas_workingbench.domain.reference_picker import candidates
from aas_workingbench.domain.reference_picker import candidates_in


def _sources() -> list[PickerSource]:
    first = PickerSource(
        "first.aasx",
        (
            make_submodel("urn:sm:1", "One", [make_property("Speed")]),
            make_concept_description("urn:cd:1", "ConceptOne"),
        ),
    )
    second = PickerSource(
        "second.aasx", (make_concept_description("urn:cd:2", "ConceptTwo"),)
    )
    return [first, second]


def test_the_candidates_of_each_package_follow_in_turn() -> None:
    found = candidates_in(_sources(), (model.ConceptDescription,))

    assert [(c.package, c.label) for c in found] == [
        ("first.aasx", "ConceptOne"),
        ("second.aasx", "ConceptTwo"),
    ]


def test_only_concept_descriptions_are_leaves_when_the_filter_says_so() -> None:
    found = candidates_in(_sources(), (model.ConceptDescription,))

    assert {c.kind for c in found} == {"ConceptDescription"}


def test_the_text_filters_every_package() -> None:
    found = candidates_in(_sources(), text="two")

    assert [c.label for c in found] == ["ConceptTwo"]


def test_a_candidate_of_a_single_package_has_no_package_name() -> None:
    (found,) = candidates(
        [make_concept_description("urn:cd:1", "ConceptOne")],
        (model.ConceptDescription,),
    )

    assert found.package == ""


def test_the_target_of_a_candidate_is_the_object_of_its_package() -> None:
    sources = _sources()

    found = candidates_in(sources, (model.ConceptDescription,))

    assert found[1].target is sources[1].objects[0]
