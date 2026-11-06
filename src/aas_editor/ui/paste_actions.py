"""The actions that paste the buffer above, below, or into the selected row.

Call `register_paste_actions` once, before the first tree view exists. The
composition root does that. The shortcuts are the ones of Package Explorer:
Ctrl+Alt+V above, Ctrl+Shift+V below, and Ctrl+Shift+Alt+V into. Clear paste
buffer empties the internal buffer and the system clipboard.

A paste inserts copies (see `application/operations/paste.py`). Copies that
come from another package ask whether the concept descriptions that their
semantic ids refer to should come along (see `companions.py`). The whole
paste is one undo step.

The buffer is the `treeClipboard` of the tree views. Text on the system
clipboard that is AAS JSON becomes objects in it, so a copy from another
program or another instance pastes like an internal one.
"""

from collections.abc import Iterable
from typing import Any
from typing import cast

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QApplication

from aas_editor.application.changes import observer_for
from aas_editor.application.file_transfer import transfer_commands
from aas_editor.application.operations.companions import ConceptChoice
from aas_editor.application.operations.companions import Companions
from aas_editor.application.operations.companions import concept_commands
from aas_editor.application.operations.companions import gather_companions
from aas_editor.application.operations.companions import plan_concepts
from aas_editor.application.operations.companions import (
    retarget_semantic_ids,
)
from aas_editor.application.operations.paste import PasteError
from aas_editor.application.operations.paste import PastePlan
from aas_editor.application.operations.paste import paste_commands
from aas_editor.application.operations.paste import plan_paste
from aas_editor.application.operations.paste import plan_paste_into_shell
from aas_editor.application.operations.paste import shell_paste_commands
from aas_editor.domain import containers
from aas_editor.domain.clipboard_json import ClipboardError
from aas_editor.domain.clipboard_json import load_objects
from aas_editor.domain.clipboard_json import looks_like_json
from aas_editor.domain.references import describe_object
from aas_editor.settings.app_settings import NAME_ROLE
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.app_settings import PACKAGE_ROLE
from aas_editor.ui import paste_dialogs
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.move_actions import container_of_row
from aas_editor.ui.move_actions import selected_rows

ABOVE_ID = "structure.paste_above"
BELOW_ID = "structure.paste_below"
INTO_ID = "structure.paste_into"
CLEAR_ID = "structure.clear_buffer"

# Rows of these attributes hold qualifiers or extensions, not elements.
_NOT_ELEMENTS = ("qualifier", "extension")


def buffer_objects(
    view: Any, allow_references: bool = False
) -> list[model.Referable]:
    """Returns the objects in the paste buffer of a view.

    Args:
        view: The tree view whose buffer is read.
        allow_references: Whether a model reference in the buffer is returned
            too. A reference is no element, but it can be pasted into an AAS.

    Raises:
        ClipboardError: If the buffer holds text that is no AAS object, with a
            message for the user.
    """
    clipboard = view.treeClipboard
    if clipboard.isEmpty():
        raise ClipboardError(
            "No sufficient information in the paste buffer or on the clipboard"
        )
    held = clipboard.objects[-1]
    entries = cast("list[Any]", held if isinstance(held, list) else [held])
    objects: list[model.Referable] = []
    for entry in entries:
        if isinstance(entry, str):
            if not looks_like_json(entry):
                raise ClipboardError(
                    "The clipboard holds text, not copied AAS elements"
                )
            objects.extend(load_objects(entry))
        elif isinstance(entry, model.Referable):
            objects.append(entry)
        elif allow_references and isinstance(entry, model.ModelReference):
            objects.append(cast("model.Referable", entry))
        else:
            raise ClipboardError(
                "The buffer holds something that is no element"
            )
    return objects


def child_container(index: QModelIndex) -> object | None:
    """Returns where a paste into the row puts its objects, or None.

    That is the elements of a submodel, collection, list, entity or annotated
    relationship, a set of variables of an operation, or the object store when
    the row is a node of shells, submodels or concept descriptions.
    """
    from aas_editor.utils.util_classes import ClassesInfo

    obj: Any = index.data(OBJECT_ROLE)
    if isinstance(obj, model.AbstractObjectStore | model.NamespaceSet):
        if index.data(NAME_ROLE) in _NOT_ELEMENTS:
            return None
        return cast("object", obj)
    attribute: str = ClassesInfo.changedParentObject(  # pyright: ignore[reportUnknownMemberType]
        type(obj)
    )
    held = getattr(obj, attribute, None) if attribute else None
    return (
        cast("object", held) if isinstance(held, model.NamespaceSet) else None
    )


