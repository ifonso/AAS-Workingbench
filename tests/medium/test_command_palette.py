"""The command palette lists the actions, finds elements, and runs both."""

from collections.abc import Iterator

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QMainWindow
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.command_palette import EntryKind
from aas_editor.application.command_palette import PaletteEntry
from aas_editor.application.command_palette import RecentCommands
from aas_editor.application.editing import edit_mode
from aas_editor.settings.app_settings import OBJECT_ROLE
from aas_editor.ui.actions import ViewKind
from aas_editor.ui.actions import default_registry
from aas_editor.ui.command_palette import PaletteController
from aas_editor.ui.command_palette import install_palette


@pytest.fixture
def window(qtbot: QtBot, views):
    """A window with menus, the package tree, and the palette.

    The commands used last are kept in memory, so that no test writes to the
    settings of the user.
    """
    from aas_editor.ui.location_actions import register_location_actions
    from aas_editor.ui.move_actions import register_move_actions
    from aas_editor.ui.paste_actions import register_paste_actions

    # The application registers these before its first view.
    register_move_actions()
    register_paste_actions()
    register_location_actions()
    shown = views()
    main = QMainWindow()
    qtbot.addWidget(main)
    main.mainTreeView = shown.view  # type: ignore[attr-defined]
    main.packTreeModel = shown.table  # type: ignore[attr-defined]
    file_menu = main.menuBar().addMenu("&File")
    triggered: list[str] = []
    save = QAction("&Save", main)
    save.setShortcut(QKeySequence("Ctrl+S"))
    save.triggered.connect(lambda: triggered.append("save"))
    file_menu.addAction(save)
    file_menu.addSeparator()
    nested = file_menu.addMenu("Save in")
    json_action = QAction("Save in JSON", main)
    json_action.triggered.connect(lambda: triggered.append("json"))
    nested.addAction(json_action)
    disabled = QAction("Close all", main)
    disabled.setEnabled(False)
    file_menu.addAction(disabled)
    # A window takes a key only while a widget of it has the focus.
    editor = QLineEdit()
    main.setCentralWidget(editor)
    main.resize(900, 600)
    controller = install_palette(main, RecentCommands())

    class Window:
        main_ = main
        controller_ = controller
        palette = controller.palette
        views_ = shown
        editor_ = editor
        ran = triggered
        save_action = save

        @staticmethod
        def titles() -> list[str]:
            return [entry.title for entry in controller.palette.shown_entries]

        @staticmethod
        def entry(key: str) -> PaletteEntry:
            return next(e for e in controller.commands() if e.key == key)

        @staticmethod
        def open_package(*elements: object) -> object:
            package = shown.open_package(
                make_submodel(elements=elements)  # type: ignore[arg-type]
            )
            shown.select(
                shown.index(package=len(shown.table.openedPacks()) - 1)
            )
            return package

    return Window


