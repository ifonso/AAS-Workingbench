"""Drives the generated edit dialogs the way a user does, for tests.

A dialog is built from the type hints of a BaSyx class: one widget for each
parameter of the constructor, and a Create button for each optional parameter
that has no value yet. `Form` finds these widgets by the name of the parameter
and fills them. Nothing here changes an AAS object: the test accepts the dialog,
and the editor makes the object from what the widgets hold.
"""

from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Sequence
import contextlib
from enum import Enum
from typing import Any

from PyQt6.QtWidgets import QCheckBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPushButton
import pytest


class Form:
    """The widgets of one generated dialog, found by parameter name."""

    def __init__(self, dialog: Any) -> None:
        self.dialog = dialog

    @property
    def group(self) -> Any:
        """The box that holds the parameters of the class being made."""
        widget = self.dialog.inputWidget
        # The chooser of the type of a submodel element holds the box.
        return widget.widget if hasattr(widget, "typeComboBox") else widget

    def choose_type(self, element_type: type) -> "Form":
        """Chooses the class to make in the chooser at the top of the dialog."""
        chooser = self.dialog.inputWidget
        box = chooser.typeComboBox
        box.setCurrentIndex(box.findData(element_type))
        assert box.currentData() is element_type
        return self

    def has(self, param: str) -> bool:
        """Tells whether the parameter has a widget or a Create button."""
        return (
            param in self.group.paramWidgets
            or self._create_button(self.group, param) is not None
        )

    def create(self, param: str) -> Any:
        """Presses Create for an optional parameter, and returns its widget."""
        button = self._create_button(self.group, param)
        assert button is not None, f"No Create button for '{param}'"
        button.click()
        return self.group.paramWidgets[param]

    def widget(self, param: str) -> Any:
        """Returns the widget of a parameter, creating it if it is optional."""
        if param in self.group.paramWidgets:
            return self.group.paramWidgets[param]
        return self.create(param)

    def type_text(self, param: str, text: str) -> None:
        """Types into the line of a text, number, or value parameter."""
        widget = self.widget(param)
        inner = widget.widget
        if hasattr(inner, "set_text"):  # a value that follows a value type
            inner.set_text(text)
        elif isinstance(inner, QLineEdit):
            inner.setText(text)
        else:
            raise AssertionError(f"'{param}' is not a text: {type(inner)}")

    def choose(self, param: str, member: object) -> None:
        """Chooses an entry of a list: an enum member, a class, or a type."""
        combo = self.widget(param).widget
        assert isinstance(combo, QComboBox)
        index = combo.findData(member)
        assert index >= 0, f"'{member}' is not offered for '{param}'"
        combo.setCurrentIndex(index)

    def check(self, param: str, checked: bool) -> None:
        """Ticks or clears the check box of a parameter."""
        box = self.widget(param).widget
        assert isinstance(box, QCheckBox)
        box.setChecked(checked)

    def checked(self, param: str) -> bool:
        """Tells whether the check box of a parameter is ticked."""
        box = self.widget(param).widget
        assert isinstance(box, QCheckBox)
        return box.isChecked()

    def add_language(self, param: str, language: str, text: str) -> None:
        """Adds a language and its text to a multi-language parameter."""
        group = self.widget(param)
        group.findChild(QPushButton).click()
        entry = group.inputWidgets[-1]
        entry.paramWidgets["key"].widget.setText(language)
        entry.paramWidgets["value"].widget.setText(text)

    def fill_reference(
        self, param: str, keys: Sequence[tuple[Enum, str]]
    ) -> None:
        """Makes a reference from keys: pairs of the type and value of a key.

        The chooser of the kind of reference keeps its first entry, the
        external reference. Use `fill_model_reference` for a model reference.
        """
        self._fill_keys(self.widget(param).widget, keys)

    def fill_model_reference(
        self, param: str, keys: Sequence[tuple[Enum, str]], target: type
    ) -> None:
        """Makes a model reference from keys, to an object of the given class."""
        box = self.widget(param)
        self._fill_keys(box, keys)
        type_widget = box.paramWidgets["type_"]
        combo = type_widget.widget
        combo.setCurrentIndex(combo.findData(target))
        assert combo.currentData() is target

    def _fill_keys(self, box: Any, keys: Sequence[tuple[Enum, str]]) -> None:
        keys_group = box.paramWidgets["key"]
        for key_type, value in keys:
            keys_group.findChild(QPushButton).click()
            key_box = keys_group.inputWidgets[-1]
            type_combo = key_box.paramWidgets["type_"].widget
            type_combo.setCurrentIndex(type_combo.findData(key_type))
            key_box.paramWidgets["value"].widget.setText(value)

    @staticmethod
    def _create_button(box: Any, param: str) -> QPushButton | None:
        layout = box.layout()
        for row in range(layout.rowCount()):
            item = layout.itemAt(row, layout.ItemRole.FieldRole)
            widget = item.widget() if item else None
            if (
                widget is not None
                and getattr(widget, "paramName", None) == param
            ):
                return widget
        return None


@contextlib.contextmanager
def answering(
    monkeypatch: pytest.MonkeyPatch,
    dialog_class: type,
    script: Callable[[Any], None],
    errors: list[str] | None = None,
    cancel_when_asked_again: bool = False,
) -> Iterator[list[Any]]:
    """Makes a dialog class answer OK after the script has filled it.

    The dialogs of the editor are modal, and `exec` would block the test. The
    stand-in runs the script on the dialog, accepts it, and returns as `exec`
    would. If the editor refuses the answer and asks again, the test fails with
    the errors that were shown, or cancels the dialog if the test expects the
    refusal.

    Args:
        monkeypatch: Replaces `exec` for the length of the test.
        dialog_class: The class whose `exec` is replaced.
        script: Fills the dialog.
        errors: The messages the editor showed in error boxes, if recorded.
        cancel_when_asked_again: Whether to cancel the dialog when the editor
            refuses the answer, so that the test can look at the refusal.

    Yields:
        The dialogs that were opened.
    """
    opened: list[Any] = []

    def fake_exec(dialog: Any) -> int:
        opened.append(dialog)
        if len(opened) > 1:
            if cancel_when_asked_again:
                dialog.reject()
                return QDialog.DialogCode.Rejected
            raise AssertionError(
                "The editor refused the answer and asked again: "
                f"{errors if errors is not None else 'no error recorded'}"
            )
        script(dialog)
        dialog.accept()
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(dialog_class, "exec", fake_exec)
    yield opened
