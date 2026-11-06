"""The actions for concept descriptions, in the context menu of the package tree.

Call `register_concept_actions` once, before the first tree view exists. The
composition root does that. The actions are:

- **Create concept description**, from the semantic id of the selected
  submodel or element, and **from all semantic ids** below the selection.
- **Assign concept description**, which sets the semantic id of the selection
  to a description of the package, after asking when it replaces one.
- **Auto-detect concept descriptions**, which gives an element without a
  semantic id the description with its idShort (see `plan_detect`).
- **Create from value list**, one description for each pair of a value list.
- **Delete invalid concept descriptions**, through the delete flow, so the
  usages are shown.
- **Add**, **edit** and **clean up IEC 61360 record**, **fix data
  specification keys**, and **import value list**, for a description.
- **Order concept descriptions**, which changes the view only (D16).

Every change is one step of the undo history of the package. The plans decide
what happens, and the dialogs only show it.
"""

from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from typing import cast

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QInputDialog

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import Command
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import RemoveMember
from aas_editor.application.operations import concepts as ops
from aas_editor.application.operations import data_specs
from aas_editor.application.operations import sort_concepts as sorting
from aas_editor.domain.concept_order import ConceptOrder
from aas_editor.domain.concept_order import ranks_for
from aas_editor.domain.concepts import SemanticHolder
from aas_editor.domain.concepts import children_of
from aas_editor.domain.concepts import holders_of
from aas_editor.domain.concepts import new_empty_concept
from aas_editor.domain.data_specifications import Iec61360Draft
from aas_editor.domain.data_specifications import build_content
from aas_editor.domain.data_specifications import build_record
from aas_editor.domain.data_specifications import draft_of
from aas_editor.domain.data_specifications import empty_attributes
from aas_editor.domain.references import describe_object
from aas_editor.domain.references import describe_reference
from aas_editor.settings.app_settings import NAME_ROLE
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui import concept_dialogs
from aas_editor.ui import reference_dialogs
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import register_action
from aas_editor.ui.delete_flow import DeleteCancelled
from aas_editor.ui.delete_flow import prepare_delete
from aas_editor.ui.iec61360_dialog import ask_iec61360
from aas_editor.ui.tree_navigation import select_object
from aas_editor.ui.user_defaults import first_default_language
from aas_editor.ui.value_list_dialog import ask_value_list

TITLE = concept_dialogs.TITLE
ORDER_TITLE = "Order concept descriptions"

_registered = False


def register_concept_actions() -> None:
    """Adds the actions of this module to the registry, once."""
    global _registered  # noqa: PLW0603
    if _registered:
        return
    _registered = True
    for spec in _SPECS:
        register_action(spec)


# What the context holds


def _objects(context: ActionContext) -> list[object]:
    """Returns the object of each selected row, once, in order."""
    seen: set[int] = set()
    found: list[object] = []
    indexes: Iterable[QModelIndex] = context.selection or (context.index,)
    for index in indexes:
        if not index.isValid():
            continue
        obj = cast("object | None", index.data(OBJECT_ROLE))
        if obj is not None and id(obj) not in seen:
            seen.add(id(obj))
            found.append(obj)
    return found


def _holder_roots(context: ActionContext) -> list[model.Referable]:
    return [
        o
        for o in _objects(context)
        if isinstance(o, (model.Submodel, model.SubmodelElement))
    ]


def _concept(context: ActionContext) -> ConceptDescription | None:
    objects = _objects(context)
    if len(objects) == 1 and isinstance(objects[0], ConceptDescription):
        return objects[0]
    return None


def _store(context: ActionContext) -> Any:
    return cast("Any", context.package).objStore


def _all_objects(context: ActionContext) -> list[model.Identifiable]:
    return list(_store(context))


def _show(context: ActionContext, text: str, title: str = TITLE) -> None:
    reference_dialogs.show_message(title, text, context.view)


def _push(
    context: ActionContext, description: str, commands: list[Command]
) -> bool:
    """Pushes commands as one step. Tells the user why it did not work."""
    if context.stack is None or not commands:
        return False
    try:
        with context.stack.group(description):
            for command in commands:
                context.stack.push(command)
    except ReadOnlyError as error:
        _show(context, str(error))
        return False
    except (model.AASConstraintViolation, ValueError, KeyError) as error:
        _show(context, f"The change was refused: {error}")
        return False
    return True


# Rules for enabling


def _has_package(context: ActionContext) -> bool:
    return context.package is not None and context.index.isValid()


def _can_hold_semantics(context: ActionContext) -> bool:
    return _has_package(context) and bool(_holder_roots(context))


