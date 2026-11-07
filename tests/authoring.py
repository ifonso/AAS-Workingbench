"""Drives the main window as a person does, from an empty application.

`Author` wraps a real main window with no package open. It starts a package
with the New button of the start panel, and finds, selects, and acts on the
rows of the package tree. Dialogs that the editor opens are answered by a
script that fills their fields, because a modal dialog would block the test.
Nothing here edits the model: the editor does that, through its own actions.
"""

from collections.abc import Callable
from collections.abc import Iterator
import contextlib
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QItemSelectionModel
from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QDialogButtonBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QInputDialog


def register_every_action() -> None:
    """Registers the actions that `__main__.py` registers, in its order."""
    from aas_editor.ui.blob_actions import register_blob_actions
    from aas_editor.ui.bulk_actions import register_bulk_actions
    from aas_editor.ui.bulk_edit_actions import register_bulk_edit_actions
    from aas_editor.ui.concept_actions import register_concept_actions
    from aas_editor.ui.conversion_actions import register_conversion_actions
    from aas_editor.ui.create_actions import register_create_actions
    from aas_editor.ui.file_actions import register_file_actions
    from aas_editor.ui.load_report_actions import register_load_report_actions
    from aas_editor.ui.location_actions import register_location_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions
    from aas_editor.ui.preset_actions import register_preset_actions
    from aas_editor.ui.reference_actions import register_reference_actions
    from aas_editor.ui.reference_jump import register_jump_actions
    from aas_editor.ui.shell_copy_actions import register_shell_copy_actions

    register_blob_actions()
    register_file_actions()
    register_reference_actions()
    register_move_actions()
    register_paste_actions()
    register_jump_actions()
    register_create_actions()
    register_shell_copy_actions()
    register_bulk_actions()
    register_concept_actions()
    register_conversion_actions()
    register_bulk_edit_actions()
    register_preset_actions()
    register_load_report_actions()
    register_location_actions()


@dataclass
class Answer:
    """What happened to a dialog that a script answered.

    Attributes:
        dialogs: The dialogs that the editor opened, in order.
        ok_enabled: Whether the OK button was on when the script was done.
        problem: The reason that the dialog gave for a disabled OK, if it
            has one.
        asked_again: Whether the editor refused the answer and opened the
            dialog again. The second dialog is cancelled.
    """

    dialogs: list[Any] = field(default_factory=list)
    ok_enabled: bool | None = None
    problem: str = ""
    asked_again: bool = False

    @property
    def accepted(self) -> bool:
        """Whether the first dialog was closed with OK."""
        return bool(self.dialogs) and self.ok_enabled is True


def button_of(dialog: Any, role: QDialogButtonBox.ButtonRole) -> Any:
    """Finds the button of a dialog that accepts it, or that rejects it.

    Returns:
        The button, or None for a dialog that has none of that role, such as
        a message with an OK button only.
    """
    box = dialog.findChild(QDialogButtonBox)
    assert box is not None, type(dialog).__name__
    for button in box.buttons():
        if box.buttonRole(button) is role:
            return button
    return None


class _Closer:
    """Stands for the cancel button of a dialog that has none."""

    def __init__(self, dialog: Any) -> None:
        self._dialog = dialog

    def click(self) -> None:
        self._dialog.reject()


ACCEPT = QDialogButtonBox.ButtonRole.AcceptRole
REJECT = QDialogButtonBox.ButtonRole.RejectRole


