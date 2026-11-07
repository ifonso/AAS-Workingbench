"""A person gives each dialog wrong input: the editor must say so and change nothing.

Each case opens the real dialog, fills it wrongly, and presses OK as a person
does. Either the dialog keeps OK off and says why, or the editor refuses the
answer with a message. No case may add anything, leave an undo step behind, or
show the person a Python name or a traceback.
"""

from pathlib import Path

from basyx.aas import model
from basyx.aas.model import datatypes
import pytest
from tests.authoring import Author
from tests.authoring_builders import add_item
from tests.authoring_builders import make_shell
from tests.authoring_builders import make_submodel
from tests.medium.forms import Form
from tests.serialization import snapshot

pytest.importorskip(
    "PyQt6.QtWebEngineWidgets", reason="PyQt6.QtWebEngineWidgets not available"
)

BOX = ("submodels", "Box")
BOX_ID = "urn:example:sm:box"
# What a person must never read in a message.
INTERNALS = ("Traceback", "__init__", "unexpected keyword", "TypeError")


@pytest.fixture
def small(author: Author, tmp_path: Path) -> Author:
    """A new package with a shell, and an Instance submodel called Box."""
    author.start_new_package(tmp_path / "box.aasx")
    make_shell(author)
    make_submodel(author, "Box", BOX_ID, model.ModellingKind.INSTANCE)
    author.stack.mark_saved()
    return author


def _said(author: Author, answer, *needles: str) -> str:
    """Returns what the person was told, and checks it names the problem."""
    told = answer.problem or " ".join(author.errors)
    assert told, "Nothing told the person that the input is wrong"
    for internal in INTERNALS:
        assert internal not in told, told
    for needle in needles:
        assert needle.lower() in told.lower(), told
    return told


def _nothing_changed(author: Author, before: str) -> None:
    assert snapshot(author.package.objStore) == before
    assert author.stack.is_clean
    assert not author.window.isWindowModified()


@pytest.mark.parametrize(
    ("fill", "needle"),
    [
        (lambda d: d.id_edit.setText("urn:example:aas:pump"), "already"),
        (lambda d: d.id_short_edit.setText("1 bad name"), "idshort"),
        (lambda d: d.global_id_edit.setText(""), "asset id"),
        (lambda d: d.add_specific_row("onlyAName", ""), "value"),
    ],
    ids=[
        "duplicate id",
        "invalid idShort",
        "no asset id at all",
        "specific asset id without a value",
    ],
)
def test_create_aas_keeps_ok_off_and_says_why_for_wrong_input(
    small: Author, fill, needle: str
) -> None:
    from aas_editor.ui.create_dialogs import CreateShellDialog

    before = snapshot(small.package.objStore)

    def script(dialog: CreateShellDialog) -> None:
        dialog.id_edit.setText("urn:example:aas:second")
        dialog.id_short_edit.setText("Second")
        dialog.global_id_edit.setText("urn:example:asset:second")
        fill(dialog)

    small.select_path("shells")
    with small.answering(CreateShellDialog, script) as answer:
        small.act("create.shell")

    assert answer.ok_enabled is False
    _said(small, answer, needle)
    _nothing_changed(small, before)


@pytest.mark.parametrize(
    ("fill", "needle"),
    [
        (lambda d: d.id_edit.setText(BOX_ID), "already"),
        (lambda d: d.id_short_edit.setText("9lives"), "idshort"),
    ],
    ids=["duplicate id", "invalid idShort"],
)
def test_create_submodel_keeps_ok_off_and_says_why_for_wrong_input(
    small: Author, fill, needle: str
) -> None:
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    before = snapshot(small.package.objStore)

    def script(dialog: CreateSubmodelDialog) -> None:
        dialog.id_edit.setText("urn:example:sm:second")
        dialog.id_short_edit.setText("Second")
        fill(dialog)

    small.select_path("submodels")
    with small.answering(CreateSubmodelDialog, script) as answer:
        small.act("create.submodel")

    assert answer.ok_enabled is False
    _said(small, answer, needle)
    _nothing_changed(small, before)


@pytest.mark.parametrize(
    ("name", "value"), [("", "B7"), ("batch", ""), ("  ", "  ")]
)
def test_a_specific_asset_id_needs_a_name_and_a_value(
    small: Author, name: str, value: str
) -> None:
    from aas_editor.ui.create_dialogs import SpecificAssetIdDialog

    before = snapshot(small.package.objStore)

    def script(dialog: SpecificAssetIdDialog) -> None:
        dialog.name_edit.setText(name)
        dialog.value_edit.setText(value)

    small.select_path("shells", "Pump")
    with small.answering(SpecificAssetIdDialog, script) as answer:
        small.act("asset.add_specific_id")

    assert answer.ok_enabled is False
    _said(small, answer)
    _nothing_changed(small, before)


def _property(id_short: str, value: str = "1"):
    def fill(form: Form) -> None:
        form.choose("value_type", datatypes.Int)
        form.type_text("value", value)

    return model.Property, id_short, fill


def _qualifier_without_a_type(form: Form) -> None:
    form.type_text("value", "x")
    add_item(form.widget("qualifier"))


def _file_without_a_media_type(form: Form) -> None:
    form.type_text("content_type", "")


