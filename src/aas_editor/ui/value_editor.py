"""Editors for values: a value of an XSD type, and the bytes of a Blob.

* `ValueTypeBox` chooses the XSD type, by its name such as `xs:int`.
* `ValueEdit` is a line of text that checks itself against a type, and gives a
  value of that type. It tells the user what is wrong while they type.
* `BinaryEdit` shows bytes as text or as hex, and loads and saves files. The
  user never types a Python literal.
* `ValueEditDialog` puts one of them in a dialog, for the attributes that are
  edited alone.

The parsing is in `aas_editor.domain.value_types`, and the display of bytes in
`aas_editor.domain.blob_content`. This module only shows them.
"""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QCompleter
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from basyx.aas.model import datatypes

from aas_editor.domain import blob_content
from aas_editor.domain import value_types
from aas_editor.domain.value_types import InvalidValueError
from aas_editor.domain.value_types import XsdType

# What the line shows while it is empty, to tell the user the form of a value.
_EXAMPLES: dict[XsdType, str] = {
    datatypes.Boolean: "true or false",
    datatypes.Duration: "P1Y2M3DT4H5M6S",
    datatypes.DateTime: "2024-05-31T13:45:00Z",
    datatypes.Date: "2024-05-31",
    datatypes.Time: "13:45:00",
    datatypes.GYearMonth: "2024-05",
    datatypes.GYear: "2024",
    datatypes.GMonthDay: "--05-31",
    datatypes.GMonth: "--05",
    datatypes.GDay: "---31",
    datatypes.Base64Binary: "SGVsbG8=",
    datatypes.HexBinary: "48656c6c6f",
    datatypes.Float: "1.5 or 2E10",
    datatypes.Double: "1.5 or 2E10",
    datatypes.Decimal: "12.5",
    datatypes.AnyURI: "https://example.com",
}


