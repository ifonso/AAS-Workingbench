"""Finds the controls that a screen reader cannot name.

PyQt6 does not expose `QAccessible`, so this reads what Qt reads. The name of a
control is its accessible name; failing that, a button's own text, or the text
of the label that has the control as its buddy. A control that has none of
them is read as only its role, "button" or "edit".

The rules, as `unnamed` applies them to the visible widgets under a root:

* A button, with a checked state or without, has a name.
* A field (line edit, text edit, combo box, spin box) has a name.
* A view (tree, table, list) has a name, because its role says nothing.
* A button that shows no text has a tooltip, and if its action has a key, the
  tooltip says it.
"""

from PyQt6.QtGui import QAction
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import QAbstractButton
from PyQt6.QtWidgets import QAbstractItemView
from PyQt6.QtWidgets import QAbstractSpinBox
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtWidgets import QWidget

_FIELDS = (QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QAbstractSpinBox)

# The inner widgets that Qt makes for a composite control. The composite is
# the control that is named.
_INNER = (
    "qt_spinbox_lineedit",
    "qt_scrollarea_viewport",
    # The square above the row numbers of a table, which selects all.
    "qt_tableview_cornerbutton",
)


def _strip(text: str) -> str:
    return text.replace("&", "").strip()


def label_of(widget: QWidget) -> str:
    """Returns the text of the label that has the widget as its buddy."""
    window = widget.window()
    for label in window.findChildren(QLabel):
        if label.buddy() is widget and _strip(label.text()):
            return _strip(label.text())
    return ""


def name_of(widget: QWidget) -> str:
    """Returns the name that a screen reader reads for the widget, or ''."""
    if widget.accessibleName().strip():
        return widget.accessibleName().strip()
    if isinstance(widget, QAbstractButton) and _strip(widget.text()):
        return _strip(widget.text())
    return label_of(widget)


def _is_inner(widget: QWidget) -> bool:
    if widget.objectName() in _INNER:
        return True
    parent = widget.parentWidget()
    # The line edit of an editable combo box, and the buttons of a spin box.
    return isinstance(parent, (QComboBox, QAbstractSpinBox))


def _describe(widget: QWidget) -> str:
    where = widget.window().windowTitle() or type(widget.window()).__name__
    name = widget.objectName() or "-"
    return f"{type(widget).__name__}({name}) in {where}"


def _shortcut_text(action: QAction | None) -> str:
    if action is None or not action.shortcuts():
        return ""
    return action.shortcuts()[0].toString(
        QKeySequence.SequenceFormat.NativeText
    )


def _button_problem(button: QAbstractButton) -> str | None:
    if not name_of(button):
        return "no name"
    if button.text().strip():
        return None
    tip = button.toolTip().strip()
    if not tip:
        return "no tooltip"
    if isinstance(button, QToolButton):
        key = _shortcut_text(button.defaultAction())
        if key and key not in tip:
            return f"tooltip lacks {key}"
    return None


def _problem(widget: QWidget) -> str | None:
    if isinstance(widget, QAbstractButton):
        return _button_problem(widget)
    # A header is read with the view that it belongs to.
    needs_name = isinstance(widget, _FIELDS) or (
        isinstance(widget, QAbstractItemView)
        and not isinstance(widget, QHeaderView)
    )
    if needs_name and not name_of(widget):
        return "no name"
    return None


def unnamed(root: QWidget) -> list[str]:
    """Lists the visible controls under the root that break the rules above."""
    problems: list[str] = []
    for widget in [root, *root.findChildren(QWidget)]:
        if not widget.isVisible() or _is_inner(widget):
            continue
        problem = _problem(widget)
        if problem is not None:
            problems.append(f"{problem}: {_describe(widget)}")
    return problems
