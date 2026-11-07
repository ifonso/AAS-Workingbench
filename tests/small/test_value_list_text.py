"""Value list pairs read from clipboard text."""

import json
import time

from basyx.aas import model
import pytest

from aas_workingbench.domain.value_list_text import MAX_CHARS
from aas_workingbench.domain.value_list_text import MAX_PAIRS
from aas_workingbench.domain.value_list_text import NO_VALUE_ID
from aas_workingbench.domain.value_list_text import parse_value_pairs


def _keys(pair: model.ValueReferencePair) -> list[tuple[str, str]]:
    assert pair.value_id is not None
    return [(k.type.name, k.value) for k in pair.value_id.key]


def _json_pair(value: str = "Red", id_: str = "urn:red") -> dict[str, object]:
    return {
        "value": value,
        "valueId": {
            "type": "ExternalReference",
            "keys": [{"type": "GlobalReference", "value": id_}],
        },
    }


class TestLines:
    def test_a_comma_separates_value_and_value_id(self) -> None:
        result = parse_value_pairs("Red, 0173-1#07-AAA#001")

        (pair,) = result.pairs
        assert pair.value == "Red"
        assert isinstance(pair.value_id, model.ExternalReference)
        assert _keys(pair) == [("GLOBAL_REFERENCE", "0173-1#07-AAA#001")]

    def test_each_line_is_a_pair_in_the_order_of_the_text(self) -> None:
        result = parse_value_pairs("A, urn:a\nB, urn:b\r\nC, urn:c\n")

        assert [p.value for p in result.pairs] == ["A", "B", "C"]
        assert [e.place for e in result.entries] == [
            "Line 1",
            "Line 2",
            "Line 3",
        ]

    def test_a_tab_separates_what_a_spreadsheet_copies(self) -> None:
        result = parse_value_pairs("Dark red, almost\turn:dark-red\r\n")

        (pair,) = result.pairs
        assert pair.value == "Dark red, almost"
        assert _keys(pair) == [("GLOBAL_REFERENCE", "urn:dark-red")]

    def test_the_last_comma_separates_when_the_value_has_commas(self) -> None:
        (pair,) = parse_value_pairs("one, two, urn:x").pairs

        assert pair.value == "one, two"
        assert _keys(pair) == [("GLOBAL_REFERENCE", "urn:x")]

    def test_blank_lines_are_ignored(self) -> None:
        result = parse_value_pairs("\n\nA, urn:a\n   \n")

        assert len(result.entries) == 1
        assert result.entries[0].place == "Line 3"

    def test_a_line_without_value_id_is_reported_with_the_reason(self) -> None:
        result = parse_value_pairs("A, urn:a\nlonely")

        assert [p.value for p in result.pairs] == ["A"]
        (problem,) = result.problems
        assert problem.place == "Line 2"
        assert problem.problem == NO_VALUE_ID

    def test_a_line_without_value_is_reported(self) -> None:
        (problem,) = parse_value_pairs(", urn:a").problems

        assert problem.problem == "has no value"

    def test_a_value_over_2048_characters_is_reported_with_the_sdk_reason(
        self,
    ) -> None:
        (problem,) = parse_value_pairs(f"{'x' * 2049}, urn:a").problems

        assert "maximum length of 2048" in (problem.problem or "")

    def test_a_byte_order_mark_is_dropped(self) -> None:
        (pair,) = parse_value_pairs("﻿A, urn:a").pairs

        assert pair.value == "A"

    @pytest.mark.parametrize("text", ["", "  \n\t\n", "\n"])
    def test_empty_text_is_refused(self, text: str) -> None:
        result = parse_value_pairs(text)

        assert result.error == "There is no text to read."
        assert result.entries == ()


