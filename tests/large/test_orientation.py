"""The orientation of the two zones that a session saved comes back.

The settings of these tests are real `QSettings` in a file of the session, as
the program writes them, so what the store gives back is what a user gets.
"""

from collections.abc import Iterator
from typing import Any

from PyQt6.QtCore import Qt
import pytest

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


@pytest.fixture(scope="module", autouse=True)
def registered_actions(qapp: object) -> Iterator[None]:
    """Registers the paste actions, as `__main__` does before the first view."""
    from aas_editor.ui.actions import ViewKind
    from aas_editor.ui.actions import default_registry
    from aas_editor.ui.paste_actions import register_paste_actions

    before = {s.action_id for s in default_registry().specs_for(ViewKind.ANY)}
    register_paste_actions()
    yield
    for spec in default_registry().specs_for(ViewKind.ANY):
        if spec.action_id not in before:
            default_registry().unregister(spec.action_id)


def _open(qtbot: Any) -> Any:
    from aas_editor.editorApp import EditorApp

    window = EditorApp()
    qtbot.addWidget(window)
    return window


def _close(window: Any) -> None:
    window._recoveryTimer.stop()
    window.close()


def test_a_first_run_puts_the_zones_side_by_side(
    qapp: object, qtbot: Any
) -> None:
    window = _open(qtbot)

    assert window.splitter.orientation() == Qt.Orientation.Horizontal
    _close(window)


def test_a_saved_vertical_orientation_is_restored(
    qapp: object, qtbot: Any
) -> None:
    from aas_editor.settings.app_settings import AppSettings

    AppSettings.ORIENTATION.setValue(Qt.Orientation.Vertical)

    window = _open(qtbot)

    assert window.splitter.orientation() == Qt.Orientation.Vertical
    _close(window)


def test_choosing_the_orientation_in_one_window_is_kept_for_the_next(
    qapp: object, qtbot: Any
) -> None:
    first = _open(qtbot)
    first.setOrientation(Qt.Orientation.Vertical)
    _close(first)

    second = _open(qtbot)

    assert second.splitter.orientation() == Qt.Orientation.Vertical
    _close(second)


def test_a_saved_horizontal_orientation_is_restored(
    qapp: object, qtbot: Any
) -> None:
    from aas_editor.settings.app_settings import AppSettings

    AppSettings.ORIENTATION.setValue(Qt.Orientation.Horizontal)

    window = _open(qtbot)

    assert window.splitter.orientation() == Qt.Orientation.Horizontal
    _close(window)


@pytest.mark.parametrize(
    "old", ["", "something else", 7, "Orientation.Diagonal"]
)
def test_a_value_of_an_old_release_keeps_the_default_layout(
    qapp: object, qtbot: Any, old: object
) -> None:
    from aas_editor.settings.app_settings import AppSettings

    AppSettings.ORIENTATION.setValue(old)

    window = _open(qtbot)

    assert window.splitter.orientation() == Qt.Orientation.Horizontal
    _close(window)


def test_zones_one_above_the_other_come_back_with_their_heights(
    qapp: object, qtbot: Any
) -> None:
    first = _open(qtbot)
    first.show()
    first.setOrientation(Qt.Orientation.Vertical)
    first.splitter.setSizes([200, 400])
    qtbot.wait(50)
    saved_heights = (
        first.mainLayoutWidget.height(),
        first.subLayoutWidget.height(),
    )
    _close(first)

    second = _open(qtbot)
    second.show()
    qtbot.wait(50)

    heights = (
        second.mainLayoutWidget.height(),
        second.subLayoutWidget.height(),
    )
    assert second.splitter.orientation() == Qt.Orientation.Vertical
    assert heights[0] < heights[1]
    assert (
        abs(heights[0] / heights[1] - saved_heights[0] / saved_heights[1]) < 0.1
    )
    _close(second)