class Author:
    """A person at the main window of the editor."""

    def __init__(self, window: Any, monkeypatch: Any, folder: Path) -> None:
        self.window = window
        self.monkeypatch = monkeypatch
        self.folder = folder
        self.errors: list[str] = []
        self.details: list[str] = []
        self.replies: list[tuple[str, str]] = []
        self.questions: list[str] = []
        self._record_messages()

    @property
    def view(self) -> Any:
        return self.window.mainTreeView

    @property
    def package(self) -> Any:
        (package,) = self.window.packTreeModel.openedPacks()
        return package

    @property
    def stack(self) -> Any:
        return self.package.commandStack

    def _record_messages(self) -> None:
        """Keeps the text of every message box, which would block the test.

        A box that asks something is answered by the first reply of
        `self.replies` whose text is in the box, by clicking the button of
        that name. A box with no reply is cancelled.
        """
        from PyQt6.QtWidgets import QMessageBox

        from aas_editor.widgets.messsageBoxes import ErrorMessageBox

        def record(box: Any) -> int:
            text = box.text()
            if box.informativeText():
                text = f"{text} {box.informativeText()}"
            self.errors.append(text)
            self.details.append(box.detailedText())
            for wanted, button_text in self.replies:
                if wanted in text:
                    for button in box.buttons():
                        if button.text().replace("&", "") == button_text:
                            button.click()
                            return box.result()
                    raise AssertionError(f"No '{button_text}' in: {text}")
            return QDialog.DialogCode.Rejected

        self.monkeypatch.setattr(QMessageBox, "exec", record)
        self.monkeypatch.setattr(ErrorMessageBox, "exec", record)

        # The static helpers run a box of their own in C++, which would block.
        def static_box(default: str) -> Any:
            def show(parent: Any, title: str, text: str, *args: Any) -> Any:
                self.errors.append(f"{title}: {text}")
                answer = default
                for wanted, button_text in self.replies:
                    if wanted in text:
                        answer = button_text
                return getattr(QMessageBox.StandardButton, answer)

            return staticmethod(show)

        for name, default in (
            ("warning", "Ok"),
            ("critical", "Ok"),
            ("information", "Ok"),
            ("question", "No"),
        ):
            self.monkeypatch.setattr(QMessageBox, name, static_box(default))

    def _last_detail(self) -> str:
        lines = self.details[-1].strip().splitlines() if self.details else []
        return lines[-1] if lines else ""

    def assert_accepted(self, answer: Answer) -> None:
        """Fails with what the editor said if a dialog was not accepted."""
        if not answer.accepted:
            raise AssertionError(
                f"The dialog was not accepted. OK on: {answer.ok_enabled}. "
                f"Problem: {answer.problem!r}. Messages: {self.errors}. "
                f"Last line of the details: {self._last_detail()}"
            )

    @contextlib.contextmanager
    def answering(
        self, dialog_class: type, script: Callable[[Any], None]
    ) -> Iterator[Answer]:
        """Makes a modal dialog fill itself by a script and press its OK.

        A modal `exec` would block the test. The stand-in runs the script on
        the dialog, and then presses OK if the dialog allows it, as a user
        does. A dialog whose OK is off is cancelled, and `ok_enabled` says so.
        If the editor refuses the answer and asks again, the second dialog is
        cancelled and `asked_again` is set.
        """
        answer = Answer()

        def fake_exec(dialog: Any) -> int:
            answer.dialogs.append(dialog)
            cancel = button_of(dialog, REJECT) or _Closer(dialog)
            if len(answer.dialogs) > 1:
                answer.asked_again = True
                cancel.click()
                return QDialog.DialogCode.Rejected
            script(dialog)
            ok = button_of(dialog, ACCEPT)
            assert ok is not None, type(dialog).__name__
            answer.ok_enabled = ok.isEnabled()
            answer.problem = getattr(dialog, "problem", "")
            if not answer.problem and hasattr(dialog, "error_label"):
                answer.problem = dialog.error_label.text()
            if not ok.isEnabled():
                cancel.click()
                return QDialog.DialogCode.Rejected
            ok.click()
            return dialog.result()

        self.monkeypatch.setattr(dialog_class, "exec", fake_exec)
        yield answer

    def pick_save_path(self, path: Path | None) -> None:
        """Makes the next file dialogs for saving answer with a path.

        None answers as a cancel does.
        """
        answer = (str(path), "") if path is not None else ("", "")
        self.monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            staticmethod(lambda *args, **kwargs: answer),
        )

    def pick_open_path(self, path: Path | None) -> None:
        """Makes the next file dialogs for opening answer with a path."""
        answer = (str(path), "") if path is not None else ("", "")
        self.monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            staticmethod(lambda *args, **kwargs: answer),
        )

    def answer_text_question(self, text: str | None = None) -> None:
        """Makes the one-line question dialogs accept with a text.

        Without a text they accept the one that the dialog offers.
        """

        def get_text(
            parent: Any,
            title: str,
            label: str,
            mode: Any = None,
            offered: str = "",
            *args: Any,
        ) -> tuple[str, bool]:
            self.questions.append(f"{title}: {label}")
            return (offered if text is None else text, True)

        self.monkeypatch.setattr(
            QInputDialog, "getText", staticmethod(get_text)
        )

    def answer_choice(self, choice: str) -> None:
        """Makes the questions that pick one of a list of texts choose one."""

        def get_item(
            parent: Any,
            title: str,
            label: str,
            items: list[str],
            *args: Any,
        ) -> tuple[str, bool]:
            self.questions.append(f"{title}: {label} {items}")
            return (choice, choice in items)

        self.monkeypatch.setattr(
            QInputDialog, "getItem", staticmethod(get_item)
        )

    def open_tab(self, *names: str) -> Any:
        """Opens an item in a new tab, as Open in new tab does, and returns it."""
        self.window.mainTabWidget.openItemInNewTab(self.path(*names))
        return self.window.mainTabWidget.currentWidget()

    def start_new_package(self, path: Path, kind: str = "aasx") -> None:
        """Presses New on the start panel and picks the entry of a file kind."""
        self.pick_save_path(path)
        menu = self.window.emptyState.new_button.menu()
        (action,) = [a for a in menu.actions() if a.text().endswith(kind)]
        action.trigger()
        self.view.expandAll()

    def find(self, parent: QModelIndex, name: str) -> QModelIndex:
        from aas_editor.settings.app_settings import NAME_ROLE

        proxy = self.view.model()
        self.view.expand(parent)
        for row in range(proxy.rowCount(parent)):
            child = proxy.index(row, 0, parent)
            if child.data(NAME_ROLE) == name:
                return child
        raise LookupError(f"{name} below {parent.data()}")

    def path(self, *names: str) -> QModelIndex:
        """Finds a row by the names from the package down."""
        index = self.view.model().index(0, 0)
        for name in names:
            index = self.find(index, name)
        return index

    def names(self, *names: str) -> list[str]:
        from aas_editor.settings.app_settings import NAME_ROLE

        proxy = self.view.model()
        parent = self.path(*names)
        return [
            proxy.index(row, 0, parent).data(NAME_ROLE)
            for row in range(proxy.rowCount(parent))
        ]

    def select(self, *indexes: QModelIndex) -> None:
        selection = self.view.selectionModel()
        selection.clear()
        for index in indexes:
            selection.select(index, QItemSelectionModel.SelectionFlag.Select)
        selection.setCurrentIndex(
            indexes[-1], QItemSelectionModel.SelectionFlag.NoUpdate
        )

    def select_path(self, *names: str) -> QModelIndex:
        index = self.path(*names)
        self.select(index)
        return index

    def act(self, action_id: str) -> bool:
        """Triggers a registered action of the tree, and says if it was on."""
        action = self.view.registeredActions.find(action_id)
        assert action is not None, action_id
        enabled = action.isEnabled()
        action.trigger()
        return enabled

    def edit_menu(self, key: str) -> bool:
        """Chooses an entry of the Edit menu, and says if it was on.

        The entries follow the view with the focus, which is the package tree
        unless a tab has taken it.
        """
        action = self.window.focusedActs.actions[key]
        assert action in self.window.menuEdit.actions(), key
        enabled = action.isEnabled()
        action.trigger()
        return enabled

    def undo_all(self) -> int:
        steps = 0
        while self.stack.can_undo:
            self.view.onUndo()
            steps += 1
        return steps

    def undo_to_saved(self) -> int:
        """Undoes the steps made since the last save or `mark_saved`."""
        steps = 0
        while not self.stack.is_clean:
            self.view.onUndo()
            steps += 1
        return steps

    def redo_all(self) -> int:
        steps = 0
        while self.stack.can_redo:
            self.view.onRedo()
            steps += 1
        return steps

    # -- adding through the real dialogs --------------------------------

    def add_element(
        self,
        path: tuple[str, ...],
        element_type: type,
        id_short: str | None,
        fill: Callable[[Any], None] | None = None,
    ) -> Answer:
        """Selects a row, presses Add, and fills the dialog of the element.

        Args:
            path: The names from the package down to the row to add to.
            element_type: The class to choose in the dialog, or None where the
                dialog has no chooser, such as below a list of one type.
            id_short: The idShort to type, or None for an element without one.
            fill: Fills the other fields of the form.

        Returns:
            What happened to the dialog.
        """
        from tests.medium.forms import Form

        from aas_editor.dialogs import EditObjDialog

        def script(dialog: Any) -> None:
            form = Form(dialog)
            if hasattr(dialog.inputWidget, "typeComboBox"):
                form.choose_type(element_type)
            if id_short is not None:
                form.type_text("id_short", id_short)
            if fill is not None:
                fill(form)

        self.select_path(*path)
        action = self.view.addAct
        assert action.isEnabled(), f"Add is off on {path}"
        with self.answering(EditObjDialog, script) as answer:
            action.trigger()
        return answer

    # -- editing in the cells ------------------------------------------------

    def show_column(self, column: str) -> None:
        """Shows a column of the package tree with the Columns entry of View."""
        self.window.fillColumnsMenu()
        (action,) = [
            a
            for a in self.window.menuColumns.actions()
            if a.text().replace("&", "") == column
        ]
        if not action.isChecked():
            action.trigger()
        assert action.isChecked(), column

    def cell(self, column: str, *names: str) -> QModelIndex:
        """Finds a cell of the package tree by its column and the row path."""
        from PyQt6.QtCore import Qt

        source = self.view.sourceModel()
        number = [
            source.headerData(i, Qt.Orientation.Horizontal, 0)
            for i in range(source.columnCount())
        ].index(column)
        return self.path(*names).siblingAtColumn(number)

    def edit_cell(self, column: str, text: str, *names: str) -> bool:
        """Types a text into a cell with its editor, and presses Enter.

        Returns:
            Whether the text was taken. A refused text leaves the old value,
            and the reason is in `errors`.
        """
        return self._type_into(self.view, self.cell(column, *names), text)

    def attribute_cell(self, attrs: Any, name: str) -> QModelIndex:
        """Finds the value cell of an attribute row in the tree of a tab."""
        from aas_editor.settings.app_settings import NAME_ROLE

        proxy = attrs.model()
        for row in range(proxy.rowCount()):
            if proxy.index(row, 0).data(NAME_ROLE) == name:
                return proxy.index(row, 1)
        raise LookupError(name)

    def edit_attribute(self, tab: Any, name: str, text: str) -> bool:
        """Types a text into the value of an attribute in the tab of an item."""
        attrs = tab.attrsTreeView
        return self._type_into(attrs, self.attribute_cell(attrs, name), text)

    def double_click(self, view: Any, index: QModelIndex) -> None:
        """Double clicks a cell with the mouse, which edits it."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest

        view.scrollTo(index)
        point = view.visualRect(index).center()
        assert view.viewport().rect().contains(point), index.data()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        QTest.mouseDClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)

    def edit_attribute_in_dialog(
        self, tab: Any, name: str, script: Callable[[Any], None]
    ) -> Answer:
        """Double clicks an attribute whose editor is a dialog, and fills it."""
        from aas_editor.dialogs import EditObjDialog

        attrs = tab.attrsTreeView
        with self.answering(EditObjDialog, script) as answer:
            self.double_click(attrs, self.attribute_cell(attrs, name))
        return answer

    def _type_into(self, view: Any, index: QModelIndex, text: str) -> bool:
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QLineEdit

        self.double_click(view, index)
        # An editor that closed is deleted when the loop runs, so only an
        # editor that is shown counts.
        editors = [
            e for e in view.viewport().findChildren(QLineEdit) if e.isVisible()
        ]
        assert editors, f"No line editor for {index.data()}"
        editors[-1].setText(text)
        before = len(self.errors)
        QTest.keyClick(editors[-1], Qt.Key.Key_Return)
        # The editor commits when the loop runs.
        QApplication.processEvents()
        return len(self.errors) == before
