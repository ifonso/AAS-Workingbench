"""What the detail reads for texts in languages and for semantics (3.4-3.7)."""

from basyx.aas import model
import pytest
from tests.factories import make_concept_description
from tests.factories import make_external_reference

from aas_workingbench.domain.detail_values import LanguageText
from aas_workingbench.domain.detail_values import concept_label
from aas_workingbench.domain.detail_values import concept_unit
from aas_workingbench.domain.detail_values import language_badge
from aas_workingbench.domain.detail_values import preferred_text
from aas_workingbench.domain.detail_values import semantic_link

CYCLE_ID = "https://example.com/ids/concept/CycleTimeTarget"


def _cycle_concept() -> model.ConceptDescription:
    concept = make_concept_description(CYCLE_ID, "CycleTimeTarget")
    content = model.DataSpecificationIEC61360(
        preferred_name=model.PreferredNameTypeIEC61360(
            {"en": "Target cycle time", "de": "Ziel-Zykluszeit"}
        ),
        unit="s",
    )
    concept.embedded_data_specifications.append(
        model.EmbeddedDataSpecification(
            data_specification=make_external_reference(
                "https://admin-shell.io/DataSpecificationTemplates/"
                "DataSpecificationIEC61360/3/0"
            ),
            data_specification_content=content,
        )
    )
    return concept


def test_the_first_preferred_language_is_shown_with_the_count_of_others() -> (
    None
):
    texts = {"en": "Cycle time", "de": "Zykluszeit", "pt": "Tempo de ciclo"}

    shown = preferred_text(texts, ["de"])

    assert shown == LanguageText("Zykluszeit", "de", 2)
    assert language_badge(shown) == "de +2"


def test_english_is_read_when_the_preferred_language_has_no_text() -> None:
    shown = preferred_text({"de": "Zykluszeit", "en": "Cycle time"}, ["fr"])

    assert shown is not None
    assert shown.text == "Cycle time"


def test_a_region_of_the_preferred_language_is_taken() -> None:
    shown = preferred_text({"en-US": "Color", "de": "Farbe"}, ["en"])

    assert shown is not None
    assert shown.language == "en-US"


def test_the_first_language_is_read_when_neither_has_a_text() -> None:
    shown = preferred_text({"ja": "サイクル", "ko": "주기"}, ["fr"])

    assert shown is not None
    assert (shown.text, shown.language) == ("サイクル", "ja")


def test_a_value_without_text_shows_nothing() -> None:
    assert preferred_text({}, ["en"]) is None
    assert preferred_text({"en": ""}, ["en"]) is None


def test_one_language_is_named_without_a_count() -> None:
    assert language_badge(LanguageText("Speed", "en", 0)) == "en"


@pytest.mark.parametrize(
    ("languages", "label"),
    [(["en"], "Target cycle time"), (["de"], "Ziel-Zykluszeit")],
)
def test_a_concept_is_named_by_its_preferred_name(
    languages: list[str], label: str
) -> None:
    assert concept_label(_cycle_concept(), languages) == label


def test_a_concept_without_a_record_is_named_by_its_id_short() -> None:
    concept = make_concept_description(CYCLE_ID, "CycleTimeTarget")

    assert concept_label(concept, ["en"]) == "CycleTimeTarget"


def test_the_unit_comes_from_the_record_of_the_concept() -> None:
    assert concept_unit(_cycle_concept()) == "s"
    assert concept_unit(make_concept_description()) == ""


def test_a_semantic_id_links_to_the_concept_of_the_package() -> None:
    concept = _cycle_concept()

    link = semantic_link([concept], make_external_reference(CYCLE_ID), ["en"])

    assert link is not None
    assert link.concept is concept
    assert (link.label, link.address, link.unit) == (
        "Target cycle time",
        CYCLE_ID,
        "s",
    )
    assert link.source == "CycleTimeTarget"


def test_a_semantic_id_outside_of_the_package_has_no_link() -> None:
    link = semantic_link(
        [_cycle_concept()], make_external_reference("urn:other"), ["en"]
    )

    assert link is None
    assert semantic_link([], None, ["en"]) is None
