"""Moving the entries of a multi-language text (F-EDT-06 AC15).

A display name, a description, and the value of a MultiLanguageProperty map
languages to texts, and the file keeps their order. The user moves a row up,
down, to the top, or to the end like any other row. The entries are named by
their language, so a move never gives a language to another text.

Example:
    Moving the German text of a description up::

        plan = plan_language_move(element.description, ["de"], MoveKind.UP)
        if plan is not None:
            stack.push(language_move_command(observer, plan))
"""

from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass

from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import Command
from aas_editor.application.edits import ReorderLanguages
from aas_editor.application.operations.move import MoveKind
from aas_editor.application.operations.move import new_order

_TEXTS = {
    MoveKind.UP: "up",
    MoveKind.DOWN: "down",
    MoveKind.TO_TOP: "to the top",
    MoveKind.TO_END: "to the end",
}


@dataclass(frozen=True, eq=False)
class LanguageMovePlan:
    """What a move of language entries would do.

    Attributes:
        texts: The `LangStringSet` that changes.
        order: Its languages in the new order.
        description: Text for the undo step.
    """

    texts: Mapping[str, str]
    order: tuple[str, ...]
    description: str


def plan_language_move(
    texts: Mapping[str, str], selected: Iterable[str], kind: MoveKind
) -> LanguageMovePlan | None:
    """Plans moving some entries of a multi-language text.

    Args:
        texts: The `LangStringSet`.
        selected: The languages of the entries to move.
        kind: Where to move them. Entries at the start (for up and top) or at
            the end (for down and end) stay, and the others still move.

    Returns:
        The plan, or None when the order would not change.

    Raises:
        ValueError: If a selected language is not in the set.
    """
    languages = list(texts)
    chosen = list(selected)
    missing = [language for language in chosen if language not in languages]
    if missing:
        raise ValueError(f"The text has no entry for '{missing[0]}'")
    # `new_order` compares by identity, so the same objects go in and out.
    chosen_objects = [language for language in languages if language in chosen]
    order = new_order(languages, chosen_objects, kind)
    if order == languages:
        return None
    name = chosen[0] if len(chosen) == 1 else f"{len(chosen)} languages"
    return LanguageMovePlan(
        texts, tuple(order), f"Move language {name} {_TEXTS[kind]}"
    )


def can_move_languages(
    texts: Mapping[str, str], selected: Iterable[str], kind: MoveKind
) -> bool:
    """Tells whether a move would change the order of the entries."""
    try:
        return plan_language_move(texts, selected, kind) is not None
    except ValueError:
        return False


def language_move_command(
    observer: ModelChangeObserver, plan: LanguageMovePlan
) -> Command:
    """Builds the command of a move. It is one undo step."""
    return ReorderLanguages(
        observer, plan.texts, plan.order, description=plan.description
    )
