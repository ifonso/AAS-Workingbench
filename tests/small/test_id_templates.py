"""Ids made from a template (F-EDT-06 AC5)."""

import re

import pytest

from aas_workingbench.domain.id_templates import check_id_template
from aas_workingbench.domain.id_templates import generate_id


def test_a_template_with_digits_gives_two_ids_of_that_form() -> None:
    first = generate_id("urn:x:DDDD")
    second = generate_id("urn:x:DDDD")

    assert re.fullmatch(r"urn:x:\d{4}", first)
    assert re.fullmatch(r"urn:x:\d{4}", second)


def test_digits_come_from_the_random_source() -> None:
    assert generate_id("urn:x:DDDD", lambda limit: 7) == "urn:x:7777"


def test_each_placeholder_draws_from_its_own_characters() -> None:
    drawn: list[int] = []

    def last(limit: int) -> int:
        drawn.append(limit)
        return limit - 1

    assert generate_id("DXA", last) == "9FZ"
    assert drawn == [10, 16, 26]


def test_other_characters_are_copied() -> None:
    assert (
        generate_id("https://example.com/ids/aas/DD_DD", lambda limit: 0)
        == "https://example.com/ids/aas/00_00"
    )


def test_a_backslash_makes_the_next_character_literal() -> None:
    assert generate_id(r"urn:\Dx:\\DD", lambda limit: 3) == "urn:Dx:\\33"


def test_ids_of_a_long_template_differ() -> None:
    template = "urn:x:DDDD_DDDD_DDDD_DDDD"

    assert len({generate_id(template) for _ in range(50)}) == 50


@pytest.mark.parametrize("template", ["", "   "])
def test_no_template_gives_a_uuid_urn(template: str) -> None:
    assert re.fullmatch(r"urn:uuid:[0-9a-f-]{36}", generate_id(template))


def test_an_unusable_template_gives_a_uuid_urn_and_not_a_constant() -> None:
    assert generate_id("urn:x:fixed").startswith("urn:uuid:")


@pytest.mark.parametrize("template", ["", "urn:x:DDDD", "urn:x:\\D\\D:X"])
def test_a_usable_template_has_no_problem(template: str) -> None:
    assert check_id_template(template) is None


@pytest.mark.parametrize(
    ("template", "reason"),
    [
        ("urn:x:fixed", "needs at least one D"),
        (r"urn:\D\X\A", "needs at least one D"),
        ("urn:x:DDDD\\", "ends with a backslash"),
        (" urn:x:DDDD", "must not start or end with a blank"),
        ("D" * 2049, "2049 characters"),
    ],
)
def test_an_unusable_template_says_what_to_change(
    template: str, reason: str
) -> None:
    problem = check_id_template(template)

    assert problem is not None
    assert reason in problem
