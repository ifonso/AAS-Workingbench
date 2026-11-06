"""Dialogs give their content room, so that text is not cut off.

Each case renders the dialog on screen and measures what the user sees. The
sizes are those of a laptop, not of the largest screen.
"""

from tests.factories import make_annotated_relationship
from tests.factories import make_property
from tests.factories import make_submodel


def test_the_save_warning_is_wide_enough_for_a_validation_message(
    qapp, qtbot
) -> None:
    from aas_editor.application.save import SaveIssue
    from aas_editor.ui.save_warnings import IssuesDialog

    message = (
        "RelationshipElement 'Q' of Submodel 'MotorData': The idShort 'Q' "
        "must have at least two characters"
    )
    dialog = IssuesDialog(
        "Save",
        "Saving this package breaks rules of the metamodel.",
        [SaveIssue(message, (), "VALIDATION")],
        accept_text="Save anyway",
    )
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    # A message that is wider than the list needs a bar to scroll to its end.
    assert dialog.issues_list.horizontalScrollBar().maximum() == 0


def test_the_element_column_of_the_pattern_dialog_shows_a_name(
    qapp, qtbot
) -> None:
    from aas_editor.ui.bulk_dialogs import ChangeAttributeDialog

    props = [make_property("RatedPower"), make_property("Speed")]
    dialog = ChangeAttributeDialog([make_submodel(elements=props)], props)
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    # "Property 'RatedPower'" needs about this much, and the column was 100.
    assert dialog.table.columnWidth(0) >= 200


def test_a_long_reference_in_a_table_wraps_instead_of_ending_in_dots(
    qapp, qtbot
) -> None:
    from aas_editor.ui.reference_dialogs import ReferenceTable

    table = ReferenceTable(["Where", "Reference"])
    qtbot.addWidget(table)
    table.resize(400, 300)
    long_text = (
        "Submodel 'urn:uuid:5a1f1e0e-0000-4000-8000-000000000001' / " * 2
    )

    table.set_rows([["Property 'RatedPower'", long_text]])
    table.show()
    qtbot.waitExposed(table)

    assert table.rowHeight(0) >= 3 * table.fontMetrics().height()


def test_a_tall_form_gets_the_width_of_its_scroll_bar(
    qapp, qtbot, monkeypatch
) -> None:
    from PyQt6.QtWidgets import QWidget

    from aas_editor.dialogs import EditDialog

    # A screen that is not tall enough for the form, as a laptop is not.
    monkeypatch.setattr(EditDialog, "MAX_HEIGHT", 400)
    dialog = EditDialog(None, "Edit")
    qtbot.addWidget(dialog)
    form = QWidget()
    form.setMinimumSize(700, 900)
    dialog.layout().addWidget(form)

    dialog.adjustSize()

    # The bar of a tall form takes room from the form, which has no bar of its
    # own for the width, so the Clear button of a Blob was cut at the edge.
    bar = dialog.scrollArea.verticalScrollBar().sizeHint().width()
    assert dialog.width() >= 700 + bar


def test_the_reference_picker_shows_its_kind_and_the_types_in_full(
    qapp, qtbot
) -> None:
    from basyx.aas import model

    from aas_editor.domain.reference_picker import rule_for_hint
    from aas_editor.ui.reference_picker import ReferencePickerDialog

    submodel = make_submodel(
        elements=[make_annotated_relationship("AnnotatedRelationshipElement")]
    )
    dialog = ReferencePickerDialog(
        [submodel], rule_for_hint(model.Reference), parent=None
    )
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    kind = dialog.kind_box
    text_width = kind.fontMetrics().horizontalAdvance(kind.currentText())
    longest_type = dialog.tree.fontMetrics().horizontalAdvance(
        "AnnotatedRelationshipElement"
    )
    assert text_width <= kind.width() - 40
    assert dialog.tree.columnWidth(1) >= longest_type