class TestJson:
    def test_an_array_is_read_in_order(self) -> None:
        text = json.dumps([_json_pair("A", "urn:a"), _json_pair("B", "urn:b")])

        result = parse_value_pairs(text)

        assert [p.value for p in result.pairs] == ["A", "B"]
        assert [e.place for e in result.entries] == ["Entry 1", "Entry 2"]
        assert _keys(result.pairs[1]) == [("GLOBAL_REFERENCE", "urn:b")]

    def test_one_object_is_one_pair(self) -> None:
        (pair,) = parse_value_pairs(json.dumps(_json_pair())).pairs

        assert pair.value == "Red"

    def test_a_whole_value_list_is_read(self) -> None:
        text = json.dumps({"valueReferencePairs": [_json_pair()]})

        assert len(parse_value_pairs(text).pairs) == 1

    def test_a_model_reference_keeps_its_kind(self) -> None:
        pair = _json_pair()
        pair["valueId"] = {
            "type": "ModelReference",
            "keys": [{"type": "ConceptDescription", "value": "urn:cd"}],
        }

        (read,) = parse_value_pairs(json.dumps([pair])).pairs

        assert isinstance(read.value_id, model.ModelReference)

    def test_an_entry_with_a_bad_key_type_is_reported_and_the_rest_is_read(
        self,
    ) -> None:
        bad = _json_pair("Bad")
        bad["valueId"] = {
            "type": "ExternalReference",
            "keys": [{"type": "Bogus", "value": "x"}],
        }
        text = json.dumps([_json_pair("A"), bad, _json_pair("C")])

        result = parse_value_pairs(text)

        assert [p.value for p in result.pairs] == ["A", "C"]
        (problem,) = result.problems
        assert problem.place == "Entry 2"
        assert "Bogus" in (problem.problem or "")

    def test_a_null_value_id_is_reported_like_a_missing_one(self) -> None:
        (problem,) = parse_value_pairs(
            json.dumps([{"value": "A", "valueId": None}])
        ).problems

        assert problem.problem == NO_VALUE_ID

    def test_an_entry_that_is_not_an_object_is_reported(self) -> None:
        (problem,) = parse_value_pairs('["text"]').problems

        assert "not an object" in (problem.problem or "")

    def test_a_number_as_value_is_reported(self) -> None:
        entry = _json_pair()
        entry["value"] = 5

        (problem,) = parse_value_pairs(json.dumps([entry])).problems

        assert "value" in (problem.problem or "")

    def test_invalid_json_is_refused_with_the_position(self) -> None:
        result = parse_value_pairs('[{"value": "A",')

        assert result.error is not None
        assert "cannot be read" in result.error
        assert "line 1" in result.error

    @pytest.mark.parametrize(
        "text", ["[]", "{}", '{"other": 1}'], ids=["empty", "object", "other"]
    )
    def test_json_without_pairs_is_refused(self, text: str) -> None:
        assert parse_value_pairs(text).error is not None

    def test_deeply_nested_json_is_refused_without_a_traceback(self) -> None:
        result = parse_value_pairs("[" * 100_000)

        assert result.error is not None
        assert result.entries == ()


class TestUntrustedText:
    @pytest.mark.parametrize(
        "text",
        [
            "__import__('os').system('echo owned')",
            "[__import__('os').system('echo owned')]",
            '{"value": "__import__(\'os\')", "valueId": {"type": "x"}}',
        ],
    )
    def test_code_is_refused_as_text_and_never_runs(self, text: str) -> None:
        result = parse_value_pairs(text)

        assert result.pairs == ()
        assert result.error is not None or len(result.problems) == 1

    def test_text_over_the_limit_is_refused(self) -> None:
        result = parse_value_pairs("a" * (MAX_CHARS + 1))

        assert result.error is not None
        assert "looks like a file" in result.error

    def test_too_many_lines_are_refused(self) -> None:
        result = parse_value_pairs("a, urn:a\n" * (MAX_PAIRS + 1))

        assert result.error is not None
        assert str(MAX_PAIRS + 1) in result.error.replace(",", "")

    def test_a_long_list_of_lines_is_read_quickly(self) -> None:
        text = "\n".join(f"Value {n}, urn:v:{n}" for n in range(5000))

        started = time.perf_counter()
        result = parse_value_pairs(text)

        assert len(result.pairs) == 5000
        assert time.perf_counter() - started < 5

    def test_a_long_json_list_is_read_quickly(self) -> None:
        text = json.dumps([_json_pair(f"V{n}", f"u{n}") for n in range(3000)])

        started = time.perf_counter()
        result = parse_value_pairs(text)

        assert len(result.pairs) == 3000
        assert time.perf_counter() - started < 5
