import re

from basyx.aas import model
import pytest
from tests.factories import make_property

from aas_workingbench.domain.ids import fix_id_short
from aas_workingbench.domain.ids import id_short_prefix
from aas_workingbench.domain.ids import is_valid_id_short
from aas_workingbench.domain.ids import new_identifier
from aas_workingbench.domain.ids import unique_id_short


def _six_digits() -> str:
    return "123456"


class TestNewIdentifier:
    def test_new_identifier_is_a_uuid_urn(self) -> None:
        assert re.fullmatch(
            r"urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}"
            r"-[0-9a-f]{12}",
            new_identifier(),
        )

    def test_new_identifier_differs_between_calls(self) -> None:
        assert len({new_identifier() for _ in range(100)}) == 100

    def test_new_identifier_is_accepted_as_an_id(self) -> None:
        shell = model.Submodel(id_=new_identifier())

        assert shell.id.startswith("urn:uuid:")


class TestIsValidIdShort:
    @pytest.mark.parametrize(
        "text", ["a", "Pump", "Pump_1", "Pump-1", "a_", "A1_b-2"]
    )
    def test_accepts_valid_id_short(self, text: str) -> None:
        assert is_valid_id_short(text)

    @pytest.mark.parametrize(
        "text", ["", "1abc", "_abc", "my motor", "abc-", "a" * 129, "Größe"]
    )
    def test_rejects_invalid_id_short(self, text: str) -> None:
        assert not is_valid_id_short(text)


class TestFixIdShort:
    def test_fix_keeps_valid_id_short_when_nothing_is_wrong(self) -> None:
        assert fix_id_short("my-motor_1") == "my-motor_1"

    def test_fix_replaces_blank_and_symbols_for_aas_criterion_2(self) -> None:
        assert fix_id_short("my motor!") == "My_motor"

    def test_fix_uses_prefix_and_digits_when_nothing_is_usable(self) -> None:
        assert fix_id_short("!!!", "Prop", _six_digits) == "Prop123456"

    def test_fix_uses_prefix_and_digits_when_text_is_empty(self) -> None:
        assert fix_id_short("", "SMC", _six_digits) == "SMC123456"

    def test_fix_random_digits_make_a_valid_id_short_by_default(self) -> None:
        fixed = fix_id_short("???", "Prop")

        assert re.fullmatch(r"Prop\d{6}", fixed)

    def test_fix_keeps_hyphens_that_are_valid(self) -> None:
        assert fix_id_short("Motor-A b") == "Motor-A_b"

    def test_fix_puts_prefix_before_leading_digit(self) -> None:
        assert fix_id_short("1abc", "Prop") == "Prop1abc"

    def test_fix_drops_leading_underscore_and_trailing_hyphen(self) -> None:
        assert fix_id_short("_abc-") == "Abc"

    def test_fix_removes_accents_and_transliterates_sharp_s(self) -> None:
        assert fix_id_short("Größe élan") == "Grosse_elan"

    def test_fix_shortens_text_that_is_too_long(self) -> None:
        fixed = fix_id_short("a b" * 100)

        assert len(fixed) <= 128
        assert is_valid_id_short(fixed)

    def test_fix_result_is_always_valid(self) -> None:
        for text in ["-", "_", "9", "a-", "  ", "ä", "日本語", "x" * 200]:
            assert is_valid_id_short(fix_id_short(text, "Prop", _six_digits))


class TestUniqueIdShort:
    def test_unique_returns_wanted_when_free(self) -> None:
        assert unique_id_short("Pump", {"Other"}) == "Pump"

    def test_unique_adds_suffix_when_taken_for_decision_d13(self) -> None:
        assert unique_id_short("Pump", {"Pump"}) == "Pump_1"

    def test_unique_skips_taken_suffixes(self) -> None:
        taken = {"Pump", "Pump_1", "Pump_2"}

        assert unique_id_short("Pump", taken) == "Pump_3"

    def test_unique_counts_up_when_name_is_numbered_already(self) -> None:
        assert unique_id_short("Pump_1", {"Pump_1"}) == "Pump_2"

    def test_unique_compares_case_sensitive(self) -> None:
        assert unique_id_short("pump", {"Pump"}) == "pump"

    def test_unique_shortens_base_to_fit_the_limit(self) -> None:
        name = "a" * 128

        result = unique_id_short(name, {name})

        assert result == "a" * 126 + "_1"
        assert is_valid_id_short(result)


class TestIdShortPrefix:
    def test_prefix_names_property(self) -> None:
        assert id_short_prefix(make_property()) == "Prop"

    def test_prefix_prefers_the_subclass(self) -> None:
        assert id_short_prefix(model.AnnotatedRelationshipElement) == "ARel"

    def test_prefix_is_generic_for_unknown_type(self) -> None:
        assert id_short_prefix(object()) == "Id"