def pasteCopyFor(view: Any, index: QModelIndex, obj: Any) -> Any:  # noqa: N802
    """Returns the copy that the existing Paste puts into the row (D13).

    The existing Paste adds the object of the buffer to the item, with a
    dialog for a missing attribute. This gives it a free name, so a second
    paste or a copy into the same collection does not fail.
    """
    if not isinstance(obj, model.Referable):
        return obj
    target = child_container(index)
    if target is None:
        return obj
    package: Any = index.data(PACKAGE_ROLE)
    taken: set[str] = (
        {item.id for item in package.objStore} if package is not None else set()
    )
    try:
        plan = plan_paste(
            target,
            [obj],
            keep_ids=view.treeClipboard.cut,
            taken_ids=taken,
        )
    except PasteError:
        return obj
    return plan.items[0].copy


def _has_buffer(context: ActionContext) -> bool:
    view: Any = context.view
    return not view.treeClipboard.isEmpty()


def _single_row(context: ActionContext) -> QModelIndex | None:
    rows = selected_rows(context)
    return rows[0] if len(rows) == 1 else None


def _can_paste_beside(context: ActionContext) -> bool:
    row = _single_row(context)
    if row is None or context.package is None or not _has_buffer(context):
        return False
    return container_of_row(row) is not None or isinstance(
        row.data(OBJECT_ROLE), model.Identifiable
    )


def _can_paste_into(context: ActionContext) -> bool:
    row = _single_row(context)
    return (
        row is not None
        and context.package is not None
        and _has_buffer(context)
        and (
            child_container(row) is not None
            or isinstance(row.data(OBJECT_ROLE), model.AssetAdministrationShell)
        )
    )


def _position(
    context: ActionContext, row: QModelIndex, below: bool
) -> tuple[object, int | None]:
    """Returns the container and the position for a paste beside a row."""
    container = container_of_row(row)
    if container is None:
        # Shells, submodels and concept descriptions have no order.
        package: Any = context.package
        return package.objStore, None
    members = containers.members_in_order(container)
    obj = row.data(OBJECT_ROLE)
    place = next(n for n, member in enumerate(members) if member is obj)
    return container, place + 1 if below else place


def _ask_companions(
    context: ActionContext,
    items: list[model.Referable],
    source: Any,
) -> tuple[list[Any], dict[str, str]] | None:
    """Asks about the concept descriptions of a copy from another package.

    Returns:
        The commands that add them and the ids that changed, or None if the
        user cancelled.
    """
    package: Any = context.package
    companions: Companions = gather_companions(items, source.objStore)
    plan = plan_concepts(companions, package.objStore)
    if not plan.to_add and not plan.conflicts:
        return [], {}
    wanted = paste_dialogs.ask_copy_concepts(plan, context.view)
    if wanted is None:
        return None
    if not wanted:
        return [], {}
    choices: dict[str, ConceptChoice] = {}
    for conflict in plan.conflicts:
        choice = paste_dialogs.ask_concept_conflict(conflict, context.view)
        if choice is None:
            return None
        choices[conflict.source.id] = choice
    return concept_commands(
        observer_for(package), package.objStore, plan, choices
    )


def _paste(context: ActionContext, where: str) -> None:
    package: Any = context.package
    stack = context.stack
    row = _single_row(context)
    if package is None or stack is None or row is None:
        return
    view: Any = context.view
    shell = row.data(OBJECT_ROLE)
    if where == "into" and isinstance(shell, model.AssetAdministrationShell):
        _paste_into_shell(context, row, shell)
        return
    try:
        items = buffer_objects(view)
        if where == "into":
            container = child_container(row)
            index = None
        else:
            container, index = _position(context, row, where == "below")
        buffer = view.treeClipboard
        plan: PastePlan = plan_paste(
            container,
            items,
            index,
            keep_ids=buffer.cut,
            taken_ids={o.id for o in package.objStore},
        )
        source = buffer.source
        companion_commands: list[Any] = []
        file_before: list[Any] = []
        file_after: list[Any] = []
        if (
            source is not None
            and source is not package
            and not isinstance(buffer.objects[-1], str)
        ):
            answer = _ask_companions(context, items, source)
            if answer is None:
                return
            companion_commands, renamed = answer
            copies = [item.copy for item in plan.items]
            retarget_semantic_ids(copies, renamed)
            # The files that the copies refer to come along, and the pasted
            # paths follow the names they get in this package.
            file_before, file_after = transfer_commands(
                observer_for(package),
                gather_companions(copies, source.objStore, True).files,
                source.fileStore,
                package.fileStore,
            )
        with stack.group(plan.description):
            for command in [*file_before, *companion_commands]:
                context.push(command)
            for command in paste_commands(observer_for(package), plan):
                context.push(command)
            for command in file_after:
                context.push(command)
    except (ClipboardError, PasteError) as error:
        paste_dialogs.show_problem(str(error), view)
        return
    except Exception as error:  # noqa: BLE001
        paste_dialogs.show_problem(f"The paste was refused: {error}", view)
        return
    # The next paste of a cut is a copy again: the objects are in the package.
    buffer.cut = False
    _select_pasted(context, row, where, [item.copy for item in plan.items])