def _is_single_holder(context: ActionContext) -> bool:
    """Tells whether one submodel or element is selected.

    The action that creates a description for its semantic id is on for any
    such row, also one with no semantic id, and says why it cannot work then
    (F-EDT-11 AC16). Off in the menu it said nothing.
    """
    return _has_package(context) and len(_holder_roots(context)) == 1


def _can_create_empty(context: ActionContext) -> bool:
    return _has_package(context) and (
        _in_concept_area(context) or bool(_holder_roots(context))
    )


def _has_children(context: ActionContext) -> bool:
    return _has_package(context) and any(
        isinstance(root, model.Submodel) or any(True for _ in children_of(root))
        for root in _holder_roots(context)
    )


def _is_concept(context: ActionContext) -> bool:
    return _has_package(context) and _concept(context) is not None


def _has_value_pairs(context: ActionContext) -> bool:
    concept = _concept(context)
    return concept is not None and bool(ops.value_pairs_of(concept))


def _has_record(context: ActionContext) -> bool:
    concept = _concept(context)
    return concept is not None and bool(data_specs.iec_records(concept))


def _has_empty_attributes(context: ActionContext) -> bool:
    concept = _concept(context)
    return concept is not None and any(
        empty_attributes(content)
        for _, content in data_specs.iec_records(concept)
    )


def _in_concept_area(context: ActionContext) -> bool:
    """Tells whether the row is the concept descriptions or one of them."""
    return _has_package(context) and (
        context.index.data(NAME_ROLE) == "concept_descriptions"
        or any(isinstance(o, ConceptDescription) for o in _objects(context))
    )


def _can_sort(context: ActionContext) -> bool:
    return _in_concept_area(context) and hasattr(
        context.view.model(), "setConceptOrder"
    )


# Creating


def _run_create_from_semantic_id(context: ActionContext) -> None:
    roots = _holder_roots(context)
    plan = ops.plan_create(
        _all_objects(context),
        roots,
        adaptive=True,
        below=False,
        language=first_default_language(),
    )
    if not plan.new:
        _show(context, _why_nothing_created(plan, roots))
        return
    commands = ops.create_commands(
        observer_for(context.package), _store(context), plan
    )
    _push(context, f"Create concept description {plan.new[0].id}", commands)


def _why_nothing_created(
    plan: ops.CreatePlan, roots: list[model.Referable]
) -> str:
    if plan.existing:
        concept = plan.existing[0][1]
        return (
            "The semantic id names a concept description that the package "
            f"has already: {describe_object(concept)}."
        )
    if plan.conflicts:
        _, other = plan.conflicts[0]
        return (
            "The id of the semantic id belongs to "
            f"{describe_object(other)}, which is not a concept description."
        )
    name = describe_object(roots[0]) if roots else "the selection"
    return (
        "Cannot create a concept description because no valid semantic id is "
        f"present in {name}."
    )


def _run_create_from_all(context: ActionContext) -> None:
    roots = _holder_roots(context)
    language = first_default_language()
    plan = ops.plan_create(
        _all_objects(context), roots, adaptive=True, language=language
    )
    if not plan.new:
        _show(context, f"Nothing to create. {plan.summary}")
        return
    adaptive = concept_dialogs.ask_create_kind(plan.summary, context.view)
    if adaptive is None:
        return
    if not adaptive:
        plan = ops.plan_create(
            _all_objects(context), roots, adaptive=False, language=language
        )
    commands = ops.create_commands(
        observer_for(context.package), _store(context), plan
    )
    _push(context, f"Create {len(plan.new)} concept descriptions", commands)


def _run_create_empty(context: ActionContext) -> None:
    """Adds a description with a generated id, and selects it.

    The semantic id of a selected element stays as it is (F-EDT-11 AC15).
    Assign concept description puts the new description in it afterwards.
    """
    concept = new_empty_concept()
    command = AddMember(
        observer_for(context.package),
        _store(context),
        concept,
        description="Create empty concept description",
    )
    if _push(context, command.description, [command]):
        select_object(context.view, concept, context.package)


