"""Hints mode: advice about an object, and under the fields of the dialogs.

Hints never block. The value stays in the model, the dialog can be accepted, and
the package can be saved. Hints mode switches the advice off (F-EDT-06 AC11).
"""

from basyx.aas import model
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QWidget
import pytest
from pytestqt.qtbot import QtBot
from tests.factories import make_property
from tests.factories import make_submodel
from tests.medium.forms import Form

from aas_editor.application.changes import observer_for
from aas_editor.application.edits import SetAttribute
from aas_editor.application.hints import hints_mode
from aas_editor.application.validation import hints_for
from aas_editor.application.validation import validate_package

CATEGORY_HINT = (
    "Hint: The category 'PARAMETER' is deprecated. Do not plan to use it in "
    "new developments (EDT-HINT-CATEGORY)"
)


@pytest.fixture
def bar(qapp: object, qtbot: QtBot):
    from aas_editor.ui.hints_bar import HintsBar

    widget = HintsBar()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def shown_package(views):
    class Shown:
        element = make_property("Pump")
        submodel = make_submodel(elements=[element])
        package = views().open_package(submodel)

    return Shown


# ---------------------------------------------------------------------------
# The application layer
# ---------------------------------------------------------------------------


def test_hints_for_selects_the_findings_whose_anchor_is_the_object(
    shown_package,
) -> None:
    shown_package.element.category = "PARAMETER"
    report = validate_package(
        shown_package.package.save_source(), with_hints=True
    )

    assert [f.rule_id for f in hints_for(report, shown_package.element)] == [
        "EDT-HINT-CATEGORY"
    ]
    assert hints_for(report, shown_package.submodel) == ()


def test_the_package_check_has_no_hints_unless_asked(shown_package) -> None:
    shown_package.element.category = "PARAMETER"

    report = validate_package(shown_package.package.save_source())

    assert report.of_rule("EDT-HINT-CATEGORY") == ()


# ---------------------------------------------------------------------------
# The bar above a tab
# ---------------------------------------------------------------------------


def test_bar_lists_the_hints_of_the_shown_object(bar, shown_package) -> None:
    shown_package.element.category = "PARAMETER"

    bar.set_target(shown_package.package, shown_package.element)

    assert bar.lines == [CATEGORY_HINT]


def test_bar_lists_the_rules_the_object_breaks(bar, shown_package) -> None:
    shown_package.element.id_short = "X"

    bar.set_target(shown_package.package, shown_package.element)

    assert len(bar.lines) == 1
    assert bar.lines[0].startswith("Error: The idShort 'X' must have at least")
    assert bar.lines[0].endswith("(AASd-002)")


def test_bar_is_hidden_when_the_object_has_no_hint(bar, shown_package) -> None:
    bar.set_target(shown_package.package, shown_package.element)

    assert bar.lines == []
    assert bar.isHidden()


def test_bar_shows_nothing_for_an_object_it_has_no_package_for(bar) -> None:
    bar.set_target(None, None)

    assert bar.lines == []


def test_bar_is_off_when_hints_mode_is_off(bar, shown_package) -> None:
    shown_package.element.category = "PARAMETER"
    hints_mode().set_on(False)

    bar.set_target(shown_package.package, shown_package.element)

    assert bar.lines == []


def test_bar_follows_hints_mode(bar, shown_package) -> None:
    shown_package.element.category = "PARAMETER"
    bar.set_target(shown_package.package, shown_package.element)

    hints_mode().set_on(False)
    after_off = bar.lines
    hints_mode().set_on(True)

    assert after_off == []
    assert bar.lines == [CATEGORY_HINT]


def test_bar_does_not_wait_for_the_rules_while_the_user_edits(
    bar, shown_package, qtbot: QtBot
) -> None:
    package = shown_package.package
    bar.set_target(package, shown_package.element)

    # The edit is made at once. The advice about it comes after the debounce.
    package.commandStack.push(
        SetAttribute(
            observer_for(package), shown_package.element, "id_short", "Y"
        )
    )

    assert shown_package.element.id_short == "Y"
    assert bar.lines == []
    qtbot.waitUntil(lambda: len(bar.lines) == 1, timeout=2000)


