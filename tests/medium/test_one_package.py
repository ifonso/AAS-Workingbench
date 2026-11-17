"""The editor has one package open at a time.

Opening or creating a package closes the one that is open, after asking about
its changes, and the package tree starts at the groups of the open package,
whose row it does not show. The header of the pane has the menu of the package.
"""

from pathlib import Path
import shutil
from typing import Any

from PyQt6.QtCore import QModelIndex
from PyQt6.QtWidgets import QMessageBox
import pytest
from tests.conftest import TEST_DATA_DIR

from aas_workingbench.settings.app_settings import OPENED_PACKS_ROLE

FIRST = TEST_DATA_DIR / "IDTA 02002-1-0_Template_ContactInformation.json"
SECOND = TEST_DATA_DIR / "IDTA 02058-1-0_Template_AIDataset.json"


@pytest.fixture
def tree(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """A package tree whose files are copies, and whose questions are noted."""
    shown = views()
    shown.asked = []

    def answer(box: QMessageBox) -> QMessageBox.StandardButton:
        shown.asked.append(box.text())
        return shown.answer

    monkeypatch.setattr(QMessageBox, "exec", answer)
    shown.answer = QMessageBox.StandardButton.Discard
    shown.files = []
    for source in (FIRST, SECOND):
        copy = tmp_path / source.name
        shutil.copy(source, copy)
        shown.files.append(copy.as_posix())
    return shown


def _open_packages(shown: Any) -> list[Any]:
    return list(shown.view.model().data(QModelIndex(), OPENED_PACKS_ROLE))


def test_opening_a_second_package_closes_the_first(tree) -> None:
    tree.view.openPack(tree.files[0])

    second = tree.view.openPack(tree.files[1])

    assert _open_packages(tree) == [second]
    assert tree.asked == []


def test_a_package_with_changes_asks_before_it_closes(tree) -> None:
    first = tree.view.openPack(tree.files[0])
    first.changed = True

    second = tree.view.openPack(tree.files[1])

    assert len(tree.asked) == 1
    assert _open_packages(tree) == [second]


def test_cancel_keeps_the_open_package_and_opens_nothing(tree) -> None:
    first = tree.view.openPack(tree.files[0])
    first.changed = True
    tree.answer = QMessageBox.StandardButton.Cancel

    second = tree.view.openPack(tree.files[1])

    assert second is None
    assert _open_packages(tree) == [first]
    first.changed = False


def test_the_tree_starts_at_the_groups_of_the_package(tree) -> None:
    tree.view.openPack(tree.files[0])

    root = tree.view.rootIndex()

    assert root == tree.view.packageIndex()
    model = tree.view.model()
    groups = [
        model.index(r, 0, root).data() for r in range(model.rowCount(root))
    ]
    assert "Submodels" in groups


def test_without_a_package_the_tree_has_no_root(tree) -> None:
    tree.view.openPack(tree.files[0])

    tree.view.closeAllFiles()

    assert not tree.view.rootIndex().isValid()


def test_the_menu_of_the_package_is_for_the_package(
    tree, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QMenu

    shown: list[QMenu] = []
    monkeypatch.setattr(QMenu, "exec", lambda menu, *a: shown.append(menu))
    tree.view.openPack(tree.files[0])

    tree.view.openPackageMenu(QPoint(0, 0))

    assert shown == [tree.view.attrsMenu]
    assert tree.view.currentIndex() == tree.view.packageIndex()
    assert tree.view.closeAct.isEnabled()


def test_close_closes_the_package_without_its_row_being_current(tree) -> None:
    tree.view.openPack(tree.files[0])
    group = tree.view.model().index(0, 0, tree.view.rootIndex())
    tree.view.setCurrentIndex(group)

    tree.view.closeFileWithDialog()

    assert _open_packages(tree) == []
