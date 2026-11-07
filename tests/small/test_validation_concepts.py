"""AASc-3a-004 to 007: the category limits the data type (Part 3a)."""

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_store

from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_workingbench.domain.validation import ALL_RULES
from aas_workingbench.domain.validation import Severity
from aas_workingbench.domain.validation import validate

T = model.DataTypeIEC61360


def _concept(
    category: str | None, *data_types: T | None
) -> model.ConceptDescription:
    """A description whose records have the given data types, in order."""
    concept = model.ConceptDescription(
        "urn:cd:x", id_short="X", category=category
    )
    for number, data_type in enumerate(data_types):
        concept.embedded_data_specifications.append(
            model.EmbeddedDataSpecification(
                make_external_reference(f"{IEC_61360_TEMPLATE_KEY}#{number}"),
                model.DataSpecificationIEC61360(
                    model.PreferredNameTypeIEC61360({"en": "Name"}),
                    data_type=data_type,
                ),
            )
        )
    return concept


def _ids(concept: model.ConceptDescription) -> list[str]:
    report = validate(make_store(concept))
    return [f.rule_id for f in report.findings if f.rule_id.startswith("AASc")]


class TestPropertyOrValue:
    @pytest.mark.parametrize("category", ["PROPERTY", "VALUE"])
    @pytest.mark.parametrize(
        "data_type",
        [
            T.DATE,
            T.STRING,
            T.STRING_TRANSLATABLE,
            T.INTEGER_MEASURE,
            T.INTEGER_COUNT,
            T.INTEGER_CURRENCY,
            T.REAL_MEASURE,
            T.REAL_COUNT,
            T.REAL_CURRENCY,
            T.BOOLEAN,
            T.RATIONAL,
            T.RATIONAL_MEASURE,
            T.TIME,
            T.TIMESTAMP,
        ],
    )
    def test_the_fourteen_types_of_the_group_pass(
        self, category: str, data_type: T
    ) -> None:
        assert _ids(_concept(category, data_type)) == []

    @pytest.mark.parametrize(
        "data_type", [T.FILE, T.BLOB, T.HTML, T.IRI, T.IRDI]
    )
    def test_a_type_of_another_group_is_reported(self, data_type: T) -> None:
        assert _ids(_concept("PROPERTY", data_type)) == ["AASc-3a-004"]

    def test_a_missing_data_type_is_reported(self) -> None:
        assert _ids(_concept("VALUE", None)) == ["AASc-3a-004"]

    def test_the_finding_names_the_category_and_the_type(self) -> None:
        concept = _concept("PROPERTY", T.FILE)

        (finding,) = validate(make_store(concept)).of_rule("AASc-3a-004")

        assert finding.severity is Severity.ERROR
        assert finding.anchor is concept
        assert finding.attribute == "data_type"
        assert "'PROPERTY'" in finding.message
        assert "The data type is FILE." in finding.message
        assert "INTEGER_MEASURE" in finding.message

    def test_a_missing_type_is_said_in_the_message(self) -> None:
        (finding,) = validate(make_store(_concept("VALUE", None))).of_rule(
            "AASc-3a-004"
        )

        assert "The data type is missing." in finding.message


class TestReference:
    @pytest.mark.parametrize("data_type", [T.STRING, T.IRI, T.IRDI])
    def test_string_iri_and_irdi_pass(self, data_type: T) -> None:
        assert _ids(_concept("REFERENCE", data_type)) == []

    @pytest.mark.parametrize("data_type", [T.INTEGER_COUNT, T.FILE, None])
    def test_other_types_and_none_are_reported(
        self, data_type: T | None
    ) -> None:
        assert _ids(_concept("REFERENCE", data_type)) == ["AASc-3a-005"]


class TestDocument:
    @pytest.mark.parametrize("data_type", [T.FILE, T.BLOB, T.HTML])
    def test_file_blob_and_html_pass(self, data_type: T) -> None:
        assert _ids(_concept("DOCUMENT", data_type)) == []

    @pytest.mark.parametrize("data_type", [T.STRING, T.IRI, None])
    def test_other_types_and_none_are_reported(
        self, data_type: T | None
    ) -> None:
        assert _ids(_concept("DOCUMENT", data_type)) == ["AASc-3a-006"]


class TestQualifierType:
    def test_any_data_type_passes(self) -> None:
        assert _ids(_concept("QUALIFIER_TYPE", T.INTEGER_COUNT)) == []

    def test_a_missing_data_type_is_reported(self) -> None:
        assert _ids(_concept("QUALIFIER_TYPE", None)) == ["AASc-3a-007"]


class TestWhatIsNotChecked:
    @pytest.mark.parametrize(
        "category", [None, "PARAMETER", "CONSTANT", "VARIABLE", "property"]
    )
    def test_another_category_or_none_is_never_reported(
        self, category: str | None
    ) -> None:
        assert _ids(_concept(category, None)) == []

    def test_a_description_without_a_record_is_never_reported(self) -> None:
        assert _ids(_concept("PROPERTY")) == []

    def test_every_record_counts_and_one_bad_one_is_reported(self) -> None:
        concept = _concept("PROPERTY", T.STRING, T.FILE)

        assert _ids(concept) == ["AASc-3a-004"]

    def test_the_rules_are_among_the_package_rules(self) -> None:
        listed = {rule.rule_id for rule in ALL_RULES}

        assert {
            "AASc-3a-004",
            "AASc-3a-005",
            "AASc-3a-006",
            "AASc-3a-007",
        } <= listed

    def test_a_package_without_descriptions_has_no_finding(self) -> None:
        assert _ids(_concept(None)) == []