class ValueTypeBox(QComboBox):
    """A list of the XSD value types, shown by their names.

    Signals:
        value_type_changed: The user chose another type. The argument is the
            class of `basyx.aas.model.datatypes`, or None for "no type".
    """

    value_type_changed = pyqtSignal(object)

    def __init__(
        self,
        value_type: XsdType | None = datatypes.String,
        allow_none: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the list.

        Args:
            value_type: The type to show first.
            allow_none: Whether the list offers "(no value type)", for an
                attribute that may be missing.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._allow_none = allow_none
        if allow_none:
            self.addItem("(no value type)", None)
        for candidate in value_types.XSD_TYPES:
            self.addItem(value_types.type_name(candidate), candidate)
        self.set_value_type(value_type)
        self.currentIndexChanged.connect(self._emit_changed)

    def value_type(self) -> XsdType | None:
        """Returns the chosen type, or None if "no value type" is chosen."""
        return self.currentData()

    def set_value_type(self, value_type: XsdType | None) -> None:
        """Shows a type without telling anybody.

        Args:
            value_type: The type. None shows "no value type" if the list has
                it, otherwise `xs:string`.
        """
        if value_type is None and not self._allow_none:
            value_type = datatypes.String
        index = self.findData(value_type)
        if index >= 0:
            blocked = self.blockSignals(True)
            self.setCurrentIndex(index)
            self.blockSignals(blocked)

    def _emit_changed(self, _: int) -> None:
        self.value_type_changed.emit(self.value_type())


class ValueEdit(QWidget):
    """A line of text for a value of an XSD type.

    The text is checked against the type while the user types, and the
    problem is shown below the line. `value` gives the typed value, or raises
    with the same message.

    Signals:
        changed: The text or the type changed.
    """

    changed = pyqtSignal()

    def __init__(
        self,
        value_type: XsdType = datatypes.String,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the editor.

        Args:
            value_type: The type that the text must follow.
            parent: The parent widget.
        """
        super().__init__(parent)
        self._value_type: XsdType = value_type
        self.line = QLineEdit(self)
        self.problem_label = QLabel(self)
        self.problem_label.setWordWrap(True)
        self.problem_label.setVisible(False)
        # The label is read by screen readers, and the color alone says nothing.
        self.problem_label.setStyleSheet("color: #c0392b;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.line)
        layout.addWidget(self.problem_label)
        self.line.textChanged.connect(self._on_text_changed)
        self._update()

    def value_type(self) -> XsdType:
        """Returns the type that the text must follow."""
        return self._value_type

    def set_value_type(self, value_type: XsdType | None) -> None:
        """Checks the text against another type.

        Args:
            value_type: The new type. None means `xs:string`.
        """
        self._value_type = value_type or datatypes.String
        self._update()
        self.changed.emit()

    def text(self) -> str:
        """Returns the text as it is."""
        return self.line.text()

    def set_text(self, text: str) -> None:
        """Shows text."""
        self.line.setText(text)

    def set_value(self, value: Any) -> None:
        """Shows a value in its lexical form, or nothing for None."""
        self.line.setText(
            "" if value is None else value_types.format_value(value)
        )

    def value(self) -> Any:
        """Returns the typed value.

        Returns:
            A value of the type, or None if the text is empty and the type is
            not a text type, where an empty text is a value.

        Raises:
            InvalidValueError: If the text is no value of the type.
        """
        text = self.line.text()
        if not text and not value_types.keeps_whitespace(self._value_type):
            return None
        return value_types.parse(text, self._value_type)

    def problem(self) -> str | None:
        """Tells what is wrong with the text, or None if it is fine."""
        text = self.line.text()
        if not text:
            return None
        return value_types.check(text, self._value_type)

    def _on_text_changed(self, _: str) -> None:
        self._update()
        self.changed.emit()

    def _update(self) -> None:
        name = value_types.type_name(self._value_type)
        example = _EXAMPLES.get(self._value_type)
        self.line.setPlaceholderText(f"{name}: {example}" if example else name)
        if self._value_type is datatypes.Boolean:
            completer = QCompleter(["true", "false"], self.line)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            self.line.setCompleter(completer)
        else:
            self.line.setCompleter(None)
        problem = self.problem()
        self.problem_label.setText(problem or "")
        self.problem_label.setVisible(problem is not None)
        self.line.setToolTip(problem or name)
        self.line.setAccessibleDescription(problem or "")


class BinaryEdit(QWidget):
    """Shows the bytes of a Blob as text or as hex, and loads and saves files.

    The content shows as text when it is text (see
    `aas_editor.domain.blob_content.as_text`), and as hex otherwise. The user
    can switch to hex at any time, and to text when the bytes allow it. The
    bytes are not touched until the user edits the text or loads a file.
    Content above `MAX_SHOWN_BYTES` is not shown, only its size.

    Signals:
        changed: The content changed.
        content_type_suggested: A file was loaded, and this is the media type
            of its extension.
    """

    changed = pyqtSignal()
    content_type_suggested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Builds the editor with no content."""
        super().__init__(parent)
        self._data: bytes | None = None
        self._newline = "\n"
        self._dirty = False
        self._hidden = False
        self._content_type: str | None = None
        self._loading = False
        self._shown_mode = "text"

        self.size_label = QLabel(self)
        self.view_box = QComboBox(self)
        self.view_box.addItem("Text (UTF-8)", "text")
        self.view_box.addItem("Hex", "hex")
        self.editor = QPlainTextEdit(self)
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.problem_label = QLabel(self)
        self.problem_label.setWordWrap(True)
        self.problem_label.setVisible(False)
        self.problem_label.setStyleSheet("color: #c0392b;")
        self.load_button = QPushButton("Load from file...", self)
        self.save_button = QPushButton("Save to file...", self)
        self.clear_button = QPushButton("Clear", self)

        header = QHBoxLayout()
        header.addWidget(self.size_label, 1)
        header.addWidget(QLabel("Show as", self))
        header.addWidget(self.view_box)
        buttons = QHBoxLayout()
        buttons.addWidget(self.load_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.clear_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.editor)
        layout.addWidget(self.problem_label)
        layout.addLayout(buttons)

        self.editor.textChanged.connect(self._on_text_edited)
        self.view_box.activated.connect(self._on_view_chosen)
        self.load_button.clicked.connect(self.load_file)
        self.save_button.clicked.connect(self.save_file)
        self.clear_button.clicked.connect(self.clear)
        self._refresh_size()

    def set_content_type(self, content_type: str | None) -> None:
        """Tells the media type of the content, to name the file on saving."""
        self._content_type = content_type or None

    def mode(self) -> str:
        """Returns how the content is shown, `"text"` or `"hex"`."""
        return self._shown_mode

    def is_content_shown(self) -> bool:
        """Tells whether the content is in the editor, and not too large."""
        return not self._hidden

    def set_data(self, data: bytes | None) -> None:
        """Shows content, as text where it is text and as hex otherwise.

        Args:
            data: The bytes, or None for no content.
        """
        self._data = data
        self._dirty = False
        self._show_data(data, self._preferred_mode(data))
        self._set_problem(None)
        self.changed.emit()

    def data(self) -> bytes | None:
        """Returns the bytes.

        Returns:
            Exactly the bytes that were set, if the user changed nothing.
            Otherwise the bytes of the edited text or hex. None if there is
            no content.

        Raises:
            InvalidValueError: If the hex text is no bytes.
        """
        if not self._dirty:
            return self._data
        text = self.editor.toPlainText()
        if self._shown_mode == "hex":
            content = blob_content.from_hex(text)
        else:
            content = blob_content.from_text(text, self._newline)
        return content or None

    def problem(self) -> str | None:
        """Tells what is wrong with the content, or None if it is fine."""
        try:
            self.data()
        except InvalidValueError as error:
            return str(error)
        return None

    def clear(self) -> None:
        """Removes the content."""
        self.set_data(None)

    def load_file(self) -> None:
        """Asks for a file and takes its bytes as the content."""
        path = self._ask_open_path()
        if not path:
            return
        try:
            content = Path(path).read_bytes()
        except OSError as error:
            self._set_problem(f"The file could not be read: {error}")
            return
        self.set_data(content)
        suggested = blob_content.guess_content_type(path)
        if suggested:
            self.content_type_suggested.emit(suggested)

    def save_file(self) -> None:
        """Asks for a file name and writes the content into it."""
        try:
            content = self.data()
        except InvalidValueError as error:
            self._set_problem(str(error))
            return
        if content is None:
            self._set_problem("There is no content to save")
            return
        path = self._ask_save_path(
            "content" + blob_content.guess_extension(self._content_type)
        )
        if not path:
            return
        try:
            Path(path).write_bytes(content)
        except OSError as error:
            self._set_problem(f"The file could not be written: {error}")
            return
        self._set_problem(None)

    def _ask_open_path(self) -> str:
        path, _ = QFileDialog.getOpenFileName(self, "Load content from file")
        return path

    def _ask_save_path(self, suggested: str) -> str:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save content to file", suggested
        )
        return path

    def _preferred_mode(self, data: bytes | None) -> str:
        if not data or blob_content.as_text(data) is not None:
            return "text"
        return "hex"

    def _show_data(self, data: bytes | None, mode: str) -> None:
        self._loading = True
        self._shown_mode = mode
        try:
            self.view_box.setCurrentIndex(self.view_box.findData(mode))
            self._hidden = (
                data is not None and len(data) > blob_content.MAX_SHOWN_BYTES
            )
            self.editor.setReadOnly(self._hidden)
            if self._hidden:
                self.editor.setPlainText("")
                self.editor.setPlaceholderText(
                    "The content is too large to show. "
                    "Use Save to file to read it, or Load from file to replace it."
                )
            else:
                self.editor.setPlaceholderText("")
                self.editor.setPlainText(self._shown_text(data, mode))
            self.view_box.setEnabled(not self._hidden)
        finally:
            self._loading = False
        self._refresh_size()

    def _shown_text(self, data: bytes | None, mode: str) -> str:
        if not data:
            return ""
        if mode == "hex":
            return blob_content.to_hex(data)
        shown = blob_content.as_text(data)
        self._newline = shown.newline if shown else "\n"
        return shown.text if shown else ""

    def _on_text_edited(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._set_problem(self.problem())
        self._refresh_size()
        self.changed.emit()

    def _on_view_chosen(self, _: int) -> None:
        wanted = str(self.view_box.currentData())
        try:
            content = self.data()
        except InvalidValueError as error:
            self._refuse_view(str(error))
            return
        if (
            wanted == "text"
            and content
            and blob_content.as_text(content) is None
        ):
            self._refuse_view(
                "The content has bytes that are not text. "
                "It can only be shown as hex"
            )
            return
        self._data = content
        self._dirty = False
        self._show_data(content, wanted)
        self._set_problem(None)

    def _refuse_view(self, message: str) -> None:
        # The list already shows the wanted view, but the editor does not.
        self.view_box.setCurrentIndex(self.view_box.findData(self._shown_mode))
        self._set_problem(message)

    def _refresh_size(self) -> None:
        if self._hidden and self._data is not None:
            self.size_label.setText(f"{len(self._data)} bytes (not shown)")
            return
        try:
            content = self.data()
        except InvalidValueError:
            self.size_label.setText("")
            return
        size = len(content) if content else 0
        kind = ""
        if content:
            kind = (
                ", text"
                if blob_content.as_text(content) is not None
                else ", binary"
            )
        self.size_label.setText(f"{size} bytes{kind}")

    def _set_problem(self, message: str | None) -> None:
        self.problem_label.setText(message or "")
        self.problem_label.setVisible(message is not None)


class ValueEditDialog(QDialog):
    """A dialog to edit one value alone, such as the value of a Property.

    It has the signature that the views use for their edit dialogs, so that a
    view can open it in place of the generated dialog. Pass `binary=True` for
    the bytes of a Blob, otherwise the value follows `value_type`.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "",
        objVal: Any = None,  # noqa: N803 - the name the views pass
        value_type: XsdType | None = None,
        binary: bool = False,
        content_type: str | None = None,
        **_: object,
    ) -> None:
        """Builds the dialog.

        Args:
            parent: The parent widget.
            title: The window title.
            objVal: The current value, to show first.
            value_type: The type that the value follows. Ignored for bytes.
            binary: Whether the value is the bytes of a Blob.
            content_type: The media type of the bytes, to name a saved file.
            **_: Other arguments of the generated dialogs, which are not used.
        """
        super().__init__(parent)
        self.setWindowTitle(title or "Edit value")
        self.setMinimumWidth(480)
        self._binary = binary
        self.value_edit: ValueEdit | None = None
        self.binary_edit: BinaryEdit | None = None
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.clear_button = self.buttons.addButton(
            "Clear value", QDialogButtonBox.ButtonRole.ResetRole
        )
        layout = QVBoxLayout(self)
        if binary:
            self.binary_edit = BinaryEdit(self)
            self.binary_edit.set_content_type(content_type)
            self.binary_edit.set_data(
                objVal if isinstance(objVal, bytes) else None
            )
            self.binary_edit.changed.connect(self._validate)
            layout.addWidget(self.binary_edit)
            if self.clear_button is not None:
                self.clear_button.clicked.connect(self.binary_edit.clear)
        else:
            self.value_edit = ValueEdit(value_type or datatypes.String, self)
            self.value_edit.set_value(objVal)
            self.value_edit.changed.connect(self._validate)
            layout.addWidget(self.value_edit)
            if self.clear_button is not None:
                self.clear_button.clicked.connect(
                    lambda: (
                        self.value_edit.set_text("")
                        if self.value_edit
                        else None
                    )
                )
        layout.addWidget(self.buttons)
        self._validate()

    def getObj2add(self) -> Any:  # noqa: N802 - the name the views call
        """Returns the value the user entered, or None to clear it.

        Raises:
            InvalidValueError: If the value is not valid.
        """
        if self.binary_edit is not None:
            return self.binary_edit.data()
        assert self.value_edit is not None
        return self.value_edit.value()

    def problem(self) -> str | None:
        """Tells what is wrong with the entered value, or None."""
        if self.binary_edit is not None:
            return self.binary_edit.problem()
        assert self.value_edit is not None
        return self.value_edit.problem()

    def _validate(self) -> None:
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setEnabled(self.problem() is None)