def _run_from_pairs(context: ActionContext) -> None:
    concept = _concept(context)
    if concept is None:
        return
    plan = ops.plan_from_pairs(
        _all_objects(context), concept, first_default_language()
    )
    if not plan.new:
        notes = [f"{pair.value}: {reason}" for pair, reason in plan.skipped]
        _show(
            context, "\n".join([f"Nothing to create. {plan.summary}", *notes])
        )
        return
    rows = [
        [pair.value, created.id, created.id_short or ""]
        for pair, created in plan.new
    ]
    notes = [f"Skipped {pair.value}: {reason}" for pair, reason in plan.skipped]
    notes += [
        f"{pair.value}: {describe_object(found)} has the id already"
        for pair, found in plan.existing
    ]
    if not concept_dialogs.confirm_preview(
        "Create concept descriptions from the value list",
        f"{plan.summary} The value list stays as it is.",
        ["Value", "Id", "idShort"],
        rows,
        notes,
        "Create",
        context.view,
    ):
        return
    commands = ops.from_pairs_commands(
        observer_for(context.package), _store(context), plan
    )
    _push(context, f"Create {len(plan.new)} concept descriptions", commands)


# Assigning


def _name(holder: SemanticHolder) -> str:
    return describe_object(holder.owner)


def _run_assign(context: ActionContext) -> None:
    holders = holders_of(_holder_roots(context), below=False)
    concepts = sorted(
        (o for o in _all_objects(context) if isinstance(o, ConceptDescription)),
        key=lambda c: ((c.id_short or "").lower(), c.id),
    )
    if not concepts:
        _show(
            context,
            "The package has no concept descriptions. Create one from a "
            "semantic id, or add one, first.",
        )
        return
    current = (
        "The element has no semantic id."
        if len(holders) != 1 or holders[0].reference is None
        else "The semantic id now is "
        f"{describe_reference(holders[0].reference)}."
    )
    chosen = concept_dialogs.ask_concept(concepts, current, context.view)
    if chosen is None:
        return
    plans = [ops.plan_assign(holder, chosen) for holder in holders]
    replaced = [plan for plan in plans if plan.replaces]
    if replaced and not concept_dialogs.confirm_replace_semantic_ids(
        [
            f"{_name(plan.holder)}: "
            f"{describe_reference(cast('model.Reference', plan.previous))} -> "
            f"{chosen.id}"
            for plan in replaced
        ],
        context.view,
    ):
        return
    commands = ops.assign_commands(observer_for(context.package), plans)
    if not commands:
        _show(context, "The element has this semantic id already.")
        return
    _push(context, "Assign concept description", commands)


def _run_auto_detect(context: ActionContext) -> None:
    plan = ops.plan_detect(_all_objects(context), _holder_roots(context))
    if not plan.assign:
        _show(context, f"Nothing to assign. {plan.summary}")
        return
    rows = [
        [_name(item.holder), item.concept.id_short or "", item.concept.id]
        for item in plan.assign
    ]
    notes = [
        f"{_name(holder)} matches {len(found)} concept descriptions: "
        f"{', '.join(c.id for c in found)}"
        for holder, found in plan.ambiguous
    ]
    if not concept_dialogs.confirm_preview(
        "Auto-detect concept descriptions",
        f"{plan.summary} An element gets the description with its idShort. "
        "A semantic id that is set is never replaced.",
        ["Element", "Concept description", "Id"],
        rows,
        notes,
        "Assign",
        context.view,
    ):
        return
    commands = ops.assign_commands(observer_for(context.package), plan.assign)
    _push(
        context,
        f"Auto-detect {len(plan.assign)} concept descriptions",
        commands,
    )


# Deleting


def _run_delete_invalid(context: ActionContext) -> None:
    found = ops.plan_invalid(_all_objects(context))
    if not found:
        _show(
            context,
            "No concept description is invalid. A description is invalid "
            "when it has no data specification, no isCaseOf and no extension.",
        )
        return
    rows = [
        [
            item.concept.id_short or "",
            item.concept.id,
            str(item.usages),
        ]
        for item in found
    ]
    chosen = concept_dialogs.choose_rows(
        "Delete invalid concept descriptions",
        "These concept descriptions have no data specification, no isCaseOf "
        "and no extension, so they define nothing. Select the ones to "
        "delete. If something refers to one, the next step shows it.",
        ["idShort", "Id", "References"],
        rows,
        [],
        "Delete",
        context.view,
    )
    if not chosen:
        return
    targets = [found[number].concept for number in chosen]
    observer = observer_for(context.package)
    try:
        prepared = prepare_delete(
            _store(context),
            targets,
            observer,
            confirm=True,
            skip_confirmation=True,
            parent=context.view,
        )
    except DeleteCancelled:
        return
    commands = [
        *prepared.commands,
        *(
            RemoveMember(observer, _store(context), target)
            for target in targets
        ),
    ]
    _push(context, prepared.description, commands)


# Records


