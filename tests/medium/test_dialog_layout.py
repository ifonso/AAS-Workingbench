"""Dialogs give their content room, so that text is not cut off.

Each case renders the dialog on screen and measures what the user sees. The
sizes are those of a laptop, not of the largest screen.
"""

from collections.abc import Iterator

import pytest
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


# The pattern of the dialogs (ui/dialog_layout.py): padding, the button that
# Enter presses, the accent, and the field that has the focus first.


@pytest.fixture
def light_theme(qapp) -> Iterator[None]:
    """Puts the light theme on, and gives the platform look back."""
    from aas_editor.ui.theme import THEME_LIGHT
    from aas_editor.ui.theme import theme_manager

    theme_manager().apply(THEME_LIGHT)
    yield
    theme_manager().reset_to_native()


def _default_buttons(dialog) -> list[str]:
    from PyQt6.QtWidgets import QPushButton

    return [
        button.text()
        for button in dialog.findChildren(QPushButton)
        if button.isDefault()
    ]


def _rename_dialog():
    from aas_editor.application.operations.rename import RenameError
    from aas_editor.ui.reference_dialogs import RenameDialog

    def refuse(text: str):
        raise RenameError("Not now")

    return RenameDialog(
        "Rename", "New id", "urn:old", refuse, generate=lambda: "urn:new"
    )


def test_a_dialog_has_12_pixels_of_padding_and_8_between_its_parts(
    qapp, qtbot
) -> None:
    from aas_editor.ui.paste_dialogs import PasteTextDialog

    dialog = PasteTextDialog([("below", "Below the selected row")])
    qtbot.addWidget(dialog)

    margins = dialog.layout().contentsMargins()

    assert (
        margins.left(),
        margins.top(),
        margins.right(),
        margins.bottom(),
    ) == (12, 12, 12, 12)
    assert dialog.layout().spacing() == 8


def test_enter_presses_cancel_in_a_dialog_with_a_safe_default_even_when_a_helper_button_comes_first(
    qapp, qtbot
) -> None:
    dialog = _rename_dialog()
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    # "Generate" is the first button that could take the default.
    assert _default_buttons(dialog) == ["Cancel"]


def test_enter_presses_ok_in_a_dialog_that_asks_for_input(qapp, qtbot) -> None:
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    dialog = CreateSubmodelDialog([], [])
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    assert _default_buttons(dialog) == ["OK"]


def test_a_dialog_that_asks_for_input_opens_in_its_first_field(
    qapp, qtbot
) -> None:
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    dialog = CreateSubmodelDialog([], [])
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    # The buttons are made before the fields, and held the focus.
    assert dialog.focusWidget() is dialog.id_edit


def test_a_form_opens_in_its_first_field_not_on_ok(qapp, qtbot) -> None:
    from basyx.aas import model

    from aas_editor.dialogs import EditObjDialog

    dialog = EditObjDialog(model.Qualifier, None, rmDefParams=False)
    qtbot.addWidget(dialog)

    dialog.show()
    qtbot.waitExposed(dialog)

    assert (
        dialog.focusWidget() is dialog.inputWidget.paramWidgets["type_"].widget
    )


def _pixel_inside(button, dialog, qtbot):
    """The colour near the left edge of a button, away from its text."""
    image = dialog.grab().toImage()
    corner = button.mapTo(dialog, button.rect().center())
    point = button.mapTo(dialog, button.rect().topLeft())
    return image.pixelColor(point.x() + 6, corner.y()).name()


def test_the_accept_button_is_filled_with_the_accent(
    qapp, qtbot, light_theme
) -> None:
    from aas_editor.domain.design_tokens import LIGHT
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    dialog = CreateSubmodelDialog([], [])
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    dialog.ok_button.setEnabled(True)

    assert _pixel_inside(dialog.ok_button, dialog, qtbot) == LIGHT.accent


def test_a_safe_default_has_an_accent_outline_and_no_fill(
    qapp, qtbot, light_theme
) -> None:
    from aas_editor.domain.design_tokens import LIGHT

    dialog = _rename_dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    (cancel,) = [
        button
        for button in dialog.buttons.buttons()
        if button.text() == "Cancel"
    ]

    inside = _pixel_inside(cancel, dialog, qtbot)

    assert inside == LIGHT.bg_content
    assert (
        dialog.grab()
        .toImage()
        .pixelColor(
            cancel.mapTo(dialog, cancel.rect().topLeft()).x() + 40,
            cancel.mapTo(dialog, cancel.rect().topLeft()).y(),
        )
        .name()
        == LIGHT.accent
    )


def test_a_helper_button_has_no_accent(qapp, qtbot, light_theme) -> None:
    from aas_editor.domain.design_tokens import LIGHT

    dialog = _rename_dialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert dialog.generate_button is not None
    assert (
        _pixel_inside(dialog.generate_button, dialog, qtbot) == LIGHT.bg_content
    )


def test_the_button_of_a_deletion_is_not_filled(
    qapp, qtbot, light_theme
) -> None:
    from aas_editor.application.operations.delete import plan_delete
    from aas_editor.domain.design_tokens import LIGHT
    from aas_editor.ui.reference_dialogs import DeleteDialog

    prop = make_property("Speed")
    submodel = make_submodel(elements=[prop])
    dialog = DeleteDialog(plan_delete([submodel], [prop]))
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    (delete,) = [
        button
        for button in dialog.buttons.buttons()
        if button.text() == "Delete"
    ]

    assert _pixel_inside(delete, dialog, qtbot) == LIGHT.bg_content


def test_a_problem_label_follows_a_switch_of_theme(
    qapp, qtbot, light_theme
) -> None:
    from aas_editor.domain.design_tokens import DARK
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog
    from aas_editor.ui.theme import THEME_DARK
    from aas_editor.ui.theme import theme_manager

    dialog = CreateSubmodelDialog([], [])
    qtbot.addWidget(dialog)

    theme_manager().apply(THEME_DARK)

    assert DARK.status_error in dialog.problem_label.styleSheet()