def test_bar_drops_a_hint_after_an_undo(
    bar, shown_package, qtbot: QtBot
) -> None:
    package = shown_package.package
    bar.set_target(package, shown_package.element)
    package.commandStack.push(
        SetAttribute(
            observer_for(package), shown_package.element, "id_short", "Y"
        )
    )
    qtbot.waitUntil(lambda: len(bar.lines) == 1, timeout=2000)

    package.commandStack.undo()

    qtbot.waitUntil(lambda: bar.lines == [], timeout=2000)


def test_bar_lists_a_few_hints_and_counts_the_rest(bar, shown_package) -> None:
    element = shown_package.element
    element.category = "PARAMETER"
    element.semantic_id = model.ExternalReference(
        (model.Key(model.KeyTypes.GLOBAL_REFERENCE, "urn:a b"),)
    )
    element.supplemental_semantic_id.extend(
        model.ExternalReference(
            (model.Key(model.KeyTypes.GLOBAL_REFERENCE, f"urn:x y{number}"),)
        )
        for number in range(6)
    )

    bar.set_target(shown_package.package, element)

    assert len(bar.lines) == 6
    assert bar.lines[-1].startswith("... and 3 more.")


# ---------------------------------------------------------------------------
# Hints in the create dialogs
# ---------------------------------------------------------------------------


def _line_with_hint(text: str, owner: str, param: str):
    from aas_editor.ui.inline_hints import InlineHint
    from aas_editor.ui.inline_hints import attach_inline_hint
    from aas_editor.widgets.editWidgets import StandardInputWidget

    parent = QWidget()
    widget = StandardInputWidget(str, parent, text)
    layout = QHBoxLayout(parent)
    layout.addWidget(widget)
    attach_inline_hint(owner, param, widget)
    field = widget.widget
    assert isinstance(field, QLineEdit)
    hint = field.findChild(InlineHint)
    assert hint is not None
    return parent, field, hint


def test_inline_hint_says_why_an_id_short_is_wrong_while_typing(
    qapp: object, qtbot: QtBot
) -> None:
    parent, field, hint = _line_with_hint("", "Property", "id_short")
    qtbot.addWidget(parent)

    field.setText("1abc")

    assert hint.text.startswith("The idShort '1abc' must have at least")


def test_inline_hint_goes_away_when_the_id_short_is_right(
    qapp: object, qtbot: QtBot
) -> None:
    parent, field, hint = _line_with_hint("1abc", "Property", "id_short")
    qtbot.addWidget(parent)

    field.setText("abc")

    assert hint.text == ""


def test_inline_hint_says_nothing_about_an_empty_id_short(
    qapp: object, qtbot: QtBot
) -> None:
    parent, _, hint = _line_with_hint("", "Property", "id_short")
    qtbot.addWidget(parent)

    assert hint.text == ""


def test_inline_hint_finds_whitespace_in_the_value_of_a_key(
    qapp: object, qtbot: QtBot
) -> None:
    parent, field, hint = _line_with_hint("", "Key", "value")
    qtbot.addWidget(parent)

    field.setText("urn:a b")

    assert hint.text.startswith("There seems to be whitespace")


def test_inline_hint_says_that_the_global_asset_id_is_empty(
    qapp: object, qtbot: QtBot
) -> None:
    parent, _, hint = _line_with_hint("", "AssetInformation", "global_asset_id")
    qtbot.addWidget(parent)

    assert hint.text.startswith("The global asset id is empty")


def test_inline_hint_is_off_when_hints_mode_is_off(
    qapp: object, qtbot: QtBot
) -> None:
    hints_mode().set_on(False)
    parent, field, hint = _line_with_hint("", "Property", "id_short")
    qtbot.addWidget(parent)

    field.setText("1abc")

    assert hint.text == ""


