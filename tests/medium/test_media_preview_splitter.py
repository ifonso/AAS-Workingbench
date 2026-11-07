"""The preview of a stored file does not squeeze the attributes of the tab."""

from typing import Any

import pytest
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_submodel

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

# One pixel of a PNG: the preview needs bytes, not a picture to look at.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfe\xa7\x9a\x0b\xd9\x00\x00\x00\x00IEND\xaeB`\x82"
)
PATH = "/aasx/files/picture.png"
WIDE_TAB = 1100
NARROW_TAB = 600
# What the attributes need to be read.
READABLE_ATTRIBUTES = 360


@pytest.fixture
def tabs(views: Any, qtbot: Any, monkeypatch: pytest.MonkeyPatch):
    """A tab widget over a package with a File element and a Property."""
    from PyQt6.QtWidgets import QWidget

    import aas_workingbench.widgets.tab as tab_module
    from aas_workingbench.widgets.tab import TabWidget

    class PreviewStandIn(QWidget):
        """Takes the place of the web view, whose renderer does not stop
        cleanly when a shown widget is deleted on a platform without a screen.
        The layout is what is tested here, not the page.
        """

        def setContent(self, *_args: Any) -> None:  # noqa: N802
            pass

        def load(self, *_args: Any) -> None:
            pass

        def setZoomFactor(self, *_args: Any) -> None:  # noqa: N802
            pass

    monkeypatch.setattr(tab_module, "QWebEngineView", PreviewStandIn)
    shown = views()
    shown.open_package(
        make_submodel(
            elements=[
                make_file_element("Picture", PATH, "image/png"),
                make_property("Speed"),
            ]
        ),
        files={PATH: (PNG, "image/png")},
    )
    widget = TabWidget(unclosable=True)
    qtbot.addWidget(widget)

    class Tabs:
        views = shown

        @staticmethod
        def show(width: int) -> None:
            widget.resize(width, 500)
            widget.show()
            qtbot.waitExposed(widget)

        @staticmethod
        def open(*names: str) -> Any:
            widget.openItemInNewTab(shown.index(*names))
            tab = widget.currentWidget()
            # The preview is placed once the tab has its width.
            qtbot.wait(50)
            return tab

    return Tabs


def test_a_wide_tab_gives_the_preview_a_third(tabs: Any) -> None:
    tabs.show(WIDE_TAB)

    tab = tabs.open("submodels", "Submodel", "Picture")
    attributes, preview = tab.splitter.sizes()

    assert tab.mediaViewWidget.isVisible()
    assert 0.25 < preview / (attributes + preview) < 0.4
    assert attributes >= READABLE_ATTRIBUTES


def test_a_narrow_tab_opens_with_the_preview_dragged_shut(tabs: Any) -> None:
    tabs.show(NARROW_TAB)

    tab = tabs.open("submodels", "Submodel", "Picture")
    attributes, preview = tab.splitter.sizes()

    assert preview == 0
    assert attributes >= NARROW_TAB - 20


def test_the_preview_can_be_opened_by_dragging_the_handle(tabs: Any) -> None:
    tabs.show(NARROW_TAB)
    tab = tabs.open("submodels", "Submodel", "Picture")

    tab.splitter.setSizes([400, 200])

    assert tab.splitter.sizes()[1] > 0
    assert tab.splitter.isCollapsible(1)
    assert not tab.splitter.isCollapsible(0)


def test_the_share_that_a_user_dragged_is_kept_for_the_next_file(
    tabs: Any,
) -> None:
    tabs.show(WIDE_TAB)
    tab = tabs.open("submodels", "Submodel", "Picture")
    tab.splitter.setSizes([600, 400])
    tab.splitter.splitterMoved.emit(600, 1)

    tab.openItem(tabs.views.index("submodels", "Submodel", "Speed"))
    assert tab.mediaViewWidget.isHidden()
    tab.openItem(tabs.views.index("submodels", "Submodel", "Picture"))
    tab.splitter.refresh()
    attributes, preview = tab.splitter.sizes()

    assert 0.3 < preview / (attributes + preview) < 0.5


def test_an_element_without_a_file_has_no_preview(tabs: Any) -> None:
    tabs.show(WIDE_TAB)

    tab = tabs.open("submodels", "Submodel", "Speed")

    assert tab.mediaViewWidget.isHidden()


def test_a_file_can_be_opened_in_a_new_tab_at_once(tabs: Any) -> None:
    # The splitter must exist before the first item is opened.
    tabs.show(WIDE_TAB)

    tab = tabs.open("submodels", "Submodel", "Picture")

    assert tab.splitter.widget(1) is tab.mediaViewWidget


def test_a_preview_that_is_shut_has_a_button_that_opens_it(tabs: Any) -> None:
    tabs.show(NARROW_TAB)
    tab = tabs.open("submodels", "Submodel", "Picture")
    assert tab.splitter.sizes()[1] == 0
    assert tab.showPreviewBtn.isVisible()

    tab.showPreviewBtn.click()

    assert tab.splitter.sizes()[1] > 0
    assert not tab.showPreviewBtn.isVisible()


def test_a_tab_with_an_open_preview_has_no_button(tabs: Any) -> None:
    tabs.show(WIDE_TAB)

    tab = tabs.open("submodels", "Submodel", "Picture")

    assert not tab.showPreviewBtn.isVisible()


def test_an_element_without_a_file_has_no_button(tabs: Any) -> None:
    tabs.show(NARROW_TAB)

    tab = tabs.open("submodels", "Submodel", "Speed")

    assert not tab.showPreviewBtn.isVisible()


def test_the_button_comes_back_when_the_handle_is_dragged_shut(
    tabs: Any,
) -> None:
    tabs.show(WIDE_TAB)
    tab = tabs.open("submodels", "Submodel", "Picture")

    tab.splitter.setSizes([WIDE_TAB, 0])
    tab.splitter.splitterMoved.emit(WIDE_TAB, 1)

    assert tab.showPreviewBtn.isVisible()
