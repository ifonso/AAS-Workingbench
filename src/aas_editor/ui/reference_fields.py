"""The fields of the generated forms that hold a reference (F-EDT-11).

Every place that enters or edits a reference gets the same help: a button that
picks the target from the package, and a line under the keys that says whether
the reference resolves, dangles, or points outside of the package. When the
SDK refuses the keys (AASd-121 to AASd-128) the reason is shown there, and OK
stays disabled until the keys are right. The keys themselves stay editable, so
an external reference to anything can still be typed.

A reference of the SDK is immutable, so the form makes a new one and the editor
replaces the old one where it is stored.

Three classes cover the type hints of the SDK: `ReferenceGroupBox` for
`Reference` (the user chooses external or model), `ModelReferenceField` for
`ModelReference[...]`, and `ExternalReferenceField` for `ExternalReference`.
`widgets/widgetUtil.py` picks them.
"""

from typing import Any
from typing import cast

from basyx.aas import model
from PyQt6.QtCore import QEvent
from PyQt6.QtCore import QModelIndex
from PyQt6.QtCore import QObject
from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QWidget

from aas_editor.ui.colors import advisory_style
from aas_editor.ui.colors import problem_style
from aas_editor.domain.reference_picker import ReferenceRule
from aas_editor.domain.reference_picker import ReferenceStatus
from aas_editor.domain.reference_picker import class_for_key_type
from aas_editor.domain.reference_picker import explain
from aas_editor.domain.reference_picker import rule_for_hint
from aas_editor.domain.reference_picker import status_of
from aas_editor.domain.references import ReferenceIndex
from aas_editor.domain.reference_picker import PickerSource
from aas_editor.settings.app_settings import OPENED_PACKS_ROLE
from aas_editor.settings.app_settings import PACK_ITEM_ROLE
from aas_editor.settings.app_settings import NAME_ROLE
from aas_editor.settings.app_settings import PACKAGE_ROLE
from aas_editor.settings.app_settings import PARENT_OBJ_ROLE
from aas_editor.ui.reference_picker import ReferencePickerDialog
from aas_editor.widgets.groupBoxes import ModelReferenceGroupBox
from aas_editor.widgets.groupBoxes import ObjGroupBox
from aas_editor.widgets.groupBoxes import TypeOptionObjGroupBox

CHOOSE_TEXT = "Choose from package..."
_WATCHED = (
    QEvent.Type.KeyRelease,
    QEvent.Type.MouseButtonRelease,
    QEvent.Type.FocusOut,
    QEvent.Type.Hide,
)


def package_of(widget: QWidget) -> Any:
    """Finds the package that a reference form belongs to, or None.

    The form sits in a dialog that was made for a tree view. The package is
    the one of the current item of that view. A dialog can also carry the
    package as its `package` attribute, which comes first.
    """
    window: QWidget | None = widget.window()
    if window is None:
        return None
    explicit: Any = getattr(window, "package", None)
    if explicit is not None:
        return explicit
    owner: QObject | None = window.parent() if window is not widget else None
    while owner is not None:
        current: Any = getattr(owner, "currentIndex", None)
        if current is not None:
            index: Any = current()
            # A tab widget has a currentIndex too, and it is a number.
            package: Any = (
                index.data(PACKAGE_ROLE) if hasattr(index, "data") else None
            )
            if package is not None:
                return package
        owner = owner.parent()
    return None


def open_packages_of(widget: QWidget) -> list[Any]:
    """Finds the packages that are open next to the one of a form.

    The tree view that the dialog was made for knows them, through its model.
    A tab asks the model of the package tree that its object came from.

    Args:
        widget: A reference form.

    Returns:
        The open packages, in the order of their names, or an empty list when
        the form has no tree view to ask.
    """
    window: QWidget | None = widget.window()
    if window is None or window is widget:
        return []
    owner: QObject | None = window.parent()
    while owner is not None:
        current: Any = getattr(owner, "currentIndex", None)
        if current is not None:
            index: Any = current()
            if hasattr(index, "model"):
                packages = _packages_in(index.model())
                if not packages and hasattr(index, "data"):
                    pack_item: Any = index.data(PACK_ITEM_ROLE)
                    packages = _packages_in(
                        pack_item.model() if pack_item is not None else None
                    )
                if packages:
                    return sorted(packages, key=lambda p: str(p.name))
        owner = owner.parent()
    return []