def test_inline_hint_follows_hints_mode(qapp: object, qtbot: QtBot) -> None:
    parent, field, hint = _line_with_hint("1abc", "Property", "id_short")
    qtbot.addWidget(parent)

    hints_mode().set_on(False)
    after_off = hint.text
    hints_mode().set_on(True)

    assert after_off == ""
    assert hint.text != ""


def test_the_add_dialog_hints_and_still_accepts_what_the_hint_complains_about(
    lab,
) -> None:
    from aas_editor.ui.inline_hints import InlineHint

    seen: list[str] = []

    def fill(form: Form) -> None:
        form.choose_type(model.Property)
        form.type_text("id_short", "X")
        field = form.widget("id_short").widget
        hint = field.findChild(InlineHint)
        assert hint is not None
        seen.append(hint.text)
        form.choose("value_type", model.datatypes.String)

    lab.add(fill)

    assert seen[0].startswith("The idShort 'X' must have at least")
    assert [e.id_short for e in lab.submodel.submodel_element] == ["X"]


# ---------------------------------------------------------------------------
# Read mode hides null attributes (F-EDT-01 AC1)
# ---------------------------------------------------------------------------


def _attribute_names(model_support, tab) -> list[str]:
    return model_support.names(tab)


def test_read_mode_shows_no_row_for_a_null_attribute(model_support) -> None:
    from aas_editor.application.editing import edit_mode

    pack = model_support.pack_table(
        make_submodel(elements=[make_property("Pump")])
    )
    tab = model_support.detail_table(pack, "submodels", "Submodel", "Pump")
    assert "semantic_id" in _attribute_names(model_support, tab)

    edit_mode().set_editing(False)

    names = _attribute_names(model_support, tab)
    assert "semantic_id" not in names
    assert "display_name" not in names
    assert "id_short" in names


def test_read_mode_keeps_the_attributes_that_have_a_value(
    model_support,
) -> None:
    from aas_editor.application.editing import edit_mode

    element = make_property("Pump", "on")
    element.category = "PARAMETER"
    pack = model_support.pack_table(make_submodel(elements=[element]))
    tab = model_support.detail_table(pack, "submodels", "Submodel", "Pump")

    edit_mode().set_editing(False)

    names = _attribute_names(model_support, tab)
    assert {"id_short", "category", "value", "value_type"} <= set(names)


def test_edit_mode_brings_the_null_rows_back(model_support) -> None:
    from aas_editor.application.editing import edit_mode

    pack = model_support.pack_table(
        make_submodel(elements=[make_property("Pump")])
    )
    tab = model_support.detail_table(pack, "submodels", "Submodel", "Pump")
    edit_mode().set_editing(False)

    edit_mode().set_editing(True)

    assert "semantic_id" in _attribute_names(model_support, tab)


def test_a_tab_that_opens_in_read_mode_hides_the_null_rows(
    model_support,
) -> None:
    from aas_editor.application.editing import edit_mode

    pack = model_support.pack_table(
        make_submodel(elements=[make_property("Pump")])
    )
    edit_mode().set_editing(False)

    tab = model_support.detail_table(pack, "submodels", "Submodel", "Pump")

    assert "semantic_id" not in _attribute_names(model_support, tab)


def test_read_mode_hides_a_null_row_of_a_nested_object(model_support) -> None:
    from aas_editor.application.editing import edit_mode

    element = make_property("Pump")
    element.qualifier.add(
        model.Qualifier("Cardinality", model.datatypes.String, "One")
    )
    pack = model_support.pack_table(make_submodel(elements=[element]))
    tab = model_support.detail_table(pack, "submodels", "Submodel", "Pump")
    edit_mode().set_editing(False)

    qualifiers = model_support.find(tab, "qualifier")
    qualifier = model_support.find(tab, "Qualifier 0", qualifiers)
    names = model_support.names(tab, qualifier)

    assert "semantic_id" not in names
    assert "type" in names
