"""IEC 61360 drafts, the template key, and the constraints on the content."""

from basyx.aas import model
import pytest

from aas_workingbench.domain.data_specifications import DATA_TYPE_GROUPS
from aas_workingbench.domain.data_specifications import IEC_61360_TEMPLATE_KEY
from aas_workingbench.domain.data_specifications import DraftError
from aas_workingbench.domain.data_specifications import Iec61360Draft
from aas_workingbench.domain.data_specifications import TemplateMatch
from aas_workingbench.domain.data_specifications import advisories_of
from aas_workingbench.domain.data_specifications import build_content
from aas_workingbench.domain.data_specifications import build_record
from aas_workingbench.domain.data_specifications import check_draft
from aas_workingbench.domain.data_specifications import draft_of
from aas_workingbench.domain.data_specifications import empty_attributes
from aas_workingbench.domain.data_specifications import match_template
from aas_workingbench.domain.data_specifications import template_reference


def _external(value: str) -> model.ExternalReference:
    return model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, value),)
    )


def _draft(**kwargs: object) -> Iec61360Draft:
    draft = Iec61360Draft(preferred_name=[("en", "Speed")])
    for name, value in kwargs.items():
        setattr(draft, name, value)
    return draft


class TestTemplateKey:
    def test_the_template_reference_is_an_external_reference_with_one_key(
        self,
    ) -> None:
        reference = template_reference()

        assert isinstance(reference, model.ExternalReference)
        assert [(k.type, k.value) for k in reference.key] == [
            (model.KeyTypes.GLOBAL_REFERENCE, IEC_61360_TEMPLATE_KEY)
        ]

    def test_the_key_is_the_one_the_sdk_names_for_metamodel_v3_1(self) -> None:
        # The SDK documents the key in AASc-3a-050 of DataSpecificationContent.
        documentation = model.base.DataSpecificationContent.__doc__ or ""

        assert IEC_61360_TEMPLATE_KEY in documentation

    def test_the_current_key_matches(self) -> None:
        assert match_template(template_reference()) is TemplateMatch.CURRENT

    @pytest.mark.parametrize(
        "spelling",
        [
            "http://admin-shell.io/DataSpecificationTemplates/DataSpecificationIEC61360/3/0",
            "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3/0",
            "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3",
            "https://admin-shell.io/DataSpecificationTemplates/DataSpecificationIec61360/3/1",
        ],
    )
    def test_spellings_found_in_real_templates_are_recognized(
        self, spelling: str
    ) -> None:
        assert (
            match_template(_external(spelling)) is TemplateMatch.OTHER_SPELLING
        )

    @pytest.mark.parametrize(
        "value",
        [
            "0112/2///62683#ACE053#001",
            "https://admin-shell.io/DataSpecificationTemplates/Other/3/0",
        ],
    )
    def test_other_references_are_unknown(self, value: str) -> None:
        assert match_template(_external(value)) is TemplateMatch.UNKNOWN

    def test_a_model_reference_with_the_template_value_is_another_spelling(
        self,
    ) -> None:
        reference = model.ModelReference(
            (
                model.Key(
                    model.KeyTypes.CONCEPT_DESCRIPTION, IEC_61360_TEMPLATE_KEY
                ),
            ),
            model.ConceptDescription,
        )

        assert match_template(reference) is TemplateMatch.OTHER_SPELLING

    def test_two_keys_are_unknown(self) -> None:
        reference = model.ExternalReference(
            (
                model.Key(model.KeyTypes.GLOBAL_REFERENCE, "a"),
                model.Key(
                    model.KeyTypes.GLOBAL_REFERENCE, IEC_61360_TEMPLATE_KEY
                ),
            )
        )

        assert match_template(reference) is TemplateMatch.UNKNOWN


class TestDataTypes:
    def test_the_groups_offer_every_literal_of_the_sdk_once(self) -> None:
        offered = [t for _, types in DATA_TYPE_GROUPS for t in types]

        assert sorted(offered, key=lambda t: t.value) == sorted(
            model.DataTypeIEC61360, key=lambda t: t.value
        )


