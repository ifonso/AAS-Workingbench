"""Trees and their headers have no box in the window, on light and on dark.

On dark surfaces the line of a frame (`stroke_subtle`) is much brighter than
both the tree and the window around it, so a frame on the tree and another on
its header read as a grid of boxes. A dialog keeps the line.
"""

from collections.abc import Iterator

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QColor
from PyQt6.QtGui import QImage
from PyQt6.QtGui import QStandardItem
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QDialog
from PyQt6.QtWidgets import QMainWindow
from PyQt6.QtWidgets import QTreeView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot

from aas_editor.domain.design_tokens import ColorTokens
from aas_editor.domain.design_tokens import DARK
from aas_editor.domain.design_tokens import LIGHT
from aas_editor.ui.theme import THEME_DARK
from aas_editor.ui.theme import THEME_LIGHT
from aas_editor.ui.theme import theme_manager

THEMES = [(THEME_LIGHT, LIGHT), (THEME_DARK, DARK)]


@pytest.fixture(autouse=True)
def native_look(qapp: QApplication) -> Iterator[None]:
    """Gives the other tests the look of the platform back."""
    QStandardPaths.setTestModeEnabled(True)
    yield
    theme_manager().reset_to_native()
    QStandardPaths.setTestModeEnabled(False)


def _tree() -> QTreeView:
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(["Package", "Type"])
    for row in range(3):
        model.appendRow([QStandardItem(f"row {row}"), QStandardItem("Type")])
    tree = QTreeView()
    tree.setModel(model)
    return tree


def _edge_pixels(tree: QTreeView) -> list[QColor]:
    """The colors along the four edges of the tree, as a person sees them.

    The header may divide its columns and close itself with a line below, so
    the pixels of those lines are left out. What is left would be a box.
    """
    image: QImage = tree.grab().toImage()
    header = tree.header()
    last_x, last_y = image.width() - 1, image.height() - 1
    dividers = {
        header.sectionPosition(i) + header.sectionSize(i) - 1
        for i in range(header.count())
    }
    header_line = header.height() - 1
    return [
        *(
            image.pixelColor(x, 0)
            for x in range(last_x + 1)
            if x not in dividers
        ),
        *(image.pixelColor(x, last_y) for x in range(last_x + 1)),
        *(
            image.pixelColor(0, y)
            for y in range(last_y + 1)
            if y != header_line
        ),
        *(
            image.pixelColor(last_x, y)
            for y in range(last_y + 1)
            if y != header_line
        ),
    ]


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
def test_a_tree_and_its_header_in_the_window_have_no_outline(
    qtbot: QtBot, choice: str, tokens: ColorTokens
) -> None:
    theme_manager().apply(choice)
    window = QMainWindow()
    qtbot.addWidget(window)
    tree = _tree()
    window.setCentralWidget(tree)
    window.resize(320, 220)
    window.show()
    qtbot.waitExposed(window)

    edges = _edge_pixels(tree)

    assert QColor(tokens.stroke_subtle) not in edges


@pytest.mark.parametrize(("choice", "tokens"), THEMES)
def test_a_tree_in_a_dialog_keeps_its_outline(
    qtbot: QtBot, choice: str, tokens: ColorTokens
) -> None:
    theme_manager().apply(choice)
    dialog = QDialog()
    qtbot.addWidget(dialog)
    holder = QWidget(dialog)
    QVBoxLayout(dialog).addWidget(holder)
    layout = QVBoxLayout(holder)
    tree = _tree()
    layout.addWidget(tree)
    dialog.resize(320, 220)
    dialog.show()
    qtbot.waitExposed(dialog)

    image = tree.grab().toImage()

    assert image.pixelColor(0, image.height() // 2) == QColor(
        tokens.stroke_subtle
    )