_SEMANTIC_ID_NAMES = ("semantic_id", "supplemental_semantic_id")
CONCEPTS_FILTER = "Concept descriptions"


def is_semantic_id_of_element(widget: QWidget) -> bool:
    """Tells whether a reference form is the semantic id of a submodel or element.

    Package Explorer lists only concept descriptions there (F-EDT-11 AC1), so
    the picker starts on that filter. Two forms exist: a part of the form of
    the whole object, which knows the attribute that holds it, and the dialog
    of one attribute, which a tab opens for the current row.

    Args:
        widget: A reference form.
    """
    child: QWidget = widget
    parent: QObject | None = widget.parent()
    while isinstance(parent, QWidget):
        params: Any = getattr(parent, "paramWidgets", None)
        if isinstance(params, dict):
            for name, held in cast("dict[str, Any]", params).items():
                if held is child:
                    owner: Any = getattr(parent, "objTypeHint", None)
                    return name in _SEMANTIC_ID_NAMES and (
                        isinstance(owner, type)
                        and issubclass(
                            owner, (model.Submodel, model.SubmodelElement)
                        )
                    )
        child, parent = parent, parent.parent()
    window: QWidget | None = widget.window()
    if window is None or window is widget:
        return False
    owner_view: QObject | None = window.parent()
    while owner_view is not None:
        current: Any = getattr(owner_view, "currentIndex", None)
        if current is not None:
            index: Any = current()
            if hasattr(index, "data"):
                return index.data(
                    NAME_ROLE
                ) in _SEMANTIC_ID_NAMES and isinstance(
                    index.data(PARENT_OBJ_ROLE),
                    (model.Submodel, model.SubmodelElement),
                )
        owner_view = owner_view.parent()
    return False


def _packages_in(shown: Any) -> set[Any]:
    if shown is None:
        return set()
    found: Any = shown.data(QModelIndex(), OPENED_PACKS_ROLE)
    return set(found) if found else set()