class TestCheckDraft:
    def test_a_name_in_one_language_is_enough(self) -> None:
        assert check_draft(_draft()).is_valid

    def test_a_draft_without_a_preferred_name_says_why(self) -> None:
        report = check_draft(Iec61360Draft(preferred_name=[("en", "")]))

        assert not report.is_valid
        assert "preferred name" in report.errors[0].lower()

    def test_text_with_no_language_is_refused(self) -> None:
        report = check_draft(_draft(preferred_name=[("", "Speed")]))

        assert any("no language" in e for e in report.errors)

    def test_a_malformed_language_tag_is_refused_with_its_reason(self) -> None:
        report = check_draft(_draft(preferred_name=[("en_US", "Speed")]))

        assert any("hyphen" in e for e in report.errors)

    def test_a_language_twice_is_refused(self) -> None:
        report = check_draft(_draft(preferred_name=[("en", "A"), ("EN", "B")]))

        assert any("twice" in e for e in report.errors)

    def test_a_short_name_over_18_characters_is_refused_with_the_count(
        self,
    ) -> None:
        report = check_draft(_draft(short_name=[("en", "x" * 19)]))

        assert any("19 characters" in e and "18" in e for e in report.errors)

    def test_the_preferred_name_may_have_255_characters_but_not_256(
        self,
    ) -> None:
        assert check_draft(_draft(preferred_name=[("en", "x" * 255)])).is_valid
        assert not check_draft(
            _draft(preferred_name=[("en", "x" * 256)])
        ).is_valid

    def test_a_definition_over_1023_characters_is_refused(self) -> None:
        report = check_draft(_draft(definition=[("en", "x" * 1024)]))

        assert any("1023" in e for e in report.errors)

    def test_a_value_over_2048_characters_is_refused(self) -> None:
        report = check_draft(_draft(value="x" * 2049))

        assert any("2048" in e for e in report.errors)

    def test_every_draft_the_check_accepts_is_accepted_by_the_sdk(self) -> None:
        draft = _draft(
            short_name=[("en", "x" * 18)],
            definition=[("en", "y" * 1023), ("de", "z")],
            value="v" * 2048,
        )

        assert check_draft(draft).is_valid
        build_content(draft)  # does not raise


class TestAdvisories:
    def test_a_measure_without_unit_and_unit_id_is_advised(self) -> None:
        report = check_draft(
            _draft(
                data_type=model.DataTypeIEC61360.REAL_MEASURE,
                definition=[("en", "d")],
            )
        )

        assert report.is_valid
        assert any("AASc-3a-009" in note for note in report.advisories)

    @pytest.mark.parametrize("field", ["unit", "unit_id"])
    def test_a_unit_or_a_unit_id_satisfies_the_measure_constraint(
        self, field: str
    ) -> None:
        report = check_draft(
            _draft(
                data_type=model.DataTypeIEC61360.INTEGER_CURRENCY,
                definition=[("en", "d")],
                **{field: "EUR"},
            )
        )

        assert not any("AASc-3a-009" in n for n in report.advisories)

    def test_a_count_needs_no_unit(self) -> None:
        report = check_draft(
            _draft(
                data_type=model.DataTypeIEC61360.INTEGER_COUNT,
                definition=[("en", "d")],
            )
        )

        assert report.advisories == ()

    def test_a_value_with_a_value_list_is_advised(self) -> None:
        pair = model.ValueReferencePair("a", _external("urn:a"))

        report = check_draft(_draft(value="x", value_list=(pair,)))

        assert any("AASc-3a-010" in note for note in report.advisories)

    def test_a_definition_without_english_is_advised(self) -> None:
        report = check_draft(_draft(definition=[("de", "Geschwindigkeit")]))

        assert any("AASc-3a-008" in note for note in report.advisories)

    def test_a_concept_for_a_value_needs_no_definition(self) -> None:
        report = check_draft(_draft(value="red"))

        assert report.advisories == ()

    def test_advisories_do_not_block_the_record(self) -> None:
        record = build_record(
            _draft(data_type=model.DataTypeIEC61360.REAL_MEASURE)
        )

        assert record.data_specification_content.data_type is (
            model.DataTypeIEC61360.REAL_MEASURE
        )


