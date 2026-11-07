"""The dialog that imports a value list from text, with a preview.

The text starts as the content of the clipboard and can be edited. After every
change it is read again with `parse_value_pairs`, and the table shows each
entry with its outcome: a pair that will be added, one that the list has
already, or the reason why the entry cannot be used. Text that cannot be read
at all shows a message instead of a table. Nothing is evaluated, and the
accept button is enabled only when there is at least one pair to add.
"""

from basyx.aas import model
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

from aas_editor.ui.colors import style_as_problem
from aas_editor.application.operations.data_specs import ImportPlan
from aas_editor.application.operations.data_specs import plan_value_list_import
from aas_editor.domain.references import describe_reference
from aas_editor.domain.value_list_text import ValueListParse
from aas_editor.domain.value_list_text import parse_value_pairs
from aas_editor.ui.concept_dialogs import answered_yes
from aas_editor.ui.dialog_layout import accept_button
from aas_editor.ui.dialog_layout import finish_dialog
from aas_editor.ui.dialog_layout import make_button_box
from aas_editor.ui.reference_dialogs import ReferenceTable

STATUS_ADD = "will be added"
STATUS_HAVE = "already in the value list"
# A table of thousands of rows is slow to build and nobody reads it.
MAX_PREVIEW_ROWS = 500


class ValueListImportDialog(QDialog):
    """Reads pairs from text and previews the import.

    Attributes:
        text_edit: The text to read. It can be edited.
        table: One row for each entry of the text: place, value, value id,
            and what happens to it.
        error_label: Why the text cannot be read at all, or empty.
        summary_label: How many pairs will be added.
        buttons: The accept and the cancel button.
        plan: The import for the text now, or None when there is nothing to
            add.
    """

    def __init__(
        self,
        content: model.DataSpecificationIEC61360,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        """Builds the dialog.

        Args:
            content: The IEC 61360 content that gets the pairs.
            text: The text to start with, usually from the clipboard.
            parent: The parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Import value list")
        self.setMinimumSize(720, 520)
        self._content = content
        self.plan: ImportPlan | None = None

        intro = QLabel(
            "One pair a line as 'value, valueId' (a tab works too), or JSON "
            "pairs. A pair needs a valueId."
        )
        intro.setWordWrap(True)
        self.text_edit = QPlainTextEdit(text)
        self.text_edit.setMaximumHeight(140)
        self.table = ReferenceTable(["Entry", "Value", "Value id", "Result"])
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        style_as_problem(self.error_label)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.buttons = make_button_box(self, "Import", safe_default=True)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.text_edit)
        layout.addWidget(self.error_label)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.buttons)
        finish_dialog(self)

        self.text_edit.textChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        parse = parse_value_pairs(self.text_edit.toPlainText())
        self.error_label.setText(parse.error or "")
        self.plan = plan_value_list_import(self._content, parse.pairs)
        self.table.set_rows(self._rows(parse))
        self.summary_label.setText(self._summary(parse))
        button = accept_button(self.buttons)
        if button is not None:
            button.setEnabled(bool(self.plan.added))

    def _rows(self, parse: ValueListParse) -> list[list[str]]:
        assert self.plan is not None
        added = {id(p) for p in self.plan.added}
        rows: list[list[str]] = []
        for entry in parse.entries[:MAX_PREVIEW_ROWS]:
            if entry.pair is None:
                rows.append(
                    [entry.place, entry.source, "", f"skipped: {entry.problem}"]
                )
                continue
            value_id = (
                ""
                if entry.pair.value_id is None
                else describe_reference(entry.pair.value_id)
            )
            status = STATUS_ADD if id(entry.pair) in added else STATUS_HAVE
            rows.append([entry.place, entry.pair.value, value_id, status])
        return rows

    def _summary(self, parse: ValueListParse) -> str:
        assert self.plan is not None
        if parse.error:
            return ""
        parts = [
            f"{len(self.plan.added)} pair"
            f"{'' if len(self.plan.added) == 1 else 's'} will be added"
        ]
        if self.plan.duplicates:
            parts.append(f"{len(self.plan.duplicates)} already in the list")
        if parse.problems:
            parts.append(f"{len(parse.problems)} skipped")
        text = ", ".join(parts) + "."
        if len(parse.entries) > MAX_PREVIEW_ROWS:
            text += f" The table shows the first {MAX_PREVIEW_ROWS} entries."
        return text


def ask_value_list(
    content: model.DataSpecificationIEC61360,
    text: str,
    parent: QWidget | None = None,
) -> ImportPlan | None:
    """Asks the user to check and confirm a value list import.

    Args:
        content: The content that gets the pairs.
        text: The text to start with.
        parent: The parent widget.

    Returns:
        The import, or None if the user cancelled or there is nothing to add.
    """
    dialog = ValueListImportDialog(content, text, parent)
    if not answered_yes(dialog):
        return None
    return dialog.plan if dialog.plan and dialog.plan.added else None
