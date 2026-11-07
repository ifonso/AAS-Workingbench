"""The actions of the package tree that keep references intact.

Call `register_reference_actions` once, before the first tree view exists. The
composition root does that. The actions are:

- Rename id, for shells, submodels and concept descriptions (D10), with a
  preview of the references that follow.
- Rename idShort, for elements, with the same preview, and a Fix button for
  text that is not a valid idShort.
- Sync idShort, which copies an idShort to the concept description of an
  element.
- Fix References, which repairs the references of a package or an object.

An edit of an id or idShort in a cell goes through the same plans. The
functions `rename_command` and `replace_command` build the command for it.
"""

from collections.abc import Callable
from collections.abc import Iterable
from typing import Protocol
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.commands import ReadOnlyError
from aas_workingbench.application.operations.fix import plan_fix_references
from aas_workingbench.application.operations.fix import sync_id_short_commands
from aas_workingbench.application.operations.references import (
    reference_commands,
)
from aas_workingbench.application.operations.rename import InvalidIdShortError
from aas_workingbench.application.operations.rename import RenameCommand
from aas_workingbench.application.operations.rename import RenameError
from aas_workingbench.application.operations.rename import RenamePlan
from aas_workingbench.application.operations.rename import ReplaceIdentifiable
from aas_workingbench.application.operations.rename import plan_rename_id
from aas_workingbench.application.operations.rename import plan_rename_id_short
from aas_workingbench.application.operations.rename import suggest_id_short
from aas_workingbench.domain.references import describe_object
from aas_workingbench.domain.references import describe_reference
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui import reference_dialogs
from aas_workingbench.ui.actions import ActionContext
from aas_workingbench.ui.actions import ActionSpec
from aas_workingbench.ui.actions import ViewKind
from aas_workingbench.ui.actions import register_action
from aas_workingbench.ui.user_defaults import id_generator
from aas_workingbench.ui.user_defaults import id_kind_of

_registered = False


class EditCancelled(Exception):  # noqa: N818
    """The user cancelled a question while editing an id or idShort."""


class _Package(Protocol):
    """What the actions need from a package."""

    objStore: Iterable[model.Identifiable]  # noqa: N815


def register_reference_actions() -> None:
    """Adds the actions of this module to the registry, once."""
    global _registered  # noqa: PLW0603
    if _registered:
        return
    _registered = True
    for spec in _SPECS:
        register_action(spec)


def rename_command(
    package: _Package,
    owner: object,
    attribute: str,
    value: str,
    origin: object | None,
    parent: QWidget | None = None,
) -> RenameCommand | None:
    """Builds the command for an id or idShort typed in a cell.

    An idShort that is not valid, or that a sibling has, offers the suggestion
    of the plan. A rename that updates references shows its preview first.

    Args:
        package: The package that holds the object.
        owner: The shell, submodel, concept description or element.
        attribute: `id` or `id_short`.
        value: The new value.
        origin: The model that makes the edit, which then updates itself.
        parent: The parent widget of the dialogs.

    Returns:
        The command, or None if nothing changes.

    Raises:
        EditCancelled: If the user cancelled a question.
        RenameError: If the value cannot be used, such as an id that another
            object has.
    """
    objects = list(package.objStore)
    if attribute == "id" and isinstance(owner, model.Identifiable):
        plan = plan_rename_id(objects, owner, value)
    elif attribute == "id_short" and isinstance(owner, model.Referable):
        try:
            plan = plan_rename_id_short(objects, owner, value)
        except InvalidIdShortError as error:
            if not reference_dialogs.confirm_suggested_id_short(error, parent):
                raise EditCancelled from error
            plan = plan_rename_id_short(objects, owner, error.suggestion)
    else:
        raise TypeError(f"Cannot rename {attribute} of {owner!r}")
    if plan.is_noop:
        return None
    if not reference_dialogs.confirm_rename(plan, parent):
        raise EditCancelled
    return RenameCommand(observer_for(package), plan, origin)


def replace_command(
    package: _Package,
    container: object,
    old: model.Identifiable,
    new: model.Identifiable,
    origin: object | None,
    parent: QWidget | None = None,
) -> ReplaceIdentifiable:
    """Builds the command that replaces an object by one with another id.

    The references to the old id get the new one. A replace that updates
    references shows the preview first.

    Args:
        package: The package that holds the objects.
        container: The object store of the package.
        old: The object to replace.
        new: The object that takes its place.
        origin: The model that makes the edit, which then updates itself.
        parent: The parent widget of the dialogs.

    Returns:
        The command.

    Raises:
        EditCancelled: If the user cancelled the preview.
        DuplicateIdError: If another object has the id of `new`.
    """
    command = ReplaceIdentifiable(
        observer_for(package),
        list(package.objStore),
        container,
        old,
        new,
        origin,
    )
    if command.changes and not reference_dialogs.confirm_reference_changes(
        "Replace object",
        f"The new object has the id '{new.id}'. These references to"
        f" '{old.id}' are updated:",
        command.changes,
        parent=parent,
    ):
        raise EditCancelled
    return command


def _object(context: ActionContext) -> object | None:
    if not context.index.isValid() or context.package is None:
        return None
    return cast("object | None", context.index.data(OBJECT_ROLE))


