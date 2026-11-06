"""Moving the entries of a multi-language text (F-EDT-06 AC15)."""

from basyx.aas import model
import pytest
from tests.serialization import snapshot

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.operations.language_order import can_move_languages
from aas_editor.application.operations.language_order import (
    language_move_command,
)
from aas_editor.application.operations.language_order import plan_language_move
from aas_editor.application.operations.move import MoveKind
from aas_editor.domain import containers


def _texts() -> model.MultiLanguageTextType:
    return model.MultiLanguageTextType(
        {"en": "Pump", "de": "Pumpe", "fr": "Pompe"}
    )


def test_the_first_entry_moves_down_and_the_texts_stay_with_their_language() -> (
    None
):
    texts = _texts()

    plan = plan_language_move(texts, ["en"], MoveKind.DOWN)

    assert plan is not None
    assert plan.order == ("de", "en", "fr")
    command = language_move_command(ModelChangeObserver(), plan)
    command.apply()
    assert list(texts.items()) == [
        ("de", "Pumpe"),
        ("en", "Pump"),
        ("fr", "Pompe"),
    ]


@pytest.mark.parametrize(
    ("selected", "kind", "order"),
    [
        (["fr"], MoveKind.UP, ("en", "fr", "de")),
        (["fr"], MoveKind.TO_TOP, ("fr", "en", "de")),
        (["en"], MoveKind.TO_END, ("de", "fr", "en")),
        (["de", "fr"], MoveKind.UP, ("de", "fr", "en")),
        (["en", "de"], MoveKind.DOWN, ("fr", "en", "de")),
    ],
)
def test_each_kind_of_move_gives_its_order(
    selected: list[str], kind: MoveKind, order: tuple[str, ...]
) -> None:
    plan = plan_language_move(_texts(), selected, kind)

    assert plan is not None
    assert plan.order == order


@pytest.mark.parametrize(
    ("selected", "kind"),
    [
        (["en"], MoveKind.UP),
        (["en"], MoveKind.TO_TOP),
        (["fr"], MoveKind.DOWN),
        (["fr"], MoveKind.TO_END),
    ],
)
def test_a_move_that_changes_nothing_has_no_plan(
    selected: list[str], kind: MoveKind
) -> None:
    texts = _texts()

    assert plan_language_move(texts, selected, kind) is None
    assert not can_move_languages(texts, selected, kind)


def test_a_language_that_is_not_in_the_text_is_refused() -> None:
    with pytest.raises(ValueError, match="no entry for 'es'"):
        plan_language_move(_texts(), ["es"], MoveKind.UP)
    assert not can_move_languages(_texts(), ["es"], MoveKind.UP)


def test_a_text_with_one_language_cannot_move() -> None:
    one = model.MultiLanguageTextType({"en": "Pump"})

    assert not can_move_languages(one, ["en"], MoveKind.DOWN)


def test_the_move_is_one_undo_step_and_is_written_to_the_file() -> None:
    prop = model.Property(
        "Pump",
        model.datatypes.String,
        description=_texts(),
    )
    submodel = model.Submodel("urn:sm", [prop])
    store = model.DictIdentifiableStore([submodel])
    before = snapshot(store)
    stack = CommandStack()
    plan = plan_language_move(prop.description, ["en"], MoveKind.TO_END)
    assert plan is not None

    stack.push(language_move_command(ModelChangeObserver(), plan))
    after = snapshot(store)
    assert prop.description is not None
    moved = list(prop.description)
    stack.undo()

    assert moved == ["de", "fr", "en"]
    assert '"language": "en"' in after
    assert after.index('"language": "de"') < after.index('"language": "en"')
    assert snapshot(store) == before
    assert list(prop.description) == ["en", "de", "fr"]
    assert not stack.can_undo


def test_reorder_keys_refuses_an_order_that_is_not_a_permutation() -> None:
    texts = _texts()

    for bad in (["en", "de"], ["en", "de", "de"], ["en", "de", "es"]):
        with pytest.raises(ValueError, match="every key exactly once"):
            containers.reorder_keys(texts, bad)

    assert list(texts) == ["en", "de", "fr"]


def test_reorder_keys_works_for_a_plain_mapping_and_refuses_a_list() -> None:
    mapping = {"a": 1, "b": 2, "c": 3}

    containers.reorder_keys(mapping, ["c", "a", "b"])

    assert list(mapping.items()) == [("c", 3), ("a", 1), ("b", 2)]
    with pytest.raises(TypeError):
        containers.reorder_keys([1, 2], [2, 1])


def test_a_selection_with_the_last_entry_does_not_move_down() -> None:
    assert plan_language_move(_texts(), ["en", "fr"], MoveKind.DOWN) is None
