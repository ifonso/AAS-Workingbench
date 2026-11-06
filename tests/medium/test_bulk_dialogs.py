"""The dialogs of the bulk actions, driven without a tree view."""

from basyx.aas import model
import pytest
from tests.factories import make_collection
from tests.factories import make_property
from tests.factories import make_submodel

from aas_editor.application.operations.bulk_edit import BulkAttribute
from aas_editor.domain.member_json import MemberKind
from aas_editor.infrastructure.preset_files import SHIPPED_PRESETS_DIR
from aas_editor.infrastructure.preset_files import load_presets


@pytest.fixture
def widgets(qapp, qtbot):
    """Builds the dialogs and registers them with qtbot."""
    from aas_editor.ui.bulk_dialogs import ChangeAttributeDialog
    from aas_editor.ui.bulk_dialogs import RemoveExtensionsDialog
    from aas_editor.ui.preset_dialogs import PresetDialog

    class Widgets:
        def change(self, objects, targets):
            dialog = ChangeAttributeDialog(objects, targets)
            qtbot.addWidget(dialog)
            return dialog

        def remove(self, owners):
            dialog = RemoveExtensionsDialog(owners)
            qtbot.addWidget(dialog)
            return dialog

        def preset(self, kind, tmp_path):
            loaded = load_presets(kind, SHIPPED_PRESETS_DIR, None)
            dialog = PresetDialog(kind, loaded, tmp_path)
            qtbot.addWidget(dialog)
            return dialog

    return Widgets()


def test_the_languages_of_the_selection_are_offered(widgets) -> None:
    props = [make_property("A"), make_property("B")]
    props[0].description = model.MultiLanguageTextType({"de": "x"})
    props[1].description = model.MultiLanguageTextType({"de": "y", "fr": "z"})
    submodel = make_submodel(elements=props)
    dialog = widgets.change([submodel], props)

    dialog.set_attribute(BulkAttribute.DESCRIPTION)
    languages = [
        dialog.languageBox.itemText(n)
        for n in range(dialog.languageBox.count())
    ]

    assert languages == ["de", "fr"]
    assert dialog.languageBox.currentText() == "de"
    assert dialog.languageBox.isEnabled()


def test_the_language_is_off_for_an_id_short(widgets) -> None:
    props = [make_property("A")]
    dialog = widgets.change([make_submodel(elements=props)], props)

    assert not dialog.languageBox.isEnabled()


def test_apply_waits_for_a_pattern_that_changes_something(widgets) -> None:
    props = [make_property("A")]
    dialog = widgets.change([make_submodel(elements=props)], props)
    start = dialog.applyButton.isEnabled()

    dialog.set_pattern("X{old}")
    changing = dialog.applyButton.isEnabled()
    dialog.set_pattern("{old")
    broken = dialog.applyButton.isEnabled()

    assert (start, changing, broken) == (False, True, False)
    assert "closing brace" in dialog.summary.text()


def test_the_summary_counts_what_changes_is_skipped_and_refused(
    widgets,
) -> None:
    props = [make_property("A"), make_property("B")]
    collection = make_collection("C")
    submodel = make_submodel(elements=[*props, collection])
    dialog = widgets.change([submodel], [*props, collection])
    dialog.set_attribute(BulkAttribute.VALUE)

    dialog.set_pattern("x{old}")
    value_summary = dialog.summary.text()
    dialog.set_attribute(BulkAttribute.ID_SHORT)
    dialog.set_pattern("Same")

    assert value_summary == "2 change, 1 skipped."
    assert "3 refused" in dialog.summary.text()
    assert not dialog.applyButton.isEnabled()


def test_the_removal_lists_the_groups_and_waits_for_a_choice(widgets) -> None:
    props = [make_property("A"), make_property("B")]
    for prop in props:
        prop.extension.add(model.Extension("Note"))
    dialog = widgets.remove(props)

    waiting = dialog.removeButton.isEnabled()
    dialog.choose("Note (2)")

    assert not waiting
    assert dialog.removeButton.isEnabled()
    assert dialog.chosen is not None
    assert dialog.chosen.count == 2


def test_without_extensions_the_removal_has_nothing_to_choose(widgets) -> None:
    dialog = widgets.remove([make_property("A")])

    assert dialog.groups == []
    assert not dialog.removeButton.isEnabled()


def test_the_filter_narrows_the_list_of_presets(widgets, tmp_path) -> None:
    dialog = widgets.preset(MemberKind.QUALIFIER, tmp_path)
    everything = dialog.list.count()

    dialog.filterEdit.setText("cardinality = onetomany")

    assert dialog.list.count() == 1
    assert everything > 10
    assert dialog.chosen is not None
    assert dialog.chosen.name == "Submodel templates | Cardinality = OneToMany"
    assert "SMT/Cardinality" in dialog.preview.toPlainText()


def test_nothing_is_chosen_when_the_filter_matches_nothing(
    widgets, tmp_path
) -> None:
    dialog = widgets.preset(MemberKind.QUALIFIER, tmp_path)

    dialog.filterEdit.setText("zzzzzz")

    assert dialog.chosen is None
    assert not dialog.addButton.isEnabled()