def _default_draft(concept: ConceptDescription) -> Iec61360Draft:
    """Starts the preferred name from the idShort, as Sync does in the original."""
    return Iec61360Draft(
        preferred_name=[(first_default_language(), concept.id_short or "")]
    )


def _run_add_record(context: ActionContext) -> None:
    concept = _concept(context)
    if concept is None:
        return
    if data_specs.iec_records(concept):
        _show(
            context,
            f"{describe_object(concept)} has an IEC 61360 record already. "
            "Use Edit IEC 61360 record to change it.",
        )
        return
    draft = ask_iec61360(_default_draft(concept), parent=context.view)
    if draft is None:
        return
    commands = data_specs.add_record_commands(
        observer_for(context.package), concept, build_record(draft)
    )
    _push(
        context, f"Add IEC 61360 record to {describe_object(concept)}", commands
    )


def _run_edit_record(context: ActionContext) -> None:
    concept = _concept(context)
    if concept is None:
        return
    ((record, content), *_) = data_specs.iec_records(concept)
    draft = ask_iec61360(
        draft_of(content),
        "Edit IEC 61360 record",
        "Save record",
        context.view,
    )
    if draft is None:
        return
    commands = data_specs.set_content_commands(
        observer_for(context.package), concept, record, build_content(draft)
    )
    _push(
        context,
        f"Edit IEC 61360 record of {describe_object(concept)}",
        commands,
    )


def _run_clear_empty(context: ActionContext) -> None:
    concept = _concept(context)
    if concept is None:
        return
    observer = observer_for(context.package)
    commands: list[Command] = []
    for _, content in data_specs.iec_records(concept):
        commands.extend(data_specs.clear_empty_commands(observer, content))
    if not commands:
        _show(context, "The IEC 61360 record has no empty attributes.")
        return
    _push(context, "Remove empty IEC 61360 attributes", commands)


def _run_fix_keys(context: ActionContext) -> None:
    selected = [
        o for o in _objects(context) if isinstance(o, ConceptDescription)
    ]
    concepts = selected or [
        o for o in _all_objects(context) if isinstance(o, ConceptDescription)
    ]
    plan = data_specs.plan_fix_keys(concepts)
    if plan.is_empty:
        _show(
            context,
            f"All {plan.correct} IEC 61360 records name the template already."
            if plan.correct
            else "There are no IEC 61360 records.",
        )
        return
    include_other = concept_dialogs.ask_fix_keys(plan, context.view)
    if include_other is None:
        return
    commands = data_specs.fix_keys_commands(
        observer_for(context.package), plan, include_other
    )
    _push(context, "Fix data specification keys", commands)


def _run_import_value_list(context: ActionContext) -> None:
    concept = _concept(context)
    if concept is None:
        return
    ((_, content), *_) = data_specs.iec_records(concept)
    text = QApplication.clipboard().text()  # pyright: ignore[reportOptionalMemberAccess]
    plan = ask_value_list(content, text, context.view)
    if plan is None:
        return
    commands = data_specs.import_commands(observer_for(context.package), plan)
    _push(context, "Import value list", commands)


# Order


def apply_concept_order(
    view: Any, order: ConceptOrder, objects: Iterable[Any]
) -> None:
    """Lists the concept descriptions of a view in an order.

    The package is not changed (D16). A tree that the user sorted by a column
    keeps that sort, which wins over this order.

    Args:
        view: The tree view, whose model is a `SearchProxyModel`.
        order: The order to use.
        objects: The identifiables of the package in the order of its store,
            for the orders that rank the descriptions.
    """
    view.model().setConceptOrder(order, ranks_for(order, objects))


def ask_concept_order(
    current: ConceptOrder, parent: Any = None
) -> ConceptOrder | None:
    """Asks how to list the concept descriptions.

    Returns:
        The order, or None if the user cancelled.
    """
    orders = list(ConceptOrder)
    labels = [order.label for order in orders]
    label, accepted = QInputDialog.getItem(
        parent,
        ORDER_TITLE,
        "List the concept descriptions by (this changes the view only, and "
        "Sort concept descriptions in the file... writes the order):",
        labels,
        orders.index(current),
        False,
    )
    return orders[labels.index(label)] if accepted else None


def _run_order(context: ActionContext) -> None:
    proxy: Any = context.view.model()
    chosen = ask_concept_order(proxy.conceptOrder(), context.view)
    if chosen is not None:
        apply_concept_order(context.view, chosen, _all_objects(context))


