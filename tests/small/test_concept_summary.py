"""What the embedded display says about a concept description."""

from basyx.aas import model
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_samm_concept

from aas_editor.domain.concept_summary import MAX_PAIRS
from aas_editor.domain.concept_summary import NOT_FOUND
from aas_editor.domain.concept_summary import summarize
from aas_editor.domain.data_specifications import IEC_61360_TEMPLATE_KEY


def _record(**kwargs: object) -> model.EmbeddedDataSpecification:
    return model.EmbeddedDataSpecification(
        make_external_reference(IEC_61360_TEMPLATE_KEY),
        model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360({"en": "Max speed", "de": "Tempo"}),
            **kwargs,  # type: ignore[arg-type]
        ),
    )


def _rows(concept: model.ConceptDescription) -> dict[str, str]:
    return {row.label: row.text for row in summarize(concept).rows}


def test_the_title_is_the_id_short_and_the_headline_the_preferred_name() -> (
    None
):
    concept = make_concept_description("urn:cd:speed", "MaxSpeed")
    concept.embedded_data_specifications.append(_record())

    summary = summarize(concept)

    assert summary.title == "MaxSpeed"
    assert summary.concept_id == "urn:cd:speed"
    assert summary.headline == "en: Max speed"


def test_a_description_without_id_short_is_titled_by_its_id() -> None:
    concept = model.ConceptDescription("urn:cd:bare")

    assert summarize(concept).title == "urn:cd:bare"


def test_the_attributes_that_have_a_value_are_listed_and_the_others_are_not() -> (
    None
):
    concept = make_concept_description("urn:cd:x", "X")
    concept.embedded_data_specifications.append(
        _record(
            unit="m/s",
            symbol="v",
            data_type=model.DataTypeIEC61360.REAL_MEASURE,
        )
    )

    rows = _rows(concept)

    assert rows["Preferred name"] == "en: Max speed; de: Tempo"
    assert rows["Unit"] == "m/s"
    assert rows["Symbol"] == "v"
    assert rows["Data type"] == "REAL_MEASURE"
    assert "Definition" not in rows
    assert "Value format" not in rows


def test_the_value_list_names_the_first_pairs_and_counts_the_rest() -> None:
    pairs = {
        model.ValueReferencePair(f"V{n}", make_external_reference(f"urn:v:{n}"))
        for n in range(MAX_PAIRS + 2)
    }
    concept = make_concept_description("urn:cd:x", "X")
    concept.embedded_data_specifications.append(_record(value_list=pairs))

    text = _rows(concept)["Value list"]

    assert text.startswith(f"{MAX_PAIRS + 2} pairs: V0 = ")
    assert text.endswith("; and 2 more")


def test_a_description_without_record_says_so() -> None:
    rows = _rows(make_concept_description("urn:cd:x", "X"))

    assert rows == {"Data specification": "No IEC 61360 record"}


def test_a_second_record_is_counted_and_not_shown() -> None:
    concept = make_concept_description("urn:cd:x", "X")
    concept.embedded_data_specifications.append(_record())
    concept.embedded_data_specifications.append(_record(unit="kg"))

    rows = _rows(concept)

    assert "Unit" not in rows
    assert rows["More records"].startswith("1 further IEC 61360 record")


def test_is_case_of_is_listed() -> None:
    concept = make_concept_description("urn:cd:x", "X")
    concept.is_case_of.add(make_external_reference("0173-1#02-AAA#001"))

    assert "0173-1#02-AAA#001" in _rows(concept)["Is case of"]


def test_a_samm_element_is_named_with_its_version() -> None:
    concept = make_samm_concept("urn:samm:a", "Aspect", version="2.0.0")

    assert _rows(concept)["SAMM element"] == "Aspect (version 2.0.0)"


def test_the_notice_for_a_missing_description_is_the_text_of_the_original() -> (
    None
):
    assert (
        NOT_FOUND
        == "The package has no concept description that this semantic id names"
    )
