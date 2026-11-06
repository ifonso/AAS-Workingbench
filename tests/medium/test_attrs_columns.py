"""The columns of the attributes of an object give room to what users edit."""

from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget
from tests.factories import make_property
from tests.factories import make_submodel

# A short value. The names of the attribute and type columns are kept whole
# (`embeddedDataSpecifications`, `MultiLanguageNameType`), so the value gets
# what is left, and no more than the names need is taken from it.
ENOUGH_FOR_A_VALUE = 180
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


def test_the_value_column_keeps_room_for_a_short_value(views, qtbot) -> None:
    from aas_editor.settings.app_settings import VALUE_COLUMN

    attrs = _shown_attrs(views, qtbot)

    assert attrs.columnWidth(VALUE_COLUMN) >= ENOUGH_FOR_A_VALUE


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


def test_the_common_names_are_whole_in_a_tab_of_a_usual_width(
    views, qtbot
) -> None:
    from PyQt6.QtGui import QFont
    from PyQt6.QtGui import QFontMetrics

    from aas_editor.models import DetailedInfoTable
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_COLUMN
    from aas_editor.settings.app_settings import WIDEST_ATTRIBUTE_NAME
    from aas_editor.settings.app_settings import WIDEST_TYPE_NAME

    attrs = _shown_attrs(views, qtbot, 1500)
    bold = QFont(DetailedInfoTable.currFont)
    bold.setBold(True)
    name = QFontMetrics(bold).horizontalAdvance(WIDEST_ATTRIBUTE_NAME)
    kind = QFontMetrics(DetailedInfoTable.currFont).horizontalAdvance(
        WIDEST_TYPE_NAME
    )

    assert attrs.columnWidth(ATTRIBUTE_COLUMN) > name
    assert attrs.columnWidth(TYPE_COLUMN) > kind


def test_a_narrow_tab_leaves_the_value_most_of_its_width(views, qtbot) -> None:
    from aas_editor.settings.app_settings import ATTR_MAX_SHARE
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN
    from aas_editor.settings.app_settings import TYPE_COLUMN
    from aas_editor.settings.app_settings import TYPE_MAX_SHARE

    attrs = _shown_attrs(views, qtbot, 450)
    width = attrs.viewport().width()

    assert attrs.columnWidth(ATTRIBUTE_COLUMN) <= width * ATTR_MAX_SHARE
    assert attrs.columnWidth(TYPE_COLUMN) <= width * TYPE_MAX_SHARE


def test_a_column_that_the_user_sized_is_not_fitted_again(views, qtbot) -> None:
    from aas_editor.settings.app_settings import ATTRIBUTE_COLUMN

    attrs = _shown_attrs(views, qtbot, 900)

    attrs.header().resizeSection(ATTRIBUTE_COLUMN, 123)
    attrs.parentWidget().resize(950, 400)
    qtbot.wait(20)

    assert attrs.columnWidth(ATTRIBUTE_COLUMN) == 123


def test_the_value_takes_the_room_that_the_window_gives(views, qtbot) -> None:
    from aas_editor.settings.app_settings import VALUE_COLUMN

    narrow = _shown_attrs(views, qtbot, 600)
    wide = _shown_attrs(views, qtbot, 900)

    assert wide.columnWidth(VALUE_COLUMN) > narrow.columnWidth(VALUE_COLUMN)
    assert (
        wide.header().sectionResizeMode(VALUE_COLUMN)
        == QHeaderView.ResizeMode.Stretch
    )
