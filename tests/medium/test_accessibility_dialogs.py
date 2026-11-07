"""Every field of a form has a name, and every icon-only button has a tooltip.

The forms are built by many dialogs, so a field that nothing labels is easy to
add. A screen reader reads such a field as only "edit". Each case builds a
dialog and walks it as `tests.accessibility` describes. Screen readers
themselves were not run.
"""

from collections.abc import Callable
from typing import Any

import pytest
from pytestqt.qtbot import QtBot
from tests.accessibility import unnamed
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel


def _create_shell() -> Any:
    from aas_workingbench.ui.create_dialogs import CreateShellDialog

    return CreateShellDialog([])


def _create_submodel() -> Any:
    from aas_workingbench.ui.create_dialogs import CreateSubmodelDialog

    return CreateSubmodelDialog([], [make_shell()])


def _link_submodels() -> Any:
    from aas_workingbench.ui.create_dialogs import LinkSubmodelsDialog

    return LinkSubmodelsDialog(make_shell(), [make_submodel()])


def _specific_asset_id() -> Any:
    from aas_workingbench.ui.create_dialogs import SpecificAssetIdDialog

    return SpecificAssetIdDialog()


def _change_attribute() -> Any:
    from aas_workingbench.ui.bulk_dialogs import ChangeAttributeDialog

    props = [make_property("RatedPower"), make_property("Speed")]
    return ChangeAttributeDialog([make_submodel(elements=props)], props)


def _list_settings() -> Any:
    from basyx.aas import model

    from aas_workingbench.ui.replacement_dialogs import ListSettingsDialog

    return ListSettingsDialog(
        model.SubmodelElementList(
            "Items",
            type_value_list_element=model.Property,
            value_type_list_element=model.datatypes.String,
        )
    )


DIALOGS: list[Callable[[], Any]] = [
    _create_shell,
    _create_submodel,
    _link_submodels,
    _specific_asset_id,
    _change_attribute,
    _list_settings,
]


@pytest.mark.parametrize("build", DIALOGS, ids=lambda build: build.__name__)
def test_a_dialog_has_a_name_for_each_control(
    qapp: object, qtbot: QtBot, build: Callable[[], Any]
) -> None:
    dialog = build()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert unnamed(dialog) == []


def _iec61360() -> Any:
    from aas_workingbench.domain.data_specifications import Iec61360Draft
    from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog

    return Iec61360Dialog(Iec61360Draft())


def _settings() -> Any:
    from aas_workingbench.widgets.settingWidgets import SettingsDialog

    return SettingsDialog()


@pytest.mark.parametrize(
    "build", [_iec61360, _settings], ids=lambda build: build.__name__
)
def test_the_larger_dialogs_have_a_name_for_each_control(
    qapp: object, qtbot: QtBot, build: Callable[[], Any]
) -> None:
    dialog = build()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert unnamed(dialog) == []