class ReferenceFieldMixin:
    """The picker button and the status line, for a form that makes a reference.

    A class that mixes this in must be a `QGroupBox` with a form layout, call
    `_start_reference_field` once its own rows exist, and say which box builds
    the reference and how to put a picked reference into the form.
    """

    _rule: ReferenceRule
    _status: ReferenceStatus | None
    _problem: str

    def _start_reference_field(self, rule: ReferenceRule) -> None:
        owner: Any = self
        self._rule = rule
        self._status = None
        self._problem = ""
        self._derived_type: type | None = None
        self._picker_button = QPushButton(CHOOSE_TEXT, owner)
        self._picker_button.setToolTip(
            "Pick the target from the shells, submodels, concept "
            "descriptions, and elements of this package"
        )
        self._picker_button.clicked.connect(self.choose_from_package)
        self._status_label = QLabel(owner)
        self._status_label.setWordWrap(True)
        owner.layout().addRow(self._picker_button)
        owner.layout().addRow(self._status_label)
        self._refresh_timer = QTimer(owner)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self.refresh_status)
        owner.installEventFilter(owner)
        for child in owner.findChildren(QWidget):
            child.installEventFilter(owner)

    # What a class that mixes this in provides

    def _reference_box(self) -> Any:
        raise NotImplementedError

    def _put_reference(self, reference: model.Reference) -> None:
        raise NotImplementedError

    # Watching the form

    def eventFilter(  # noqa: N802
        self, watched: QObject | None, event: QEvent | None
    ) -> bool:
        """Re-checks the reference a moment after the user changed the keys."""
        try:
            if event is not None and hasattr(self, "_refresh_timer"):
                if (
                    event.type() == QEvent.Type.ChildAdded
                    and watched is not None
                ):
                    child = getattr(event, "child", lambda: None)()
                    if isinstance(child, QWidget):
                        child.installEventFilter(self)  # pyright: ignore[reportArgumentType]
                        for inner in child.findChildren(QWidget):
                            inner.installEventFilter(self)  # pyright: ignore[reportArgumentType]
                    self._refresh_timer.start()
                elif event.type() in _WATCHED:
                    self._refresh_timer.start()
        except RuntimeError:
            # The form is being deleted, and Qt still delivers its last events.
            return False
        return False

    def showEvent(self, event: Any) -> None:  # noqa: N802
        """Shows the status as soon as the form is on screen."""
        super().showEvent(event)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
        self.refresh_status()

    # The package

    def _objects(self) -> list[model.Identifiable]:
        package = package_of(self)  # pyright: ignore[reportArgumentType]
        return list(package.objStore) if package is not None else []

    # The status line

    def reference_status(self) -> ReferenceStatus | None:
        """Returns what the package says about the reference in the form."""
        return self._status

    def reference_problem(self) -> str:
        """Returns why the keys do not make a reference, or an empty text."""
        return self._problem

    def current_reference(self) -> model.Reference | None:
        """Builds the reference from the form, or None if the keys are wrong."""
        try:
            return self._reference_box().getObj2add()
        except Exception as error:  # noqa: BLE001
            self._problem = explain(error)
            return None

    def refresh_status(self) -> None:
        """Checks the keys, shows the state, and gates the OK button."""
        try:
            self._check_reference()
        except RuntimeError:
            # A timer fired after the form was deleted.
            return

    def _check_reference(self) -> None:
        self._derive_target_type()
        self._problem = ""
        reference = self.current_reference()
        if reference is None:
            self._status = None
            self._show(self._problem, problem_style())
            self._gate(valid=False)
            return
        self._gate(valid=True)
        objects = self._objects()
        if not objects:
            self._status = None
            self._show("", "")
            return
        status = status_of(ReferenceIndex(objects), reference)
        self._status = status
        self._show(status.text, advisory_style() if status.is_dangling else "")

    def _show(self, text: str, style: str) -> None:
        self._status_label.setText(text)
        self._status_label.setStyleSheet(style)

    def _gate(self, valid: bool) -> None:
        """Keeps OK disabled while this field cannot make a reference."""
        dialog = cast("QWidget", self).window()
        if not isinstance(dialog, QDialog):
            return
        invalid: set[int] = dialog.property("invalid_reference_fields") or set()
        invalid = set(invalid)
        if valid:
            invalid.discard(id(self))
        else:
            invalid.add(id(self))
        dialog.setProperty("invalid_reference_fields", invalid)
        ok_button = getattr(dialog, "buttonOk", None)
        if ok_button is not None:
            ok_button.setEnabled(not invalid)

    def _derive_target_type(self) -> None:
        """Follows the last key type with the target type of a model reference.

        Typing a `Property` key makes the target type `Property`, unless the
        user chose another type by hand.
        """
        box = self._reference_box()
        type_widget = getattr(box, "paramWidgets", {}).get("type_")
        keys_group = getattr(box, "paramWidgets", {}).get("key")
        if type_widget is None or keys_group is None:
            return
        if not getattr(keys_group, "inputWidgets", None):
            return
        last = keys_group.inputWidgets[-1]
        key_type_widget = getattr(last, "paramWidgets", {}).get("type_")
        if key_type_widget is None:
            return
        wanted = class_for_key_type(key_type_widget.widget.currentData())
        combo = type_widget.widget
        if wanted is None or combo.findData(wanted) < 0:
            return
        # At first the entry is the one that the list starts with, so the
        # form takes the type of the last key. A type that the user chose later
        # is kept.
        if self._derived_type is None or combo.currentData() in (
            self._derived_type,
            None,
        ):
            with QSignalBlocker(combo):
                combo.setCurrentIndex(combo.findData(wanted))
        self._derived_type = wanted

    # The picker

    def choose_from_package(self) -> bool:
        """Opens the picker, and puts the chosen reference into the form.

        Returns:
            True if the user chose a target.
        """
        objects = self._objects()
        main = package_of(self)  # pyright: ignore[reportArgumentType]
        others = [
            PickerSource(str(pack.name), tuple(pack.objStore))
            for pack in open_packages_of(self)  # pyright: ignore[reportArgumentType]
            if pack is not main
        ]
        dialog = ReferencePickerDialog(
            objects,
            self._rule,
            as_model=self._prefers_model(),
            parent=self,  # pyright: ignore[reportArgumentType]
            others=others,
            package_name=str(main.name) if main is not None else "",
            initial_filter=(
                CONCEPTS_FILTER
                if is_semantic_id_of_element(self)  # pyright: ignore[reportArgumentType]
                else None
            ),
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        reference = dialog.reference() if accepted else None
        dialog.deleteLater()
        if reference is None:
            return False
        self.set_reference(reference)
        return True

    def _prefers_model(self) -> bool | None:
        """Whether the form is making a model reference now, if it says."""
        return isinstance(self._reference_box(), ModelReferenceGroupBox)

    def set_reference(self, reference: model.Reference) -> None:
        """Replaces the keys in the form with those of a reference."""
        self._put_reference(reference)
        self._derived_type = None
        self.refresh_status()


class ReferenceGroupBox(ReferenceFieldMixin, TypeOptionObjGroupBox):
    """The form for a `Reference`: external or model, chosen by the user."""

    def __init__(
        self, objTypes: Any, defType: Any = str, **kwargs: Any
    ) -> None:  # noqa: N803
        """Builds the form for both kinds of reference.

        Args:
            objTypes: The kinds to choose from, `ExternalReference` and
                `ModelReference`.
            defType: The kind to start with.
            **kwargs: What the other generated forms get.
        """
        super().__init__(objTypes, defType, **kwargs)  # pyright: ignore[reportUnknownMemberType]
        self._form_kwargs = {**kwargs, "parent": self, "title": ""}
        self._start_reference_field(rule_for_hint(model.Reference))
        self._hide_picker_of_inner_form()

    def replaceGroupBoxWidget(  # noqa: N802
        self, objType: Any, **kwargs: Any
    ) -> None:
        """Changes the form for the kind, and keeps one picker on screen."""
        super().replaceGroupBoxWidget(objType, **kwargs)  # pyright: ignore[reportUnknownMemberType]
        self._hide_picker_of_inner_form()

    def _hide_picker_of_inner_form(self) -> None:
        """Hides the picker of the form inside, because this form has one.

        The form of each kind brings its own button and status line. Both
        showed, one under the other, and did the same.
        """
        inner: Any = self.widget  # pyright: ignore[reportUnknownMemberType]
        if inner is self:
            return
        for name in ("_picker_button", "_status_label"):
            widget = getattr(inner, name, None)
            if widget is not None:
                widget.hide()

    def _reference_box(self) -> Any:
        return self.widget

    def _prefers_model(self) -> bool | None:
        return self.typeComboBox.currentData() is model.ModelReference

    def _put_reference(self, reference: model.Reference) -> None:
        kind = (
            model.ModelReference
            if isinstance(reference, model.ModelReference)
            else model.ExternalReference
        )
        self.objVal = reference  # pyright: ignore[reportUnknownMemberType]
        with QSignalBlocker(self.typeComboBox):
            self.typeComboBox.setCurrentIndex(self.typeComboBox.findData(kind))
        self.replaceGroupBoxWidget(kind, **self._form_kwargs)  # pyright: ignore[reportUnknownMemberType]
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)