@pytest.mark.parametrize(
    ("element_type", "id_short", "fill"),
    [
        (*_property("bad name"),),
        (*_property("1abc"),),
        (*_property("Same"),),
        (*_property("Number", "abc"),),
        (*_property("Number", "1.5"),),
        (model.Property, "Plain", _qualifier_without_a_type),
        (model.File, "Doc", _file_without_a_media_type),
        (model.SubmodelElementCollection, "", lambda form: None),
    ],
    ids=[
        "idShort with a space",
        "idShort that starts with a digit",
        "idShort that a sibling has",
        "an Int value that is a word",
        "an Int value with a fraction",
        "qualifier without a type",
        "File without a media type",
        "collection without an idShort",
    ],
)
def test_the_add_dialog_refuses_wrong_input_with_a_message_and_adds_nothing(
    small: Author, element_type: type, id_short: str, fill
) -> None:
    taken = small.add_element(BOX, model.Property, "Same", _property("Same")[2])
    small.assert_accepted(taken)
    small.stack.mark_saved()
    small.errors.clear()
    before = snapshot(small.package.objStore)

    answer = small.add_element(BOX, element_type, id_short or None, fill)

    assert answer.ok_enabled is not None, small.errors
    _said(small, answer)
    assert answer.asked_again or answer.ok_enabled is False
    _nothing_changed(small, before)


def test_a_blank_id_in_the_create_dialogs_is_replaced_by_a_generated_one(
    small: Author,
) -> None:
    from aas_editor.ui.create_dialogs import CreateShellDialog
    from aas_editor.ui.create_dialogs import CreateSubmodelDialog

    def shell(dialog: CreateShellDialog) -> None:
        dialog.id_edit.setText("")
        dialog.id_short_edit.setText("Blank")

    def submodel(dialog: CreateSubmodelDialog) -> None:
        dialog.id_edit.setText("")
        dialog.id_short_edit.setText("BlankSm")

    small.select_path("shells")
    with small.answering(CreateShellDialog, shell) as answer:
        small.act("create.shell")
    small.assert_accepted(answer)
    small.select_path("submodels")
    with small.answering(CreateSubmodelDialog, submodel) as answer:
        small.act("create.submodel")
    small.assert_accepted(answer)

    made = {
        o.id_short: o.id
        for o in small.package.objStore
        if o.id_short in ("Blank", "BlankSm")
    }
    assert made["Blank"]
    assert made["BlankSm"]
    assert made["Blank"] != made["BlankSm"]


def test_a_rename_dialog_refuses_a_taken_id_and_a_bad_idshort_and_says_why(
    small: Author,
) -> None:
    from aas_editor.ui.reference_dialogs import RenameDialog

    taken = small.add_element(BOX, model.Property, "Same", _property("Same")[2])
    small.assert_accepted(taken)
    small.stack.mark_saved()
    before = snapshot(small.package.objStore)

    small.select_path(*BOX)
    with small.answering(
        RenameDialog, lambda d: d.edit.setText("urn:example:aas:pump")
    ) as answer:
        small.act("references.rename_id")
    assert answer.ok_enabled is False
    _said(small, answer, "already")

    small.select_path(*BOX, "Same")
    with small.answering(
        RenameDialog, lambda d: d.edit.setText("bad name")
    ) as answer:
        small.act("references.rename_id_short")
    assert answer.ok_enabled is False
    _said(small, answer, "idshort")
    assert answer.dialogs[0].fix_button.isEnabled()
    _nothing_changed(small, before)


def test_an_idshort_typed_in_a_tab_is_refused_or_fixed_only_when_the_person_agrees(
    small: Author,
) -> None:
    for name in ("Same", "Other"):
        answer = small.add_element(
            BOX, model.Property, name, _property(name)[2]
        )
        small.assert_accepted(answer)
    small.stack.mark_saved()
    before = snapshot(small.package.objStore)
    box = small.package.objStore.get_item(BOX_ID)
    tab = small.open_tab(*BOX, "Other")

    # A text that is no idShort: the person is offered a fix, and declines.
    assert not small.edit_attribute(tab, "id_short", "bad name")
    assert any(
        "bad name" in message or "idShort" in message
        for message in small.errors
    )
    _nothing_changed(small, before)

    # A name that a sibling has is refused with a reason.
    small.errors.clear()
    assert not small.edit_attribute(tab, "id_short", "Same")
    assert small.errors
    for internal in INTERNALS:
        assert internal not in small.errors[0]
    _nothing_changed(small, before)

    # Accepting the offered fix renames the element to the fixed name.
    small.errors.clear()
    small.replies.append(("bad name", "Use suggestion"))
    small.edit_attribute(tab, "id_short", "bad name")
    assert [e.id_short for e in box.submodel_element] == ["Same", "Bad_name"]


def test_a_concept_description_with_a_taken_id_is_refused_with_a_message(
    small: Author,
) -> None:
    from aas_editor.dialogs import EditObjDialog

    def make(dialog) -> None:
        Form(dialog).type_text("id_", "urn:example:cd:one")

    for _ in range(2):
        small.select_path("concept_descriptions")
        with small.answering(EditObjDialog, make) as answer:
            small.view.addAct.trigger()

    ids = [
        o.id
        for o in small.package.objStore
        if isinstance(o, model.ConceptDescription)
    ]
    assert ids == ["urn:example:cd:one"]
    assert answer.asked_again or small.errors
    assert small.errors
    for internal in INTERNALS:
        assert internal not in small.errors[0]