def _package(context: ActionContext) -> _Package:
    return cast("_Package", context.package)


def _is_identifiable(context: ActionContext) -> bool:
    return isinstance(_object(context), model.Identifiable)


def _is_renamable(context: ActionContext) -> bool:
    obj = _object(context)
    return isinstance(obj, model.Referable) and not isinstance(
        obj.parent, model.SubmodelElementList
    )


def _can_sync(context: ActionContext) -> bool:
    obj = _object(context)
    return isinstance(obj, ConceptDescription) or (
        isinstance(obj, model.SubmodelElement) and obj.semantic_id is not None
    )


def _has_package(context: ActionContext) -> bool:
    return context.package is not None and context.index.isValid()


def _run_rename_id(context: ActionContext) -> None:
    target = _object(context)
    if not isinstance(target, model.Identifiable):
        return
    objects = list(_package(context).objStore)
    _ask_and_push(
        context,
        "Rename id",
        "New id",
        target.id,
        lambda text: plan_rename_id(objects, target, text),
        None,
        id_generator(id_kind_of(target)),
    )


def _run_rename_id_short(context: ActionContext) -> None:
    target = _object(context)
    if not isinstance(target, model.Referable):
        return
    objects = list(_package(context).objStore)
    _ask_and_push(
        context,
        "Rename idShort",
        "New idShort",
        target.id_short or "",
        lambda text: plan_rename_id_short(objects, target, text),
        lambda text: suggest_id_short(target, text),
        None,
    )


def _ask_and_push(
    context: ActionContext,
    title: str,
    label: str,
    text: str,
    plan_for: Callable[[str], RenamePlan],
    suggest: Callable[[str], str] | None,
    generate: Callable[[], str] | None,
) -> None:
    plan = reference_dialogs.ask_rename(
        title, label, text, plan_for, suggest, generate, context.view
    )
    if plan is None:
        return
    _push(context, RenameCommand(observer_for(context.package), plan))


def _run_sync(context: ActionContext) -> None:
    target = _object(context)
    if not isinstance(target, model.Referable):
        return
    commands = sync_id_short_commands(
        observer_for(context.package), _package(context).objStore, target
    )
    if not commands:
        reference_dialogs.show_message(
            "Sync idShort",
            "Nothing to fill in. The concept description has its idShort and"
            " short name already, or there is no concept description.",
            context.view,
        )
        return
    if context.stack is None:
        return
    try:
        with context.stack.group(f"Sync idShort of {describe_object(target)}"):
            for command in commands:
                context.stack.push(command)
    except ReadOnlyError as error:
        reference_dialogs.show_message("Sync idShort", str(error), context.view)


def _run_fix_references(context: ActionContext) -> None:
    target = _object(context)
    roots = [target] if isinstance(target, model.Identifiable) else None
    plan = plan_fix_references(_package(context).objStore, roots)
    notes = [
        f"Cannot be repaired: {item.slot.location} ->"
        f" {describe_reference(item.reference)}. {item.reason}."
        for item in plan.unfixable
    ]
    if not plan.changes:
        message = "No reference needs to be repaired."
        if notes:
            message = f"{message}\n\n" + "\n".join(notes)
        reference_dialogs.show_message("Fix References", message, context.view)
        return
    intro = (
        "These references name an object by its idShort, or by the wrong"
        " type. Fix References replaces them by what the SDK would write:"
    )
    if not reference_dialogs.confirm_reference_changes(
        "Fix References",
        intro,
        plan.changes,
        notes,
        "Fix References",
        context.view,
    ):
        return
    if context.stack is None:
        return
    try:
        with context.stack.group("Fix References"):
            for command in reference_commands(
                observer_for(context.package), plan.changes
            ):
                context.stack.push(command)
    except ReadOnlyError as error:
        reference_dialogs.show_message(
            "Fix References", str(error), context.view
        )


def _push(context: ActionContext, command: RenameCommand) -> None:
    try:
        context.push(command)
    except (ReadOnlyError, RenameError, model.AASConstraintViolation) as error:
        reference_dialogs.show_message("Rename", str(error), context.view)


_SPECS = (
    ActionSpec(
        action_id="references.rename_id",
        text="Rename id...",
        run=_run_rename_id,
        is_enabled=_is_identifiable,
        views=ViewKind.PACKAGES,
        status_tip="Change the id and update the references to it",
        order=300,
    ),
    ActionSpec(
        action_id="references.rename_id_short",
        text="Rename idShort...",
        run=_run_rename_id_short,
        is_enabled=_is_renamable,
        views=ViewKind.PACKAGES,
        status_tip="Change the idShort and update the references through it",
        order=310,
    ),
    ActionSpec(
        action_id="references.sync_id_short",
        text="Sync idShort",
        run=_run_sync,
        is_enabled=_can_sync,
        views=ViewKind.PACKAGES,
        status_tip="Copy the idShort to the concept description",
        order=320,
    ),
    ActionSpec(
        action_id="references.fix_references",
        text="Fix References...",
        run=_run_fix_references,
        is_enabled=_has_package,
        views=ViewKind.PACKAGES,
        status_tip="Repair references that name an object by its idShort",
        order=330,
    ),
)