class ModelReferenceField(ReferenceFieldMixin, ModelReferenceGroupBox):
    """The form for a `ModelReference[...]`, such as a Submodel of a shell."""

    # The old picker of the form lists every referable without a filter.
    CHOOSE_FRM_VIEW = None

    def __init__(self, objTypeHint: Any, **kwargs: Any) -> None:  # noqa: N803
        """Builds the form, with the targets the hint allows.

        Args:
            objTypeHint: `ModelReference[...]` with the classes of the target.
            **kwargs: What the other generated forms get.
        """
        super().__init__(objTypeHint, **kwargs)  # pyright: ignore[reportUnknownMemberType]
        self._start_reference_field(rule_for_hint(objTypeHint))

    def _reference_box(self) -> Any:
        return self

    def _put_reference(self, reference: model.Reference) -> None:
        self.setVal(reference)  # pyright: ignore[reportUnknownMemberType]
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)


class ExternalReferenceField(ReferenceFieldMixin, ObjGroupBox):
    """The form for an `ExternalReference`, such as an external subject id."""

    def __init__(self, objTypeHint: Any, **kwargs: Any) -> None:  # noqa: N803
        """Builds the form for an external reference.

        Args:
            objTypeHint: `ExternalReference`.
            **kwargs: What the other generated forms get.
        """
        super().__init__(objTypeHint, **kwargs)  # pyright: ignore[reportUnknownMemberType]
        self._start_reference_field(rule_for_hint(objTypeHint))

    def _reference_box(self) -> Any:
        return self

    def _prefers_model(self) -> bool | None:
        return False

    def _put_reference(self, reference: model.Reference) -> None:
        self.setVal(reference)  # pyright: ignore[reportUnknownMemberType]
        for child in self.findChildren(QWidget):
            child.installEventFilter(self)
