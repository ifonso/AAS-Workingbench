"""The pattern language of bulk changes: what each field and filter gives."""

import pytest

from aas_workingbench.domain.rename_pattern import MAX_RESULT_CHARS
from aas_workingbench.domain.rename_pattern import PatternContext
from aas_workingbench.domain.rename_pattern import PatternError
from aas_workingbench.domain.rename_pattern import compile_pattern
from aas_workingbench.domain.rename_pattern import render


def _context(
    old: str = "Foo",
    number: int = 1,
    count: int = 1,
    id_short: str = "Foo",
    parent: str = "Group",
    type_name: str = "Property",
) -> PatternContext:
    return PatternContext(old, number, count, id_short, parent, type_name)


@pytest.mark.parametrize(
    ("pattern", "old", "expected"),
    [
        ("ABC_{old}", "Foo", "ABC_Foo"),
        ("{old}_XYZ", "Foo", "Foo_XYZ"),
        ("{old|upper}", "foo", "FOO"),
        ("{old|lower}", "FOO", "foo"),
        ("{old|capitalize}", "foo bar", "Foo bar"),
        ("{old|trim}", "  foo ", "foo"),
        ("{old|reverse}", "abc", "cba"),
        ("{old|slice(1)}", "foo", "oo"),
        ("{old|slice(0,1)|upper}{old|slice(1)}", "foo", "Foo"),
        ("{old|slice(-2)}", "abcdef", "ef"),
        ("{old|slice(0,-1)}", "abc", "ab"),
        ("__{old|slice(0,3)}__{old|slice(3)}", "abcdef", "__abc__def"),
        ('{old|replace("Temp","Temperature")}', "TempMax", "TemperatureMax"),
        ('{old|remove("_")}', "a_b_c", "abc"),
        ('{old|strip_prefix("Old")}', "OldName", "Name"),
        ('{old|strip_prefix("Old")}', "Name", "Name"),
        ('{old|strip_suffix("_1")}', "Name_1", "Name"),
        ('{old|default("None")}', "", "None"),
        ('{old|default("None")}', "x", "x"),
        ("{old|pad(5)}", "42", "00042"),
        ('{old|pad(5,"-")}', "42", "---42"),
        ("{old|pad(2)}", "1234", "1234"),
        ("{old|add(9)}", "1", "10"),
        ("{old|to_id_short}", "my value", "My_value"),
    ],
)
def test_fields_and_filters_give_the_documented_text(
    pattern: str, old: str, expected: str
) -> None:
    assert render(compile_pattern(pattern), _context(old=old)) == expected


def test_a_text_without_braces_is_the_same_for_every_element() -> None:
    compiled = compile_pattern("Fixed")

    assert render(compiled, _context(old="A")) == "Fixed"
    assert render(compiled, _context(old="B")) == "Fixed"


def test_doubled_braces_are_literal_braces() -> None:
    assert render(compile_pattern("{{{old}}}"), _context(old="x")) == "{x}"


def test_the_other_fields_come_from_the_context() -> None:
    context = _context(
        old="text",
        number=7,
        count=12,
        id_short="Pump",
        parent="Motor",
        type_name="Range",
    )
    pattern = "{idShort}|{parent}|{type}|{number}|{count}"

    assert render(compile_pattern(pattern), context) == "Pump|Motor|Range|7|12"


def test_numbers_can_be_padded_and_offset() -> None:
    compiled = compile_pattern("Item{number|add(9)|pad(3)}")

    assert render(compiled, _context(number=1)) == "Item010"
    assert render(compiled, _context(number=2)) == "Item011"


def test_whitespace_around_names_and_arguments_is_ignored() -> None:
    compiled = compile_pattern(
        '{ old | slice( 1 , 3 ) | replace( "o" , "0" ) }'
    )

    assert render(compiled, _context(old="foolish")) == "00"


def test_a_quote_and_a_brace_can_be_inside_a_quoted_argument() -> None:
    compiled = compile_pattern(r'{old|replace("}\"","|")}')

    assert render(compiled, _context(old='a}"b')) == "a|b"


def test_a_pipe_inside_an_argument_does_not_split_the_filters() -> None:
    compiled = compile_pattern('{old|replace("a|b","X")|upper}')

    assert render(compiled, _context(old="a|b-c")) == "X-C"


@pytest.mark.parametrize(
    ("pattern", "fragment"),
    [
        ("{old", "closing brace"),
        ("}", "single closing brace"),
        ("{}", "field name"),
        ("{nope}", "Unknown field 'nope'"),
        ("{old|nope}", "Unknown filter 'nope'"),
        ("{old|upper(1)}", "takes no arguments"),
        ("{old|slice}", "needs"),
        ("{old|slice(a)}", "whole number"),
        ("{old|slice(1,2,3)}", "at most 2"),
        ('{old|replace("a")}', "needs 2"),
        ('{old|replace("","b")}', "must not be empty"),
        ('{old|pad(3,"ab")}', "one character"),
        ("{old|pad(-1)}", "not be negative"),
        ('{old|replace("a,b)}', "unclosed"),
        ("{old|}", "filter name"),
        ("{old upper}", "Expected"),
        ("{old|slice(1}", "closing parenthesis"),
        ("x" * 1001, "longer than"),
    ],
)
def test_a_wrong_pattern_is_refused_with_a_reason(
    pattern: str, fragment: str
) -> None:
    with pytest.raises(PatternError) as caught:
        compile_pattern(pattern)

    assert fragment in str(caught.value)


def test_the_error_names_the_place_in_the_pattern() -> None:
    with pytest.raises(PatternError) as caught:
        compile_pattern("ab{old|nope}")

    assert caught.value.position == 7
    assert "position 8" in str(caught.value)


def test_adding_to_text_that_is_no_number_is_refused_for_that_element() -> None:
    compiled = compile_pattern("{old|add(1)}")

    with pytest.raises(PatternError) as caught:
        render(compiled, _context(old="abc"))

    assert "'abc' is not a whole number" in str(caught.value)


def test_a_result_beyond_the_limit_is_refused() -> None:
    compiled = compile_pattern("{old|pad(100000)}")

    with pytest.raises(PatternError) as caught:
        render(compiled, _context(old="x"))

    assert str(MAX_RESULT_CHARS) in str(caught.value)


def test_code_in_a_pattern_is_text_and_never_runs() -> None:
    # Nothing in the language evaluates; this must be refused or kept as text.
    with pytest.raises(PatternError):
        compile_pattern("{__import__('os').getcwd()}")
    assert (
        render(compile_pattern("__import__('os').getcwd()"), _context())
        == "__import__('os').getcwd()"
    )
