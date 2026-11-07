"""New shells, submodels and concept descriptions get generated ids (D14)."""

from basyx.aas import model
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot


def _proposed_id(qtbot: QtBot, cls: type) -> str:
    """The id that the add dialog for a class offers to the user."""
    from aas_workingbench import dialogs

    parent = QWidget()
    qtbot.addWidget(parent)
    dialog = dialogs.EditObjDialog(cls, parent)
    qtbot.addWidget(dialog)
    return str(dialog.inputWidget.paramWidgets["id_"].getObj2add())


@pytest.mark.parametrize(
    "cls",
    [model.AssetAdministrationShell, model.Submodel, model.ConceptDescription],
)
def test_add_dialog_proposes_a_new_urn_uuid_for_each_object(
    qapp: object, qtbot: QtBot, cls: type
) -> None:
    first = _proposed_id(qtbot, cls)
    second = _proposed_id(qtbot, cls)

    assert first.startswith("urn:uuid:")
    assert second.startswith("urn:uuid:")
    assert first != second
