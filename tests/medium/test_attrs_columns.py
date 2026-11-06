"""The columns of the attributes of an object give room to what users edit."""

from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
from tests.factories import make_property
from tests.factories import make_submodel

# A value such as a generated id, or a short sentence.
ENOUGH_FOR_A_VALUE = 300
# What a tab has beside the tree of packages in a window of a usual size.
USUAL_TAB_WIDTH = 700

_tabs: list[QWidget] = []


def _shown_attrs(views, qtbot, width: int = USUAL_TAB_WIDTH):
    """Shows the attributes in a tab of a width, which lays them out."""
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("Speed")]))
    attrs = shown.attrs_view("submodels", "Submodel", "Speed")
    tab = QWidget()
    _tabs.append(tab)  # qtbot keeps no reference, and the view needs the tab
    qtbot.addWidget(tab)
    QVBoxLayout(tab).addWidget(attrs)
    tab.resize(width, 400)
    tab.show()
    qtbot.waitExposed(tab)
    return attrs


def test_the_value_column_is_wider_than_the_type_column(views, qtbot) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_COLUMN
    from aas_editor.settings.app_settings import VALUE_COLUMN

    attrs = _shown_attrs(views, qtbot)

    assert attrs.columnWidth(VALUE_COLUMN) >= ENOUGH_FOR_A_VALUE
    assert attrs.columnWidth(VALUE_COLUMN) > attrs.columnWidth(TYPE_COLUMN)
    assert attrs.columnWidth(VALUE_COLUMN) > attrs.columnWidth(ATTRIBUTE_COLUMN)


def test_the_columns_fit_the_tab_so_that_the_type_is_not_hidden(
    views, qtbot
) -> None:
    attrs = _shown_attrs(views, qtbot)

    assert not attrs.horizontalScrollBar().isVisible()


def test_the_type_hint_of_python_is_hidden_until_a_user_asks_for_it(
    views, qtbot
) -> None:
    from aas_editor.settings.app_settings import TYPE_HINT_COLUMN

    attrs = _shown_attrs(views, qtbot)

    assert attrs.header().isSectionHidden(TYPE_HINT_COLUMN)


def test_the_value_takes_the_room_that_the_window_gives(views, qtbot) -> None:
    from aas_editor.settings.app_settings import VALUE_COLUMN

    narrow = _shown_attrs(views, qtbot, 600)
    wide = _shown_attrs(views, qtbot, 900)

    assert wide.columnWidth(VALUE_COLUMN) > narrow.columnWidth(VALUE_COLUMN)
    assert (
        wide.header().sectionResizeMode(VALUE_COLUMN)
        == QHeaderView.ResizeMode.Stretch
    )
