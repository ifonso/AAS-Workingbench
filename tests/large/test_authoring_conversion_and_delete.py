"""A person converts elements, renames many at once, and deletes what is referred to.

The package comes from `build_everything`. Each step goes through the actions
of the context menu and the Edit menu, and the dialogs they open. Each one is
a single undo step, the references follow or are shown first, and the package
saved and read again holds what the editor showed.
"""

from pathlib import Path

from basyx.aas import model
import pytest
from tests.authoring import Author
from tests.authoring_builders import EVERYTHING
from tests.authoring_builders import SUBMODEL
from tests.authoring_builders import build_everything
from tests.authoring_builders import everything
from tests.authoring_builders import findings
from tests.authoring_builders import reopened
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)


def test_an_element_is_converted_to_another_kind_with_its_references_and_attributes(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.replacement_dialogs import ReplacementDialog

    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    held = everything(author)
    alarm = held.get_referable("Alarm")
    position = [e.id_short for e in held.submodel_element].index("Voltage")

    author.answer_choice("MultiLanguageProperty")
    author.select_path(*SUBMODEL, "Voltage")
    with author.answering(ReplacementDialog, lambda dialog: None) as answer:
        assert author.act("conversion.convert")
    author.assert_accepted(answer)

    converted = held.get_referable("Voltage")
    assert isinstance(converted, model.MultiLanguageProperty)
    assert [e.id_short for e in held.submodel_element].index("Voltage") == (
        position
    )
    assert dict(converted.display_name) == {"en": "Voltage", "de": "Spannung"}
    assert [q.type for q in converted.qualifier] == ["Cardinality"]
    assert converted.semantic_id is not None
    assert alarm.observed.key[-1].type is model.KeyTypes.MULTI_LANGUAGE_PROPERTY
    assert findings(author) == []
    done = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == done
    assert author.undo_to_saved() == 1
    assert snapshot(author.package.objStore) == before
    assert author.redo_all() == 1
    assert snapshot(author.package.objStore) == done


def test_several_elements_are_renamed_at_once_with_a_pattern(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.bulk_dialogs import ChangeAttributeDialog

    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    held = everything(author)

    author.select(
        author.path(*SUBMODEL, "Label"),
        author.path(*SUBMODEL, "Limits"),
        author.path(*SUBMODEL, "Rel"),
    )
    with author.answering(
        ChangeAttributeDialog, lambda d: d.set_pattern("{old}_{number|pad(2)}")
    ) as answer:
        assert author.act("bulk.change_attribute")
    author.assert_accepted(answer)

    names = [e.id_short for e in held.submodel_element]
    assert {"Label_01", "Limits_02", "Rel_03"} <= set(names)
    assert not {"Label", "Limits", "Rel"} & set(names)
    assert {"Label_01", "Limits_02", "Rel_03"} <= set(author.names(*SUBMODEL))
    assert findings(author) == []
    done = snapshot(author.package.objStore)
    assert reopened(author, tmp_path) == done
    assert author.undo_to_saved() == 1
    assert snapshot(author.package.objStore) == before
    assert author.redo_all() == 1
    assert snapshot(author.package.objStore) == done


def test_deleting_a_concept_description_removes_the_semantic_ids_that_may_go_and_keeps_the_rest(
    author: Author, tmp_path: Path
) -> None:
    from tests.authoring_elements import external

    from aas_workingbench.ui.reference_dialogs import DeleteDialog

    build_everything(author, tmp_path)
    answer = author.add_element(
        SUBMODEL,
        model.Property,
        "Current",
        lambda form: (
            form.type_text("value", "x"),
            form.fill_reference(
                "semantic_id", external("urn:example:cd:speed")
            ),
        ),
    )
    author.assert_accepted(answer)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    voltage = everything(author).get_referable("Voltage")
    current = everything(author).get_referable("Current")

    author.select_path("concept_descriptions", "Speed")
    with author.answering(DeleteDialog, lambda dialog: None) as answer:
        assert author.edit_menu("delete")
    author.assert_accepted(answer)

    (dialog,) = answer.dialogs
    assert "2 references refer" in dialog.summary_label.text()
    assert dialog.remove_button.text() == "Delete and remove 1 reference"
    # Voltage has supplemental semantic ids, which need its semantic id.
    assert "Voltage" in dialog.kept_label.text()
    assert current.semantic_id is None
    assert voltage.semantic_id is not None
    assert author.names("concept_descriptions") == []
    done = snapshot(author.package.objStore)
    assert author.undo_to_saved() == 1
    assert current.semantic_id is not None
    assert snapshot(author.package.objStore) == before
    assert author.redo_all() == 1
    assert snapshot(author.package.objStore) == done


def test_a_submodel_deleted_with_its_reference_left_is_reported_by_validation(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.reference_dialogs import DeleteDialog

    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)

    author.select_path(*SUBMODEL)
    with author.answering(
        DeleteDialog, lambda dialog: dialog.keep_button.setChecked(True)
    ) as answer:
        assert author.edit_menu("delete")
    author.assert_accepted(answer)

    shell = author.package.objStore.get_item("urn:example:aas:pump")
    assert EVERYTHING in [r.key[0].value for r in shell.submodel]
    assert "Everything" not in author.names("submodels")
    reported = findings(author)
    assert any(
        EVERYTHING in message or "Everything" in message
        for _, _, message in reported
    ), reported
    assert author.undo_to_saved() == 1
    assert snapshot(author.package.objStore) == before
    assert findings(author) == []


def test_an_element_that_an_event_observes_is_deleted_and_the_event_is_reported(
    author: Author, tmp_path: Path
) -> None:
    from aas_workingbench.ui.reference_dialogs import DeleteDialog

    build_everything(author, tmp_path)
    author.stack.mark_saved()
    before = snapshot(author.package.objStore)
    alarm = everything(author).get_referable("Alarm")

    author.select_path(*SUBMODEL, "Voltage")
    with author.answering(DeleteDialog, lambda dialog: None) as answer:
        assert author.edit_menu("delete")
    author.assert_accepted(answer)

    (dialog,) = answer.dialogs
    # The observed element of an event is required, so the reference stays.
    assert "observed" in dialog.kept_label.text()
    assert "Voltage" not in author.names(*SUBMODEL)
    assert alarm.observed.key[-1].value == "Voltage"
    reported = findings(author)
    assert any(
        rule == "EDT-DANGLING-REFERENCE" and "observed" in message
        for _, rule, message in reported
    ), reported
    assert author.undo_to_saved() == 1
    assert snapshot(author.package.objStore) == before
    assert findings(author) == []
