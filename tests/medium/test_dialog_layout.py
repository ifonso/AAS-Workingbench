"""Dialogs give their content room, so that text is not cut off.

Each case renders the dialog on screen and measures what the user sees. The
sizes are those of a laptop, not of the largest screen.
"""

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
