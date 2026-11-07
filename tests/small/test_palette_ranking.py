"""What the command palette lists, and in which order."""

import pytest

from aas_editor.application.command_palette import MAX_RECENT
from aas_editor.application.command_palette import MAX_RESULTS
from aas_editor.application.command_palette import EntryKind
from aas_editor.application.command_palette import PaletteEntry
from aas_editor.application.command_palette import RecentCommands
from aas_editor.application.command_palette import match_score
from aas_editor.application.command_palette import rank


def _command(
    title: str, key: str | None = None, enabled: bool = True, detail: str = ""
) -> PaletteEntry:
    return PaletteEntry(
        key or title, title, EntryKind.COMMAND, detail=detail, enabled=enabled
    )


def _element(title: str, keywords: str = "") -> PaletteEntry:
    return PaletteEntry(
        f"element:{title}", title, EntryKind.ELEMENT, keywords=keywords
    )


def _titles(entries: list[PaletteEntry]) -> list[str]:
    return [entry.title for entry in entries]


# ---------------------------------------------------------------------------
# The match of a word with an entry
# ---------------------------------------------------------------------------


def test_an_empty_query_matches_every_entry() -> None:
    assert match_score("", _command("Save")) == 0


def test_the_start_of_the_title_fits_better_than_a_word_inside_it() -> None:
    start = match_score("sa", _command("Save As"))
    inside = match_score("as", _command("Save As"))

    assert start is not None and inside is not None and start < inside


def test_a_word_inside_the_title_fits_better_than_its_initials() -> None:
    inside = match_score("ave", _command("Save As"))
    initials = match_score("sa", _command("Show All"))

    assert inside is not None and initials is not None and inside < initials


def test_the_first_letters_of_the_words_match_the_title() -> None:
    assert match_score("ca", _command("Collapse All")) is not None
    assert match_score("ea", _command("Collapse All")) is None


def test_letters_scattered_in_a_long_name_do_not_match() -> None:
    assert match_score("delete", _command("SubmodelElementCollection")) is None


def test_the_detail_matches_when_the_title_does_not() -> None:
    entry = _command("Next finding", detail="Navigate")

    assert match_score("navigate", entry) is not None
    assert match_score("navigate", _command("Next finding")) is None


def test_the_title_fits_better_than_the_detail() -> None:
    in_title = match_score("save", _command("Save"))
    in_detail = match_score("save", _command("Close", detail="Save and quit"))

    assert in_title is not None and in_detail is not None
    assert in_title < in_detail


def test_every_word_of_the_query_must_match() -> None:
    entry = _command("Save As")

    assert match_score("save as", entry) is not None
    assert match_score("save open", entry) is None


def test_a_query_is_not_case_sensitive() -> None:
    assert match_score("SAVE", _command("Save")) == 0


def test_the_keywords_of_an_element_match_but_do_not_show() -> None:
    entry = _element("Pump", keywords="urn:example:pump:1")

    assert match_score("urn:example", entry) is not None


# ---------------------------------------------------------------------------
# The order of the results
# ---------------------------------------------------------------------------


def test_without_a_query_only_the_commands_are_listed() -> None:
    entries = [_element("Pump"), _command("Save")]

    assert _titles(rank(entries, "")) == ["Save"]


def test_without_a_query_the_commands_used_last_come_first() -> None:
    entries = [_command("Close"), _command("Open"), _command("Save")]

    ranked = rank(entries, "", recent=["Save", "Open"])

    assert _titles(ranked) == ["Save", "Open", "Close"]


def test_without_a_query_the_other_commands_keep_their_order() -> None:
    entries = [_command("Save"), _command("Close"), _command("Open")]

    assert _titles(rank(entries, "")) == ["Save", "Close", "Open"]


def test_a_disabled_command_comes_after_the_enabled_ones() -> None:
    entries = [
        _command("Cut", enabled=False),
        _command("Copy"),
        _command("Close"),
    ]

    assert _titles(rank(entries, "c")) == ["Copy", "Close", "Cut"]


def test_a_query_lists_the_entries_that_fit_best_first() -> None:
    entries = [_command("Resave"), _command("Save As"), _command("Save")]

    assert _titles(rank(entries, "save")) == ["Save", "Save As", "Resave"]


def test_a_shorter_title_comes_before_a_longer_one_that_fits_the_same() -> None:
    entries = [_command("Save in json"), _command("Save All"), _command("Save")]

    assert _titles(rank(entries, "save"))[0] == "Save"


def test_a_command_comes_before_an_element_with_the_same_fit() -> None:
    entries = [_element("Save"), _command("Save")]

    ranked = rank(entries, "save")

    assert [entry.kind for entry in ranked] == [
        EntryKind.COMMAND,
        EntryKind.ELEMENT,
    ]


def test_a_query_finds_an_element_by_its_name() -> None:
    entries = [_command("Save"), _element("Speed"), _element("Pump")]

    assert _titles(rank(entries, "speed")) == ["Speed"]


def test_a_command_used_lately_comes_before_one_that_fits_the_same() -> None:
    entries = [_command("Open file", "a"), _command("Open folder", "b")]

    ranked = rank(entries, "open", recent=["b"])

    assert _titles(ranked) == ["Open folder", "Open file"]


def test_the_results_are_limited() -> None:
    entries = [_element(f"Item{number:03}") for number in range(80)]

    assert len(rank(entries, "item")) == MAX_RESULTS


def test_nothing_matches_a_query_that_fits_no_entry() -> None:
    assert rank([_command("Save")], "zzz") == []


# ---------------------------------------------------------------------------
# The commands that were used last
# ---------------------------------------------------------------------------


def test_the_command_used_last_is_first() -> None:
    recent = RecentCommands()

    recent.used("a")
    recent.used("b")

    assert recent.keys() == ("b", "a")


def test_a_command_used_again_moves_to_the_front_once() -> None:
    recent = RecentCommands()
    for key in ("a", "b", "a"):
        recent.used(key)

    assert recent.keys() == ("a", "b")


def test_only_the_last_few_commands_are_kept() -> None:
    recent = RecentCommands()
    for number in range(MAX_RECENT + 3):
        recent.used(str(number))

    assert len(recent.keys()) == MAX_RECENT
    assert recent.keys()[0] == str(MAX_RECENT + 2)


def test_recent_commands_start_from_the_store_and_save_each_use() -> None:
    saved: list[list[str]] = []
    recent = RecentCommands(lambda: ["old"], saved.append)

    recent.used("new")

    assert recent.keys() == ("new", "old")
    assert saved == [["new", "old"]]


@pytest.mark.parametrize("query", ["   ", "\t"])
def test_a_blank_query_is_no_query(query: str) -> None:
    entries = [_command("Save"), _element("Pump")]

    assert _titles(rank(entries, query)) == ["Save"]
