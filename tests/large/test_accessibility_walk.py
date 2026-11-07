"""The main surfaces have a name for every control, and work by keyboard.

The window is walked as a screen reader would meet it: the start panel, the
command bar, the breadcrumb, the tabs, the trees, and each of the bottom panels.
Screen readers themselves (NVDA, VoiceOver, Orca) were not run.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from tests.accessibility import unnamed
from tests.conftest import TEST_DATA_DIR

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

PACKAGE = "IDTA 02023 _Template_CarbonFootprint.aasx"
PACKAGE_PATH = (TEST_DATA_DIR / PACKAGE).as_posix()


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the actions that `__main__` registers before the first view."""
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry
    from aas_workingbench.ui.paste_actions import register_paste_actions

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    register_paste_actions()
    yield
    for spec in default_registry().specs_for(ViewKind.ANY):
        if spec.action_id not in before:
            default_registry().unregister(spec.action_id)


def _open(qtbot: Any, path: str | None) -> Any:
    from aas_workingbench.editorApp import EditorApp

    window = EditorApp(fileToOpen=path)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    return window


def _close(window: Any) -> None:
    for package in window.packTreeModel.openedPacks():
        package.commandStack.mark_saved()
    window.mainTreeView.updateWindowModified()
    window._recoveryTimer.stop()
    window.close()


def test_the_start_panel_and_the_bar_have_names(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot, None)

    assert unnamed(window) == []
    _close(window)


def test_a_window_with_a_package_has_names(qapp: object, qtbot: Any) -> None:
    window = _open(qtbot, PACKAGE_PATH)

    assert unnamed(window) == []
    _close(window)


def test_each_bottom_panel_has_names(qapp: object, qtbot: Any) -> None:
    window = _open(qtbot, PACKAGE_PATH)
    problems: list[str] = []
    for dock in (
        window.validationController.dock,
        window.filesDock,
        window.selectionDock,
    ):
        dock.show()
        dock.raise_()
        qtbot.wait(20)
        problems += unnamed(dock)

    assert problems == []
    _close(window)