def _run_sort(context: ActionContext) -> None:
    """Sorts the descriptions of the package by the order of the view."""
    proxy: Any = context.view.model()
    order: ConceptOrder = proxy.conceptOrder()
    objects = _all_objects(context)
    try:
        plan = sorting.plan_sort(objects, order)
    except sorting.SortRefused as refused:
        _show(context, str(refused), TITLE)
        return
    if not plan.changes:
        _show(
            context,
            f"The file lists the concept descriptions by {order.label} "
            "already.",
        )
        return
    rows = [
        [str(number), c.id_short or "", c.id]
        for number, c in enumerate(
            (o for o in plan.new_order if isinstance(o, ConceptDescription)), 1
        )
    ]
    if not concept_dialogs.confirm_preview(
        "Sort the concept descriptions",
        f"Sort the concept descriptions of the file by {order.label}? A save "
        "writes them in this order. Undo gives the old order back.",
        ["#", "idShort", "Id"],
        rows,
        (),
        "Sort",
        context.view,
    ):
        return
    command = sorting.sort_command(
        observer_for(context.package), _store(context), plan
    )
    if _push(context, command.description, [command]):
        # What the view lists now is the order of the file.
        apply_concept_order(
            context.view, ConceptOrder.LIST_INDEX, _all_objects(context)
        )


def _spec(
    action_id: str,
    text: str,
    run: Callable[[ActionContext], None],
    is_enabled: Callable[[ActionContext], bool],
    order: int,
    status_tip: str,
    mutates: bool = True,
) -> ActionSpec:
    return ActionSpec(
        action_id=action_id,
        text=text,
        run=run,
        is_enabled=is_enabled,
        mutates=mutates,
        views=ViewKind.PACKAGES,
        status_tip=status_tip,
        order=order,
    )


_SPECS = (
    _spec(
        "concepts.create",
        "Create concept description from semantic id",
        _run_create_from_semantic_id,
        _is_single_holder,
        400,
        "Add a concept description for the semantic id of this element",
    ),
    _spec(
        "concepts.create_all",
        "Create concept descriptions from all semantic ids...",
        _run_create_from_all,
        _has_children,
        401,
        "Add a concept description for each semantic id below, that has none",
    ),
    _spec(
        "concepts.create_empty",
        "Create empty concept description",
        _run_create_empty,
        _can_create_empty,
        400,
        "Add a concept description with a generated id and nothing else",
    ),
    _spec(
        "concepts.assign",
        "Assign concept description...",
        _run_assign,
        _can_hold_semantics,
        402,
        "Use a concept description of the package as the semantic id",
    ),
    _spec(
        "concepts.auto_detect",
        "Auto-detect concept descriptions...",
        _run_auto_detect,
        _can_hold_semantics,
        403,
        "Give elements without a semantic id the description with their idShort",
    ),
    _spec(
        "concepts.from_pairs",
        "Create concept descriptions from value list...",
        _run_from_pairs,
        _has_value_pairs,
        404,
        "Add one concept description for each pair of the value list",
    ),
    _spec(
        "concepts.delete_invalid",
        "Delete invalid concept descriptions...",
        _run_delete_invalid,
        _in_concept_area,
        405,
        "Delete descriptions with no data specification, isCaseOf or extension",
    ),
    _spec(
        "concepts.add_record",
        "Add IEC 61360 record...",
        _run_add_record,
        _is_concept,
        406,
        "Add an IEC 61360 data specification to this concept description",
    ),
    _spec(
        "concepts.edit_record",
        "Edit IEC 61360 record...",
        _run_edit_record,
        _has_record,
        407,
        "Change the IEC 61360 data specification of this concept description",
    ),
    _spec(
        "concepts.clear_empty",
        "Remove empty IEC 61360 attributes",
        _run_clear_empty,
        _has_empty_attributes,
        408,
        "Take away unit, symbol and others that are present but empty",
    ),
    _spec(
        "concepts.fix_keys",
        "Fix data specification keys...",
        _run_fix_keys,
        _in_concept_area,
        409,
        "Give records with IEC 61360 content the key of the template",
    ),
    _spec(
        "concepts.import_value_list",
        "Import value list from clipboard...",
        _run_import_value_list,
        _has_record,
        410,
        "Add the pairs of the clipboard to the value list, after a preview",
    ),
    _spec(
        "concepts.order",
        "Order concept descriptions...",
        _run_order,
        _can_sort,
        411,
        "Choose how the view lists the concept descriptions",
        mutates=False,
    ),
    _spec(
        "concepts.sort",
        "Sort concept descriptions in the file...",
        _run_sort,
        _can_sort,
        412,
        "Write the concept descriptions in the order the view lists them",
    ),
)
