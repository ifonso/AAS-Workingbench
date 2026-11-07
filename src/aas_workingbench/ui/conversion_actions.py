"""The context menu actions that replace an element by a new one.

* "Convert to another element type..." turns a Property into a Range, a
  collection into a list, and so on (F-EDT-04 Refactor). What the new type
  cannot hold is shown before anything changes.
* "Change list settings..." rebuilds a SubmodelElementList with another item
  type, value type, semantic id, or order flag, which the SDK fixes when the
  list is made.

Both are one undo step, keep the position of the element, and keep the
references to it valid. The decisions are in `aas_workingbench.domain.conversion`
and `aas_workingbench.domain.list_settings`, and the swap is in
`aas_workingbench.application.operations.replace`. This module asks the questions.
Call `register_conversion_actions` once, before the first tree view exists.
"""

import io
from typing import Any
from typing import Protocol
from typing import cast

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QPersistentModelIndex

from aas_workingbench.application.changes import observer_for
from aas_workingbench.application.commands import ReadOnlyError
from aas_workingbench.application.operations.replace import (
    plan_reference_updates,
)
from aas_workingbench.application.operations.replace import replacement_command
from aas_workingbench.domain.conversion import plan_conversion
from aas_workingbench.domain.conversion import refusal_for
from aas_workingbench.domain.conversion import targets_for
from aas_workingbench.domain.element_copy import item_name
from aas_workingbench.domain.list_settings import plan_list_rebuild
from aas_workingbench.domain.replacement import ConversionRefused
from aas_workingbench.domain.replacement import ReplacementPlan
from aas_workingbench.settings.app_settings import OBJECT_ROLE
from aas_workingbench.ui import reference_dialogs
from aas_workingbench.ui import replacement_dialogs
from aas_workingbench.ui.actions import ActionContext
from aas_workingbench.ui.actions import ActionSpec
from aas_workingbench.ui.actions import ViewKind
from aas_workingbench.ui.actions import register_action

CONVERT_ACTION_ID = "conversion.convert"
LIST_SETTINGS_ACTION_ID = "conversion.list_settings"

_registered = False


class _Package(Protocol):
    """What the actions need from a package."""

    objStore: Any  # noqa: N815
    fileStore: Any  # noqa: N815


def register_conversion_actions() -> None:
    """Adds the actions of this module to the registry, once."""
    global _registered  # noqa: PLW0603
    if _registered:
        return
    _registered = True
    for spec in _SPECS:
        register_action(spec)


def _element(context: ActionContext) -> model.SubmodelElement | None:
    if not context.index.isValid() or context.package is None:
        return None
    obj = context.index.data(OBJECT_ROLE)
    return obj if isinstance(obj, model.SubmodelElement) else None


def _item_list(
    context: ActionContext,
) -> "model.SubmodelElementList[Any] | None":
    element = _element(context)
    if isinstance(element, model.SubmodelElementList):
        return cast("model.SubmodelElementList[Any]", element)
    return None


def _is_element(context: ActionContext) -> bool:
    return _element(context) is not None


def _is_list(context: ActionContext) -> bool:
    return _item_list(context) is not None


def _package(context: ActionContext) -> _Package:
    return cast("_Package", context.package)


def _run_convert(context: ActionContext) -> None:
    element = _element(context)
    if element is None:
        return
    title = "Convert to another element type"
    reason = refusal_for(element)
    if reason is not None:
        reference_dialogs.show_message(title, reason, context.view)
        return
    target = replacement_dialogs.choose_target(
        element, targets_for(element), context.view
    )
    if target is None:
        return
    file_content = None
    if isinstance(element, model.File) and target is model.Blob:
        cancelled, file_content = _ask_file_content(context, element)
        if cancelled:
            return
    try:
        plan = plan_conversion(element, target, file_content=file_content)
    except ConversionRefused as error:
        reference_dialogs.show_message(title, str(error), context.view)
        return
    intro = (
        f"Converting {type(element).__name__} '{item_name(element)}' to "
        f"{target.__name__} loses what the new type cannot hold:"
        if plan.has_losses
        else "The new element lacks nothing the old one has."
    )
    _apply(context, plan, title, intro, "Convert")


def _ask_file_content(
    context: ActionContext, element: model.File
) -> tuple[bool, bytes | None]:
    """Asks whether the Blob gets the content of the stored file.

    Returns:
        Whether the user cancelled, and the bytes to copy, or None to keep
        the path as text.
    """
    content = _stored_content(_package(context), element.value)
    if not content:
        return False, None
    answer = replacement_dialogs.ask_use_file_content(
        element.value or "", len(content), context.view
    )
    if answer is None:
        return True, None
    return False, content if answer else None


def _stored_content(package: _Package, path: str | None) -> bytes | None:
    store = getattr(package, "fileStore", None)
    if store is None or not path or path not in store:
        return None
    buffer = io.BytesIO()
    store.write_file(path, buffer)
    return buffer.getvalue()


def _run_list_settings(context: ActionContext) -> None:
    item_list = _item_list(context)
    if item_list is None:
        return
    title = "Change list settings"
    settings = replacement_dialogs.ask_list_settings(item_list, context.view)
    if settings is None:
        return
    try:
        plan = plan_list_rebuild(item_list, settings)
    except ConversionRefused as error:
        reference_dialogs.show_message(title, str(error), context.view)
        return
    intro = (
        f"The list '{item_name(item_list)}' is made again with the new "
        "settings. These items do not fit them:"
        if plan.has_losses
        else "Every item fits the new settings."
    )
    _apply(context, plan, title, intro, "Rebuild list")


def _apply(
    context: ActionContext,
    plan: ReplacementPlan,
    title: str,
    intro: str,
    accept_text: str,
) -> None:
    """Asks about the losses, if there are any, and pushes the step."""
    package = _package(context)
    updates = plan_reference_updates(package.objStore, plan)
    if plan.has_losses or updates.orphaned or updates.not_updated:
        if not replacement_dialogs.confirm_replacement(
            title, intro, plan, updates, accept_text, context.view
        ):
            return
    parent = QPersistentModelIndex(context.index.parent())
    step = replacement_command(observer_for(context.package), plan, updates)
    try:
        context.push(step)
    except (ReadOnlyError, model.AASConstraintViolation) as error:
        reference_dialogs.show_message(title, str(error), context.view)
        return
    if step.new is not None:
        _select(context, QModelIndex(parent), step.new)


def _select(
    context: ActionContext, parent: QModelIndex, element: object
) -> None:
    """Makes the row of an element the current row of the view."""
    model_ = context.view.model()
    if model_ is None:
        return
    for row in range(model_.rowCount(parent)):
        index = model_.index(row, 0, parent)
        if index.data(OBJECT_ROLE) is element:
            context.view.setCurrentIndex(index)
            return


_SPECS = (
    ActionSpec(
        action_id=CONVERT_ACTION_ID,
        text="Convert to another element type...",
        run=_run_convert,
        is_enabled=_is_element,
        views=ViewKind.PACKAGES,
        status_tip="Make the element another type, and see what is lost first",
        order=400,
    ),
    ActionSpec(
        action_id=LIST_SETTINGS_ACTION_ID,
        text="Change list settings...",
        run=_run_list_settings,
        is_enabled=_is_list,
        views=ViewKind.PACKAGES,
        status_tip=(
            "Rebuild the list with another item type, value type, semantic id,"
            " or order"
        ),
        order=410,
    ),
)
