"""The steps of building a package in the running editor, as a person does.

Each function drives the dialogs and actions of the main window through an
`Author`, and returns the object that the editor made, found again in the
package. The tests assert on what the editor made, not on these steps.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QPushButton
from tests.authoring import Author
from tests.medium.forms import Form

SUBMODEL = ("submodels", "Everything")
CONCEPT_ID = "urn:example:cd:speed"
SHELL_ID = "urn:example:aas:pump"


def add_item(group: Any) -> Any:
    """Presses the Add button of a list group of a form, and returns the entry."""
    group.findChild(QPushButton).click()
    return group.inputWidgets[-1]


def make_concept(author: Author) -> model.ConceptDescription:
    """Makes an IEC 61360 concept description with a value list."""
    from aas_workingbench.dialogs import EditObjDialog
    from aas_workingbench.ui.iec61360_dialog import Iec61360Dialog
    from aas_workingbench.ui.value_list_dialog import ValueListImportDialog

    author.select_path("concept_descriptions")

    def fill(dialog: Any) -> None:
        form = Form(dialog)
        form.type_text("id_", CONCEPT_ID)
        form.type_text("id_short", "Speed")

    with author.answering(EditObjDialog, fill) as answer:
        assert author.view.addAct.isEnabled()
        author.view.addAct.trigger()
    author.assert_accepted(answer)

    def record(dialog: Any) -> None:
        dialog.preferred_name.set_rows(
            [("en", "Speed"), ("de", "Geschwindigkeit")]
        )
        dialog.definition.add_row("en", "How fast the pump turns")
        dialog.set_data_type(model.DataTypeIEC61360.STRING)

    author.select_path("concept_descriptions", "Speed")
    with author.answering(Iec61360Dialog, record) as answer:
        assert author.act("concepts.add_record")
    author.assert_accepted(answer)

    QApplication.clipboard().setText(  # pyright: ignore[reportOptionalMemberAccess]
        "slow, urn:value:slow\nfast\turn:value:fast"
    )
    author.select_path("concept_descriptions", "Speed")
    with author.answering(ValueListImportDialog, lambda dialog: None) as answer:
        assert author.act("concepts.import_value_list")
    author.assert_accepted(answer)
    concept = author.package.objStore.get_item(CONCEPT_ID)
    assert isinstance(concept, model.ConceptDescription)
    return concept


def make_shell(author: Author) -> model.AssetAdministrationShell:
    """Makes an AAS with asset information and two specific asset ids."""
    from aas_workingbench.ui.create_dialogs import CreateShellDialog
    from aas_workingbench.ui.create_dialogs import SpecificAssetIdDialog

    def fill(dialog: Any) -> None:
        dialog.id_edit.setText(SHELL_ID)
        dialog.id_short_edit.setText("Pump")
        dialog.kind_box.setCurrentIndex(
            dialog.kind_box.findData(model.AssetKind.INSTANCE)
        )
        dialog.global_id_edit.setText("urn:example:asset:pump-1")
        dialog.asset_type_edit.setText("urn:example:type:pump")
        dialog.add_specific_row("serialNumber", "SN-100")

    author.select_path("shells")
    with author.answering(CreateShellDialog, fill) as answer:
        assert author.act("create.shell")
    author.assert_accepted(answer)

    def fill_specific(dialog: Any) -> None:
        dialog.name_edit.setText("batch")
        dialog.value_edit.setText("B7")

    author.select_path("shells", "Pump")
    with author.answering(SpecificAssetIdDialog, fill_specific) as answer:
        assert author.act("asset.add_specific_id")
    author.assert_accepted(answer)
    shell = author.package.objStore.get_item(SHELL_ID)
    assert isinstance(shell, model.AssetAdministrationShell)
    return shell


def make_submodel(
    author: Author, id_short: str, id_: str, kind: model.ModellingKind
) -> model.Submodel:
    """Makes a submodel that the shell Pump refers to."""
    from aas_workingbench.ui.create_dialogs import CreateSubmodelDialog

    def fill(dialog: Any) -> None:
        dialog.kind_box.setCurrentIndex(dialog.kind_box.findData(kind))
        dialog.id_edit.setText(id_)
        dialog.id_short_edit.setText(id_short)

    author.select_path("shells", "Pump")
    with author.answering(CreateSubmodelDialog, fill) as answer:
        assert author.act("create.submodel")
    author.assert_accepted(answer)
    submodel = author.package.objStore.get_item(id_)
    assert isinstance(submodel, model.Submodel)
    return submodel


def make_submodels(author: Author) -> None:
    """Makes an Instance, a Template, and the submodel that holds everything."""
    make_submodel(
        author,
        "Nameplate",
        "urn:example:sm:nameplate",
        model.ModellingKind.INSTANCE,
    )
    make_submodel(
        author,
        "NameplateTemplate",
        "urn:example:sm:nameplate-template",
        model.ModellingKind.TEMPLATE,
    )
    make_submodel(
        author,
        "Everything",
        "urn:example:sm:everything",
        model.ModellingKind.INSTANCE,
    )


def int_property(value: str) -> Any:
    """Fills a Property of value type Int."""

    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("value", value)

    return fill


def build_everything(author: Author, folder: Path) -> model.ConceptDescription:
    """Makes a package with a shell, three submodels, a concept, all elements."""
    from tests.authoring_elements import add_blob
    from tests.authoring_elements import add_capability
    from tests.authoring_elements import add_collections_and_lists
    from tests.authoring_elements import add_entity
    from tests.authoring_elements import add_event
    from tests.authoring_elements import add_file
    from tests.authoring_elements import add_language_property
    from tests.authoring_elements import add_operation
    from tests.authoring_elements import add_range
    from tests.authoring_elements import add_reference_element
    from tests.authoring_elements import add_relationships
    from tests.authoring_elements import add_voltage

    author.start_new_package(folder / "pump.aasx")
    concept = make_concept(author)
    make_shell(author)
    make_submodels(author)
    add_voltage(author, concept)
    add_language_property(author)
    add_range(author)
    add_blob(author, SUBMODEL, "Certificate")
    add_file(author, SUBMODEL, "Datasheet")
    add_reference_element(author, "urn:example:target")
    add_relationships(author)
    add_entity(author)
    add_operation(author)
    add_capability(author)
    add_event(author)
    add_collections_and_lists(author)
    return concept


EVERYTHING = "urn:example:sm:everything"


def everything(author: Author) -> model.Submodel:
    """Returns the submodel that holds an element of every type."""
    submodel = author.package.objStore.get_item(EVERYTHING)
    assert isinstance(submodel, model.Submodel)
    return submodel


def findings(author: Author) -> list[tuple[str, str, str]]:
    """Runs the validation of the dock, and lists the errors and warnings."""
    dock = author.window.validationController.dock
    dock.show()
    dock.refresh()
    return [
        (f.severity.value, f.rule_id, f.message)
        for f in dock.report.findings
        if f.severity.value != "info"
    ]


def reopened(author: Author, folder: Path) -> str:
    """Writes the package, reads the file anew, and snapshots what it holds."""
    from tests.serialization import snapshot

    from aas_workingbench.package import Package

    path = folder / "reopened.aasx"
    author.package.write(path)
    return snapshot(Package(path).objStore)