def _paste_into_shell(
    context: ActionContext,
    row: QModelIndex,
    shell: model.AssetAdministrationShell,
) -> None:
    """Pastes Submodels, or references to them, into an AAS (F-EDT-08 AC11, 12).

    The Submodels and the references are one undo step. A reference the AAS
    holds already is skipped and said so. The concept descriptions and files of
    a Submodel from another package come along as in any other paste.
    """
    package: Any = context.package
    view: Any = context.view
    buffer = view.treeClipboard
    try:
        items = cast("list[Any]", buffer_objects(view, allow_references=True))
        source = buffer.source
        other = source if source is not None and source is not package else None
        plan = plan_paste_into_shell(
            shell,
            items,
            package.objStore,
            keep_ids=buffer.cut,
            source_objects=other.objStore if other is not None else None,
        )
        if plan.is_empty:
            paste_dialogs.show_problem(
                f"{describe_object(shell)} refers to "
                f"{'this Submodel' if len(plan.already_linked) == 1 else 'these Submodels'}"
                " already, so nothing was pasted.",
                view,
            )
            return
        copies = [item.copy for item in plan.copies]
        companion_commands: list[Any] = []
        file_before: list[Any] = []
        file_after: list[Any] = []
        if other is not None and copies:
            answer = _ask_companions(context, copies, other)
            if answer is None:
                return
            companion_commands, renamed = answer
            retarget_semantic_ids(copies, renamed)
            file_before, file_after = transfer_commands(
                observer_for(package),
                gather_companions(copies, other.objStore, True).files,
                other.fileStore,
                package.fileStore,
            )
        with context.stack.group(plan.description):  # pyright: ignore[reportOptionalMemberAccess]
            for command in [*file_before, *companion_commands]:
                context.push(command)
            for command in shell_paste_commands(observer_for(package), plan):
                context.push(command)
            for command in file_after:
                context.push(command)
    except (ClipboardError, PasteError) as error:
        paste_dialogs.show_problem(str(error), view)
        return
    except Exception as error:  # noqa: BLE001
        paste_dialogs.show_problem(f"The paste was refused: {error}", view)
        return
    buffer.cut = False
    if plan.dangling:
        paste_dialogs.show_problem(
            f"{len(plan.dangling)} pasted reference"
            f"{'s point' if len(plan.dangling) != 1 else ' points'} at a "
            "Submodel that is not in this package.",
            view,
        )
    _select_pasted(context, row, "into", copies)


def _select_pasted(
    context: ActionContext,
    row: QModelIndex,
    where: str,
    copies: Iterable[model.Referable],
) -> None:
    """Makes the last pasted object the current row, if the tree shows it."""
    parent = row if where == "into" else row.parent()
    model_ = context.view.model()
    if model_ is None or not copies:
        return
    last = list(copies)[-1]
    for number in range(model_.rowCount(parent)):
        child = model_.index(number, 0, parent)
        if child.data(OBJECT_ROLE) is last:
            context.view.setCurrentIndex(child)
            return


def _clear_buffer(context: ActionContext) -> None:
    view: Any = context.view
    view.treeClipboard.clear()
    clipboard = QApplication.clipboard()
    if clipboard is not None:
        clipboard.clear()
    view.updateActions(view.currentIndex())


def _runner(where: str):
    def run(context: ActionContext) -> None:
        _paste(context, where)

    return run


def register_paste_actions() -> None:
    """Adds the paste actions and Clear paste buffer to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    specs = (
        ActionSpec(
            action_id=ABOVE_ID,
            text="Paste above",
            run=_runner("above"),
            is_enabled=_can_paste_beside,
            views=ViewKind.PACKAGES,
            shortcut=QKeySequence("Ctrl+Alt+V"),
            status_tip="Insert the pasted elements before the selected one",
            toolbar=True,
            order=310,
        ),
        ActionSpec(
            action_id=BELOW_ID,
            text="Paste below",
            run=_runner("below"),
            is_enabled=_can_paste_beside,
            views=ViewKind.PACKAGES,
            shortcut=QKeySequence("Ctrl+Shift+V"),
            status_tip="Insert the pasted elements after the selected one",
            toolbar=True,
            order=311,
        ),
        ActionSpec(
            action_id=INTO_ID,
            text="Paste into",
            run=_runner("into"),
            is_enabled=_can_paste_into,
            views=ViewKind.PACKAGES,
            shortcut=QKeySequence("Ctrl+Shift+Alt+V"),
            status_tip="Add the pasted elements at the end of the selected one",
            order=312,
        ),
        ActionSpec(
            action_id=CLEAR_ID,
            text="Clear paste buffer",
            run=_clear_buffer,
            is_enabled=_has_buffer,
            mutates=False,
            views=ViewKind.ANY,
            status_tip="Empty the paste buffer and the system clipboard",
            order=313,
        ),
    )
    for spec in specs:
        if spec.action_id not in registered:
            register_action(spec)
