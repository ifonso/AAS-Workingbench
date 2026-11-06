"""The actions that add a qualifier, extension, or the like to the selection.

Call `register_preset_actions` once, before the first tree view exists. The
composition root does that.

Two sources feed the same plan (`application/operations/attach.py`):

- "Add ... from preset..." opens the list of presets. The files of the app are
  in `aas_editor/presets/`, and the files of the user in the `presets` folder
  next to `settings.ini`. See `aas_editor.domain.presets`.
- "Add ... from clipboard" reads one member or an array from the system
  clipboard through the SDK's JSON adapter, and refuses anything else with a
  message.

Every selected object that can have the kind gets its own copy. An object that
has the member already is skipped and named, and the others still get it. The
add is one undo step.
"""

from collections.abc import Callable
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QApplication

from aas_editor.application.changes import observer_for
from aas_editor.application.operations.attach import AttachPlan
from aas_editor.application.operations.attach import attach_commands
from aas_editor.application.operations.attach import can_hold
from aas_editor.application.operations.attach import plan_attach
from aas_editor.application.operations.paste_qualifier import (
    PasteQualifierError,
)
from aas_editor.application.operations.paste_qualifier import (
    paste_qualifier_commands,
)
from aas_editor.application.operations.paste_qualifier import (
    plan_paste_into_qualifier,
)
from aas_editor.domain.clipboard_json import ClipboardError
from aas_editor.domain.clipboard_json import load_members
from aas_editor.domain.member_json import Member
from aas_editor.domain.member_json import MemberKind
from aas_editor.domain.member_json import clone_member
from aas_editor.domain.references import describe_object
from aas_editor.infrastructure.preset_files import SHIPPED_PRESETS_DIR
from aas_editor.infrastructure.preset_files import load_presets
from aas_editor.settings.app_settings import NAME_ROLE
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.settings.app_settings import SETTINGS_FILE
from aas_editor.ui import bulk_dialogs
from aas_editor.ui import preset_dialogs
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.bulk_edit_actions import run_group
from aas_editor.ui.move_actions import selected_rows

_MAX_REASONS = 6


def user_presets_dir() -> Path:
    """Returns the folder with the preset files of the user."""
    return SETTINGS_FILE.parent / "presets"


def _owners(context: ActionContext, kind: MemberKind) -> list[Any]:
    """Returns the objects that would get the members, one for each row.

    A row can be the owner itself, or the row of the attribute that holds the
    members (named `qualifier`, `extension`, and so on), which stands for
    the owner above it. That is how a tab with the attributes of an object
    shows them.
    """
    owners: list[Any] = []
    for index in selected_rows(context):
        obj = index.data(OBJECT_ROLE)
        if obj is None:
            continue
        parent = index.parent()
        if (
            not can_hold(obj, kind)
            and parent.isValid()
            and index.data(NAME_ROLE) == kind.attribute
        ):
            obj = parent.data(OBJECT_ROLE)
        if obj is not None and not any(obj is held for held in owners):
            owners.append(obj)
    return owners


def _can_add(kind: MemberKind) -> Callable[[ActionContext], bool]:
    def check(context: ActionContext) -> bool:
        return context.package is not None and any(
            can_hold(obj, kind) for obj in _owners(context, kind)
        )

    return check


def _attach(
    context: ActionContext,
    kind: MemberKind,
    make: Callable[[], Sequence[Member]],
) -> None:
    """Plans, confirms when something is skipped, and adds."""
    package: Any = context.package
    title = f"Add {kind.label}"
    if package is None:
        return
    try:
        plan = plan_attach(_owners(context, kind), kind, make)
    except ValueError as error:
        bulk_dialogs.show_problem(title, str(error), context.view)
        return
    if not plan.can_apply:
        bulk_dialogs.show_problem(title, _nothing_to_add(plan), context.view)
        return
    if plan.skipped and not bulk_dialogs.confirm_attach(plan, context.view):
        return
    run_group(
        context,
        title,
        plan.description,
        attach_commands(observer_for(package), plan),
    )


def _nothing_to_add(plan: AttachPlan) -> str:
    reasons = [
        f"{describe_object(entry.owner)}: {entry.reason}"
        for entry in plan.skipped[:_MAX_REASONS]
    ]
    more = plan.skipped_count - len(reasons)
    if more > 0:
        reasons.append(f"and {more} more")
    return "Nothing can be added.\n" + "\n".join(reasons)


