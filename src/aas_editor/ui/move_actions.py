"""The actions that move the selected rows up, down, to the top and to the end.

Call `register_move_actions` once, before the first tree view exists. The
composition root does that. The shortcuts are the ones of Package Explorer
(Shift+Ctrl with Up, Down, Home and End). A move of several rows is one undo
step, and the rows stay selected.

A tree that a user sorted by a column hides the order of the package, so a
move first puts the tree back to the natural order (decision D16).
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMessageBox

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.operations.bulk_move import bulk_move_commands
from aas_editor.application.operations.bulk_move import can_bulk_move
from aas_editor.application.operations.bulk_move import plan_bulk_move
from aas_editor.additional.classes import DictItem
from aas_editor.application.operations.language_order import (
    can_move_languages,
)
from aas_editor.application.operations.language_order import (
    language_move_command,
)
from aas_editor.application.operations.language_order import (
    plan_language_move,
)
from aas_editor.application.operations.move import MoveKind
from aas_editor.domain import containers
from aas_editor.domain import ordering
from aas_editor.domain.selection import has_mixed_variable_directions
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.icons import NEXT_ICON
from aas_editor.settings.icons import PREV_ICON
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action


def selected_rows(context: ActionContext) -> list[QModelIndex]:
    """Returns one index for each selected row, in the order of the rows."""
    seen: set[tuple[QModelIndex, int]] = set()
    rows: list[QModelIndex] = []
    for index in context.selection or (context.index,):
        if not index.isValid():
            continue
        key = (index.parent(), index.row())
        if key not in seen:
            seen.add(key)
            rows.append(index)
    return rows


def container_of_row(index: QModelIndex) -> object | None:
    """Returns the ordered container that holds the object of a row.

    That is the `NamespaceSet` or list that a row above shows, or else the
    namespace set of the parent of an element. Shells, submodels and concept
    descriptions have none, because the SDK keeps them in sets (D16).
    """
    obj = index.data(OBJECT_ROLE)
    if obj is None or isinstance(obj, model.Identifiable):
        return None
    parent = index.parent()
    holder = parent.data(OBJECT_ROLE) if parent.isValid() else None
    try:
        held = containers.members_in_order(holder)
    except TypeError:
        held = []
    if any(member is obj for member in held):
        return holder
    sets = ordering.namespace_sets_of(obj)
    return sets[0] if sets else None


def _selection(context: ActionContext) -> list[tuple[object, object]] | None:
    """Returns each selected member with its container, or None.

    The members may be in different containers, and each moves within its
    own. None when a selected row has no ordered container, such as a
    submodel.
    """
    placements: list[tuple[object, object]] = []
    for index in selected_rows(context):
        container = container_of_row(index)
        if container is None:
            return None
        placements.append((container, index.data(OBJECT_ROLE)))
    return placements or None


def _language_selection(
    context: ActionContext,
) -> tuple[model.LangStringSet, list[str]] | None:
    """Returns the multi-language text and the languages of the selected rows.

    The rows of a display name, a description, or the value of a
    MultiLanguageProperty are `DictItem`s of a `LangStringSet`. They move
    within it (F-EDT-06 AC15). None when a selected row is something else, or
    the rows belong to different texts.
    """
    texts: model.LangStringSet | None = None
    languages: list[str] = []
    for index in selected_rows(context):
        item = index.data(OBJECT_ROLE)
        parent = index.parent()
        holder = parent.data(OBJECT_ROLE) if parent.isValid() else None
        if not isinstance(item, DictItem) or not isinstance(
            holder, model.LangStringSet
        ):
            return None
        if texts is not None and holder is not texts:
            return None
        texts = holder
        languages.append(item.key)
    if texts is None:
        return None
    return texts, languages


def _enabled(kind: MoveKind):
    def check(context: ActionContext) -> bool:
        texts = _language_selection(context)
        if texts is not None:
            return can_move_languages(texts[0], texts[1], kind)
        found = _selection(context)
        # Package Explorer offers no move for variables of different
        # directions (F-EDT-09 AC19). Cut and Copy stay.
        return (
            found is not None
            and not has_mixed_variable_directions(m for _, m in found)
            and can_bulk_move(found, kind)
        )

    return check


def _natural_order(context: ActionContext) -> None:
    """Shows the order of the package, if the user sorted the tree."""
    header: Any = context.view.header()
    if header is not None and header.sortIndicatorSection() >= 0:
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        if hasattr(header, "currSortSection"):
            header.currSortSection = -1


def _move_languages(
    context: ActionContext,
    texts: model.LangStringSet,
    languages: list[str],
    kind: MoveKind,
) -> None:
    plan = plan_language_move(texts, languages, kind)
    if plan is None:
        return
    try:
        context.push(language_move_command(observer_for(context.package), plan))
    except ReadOnlyError as error:
        QMessageBox.warning(context.view, "Move", str(error))
    except Exception as error:  # noqa: BLE001
        QMessageBox.warning(
            context.view, "Move", f"The move was refused: {error}"
        )


def _runner(kind: MoveKind):
    def run(context: ActionContext) -> None:
        texts = _language_selection(context)
        if texts is not None:
            _move_languages(context, texts[0], texts[1], kind)
            return
        found = _selection(context)
        package: Any = context.package
        if found is None or package is None:
            return
        plan = plan_bulk_move(found, kind, package.objStore)
        if plan is None:
            return
        _natural_order(context)
        try:
            with context.stack.group(plan.description):  # type: ignore[union-attr]
                for command in bulk_move_commands(
                    observer_for(context.package), plan
                ):
                    context.push(command)
        except ReadOnlyError as error:
            QMessageBox.warning(context.view, "Move", str(error))
        except Exception as error:  # noqa: BLE001
            QMessageBox.warning(
                context.view, "Move", f"The move was refused: {error}"
            )

    return run


_SPECS = (
    (MoveKind.UP, "structure.move_up", "Move up", "Up", 300, True),
    (
        MoveKind.DOWN,
        "structure.move_down",
        "Move down",
        "Down",
        301,
        True,
    ),
    (
        MoveKind.TO_TOP,
        "structure.move_top",
        "Move to top",
        "Home",
        302,
        False,
    ),
    (
        MoveKind.TO_END,
        "structure.move_end",
        "Move to end",
        "End",
        303,
        False,
    ),
)


def register_move_actions() -> None:
    """Adds the four move actions to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    for kind, action_id, text, key, order, toolbar in _SPECS:
        if action_id in registered:
            continue
        register_action(
            ActionSpec(
                action_id=action_id,
                text=text,
                run=_runner(kind),
                is_enabled=_enabled(kind),
                views=ViewKind.ANY,
                icon=(
                    PREV_ICON
                    if kind is MoveKind.UP
                    else NEXT_ICON
                    if kind is MoveKind.DOWN
                    else None
                ),
                shortcut=QKeySequence(f"Ctrl+Shift+{key}"),
                status_tip=f"{text} within the list of the selected element",
                toolbar=toolbar,
                order=order,
            )
        )
