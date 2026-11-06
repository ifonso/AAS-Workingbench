"""The actions that move the selected rows up, down, to the top and to the end.

Call `register_move_actions` once, before the first tree view exists. The
composition root does that. The shortcuts are the ones of Package Explorer
(Shift+Ctrl with Up, Down, Home and End). A move of several rows is one undo
step, and the rows stay selected.

A tree that a user sorted by a column hides the order of the package, so a
move first puts the tree back to the natural order (decision D16).
"""

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QMessageBox

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.operations.move import MoveKind
from aas_editor.application.operations.move import can_move
from aas_editor.application.operations.move import move_commands
from aas_editor.application.operations.move import plan_move
from aas_editor.domain import containers
from aas_editor.domain import ordering
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.icons import NEXT_ICON
from aas_editor.settings.icons import PREV_ICON
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action

_CTRL_SHIFT = (
    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
)


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


def _selection(context: ActionContext) -> tuple[object, list[object]] | None:
    """Returns the common container and the selected members, or None."""
    container: object | None = None
    members: list[object] = []
    for index in selected_rows(context):
        where = container_of_row(index)
        if where is None or (container is not None and where is not container):
            return None
        container = where
        members.append(index.data(OBJECT_ROLE))
    if container is None:
        return None
    return container, members


def _enabled(kind: MoveKind):
    def check(context: ActionContext) -> bool:
        found = _selection(context)
        return found is not None and can_move(found[0], found[1], kind)

    return check


def _natural_order(context: ActionContext) -> None:
    """Shows the order of the package, if the user sorted the tree."""
    header = context.view.header()
    if header is not None and header.sortIndicatorSection() >= 0:
        header.setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        sections = getattr(header, "currSortSection", None)
        if sections is not None:
            header.currSortSection = -1


def _runner(kind: MoveKind):
    def run(context: ActionContext) -> None:
        found = _selection(context)
        if found is None or context.package is None:
            return
        container, members = found
        plan = plan_move(
            container,
            members,
            kind,
            context.package.objStore,  # pyright: ignore[reportAttributeAccessIssue]
        )
        if plan is None:
            return
        _natural_order(context)
        try:
            with context.stack.group(plan.description):  # type: ignore[union-attr]
                for command in move_commands(
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


def _key(key: Qt.Key) -> QKeySequence:
    return QKeySequence(_CTRL_SHIFT | key)


_SPECS = (
    (MoveKind.UP, "structure.move_up", "Move up", Qt.Key.Key_Up, 300, True),
    (
        MoveKind.DOWN,
        "structure.move_down",
        "Move down",
        Qt.Key.Key_Down,
        301,
        True,
    ),
    (
        MoveKind.TO_TOP,
        "structure.move_top",
        "Move to top",
        Qt.Key.Key_Home,
        302,
        False,
    ),
    (
        MoveKind.TO_END,
        "structure.move_end",
        "Move to end",
        Qt.Key.Key_End,
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
                shortcut=_key(key),
                status_tip=f"{text} within the list of the selected element",
                toolbar=toolbar,
                order=order,
            )
        )
