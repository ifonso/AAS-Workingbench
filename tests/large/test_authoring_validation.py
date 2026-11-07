"""Validation must catch the mistakes that the editor lets a person make.

A new package gets four mistakes that the dialogs accept: an idShort of one
letter, a template qualifier in an Instance submodel, a File that names a file
the package does not hold, and an event that observes a property of a submodel
that is not there. The Validation panel must list each of them, the save must refuse the
missing file and write nothing, and the findings must go when the person fixes
the mistakes.
"""

from pathlib import Path
from typing import Any

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.authoring import Author
from tests.authoring_builders import add_item
from tests.authoring_builders import findings
from tests.authoring_builders import make_shell
from tests.authoring_builders import make_submodel
from tests.medium.forms import Form
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

BOX = ("submodels", "Box")
BOX_ID = "urn:example:sm:box"


def _template_qualifier(form: Form) -> None:
    form.type_text("value", "x")
    entry = add_item(form.widget("qualifier"))
    entry.paramWidgets["type_"].widget.setText("Cardinality")
    kind = entry.paramWidgets["kind"].widget
    kind.setCurrentIndex(kind.findData(model.QualifierKind.TEMPLATE_QUALIFIER))


def _file_that_is_missing(form: Form) -> None:
    form.type_text("content_type", "application/pdf")
    form.type_text("value", "/aasx/files/missing.pdf")


def _event_that_observes_nothing(form: Form) -> None:
    form.fill_model_reference(
        "observed",
        [
            (model.KeyTypes.SUBMODEL, "urn:example:sm:missing"),
            (model.KeyTypes.PROPERTY, "Temperature"),
        ],
        model.Property,
    )
    form.choose("direction", model.Direction.OUTPUT)
    form.choose("state", model.StateOfEvent.ON)


def _make_mistakes(author: Author) -> None:
    mistakes: list[tuple[type, str, Any]] = [
        (
            model.Property,
            "Q",
            lambda form: (
                form.choose("value_type", datatypes.Int),
                form.type_text("value", "1"),
            ),
        ),
        (model.Property, "Qualified", _template_qualifier),
        (model.File, "Missing", _file_that_is_missing),
        (model.BasicEventElement, "Dangling", _event_that_observes_nothing),
    ]
    for element_type, name, fill in mistakes:
        answer = author.add_element(BOX, element_type, name, fill)
        author.assert_accepted(answer)


@pytest.fixture
def mistaken(author: Author, tmp_path: Path) -> Author:
    """A saved package with a shell and a submodel, and four mistakes in it."""
    author.start_new_package(tmp_path / "box.aasx")
    make_shell(author)
    make_submodel(author, "Box", BOX_ID, model.ModellingKind.INSTANCE)
    author.select_path()
    author.view.saveAct.trigger()
    assert not author.window.isWindowModified(), author.errors
    _make_mistakes(author)
    return author


def test_validation_lists_each_mistake_with_its_rule_and_the_place(
    mistaken: Author,
) -> None:
    found = findings(mistaken)

    by_rule = {rule: (severity, message) for severity, rule, message in found}
    assert by_rule["AASd-002"][0] == "error"
    assert by_rule["AASd-129"][0] == "error"
    assert by_rule["EDT-MISSING-FILE"][0] == "error"
    assert by_rule["EDT-DANGLING-REFERENCE"][0] == "warning"
    dock = mistaken.window.validationController.dock
    where = {f.rule_id: f.location for f in dock.report.findings}
    assert "Q" in where["AASd-002"]
    assert "Qualified" in where["AASd-129"]
    assert "Missing" in where["EDT-MISSING-FILE"]
    assert "Dangling" in where["EDT-DANGLING-REFERENCE"]
    counts = mistaken.window.validationController.status.counts
    assert (counts.errors, counts.warnings) == (3, 1)


def test_the_save_refuses_the_missing_file_and_writes_nothing(
    mistaken: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.save_warnings import IssuesDialog

    path = tmp_path / "box.aasx"
    on_disk = path.read_bytes()
    shown: list[tuple[str, list[str]]] = []

    def look(dialog: IssuesDialog) -> None:
        shown.append(
            (
                dialog.windowTitle(),
                [
                    dialog.issues_list.item(row).text()
                    for row in range(dialog.issues_list.count())
                ],
            )
        )

    mistaken.select_path()
    with mistaken.answering(IssuesDialog, look):
        mistaken.view.saveAct.trigger()

    assert shown, "The save said nothing"
    title, lines = shown[0]
    assert title == "Package cannot be saved"
    assert any("missing.pdf" in line for line in lines), lines
    assert path.read_bytes() == on_disk
    assert mistaken.window.isWindowModified()


def test_the_findings_go_when_the_mistakes_are_fixed_and_the_package_saves(
    mistaken: Author, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package
    from aas_workingbench.ui.reference_dialogs import RenameDialog

    mistaken.select_path(*BOX, "Q")
    with mistaken.answering(
        RenameDialog, lambda dialog: dialog.edit.setText("Quantity")
    ) as answer:
        assert mistaken.act("references.rename_id_short")
    mistaken.assert_accepted(answer)
    for name in ("Qualified", "Missing", "Dangling"):
        mistaken.select_path(*BOX, name)
        mistaken.replies.append(("Delete", "Delete"))
        assert mistaken.edit_menu("delete")

    assert findings(mistaken) == []
    mistaken.select_path()
    mistaken.view.saveAct.trigger()
    assert not mistaken.window.isWindowModified(), mistaken.errors
    saved = Package(tmp_path / "box.aasx")
    box = saved.objStore.get_item(BOX_ID)
    assert [e.id_short for e in box.submodel_element] == ["Quantity"]
    assert snapshot(saved.objStore) == snapshot(mistaken.package.objStore)
