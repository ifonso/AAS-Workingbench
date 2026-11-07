"""Hints under the fields of the create dialogs (F-EDT-06, F-EDT-02 AC9).

A dialog that makes an object asks for its idShort, the value of a key, or the
global asset id. While the user types, a line under the field says what the
rules would find in the finished object. The check is the one of the rules
(`domain.validation.field_checks`), the hint never blocks typing or accepting
the dialog, and hints mode switches the lines off.
"""

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_workingbench.application.hints import hints_mode
from aas_workingbench.domain.validation.field_checks import field_problem

# Qt style sheets are the way to colour one label for both themes: the text
# colour comes from the palette, and only the weight and the marker are set.
_STYLE = "font-style: italic;"


class InlineHint(QObject):
    """Shows the hint for one text field, below it.

    Attributes:
        label: The label under the field. Hidden when there is no hint.
    """

    def __init__(self, owner: str, param: str, field: QLineEdit) -> None:
        """Puts the hint label under the field and starts following it.

        Args:
            owner: The name of the class that the dialog makes.
            param: The name of the parameter the field fills.
            field: The line edit to watch.
        """
        super().__init__(field)
        self._owner = owner
        self._param = param
        self._field = field
        self.label = QLabel(field.parentWidget())
        self.label.setWordWrap(True)
        self.label.setStyleSheet(_STYLE)
        self.label.hide()
        self._place_below(field)
        field.textChanged.connect(self.update)
        self._mode_subscription = hints_mode().subscribe(self._on_mode)
        self.update()

    @property
    def text(self) -> str:
        """The hint that is shown now, or an empty text."""
        return self.label.text() if not self.label.isHidden() else ""

    def update(self) -> None:
        """Shows the hint for the text in the field, if hints mode is on."""
        problem = (
            field_problem(self._owner, self._param, self._field.text())
            if hints_mode().is_on
            else None
        )
        if problem is None:
            self.label.clear()
            self.label.hide()
        else:
            self.label.setText(problem)
            self.label.show()

    def _on_mode(self, on: bool) -> None:
        del on
        try:
            self.update()
        except RuntimeError:
            # The dialog was deleted, and the subscription outlived it.
            self._mode_subscription.cancel()

    def _place_below(self, field: QLineEdit) -> None:
        parent = field.parentWidget()
        layout = None if parent is None else parent.layout()
        if parent is None or layout is None:
            return
        # The input widget lays out the field in a row. The field and the
        # label share a column in its place.
        column = QWidget(parent)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        layout.replaceWidget(field, column)
        column_layout.addWidget(field)
        column_layout.addWidget(self.label)
        self.label.setParent(column)


def attach_inline_hint(owner: str, param: str, input_widget: QWidget) -> None:
    """Adds a hint to the field of an input widget, if it is a text field.

    Args:
        owner: The name of the class that the dialog makes.
        param: The name of the parameter the field fills.
        input_widget: The widget that the dialog made for the parameter. Only
            one with a line edit gets a hint.
    """
    field = getattr(input_widget, "widget", None)
    if isinstance(field, QLineEdit):
        InlineHint(owner, param, field)