class TestBuild:
    def test_the_record_has_the_template_key_and_the_content(self) -> None:
        record = build_record(_draft())

        assert (
            match_template(record.data_specification) is TemplateMatch.CURRENT
        )
        content = record.data_specification_content
        assert isinstance(content, model.DataSpecificationIEC61360)
        assert dict(content.preferred_name) == {"en": "Speed"}

    def test_an_invalid_draft_raises_with_all_reasons(self) -> None:
        draft = Iec61360Draft(
            preferred_name=[("en", "")], short_name=[("en", "x" * 30)]
        )

        with pytest.raises(DraftError) as raised:
            build_content(draft)

        assert len(raised.value.errors) == 2

    def test_attributes_without_text_stay_absent(self) -> None:
        content = build_content(_draft(unit="  ", symbol="", value_format=""))

        assert content.unit is None
        assert content.symbol is None
        assert content.value_format is None
        assert content.source_of_definition is None
        assert content.unit_id is None
        assert content.short_name is None
        assert content.definition is None
        assert content.value_list is None

    def test_all_attributes_are_stored(self) -> None:
        pair = model.ValueReferencePair("red", _external("urn:red"))
        draft = _draft(
            short_name=[("en", "Spd")],
            definition=[("en", "How fast")],
            unit="m/s",
            unit_id="0112/2///62720#UAA733",
            source_of_definition="ISO 80000",
            symbol="v",
            data_type=model.DataTypeIEC61360.REAL_MEASURE,
            value_format="NR1..5",
            level_types=frozenset({model.IEC61360LevelType.MAX}),
            value_list=(pair,),
        )

        content = build_content(draft)

        assert dict(content.short_name or {}) == {"en": "Spd"}
        assert dict(content.definition or {}) == {"en": "How fast"}
        assert content.unit == "m/s"
        assert content.unit_id == _external("0112/2///62720#UAA733")
        assert content.source_of_definition == "ISO 80000"
        assert content.symbol == "v"
        assert content.data_type is model.DataTypeIEC61360.REAL_MEASURE
        assert content.value_format == "NR1..5"
        assert content.level_types == {model.IEC61360LevelType.MAX}
        assert content.value_list == {pair}

    @pytest.mark.parametrize("data_type", list(model.DataTypeIEC61360))
    def test_every_data_type_can_be_stored(
        self, data_type: model.DataTypeIEC61360
    ) -> None:
        assert build_content(_draft(data_type=data_type)).data_type is data_type

    def test_the_draft_of_a_content_builds_an_equal_content(self) -> None:
        original = build_content(
            _draft(
                short_name=[("en", "Spd")],
                definition=[("en", "How fast"), ("de", "Wie schnell")],
                unit="m/s",
                unit_id="urn:unit",
                symbol="v",
                data_type=model.DataTypeIEC61360.REAL_MEASURE,
            )
        )

        again = build_content(draft_of(original))

        assert dict(again.preferred_name) == dict(original.preferred_name)
        assert dict(again.definition or {}) == dict(original.definition or {})
        assert again.unit == original.unit
        assert again.unit_id == original.unit_id
        assert again.data_type is original.data_type

    def test_advisories_of_a_content_come_from_its_draft(self) -> None:
        content = build_content(
            _draft(data_type=model.DataTypeIEC61360.REAL_MEASURE)
        )

        assert any("AASc-3a-009" in n for n in advisories_of(content))


class TestEmptyAttributes:
    def test_the_sdk_allows_empty_text_and_an_empty_list(self) -> None:
        content = model.DataSpecificationIEC61360(
            model.PreferredNameTypeIEC61360({"en": "N"}),
            unit="",
            symbol=" ",
            value_list=set(),
        )

        assert empty_attributes(content) == ("unit", "symbol", "value_list")

    def test_filled_attributes_are_not_empty(self) -> None:
        content = build_content(_draft(unit="m", value_format="NR1"))

        assert empty_attributes(content) == ()