@pytest.fixture
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look of the platform back."""
    from aas_editor.ui.theme import theme_manager

    QStandardPaths.setTestModeEnabled(True)
    yield
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


# ---------------------------------------------------------------------------
# What it lists
# ---------------------------------------------------------------------------


def test_it_lists_an_entry_for_every_registered_action(window) -> None:
    keys = {entry.key for entry in window.controller_.commands()}
    registered = {
        spec.action_id
        for spec in default_registry().specs_for(ViewKind.PACKAGES)
    }

    assert registered
    assert registered <= keys


def test_it_lists_the_actions_of_the_menus_with_their_keys(window) -> None:
    save = window.entry("menu:File > Save")

    assert (save.title, save.detail, save.shortcut) == (
        "Save",
        "File",
        "Ctrl+S",
    )


def test_it_walks_a_submenu_and_names_its_path(window) -> None:
    entry = window.entry("menu:File > Save in > Save in JSON")

    assert entry.detail == "File > Save in"


def test_the_submenu_itself_is_no_command(window) -> None:
    titles = [entry.title for entry in window.controller_.commands()]

    assert "Save in" not in titles


def test_it_lists_the_actions_that_only_the_tree_has(window) -> None:
    titles = {entry.title for entry in window.controller_.commands()}

    assert {"Copy", "Paste", "Undo", "Redo"} <= titles


def test_the_action_of_the_palette_is_not_in_its_own_list(window) -> None:
    window.main_.menuBar().addMenu("&Go").addAction(window.controller_.action)

    payloads = [entry.payload for entry in window.controller_.commands()]

    assert window.controller_.action not in payloads


def test_an_action_of_a_menu_and_the_registry_is_listed_once(window) -> None:
    menu = window.main_.menuBar().addMenu("&Navigate")
    registered = window.views_.view.registeredActions.actions[0]
    menu.addAction(registered)

    payloads = [entry.payload for entry in window.controller_.commands()]

    assert payloads.count(registered) == 1


def test_a_disabled_action_is_listed_as_disabled(window) -> None:
    entry = window.entry("menu:File > Close all")

    assert entry.enabled is False


def test_a_command_that_edits_says_that_read_mode_is_why_it_is_off(
    window,
) -> None:
    window.open_package(make_property("A"), make_property("B"))
    edit_mode().set_editing(False)
    undo = next(
        e for e in window.controller_.commands() if e.title == "Delete/clear"
    )

    assert not undo.enabled
    assert "Read mode is on" in undo.reason


def test_a_registered_action_that_does_not_apply_says_so(window) -> None:
    window.open_package(make_property("A"))

    move_up = window.entry("structure.move_up")

    assert not move_up.enabled
    assert move_up.reason == "Does not apply to the selected row"


def test_a_registered_action_that_cannot_run_in_read_mode_says_so(
    window,
) -> None:
    window.open_package(make_property("A"), make_property("B"))
    window.views_.select(window.views_.index("submodels", "Submodel", "B"))
    edit_mode().set_editing(False)
    window.views_.view.registeredActions.update()

    move_up = window.entry("structure.move_up")

    assert not move_up.enabled
    assert "Read mode is on" in move_up.reason


# ---------------------------------------------------------------------------
# Opening, typing, and picking
# ---------------------------------------------------------------------------


def test_the_key_opens_the_palette_with_the_field_ready(
    window, qtbot: QtBot
) -> None:
    window.main_.show()
    window.main_.activateWindow()
    qtbot.waitActive(window.main_)
    window.editor_.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is window.editor_)

    QTest.keySequence(window.editor_, QKeySequence("Ctrl+K"))

    assert window.palette.isVisible()
    assert window.palette.input.text() == ""
    qtbot.waitUntil(window.palette.input.hasFocus, timeout=2000)


def test_the_key_is_ctrl_k(window) -> None:
    assert window.controller_.action.shortcut() == QKeySequence("Ctrl+K")


def test_ctrl_k_is_bound_to_no_other_action(window) -> None:
    owners = [
        action
        for action in window.main_.findChildren(QAction)
        if QKeySequence("Ctrl+K") in action.shortcuts()
    ]

    assert owners == [window.controller_.action]


def test_ctrl_k_is_not_a_key_of_a_registered_action_or_the_tree() -> None:
    taken = {
        shortcut
        for spec in default_registry().specs_for(ViewKind.ANY)
        if spec.shortcut is not None
        for shortcut in [spec.shortcut]
    }

    assert QKeySequence("Ctrl+K") not in taken


def test_the_empty_palette_lists_commands_and_no_elements(window) -> None:
    window.open_package(make_property("Pump"))
    window.controller_.open()

    kinds = {entry.kind for entry in window.palette.shown_entries}

    assert kinds == {EntryKind.COMMAND}


def test_typing_filters_the_commands(window) -> None:
    window.controller_.open()

    window.palette.input.setText("save")

    assert window.titles()[:2] == ["Save", "Save in JSON"]
    assert "Close all" not in window.titles()


def test_enter_runs_the_first_command(window) -> None:
    window.controller_.open()
    window.palette.input.setText("save")

    QTest.keyClick(window.palette.input, Qt.Key.Key_Return)
    QApplication.processEvents()

    assert window.ran == ["save"]
    assert not window.palette.isVisible()


def test_the_arrow_keys_move_the_selection(window) -> None:
    window.controller_.open()
    window.palette.input.setText("save")

    QTest.keyClick(window.palette.input, Qt.Key.Key_Down)

    assert window.palette.current_entry is not None
    assert window.palette.current_entry.title == "Save in JSON"


def test_the_arrow_up_stops_at_the_first_entry(window) -> None:
    window.controller_.open()
    window.palette.input.setText("save")

    QTest.keyClick(window.palette.input, Qt.Key.Key_Up)

    assert window.palette.current_entry is not None
    assert window.palette.current_entry.title == "Save"


def test_a_click_on_a_row_runs_it(window, qtbot: QtBot) -> None:
    window.main_.show()
    window.controller_.open()
    window.palette.input.setText("save in json")
    # The click is the signal of the list. A real mouse click inside a popup
    # does not return under the offscreen platform.
    window.palette.results.clicked.emit(
        window.palette.results.model().index(0, 0)
    )

    qtbot.waitUntil(lambda: window.ran == ["json"], timeout=2000)
    assert not window.palette.isVisible()


def test_escape_closes_the_palette_and_runs_nothing(
    window, qtbot: QtBot
) -> None:
    window.main_.show()
    window.controller_.open()

    QTest.keyClick(window.palette, Qt.Key.Key_Escape)

    assert not window.palette.isVisible()
    assert window.ran == []


def test_enter_on_a_disabled_command_stays_and_says_why(window) -> None:
    window.controller_.open()
    window.palette.input.setText("close all")

    QTest.keyClick(window.palette.input, Qt.Key.Key_Return)

    assert window.palette.isVisible()
    assert window.palette.note.text().startswith("Not available")


def test_the_reason_of_a_disabled_registered_command_is_in_the_note(
    window,
) -> None:
    window.open_package(make_property("A"))
    window.controller_.open()
    window.palette.input.setText("move up")

    assert window.palette.current_entry is not None
    assert "Does not apply" in window.palette.note.text()


def test_a_query_with_no_match_says_so(window) -> None:
    window.controller_.open()

    window.palette.input.setText("zzzzzz")

    assert window.palette.note.text() == "Nothing matches 'zzzzzz'"
    assert window.palette.shown_entries == []


def test_the_palette_opens_empty_after_it_was_used(window) -> None:
    window.controller_.open()
    window.palette.input.setText("save")
    window.palette.close()

    window.controller_.open()

    assert window.palette.input.text() == ""


# ---------------------------------------------------------------------------
# Recent commands
# ---------------------------------------------------------------------------


def test_a_command_that_ran_comes_first_next_time(window) -> None:
    window.controller_.open()
    window.palette.input.setText("save in json")
    window.palette.choose_current()
    QApplication.processEvents()

    window.controller_.open()

    assert window.titles()[0] == "Save in JSON"


def test_recent_commands_are_stored_through_the_store(
    qtbot: QtBot, views
) -> None:
    main = QMainWindow()
    qtbot.addWidget(main)
    shown = views()
    main.mainTreeView = shown.view  # type: ignore[attr-defined]
    main.packTreeModel = shown.table  # type: ignore[attr-defined]
    action = QAction("Do it", main)
    main.menuBar().addMenu("&Menu").addAction(action)
    stored: list[list[str]] = [["menu:Menu > Do it"]]
    controller = PaletteController(
        main, RecentCommands(lambda: stored[-1], stored.append)
    )

    controller.open()

    assert controller.palette.shown_entries[0].title == "Do it"
    controller.palette.input.setText("do")
    controller.palette.choose_current()
    QApplication.processEvents()
    assert stored[-1] == ["menu:Menu > Do it"]


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------


def test_a_name_finds_an_element_of_the_open_package(window) -> None:
    window.open_package(make_property("Speed"), make_property("Pressure"))
    window.controller_.open()

    window.palette.input.setText("speed")

    found = [
        e for e in window.palette.shown_entries if e.kind is EntryKind.ELEMENT
    ]
    assert [e.title for e in found] == ["Speed"]
    assert found[0].detail == "Property in Submodel"


def test_a_name_finds_an_element_inside_a_collection(window) -> None:
    window.open_package(make_collection("Motor", [make_property("Speed")]))
    window.controller_.open()

    window.palette.input.setText("speed")

    found = [
        e for e in window.palette.shown_entries if e.kind is EntryKind.ELEMENT
    ]
    assert found[0].detail == "Property in Motor"


def test_the_id_of_a_submodel_finds_it(window) -> None:
    window.open_package()
    window.controller_.open()

    window.palette.input.setText("urn:")

    found = [
        e for e in window.palette.shown_entries if e.kind is EntryKind.ELEMENT
    ]
    assert [e.title for e in found] == ["Submodel"]


def test_picking_an_element_selects_it_in_the_tree(window) -> None:
    speed = make_property("Speed")
    window.open_package(speed, make_property("Pressure"))
    window.views_.view.collapseAll()
    window.controller_.open()
    window.palette.input.setText("speed")

    window.palette.choose_current()
    QApplication.processEvents()

    current = window.views_.view.currentIndex()
    assert current.data(OBJECT_ROLE) is speed


def test_picking_an_element_of_the_second_package_selects_it_there(
    window,
) -> None:
    window.open_package(make_property("One"))
    target = make_property("Two")
    window.open_package(target)
    window.views_.select(window.views_.index(package=0))
    window.controller_.open()
    window.palette.input.setText("two")

    window.palette.choose_current()
    QApplication.processEvents()

    assert window.views_.view.currentIndex().data(OBJECT_ROLE) is target


def test_with_two_packages_open_an_element_names_its_package(window) -> None:
    window.open_package(make_property("One"))
    window.open_package(make_property("Two"))
    window.controller_.open()

    window.palette.input.setText("two")

    found = [
        e for e in window.palette.shown_entries if e.kind is EntryKind.ELEMENT
    ]
    assert " in " in found[0].detail and found[0].detail.count(" in ") == 2


def test_the_elements_are_gathered_when_the_first_word_is_typed(window) -> None:
    window.open_package(make_property("Speed"))
    gathered: list[int] = []
    controller = window.controller_
    original = controller.elements

    def counting() -> list[PaletteEntry]:
        gathered.append(1)
        return original()

    window.palette.open_over(window.main_, controller.commands(), counting)
    assert gathered == []

    window.palette.input.setText("s")
    window.palette.input.setText("sp")

    assert gathered == [1]


def test_an_element_that_the_tree_hides_is_reported_and_nothing_breaks(
    window,
) -> None:
    package = window.open_package(make_property("Speed"))
    window.controller_.open()
    entry = PaletteEntry(
        "element:gone",
        "Gone",
        EntryKind.ELEMENT,
        payload=(package, make_property("Gone")),
    )

    shown = window.controller_.run(entry)

    assert shown is False
    assert "does not show Gone" in window.main_.statusBar().currentMessage()


# ---------------------------------------------------------------------------
# The look follows the tokens
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme", ["fluent-light", "fluent-dark"])
def test_the_palette_is_painted_in_the_colors_of_the_theme(
    window, native_look: None, theme: str
) -> None:
    from aas_editor.ui.theme import current_tokens
    from aas_editor.ui.theme import theme_manager

    theme_manager().apply(theme)
    window.main_.show()
    window.controller_.open()
    window.palette.input.setText("save in json")
    tokens = current_tokens()
    viewport = window.palette.results.viewport()
    image = viewport.grab().toImage()
    row = window.palette.results.visualRect(
        window.palette.results.model().index(0, 0)
    )

    empty = image.pixelColor(viewport.width() // 2, viewport.height() - 4)
    selected = image.pixelColor(viewport.width() - 24, row.center().y())
    frame = window.palette.grab().toImage().pixelColor(0, 40)

    assert empty == QColor(tokens.bg_content)
    assert selected == QColor(tokens.bg_selected)
    assert frame == QColor(tokens.stroke_default)


def test_a_switch_of_theme_changes_what_the_next_opening_paints(
    window, native_look: None
) -> None:
    from aas_editor.ui.theme import theme_manager

    window.main_.show()

    def background(theme: str) -> QColor:
        theme_manager().apply(theme)
        window.controller_.open()
        window.palette.input.setText("zzzzzz")
        viewport = window.palette.results.viewport()
        color = viewport.grab().toImage().pixelColor(5, 5)
        window.palette.close()
        return color

    assert background("fluent-light") != background("fluent-dark")


def test_the_parts_of_the_palette_have_accessible_names(window) -> None:
    palette = window.palette

    assert palette.accessibleName() == "Command palette"
    assert palette.input.accessibleName()
    assert palette.results.accessibleName()


def test_a_letter_of_another_script_reaches_the_field(
    window,
) -> None:
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent

    window.controller_.open()
    # QTest.keyClicks crashes on a letter of another script, so the event is
    # made here.
    letter = "中"
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        ord(letter),
        Qt.KeyboardModifier.NoModifier,
        letter,
    )

    QApplication.sendEvent(window.palette.input, event)

    assert window.palette.input.text() == letter
    assert window.palette.isVisible()
