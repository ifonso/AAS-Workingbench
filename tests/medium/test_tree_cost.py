"""What keeps opening a package and selecting a row fast.

A row of a list or of a mapping is named by its position or its idShort, which
the type of its container does not have. Each such row logged two tracebacks,
and writing them took most of the time of opening a package. The rows below an
item are kept by the item, and the actions read the selection once.
"""

import logging
from typing import Any

from basyx.aas import model
from PyQt6.QtCore import QModelIndex
import pytest
from tests.factories import make_collection
from tests.factories import make_list
from tests.factories import make_multi_language_property
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.conftest import SUBMODEL_PATH


def _submodel_with_every_kind_of_row() -> model.Submodel:
    return make_submodel(
        elements=[
            make_property("First"),
            make_multi_language_property("Named", {"en": "one", "de": "eins"}),
            make_collection("Group", [make_property("Inside")]),
            make_list("Items", [model.Property(None, model.datatypes.String)]),
        ]
    )


def test_showing_a_package_logs_no_error(
    model_support: Any, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)

    table = model_support.pack_table(_submodel_with_every_kind_of_row())
    model_support.detail_table(table, *SUBMODEL_PATH, "Named")

    assert caplog.records == []


def test_drawing_the_rows_of_a_package_logs_no_error(
    views: Any, caplog: pytest.LogCaptureFixture
) -> None:
    shown = views()
    shown.open_package(_submodel_with_every_kind_of_row())
    caplog.set_level(logging.ERROR)

    shown.view.grab()

    assert caplog.records == []


def test_a_name_that_a_type_does_not_have_is_a_key_error_and_is_not_logged(
    qapp: object, caplog: pytest.LogCaptureFixture
) -> None:
    from aas_workingbench.utils.util import getAttrTypeHint

    caplog.set_level(logging.ERROR)

    with pytest.raises(KeyError):
        getAttrTypeHint(model.Submodel, "NoSuchAttribute")

    assert caplog.records == []


def test_the_params_of_a_type_can_be_changed_by_the_one_who_asked(
    qapp: object,
) -> None:
    from aas_workingbench.utils.util import getReqParams4init

    first = getReqParams4init(model.Property, rmDefParams=False)
    first.clear()

    again = getReqParams4init(model.Property, rmDefParams=False)

    assert "value_type" in again


def test_the_item_of_a_mapping_has_the_types_of_the_mapping_asked_last(
    qapp: object,
) -> None:
    from aas_workingbench.additional.classes import DictItem
    from aas_workingbench.utils.util import getIterItemTypeHint
    from aas_workingbench.utils.util import getParamsAndTypehints4init

    getIterItemTypeHint(dict[str, int])
    first = getParamsAndTypehints4init(DictItem, withDefaults=False)
    getIterItemTypeHint(dict[int, bytes])
    second = getParamsAndTypehints4init(DictItem, withDefaults=False)

    assert first == {"key": str, "value": int}
    assert second == {"key": int, "value": bytes}


def test_the_rows_are_right_after_rows_left_and_came(
    model_support: Any,
) -> None:
    table = model_support.pack_table(
        make_submodel(
            elements=[make_property(name) for name in ("A", "B", "C", "D")]
        )
    )
    parent = model_support.find_path(table, "", *SUBMODEL_PATH)
    model_support.watch(table)

    table.removeRows(1, 2, parent)
    after_removal = model_support.names(table, parent)
    table.update(parent)

    assert after_removal == ["A", "D"]
    assert model_support.names(table, parent) == ["A", "B", "C", "D"]
    last = table.index(3, 0, parent)
    assert table.parent(last) == parent
    assert model_support.violations() == []


def test_a_row_knows_its_place_after_a_row_before_it_left(
    model_support: Any,
) -> None:
    table = model_support.pack_table(
        make_submodel(
            elements=[make_property(name) for name in ("A", "B", "C")]
        )
    )
    parent = model_support.find_path(table, "", *SUBMODEL_PATH)
    last = table.objByIndex(table.index(2, 0, parent))
    place_before = last.row()

    table.removeRows(0, 1, parent)

    assert place_before == 2
    assert last.row() == 1
    assert table.objByIndex(parent).rows()[1] is last


def test_an_item_that_is_no_row_of_another_has_no_row_there(
    model_support: Any,
) -> None:
    table = model_support.pack_table(make_submodel())
    root = table.objByIndex(QModelIndex())
    package_item = table.objByIndex(table.index(0, 0))

    with pytest.raises(ValueError):
        package_item.rowOf(root)


def test_the_actions_read_the_selection_once_for_a_row(
    views: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.treeviews.treeview_pack import PackTreeView

    shown = views()
    shown.open_package(make_submodel(elements=[make_property("A")]))
    index = shown.index(*SUBMODEL_PATH, "A")
    shown.select(index)
    reads: list[int] = []
    read = PackTreeView.selectedIndexes

    def counted(view: Any) -> list[QModelIndex]:
        reads.append(1)
        return read(view)

    monkeypatch.setattr(PackTreeView, "selectedIndexes", counted)

    shown.view.updateActions(index)

    assert len(reads) == 1


def test_an_action_gets_the_rows_that_are_selected_when_it_is_asked(
    views: Any,
) -> None:
    shown = views()
    shown.open_package(
        make_submodel(elements=[make_property("A"), make_property("B")])
    )
    first = shown.index(*SUBMODEL_PATH, "A")
    second = shown.index(*SUBMODEL_PATH, "B")

    shown.select(first)
    selected_first = shown.view.actionContext().selection
    shown.select(second)
    selected_second = shown.view.actionContext().selection

    assert first in selected_first
    assert second not in selected_first
    assert second in selected_second
    assert first not in selected_second
