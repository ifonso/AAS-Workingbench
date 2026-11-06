"""The action "Remove attributes..." for a submodel (F-EDT-03 AC11).

The dialog lists the attributes that can be removed from the submodel and all
of its elements, with how many each would take. Its question names what goes
and where, and updates while the user ticks. Removing is one undo step.

Call `register_bulk_actions` once, before the first tree view exists.
"""

from typing import Any

from basyx.aas import model
from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.application.changes import observer_for
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.operations.bulk import RemovableAttribute
from aas_editor.application.operations.bulk import RemovalPlan
from aas_editor.application.operations.bulk import available_attributes
from aas_editor.application.operations.bulk import plan_remove_attributes
from aas_editor.application.operations.bulk import removal_commands
from aas_editor.domain.references import describe_object
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ActionContext
from aas_editor.ui.actions import ActionSpec
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.actions import register_action
from aas_editor.ui.create_actions import show_problem

REMOVE_ID = "bulk.remove_attributes"
TITLE = "Remove attributes"


class RemoveAttributesDialog(QDialog):
    """Asks which attributes to remove, and states what that takes away."""

    def __init__(
        self, submodel: model.Submodel, parent: QWidget | None = None
    ) -> None:
        """Builds the dialog.

        Args:
            submodel: The submodel to remove attributes from, with its elements.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.setMinimumWidth(460)
        self._submodel = submodel
        counts = available_attributes(submodel)
        self.boxes: dict[RemovableAttribute, QCheckBox] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Remove these attributes from {describe_object(submodel)} "
                "and from all of its elements:",
                self,
            )
        )
        for attribute in RemovableAttribute:
            number = counts[attribute]
            box = QCheckBox(f"All {attribute.plural} ({number})", self)
            box.setEnabled(number > 0)
            box.toggled.connect(self._update)
            self.boxes[attribute] = box
            layout.addWidget(box)
        self.question = QLabel(self)
        self.question.setWordWrap(True)
        layout.addWidget(self.question)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is None:
            raise RuntimeError("The dialog has no OK button")
        self.ok_button: QPushButton = ok
        self.ok_button.setText("Remove")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self._update()

    def chosen(self) -> set[RemovableAttribute]:
        """Returns the attributes that are ticked."""
        return {a for a, box in self.boxes.items() if box.isChecked()}

    def check(self, attribute: RemovableAttribute) -> None:
        """Ticks an attribute."""
        self.boxes[attribute].setChecked(True)

    def plan(self) -> RemovalPlan:
        """Returns what the ticked attributes would take away."""
        return plan_remove_attributes(self._submodel, self.chosen())

    def _update(self) -> None:
        if not self.chosen():
            self.question.setText("Tick the attributes to remove.")
            self.ok_button.setEnabled(False)
            return
        self.question.setText(self.plan().question)
        self.ok_button.setEnabled(True)


def remove_attributes(
    view: Any, package: Any, submodel: model.Submodel
) -> bool:
    """Asks which attributes to remove, and removes them as one undo step.

    Returns:
        True if something was removed.
    """
    dialog = RemoveAttributesDialog(submodel, view)
    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    plan = dialog.plan() if accepted else None
    dialog.deleteLater()
    if plan is None or plan.is_empty:
        return False
    stack = package.commandStack
    try:
        with stack.group(plan.description):
            for command in removal_commands(observer_for(package), plan):
                stack.push(command)
    except ReadOnlyError as error:
        show_problem(str(error), view)
        return False
    return True


def _submodel_of(context: ActionContext) -> model.Submodel | None:
    obj: object = context.index.data(OBJECT_ROLE)
    return obj if isinstance(obj, model.Submodel) else None


def _run(context: ActionContext) -> None:
    submodel = _submodel_of(context)
    if submodel is not None and context.package is not None:
        remove_attributes(context.view, context.package, submodel)


def register_bulk_actions() -> None:
    """Adds the bulk actions to the registry, once."""
    registered = {
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    }
    if REMOVE_ID in registered:
        return
    register_action(
        ActionSpec(
            action_id=REMOVE_ID,
            text="Remove attributes...",
            run=_run,
            is_enabled=lambda context: _submodel_of(context) is not None,
            views=ViewKind.PACKAGES,
            status_tip=(
                "Remove qualifiers, extensions, or descriptions from the "
                "Submodel and all of its elements"
            ),
            order=210,
        )
    )