def _from_preset(kind: MemberKind) -> Callable[[ActionContext], None]:
    def run(context: ActionContext) -> None:
        directory = user_presets_dir()
        loaded = load_presets(kind, SHIPPED_PRESETS_DIR, directory)
        choice = preset_dialogs.ask_preset(
            kind, loaded, directory, context.view
        )
        if choice is None:
            return
        preset, value = choice
        _attach(context, kind, lambda: [preset.make(value)])

    return run


def _from_clipboard(kind: MemberKind) -> Callable[[ActionContext], None]:
    def run(context: ActionContext) -> None:
        text = QApplication.clipboard().text()  # pyright: ignore[reportOptionalMemberAccess]
        try:
            members = load_members(text, kind)
        except ClipboardError as error:
            bulk_dialogs.show_problem(
                f"Add {kind.label}", str(error), context.view
            )
            return
        _attach(context, kind, lambda: [clone_member(m, kind) for m in members])

    return run


PASTE_QUALIFIER_ID = "clipboard.paste_qualifier"


def _selected_qualifier(context: ActionContext) -> model.Qualifier | None:
    """Returns the one qualifier that the selection is, or None."""
    rows = selected_rows(context)
    if len(rows) != 1:
        return None
    obj = rows[0].data(OBJECT_ROLE)
    return obj if isinstance(obj, model.Qualifier) else None


def _can_paste_into_qualifier(context: ActionContext) -> bool:
    return (
        context.package is not None and _selected_qualifier(context) is not None
    )


def _paste_into_qualifier(context: ActionContext) -> None:
    """Takes the qualifier on the clipboard into the selected qualifier.

    The kind stays as the selected qualifier has it (F-EDT-07 AC5). A text
    that is no qualifier, and a type that another qualifier has, are refused
    with a message and change nothing (AC4).
    """
    target = _selected_qualifier(context)
    package: Any = context.package
    title = "Paste into qualifier"
    if target is None or package is None:
        return
    text = QApplication.clipboard().text()  # pyright: ignore[reportOptionalMemberAccess]
    try:
        members = load_members(text, MemberKind.QUALIFIER)
        if len(members) != 1:
            raise ClipboardError(
                f"The clipboard has {len(members)} qualifiers. Paste into a "
                "qualifier takes one"
            )
        pasted = members[0]
        assert isinstance(pasted, model.Qualifier)
        plan = plan_paste_into_qualifier(target, pasted)
        commands = paste_qualifier_commands(observer_for(package), plan)
    except (ClipboardError, PasteQualifierError) as error:
        bulk_dialogs.show_problem(title, str(error), context.view)
        return
    run_group(context, title, plan.description, commands)


_PRESETS = (
    (MemberKind.QUALIFIER, "qualifier", 440),
    (MemberKind.EXTENSION, "extension", 441),
    (MemberKind.SPECIFIC_ASSET_ID, "specific_asset_id", 442),
    (MemberKind.EMBEDDED_DATA_SPECIFICATION, "data_specification", 443),
)
_CLIPBOARD = (
    (MemberKind.QUALIFIER, "qualifier", 450),
    (MemberKind.EXTENSION, "extension", 451),
    (MemberKind.SPECIFIC_ASSET_ID, "specific_asset_id", 452),
)


def register_preset_actions() -> None:
    """Adds the actions for presets and the clipboard, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    specs: list[ActionSpec] = []
    for kind, name, order in _PRESETS:
        specs.append(
            ActionSpec(
                action_id=f"preset.add_{name}",
                text=f"Add {kind.label} from preset...",
                run=_from_preset(kind),
                is_enabled=_can_add(kind),
                views=ViewKind.ANY,
                status_tip=f"Add a {kind.label} from the list of presets to "
                "the selected objects",
                order=order,
            )
        )
    for kind, name, order in _CLIPBOARD:
        specs.append(
            ActionSpec(
                action_id=f"clipboard.add_{name}",
                text=f"Add {kind.label} from clipboard",
                run=_from_clipboard(kind),
                is_enabled=_can_add(kind),
                views=ViewKind.ANY,
                status_tip=f"Add the {kind.label} on the clipboard (JSON) "
                "to the selected objects",
                order=order,
            )
        )
    specs.append(
        ActionSpec(
            action_id=PASTE_QUALIFIER_ID,
            text="Paste qualifier from clipboard into this qualifier",
            run=_paste_into_qualifier,
            is_enabled=_can_paste_into_qualifier,
            views=ViewKind.ANY,
            status_tip="Take the type, value, and semantic ids of the "
            "qualifier on the clipboard (JSON). The kind stays",
            order=453,
        )
    )
    for spec in specs:
        if spec.action_id not in registered:
            register_action(spec)
