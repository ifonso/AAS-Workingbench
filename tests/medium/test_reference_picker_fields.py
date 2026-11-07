"""The reference picker in the forms that enter or edit a reference (F-EDT-11).

Each test goes through the dialog that the tree view opens, as a user does:
pick a target, see the status line, and accept. Every change is one undo step,
and it survives a save and a reload.
"""

from typing import Any

from basyx.aas import model
from basyx.aas.model.concept import ConceptDescription
import pytest
from tests.factories import make_collection
from tests.factories import make_concept_description
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.medium.conftest import ELEMENT_ID
from tests.medium.forms import answering
from tests.serialization import snapshot

from aas_workingbench.application.editing import edit_mode
from aas_workingbench.domain.reference_picker import ReferenceState

K = model.KeyTypes


def _property() -> model.Property:
    return model.Property(ELEMENT_ID, value_type=str, value="x")


@pytest.fixture
def picking(lab_class, monkeypatch: pytest.MonkeyPatch):
    """A lab with a concept description, and ways to pick in the form."""
    from aas_workingbench.ui.reference_picker import ReferencePickerDialog

    class Picking:
        def __init__(self, *elements: model.SubmodelElement) -> None:
            self.lab = lab_class(*elements)
            self.concept = make_concept_description()
            self.lab.package.add(self.concept)
            self.errors = self.lab.shown.shown_errors
            self.dialogs: list[Any] = []

        def edit(
            self, attribute: str, fill: Any, refused: bool = False
        ) -> None:
            attrs = self.lab.attrs()
            self.lab.edit_in_dialog(attrs, attribute, fill, refused=refused)

        def pick(self, widget: Any, script: Any) -> bool:
            """Presses the picker button and answers its dialog with a script."""
            with answering(
                monkeypatch, ReferencePickerDialog, script
            ) as opened:
                picked = widget.choose_from_package()
            self.dialogs.extend(opened)
            return picked

    return Picking


def _picker(dialog: Any) -> Any:
    return dialog.inputWidget


class TestPickingATarget:
    def test_a_concept_description_gives_an_external_reference_to_its_id(
        self, picking
    ) -> None:
        element = _property()
        flow = picking(element)

        def fill(dialog: Any) -> None:
            flow.pick(
                _picker(dialog), lambda picker: picker.select(flow.concept)
            )

        flow.edit("semantic_id", fill)

        assert element.semantic_id == model.ExternalReference(
            (model.Key(K.GLOBAL_REFERENCE, flow.concept.id),)
        )

    def test_the_model_kind_keeps_the_concept_description_key_type(
        self, picking
    ) -> None:
        element = _property()
        flow = picking(element)

        def script(picker: Any) -> None:
            picker.set_as_model(True)
            picker.select(flow.concept)

        flow.edit("semantic_id", lambda d: flow.pick(_picker(d), script))

        assert isinstance(element.semantic_id, model.ModelReference)
        assert element.semantic_id.key == (
            model.Key(K.CONCEPT_DESCRIPTION, flow.concept.id),
        )

    def test_the_change_is_one_undo_step_that_saves_and_reloads(
        self, picking
    ) -> None:
        element = _property()
        flow = picking(element)
        before = snapshot(flow.lab.package.objStore)
        stack = flow.lab.stack

        flow.edit(
            "semantic_id",
            lambda d: flow.pick(_picker(d), lambda p: p.select(flow.concept)),
        )
        edited = snapshot(flow.lab.package.objStore)
        reloaded = flow.lab.save_and_reload()
        stack.undo()
        undone = snapshot(flow.lab.package.objStore)
        stack.redo()

        assert edited != before
        assert reloaded == edited
        assert undone == before
        assert snapshot(flow.lab.package.objStore) == edited

    def test_editing_replaces_the_old_reference_and_undo_brings_it_back(
        self, picking
    ) -> None:
        element = _property()
        element.semantic_id = make_external_reference("urn:example:old")
        flow = picking(element)

        flow.edit(
            "semantic_id",
            lambda d: flow.pick(_picker(d), lambda p: p.select(flow.concept)),
        )
        replaced = element.semantic_id
        flow.lab.stack.undo()

        assert replaced is not None
        assert replaced.key[0].value == flow.concept.id
        assert element.semantic_id == make_external_reference("urn:example:old")

    def test_nothing_is_changed_when_the_picker_is_cancelled(
        self, picking, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from PyQt6.QtWidgets import QDialog

        from aas_workingbench.ui.reference_picker import ReferencePickerDialog

        element = _property()
        flow = picking(element)
        monkeypatch.setattr(
            ReferencePickerDialog,
            "exec",
            lambda self: QDialog.DialogCode.Rejected,
        )

        def fill(dialog: Any) -> None:
            assert not _picker(dialog).choose_from_package()
            assert _picker(dialog).current_reference() is None

        flow.edit("semantic_id", fill, refused=True)

        assert element.semantic_id is None

    def test_a_submodel_reference_of_a_shell_offers_only_submodels(
        self, views, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from aas_workingbench.dialogs import EditObjDialog
        from aas_workingbench.ui.reference_picker import ReferencePickerDialog

        first = make_submodel(id_="urn:sm:1", id_short="First")
        second = make_submodel(id_="urn:sm:2", id_short="Second")
        shell = make_shell(id_short="Shell")
        shown = views()
        package = shown.open_package(shell, first, second)
        seen: list[Any] = []

        def inspect_picker(picker: Any) -> None:
            seen.append(
                (
                    picker.filter_names(),
                    picker.visible_labels(),
                    picker.kind_box.count(),
                )
            )
            picker.select(first)

        def fill(dialog: Any) -> None:
            # The dialog for a new reference has its one entry already.
            group = dialog.inputWidget
            assert len(group.inputWidgets) == 1
            field = group.inputWidgets[0]
            with answering(monkeypatch, ReferencePickerDialog, inspect_picker):
                field.choose_from_package()

        attrs = shown.attrs_view("shells", "Shell")
        parent = _attribute_row(attrs, "submodel")
        attrs.setCurrentIndex(parent)
        with answering(monkeypatch, EditObjDialog, fill):
            attrs.onAddAct(parent)

        filters, labels, kinds = seen[0]
        assert filters == ["Anything", "Submodels"]
        assert labels == ["First", "Second"]
        assert kinds == 1
        assert [r.key[0].value for r in shell.submodel] == ["urn:sm:1"]
        package.commandStack.undo()
        assert len(shell.submodel) == 0


def _attribute_row(attrs: Any, name: str) -> Any:
    from aas_workingbench.settings.app_settings import NAME_ROLE

    proxy = attrs.model()
    for row in range(proxy.rowCount()):
        index = proxy.index(row, 0)
        if index.data(NAME_ROLE) == name:
            return index.siblingAtColumn(1)
    raise LookupError(name)


class TestStatus:
    def test_a_reference_to_an_object_of_the_package_shows_it_resolves(
        self, picking
    ) -> None:
        element = _property()
        flow = picking(element)
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            flow.pick(widget, lambda p: p.select(flow.concept))
            seen.append(widget.reference_status())

        flow.edit("semantic_id", fill)

        status = seen[0]
        assert status.state is ReferenceState.RESOLVED
        assert status.target is flow.concept

    def test_a_model_reference_to_nothing_is_shown_as_dangling(
        self, picking
    ) -> None:
        element = _property()
        element.semantic_id = model.ModelReference(
            (model.Key(K.CONCEPT_DESCRIPTION, "urn:example:gone"),),
            ConceptDescription,
        )
        flow = picking(element)
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            widget.refresh_status()
            seen.append(
                (widget.reference_status(), widget._status_label.text())
            )

        flow.edit("semantic_id", fill)

        status, text = seen[0]
        assert status.state is ReferenceState.DANGLING
        assert "urn:example:gone" in text

    def test_an_external_reference_outside_the_package_is_not_dangling(
        self, picking
    ) -> None:
        element = _property()
        element.semantic_id = make_external_reference("urn:example:elsewhere")
        flow = picking(element)
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            widget.refresh_status()
            seen.append(widget.reference_status())

        flow.edit("semantic_id", fill)

        assert seen[0].state is ReferenceState.OUTSIDE
        assert not seen[0].is_dangling


class TestRefusals:
    def test_an_sdk_refusal_is_shown_as_a_reason_and_blocks_ok(
        self, picking
    ) -> None:
        element = _property()
        flow = picking(element)
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            widget.set_reference(make_external_reference("urn:example:ok"))
            keys = widget._reference_box().paramWidgets["key"]
            keys.inputWidgets[-1].paramWidgets["type_"].widget.setCurrentIndex(
                keys.inputWidgets[-1]
                .paramWidgets["type_"]
                .widget.findData(K.SUBMODEL)
            )
            widget.refresh_status()
            seen.append(
                (
                    widget.reference_problem(),
                    dialog.buttonOk.isEnabled(),
                    widget.reference_status(),
                )
            )
            # Put a valid reference back so the dialog can close.
            widget.set_reference(make_external_reference("urn:example:ok"))

        flow.edit("semantic_id", fill)

        problem, ok_enabled, status = seen[0]
        assert "AASd-122" in problem
        assert "Traceback" not in problem
        assert not ok_enabled
        assert status is None

    def test_ok_works_again_when_the_keys_are_right(self, picking) -> None:
        element = _property()
        flow = picking(element)
        seen: list[bool] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            widget.refresh_status()
            seen.append(dialog.buttonOk.isEnabled())
            widget.set_reference(make_external_reference("urn:example:ok"))
            seen.append(dialog.buttonOk.isEnabled())

        flow.edit("semantic_id", fill)

        assert seen == [False, True]

    def test_an_element_gets_a_model_reference_even_in_the_external_kind(
        self, picking
    ) -> None:
        flow = picking(_property(), make_property("Other"))
        element = flow.lab.submodel.get_referable("Other")
        seen: list[Any] = []

        def script(picker: Any) -> None:
            picker.set_as_model(False)
            picker.set_filter("Submodel elements")
            seen.append(picker.select(element))
            seen.append(picker.problem())

        flow.edit("semantic_id", lambda d: flow.pick(_picker(d), script))

        assert seen[0] is True
        assert "ModelReference" in seen[1]
        assert isinstance(
            flow.lab.submodel.get_referable(ELEMENT_ID).semantic_id,
            model.ModelReference,
        )

    def test_a_field_for_external_references_lists_only_ids(
        self, views, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from aas_workingbench.domain.reference_picker import rule_for_hint
        from aas_workingbench.ui.reference_picker import ReferencePickerDialog

        submodel = make_submodel(elements=[make_property("P")])
        concept = make_concept_description()
        dialog = ReferencePickerDialog(
            [submodel, concept], rule_for_hint(model.ExternalReference)
        )

        assert dialog.visible_labels() == ["Submodel", "Concept"]
        assert dialog.kind_box.count() == 1
        dialog.deleteLater()

    def test_read_mode_refuses_the_edit_and_changes_nothing(
        self, picking
    ) -> None:
        # Read mode hides a null attribute, so this one has a value.
        element = _property()
        original = make_external_reference("urn:example:old")
        element.semantic_id = original
        flow = picking(element)
        edit_mode().set_editing(False)
        try:
            index = flow.lab.row(flow.lab.attrs(), "semantic_id")
            edited = (
                flow.lab.attrs()
                .model()
                .setData(
                    index,
                    make_external_reference("urn:example:new"),
                    2,
                )
            )
        finally:
            edit_mode().set_editing(True)

        assert not edited
        assert element.semantic_id is original


class TestFreeEntry:
    def test_a_typed_external_reference_is_kept(self, picking) -> None:
        element = _property()
        flow = picking(element)

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            box = widget._reference_box()
            keys = box.paramWidgets["key"]
            keys.findChildren(type(widget._picker_button))[0].click()
            key = keys.inputWidgets[-1]
            key.paramWidgets["value"].widget.setText("0173-1#02-AAO677#002")

        flow.edit("semantic_id", fill)

        assert element.semantic_id == make_external_reference(
            "0173-1#02-AAO677#002"
        )

    def test_the_target_type_follows_the_last_key_type(self, picking) -> None:
        from PyQt6.QtWidgets import QPushButton

        flow = picking(_property())
        seen: list[Any] = []

        def fill(dialog: Any) -> None:
            widget = _picker(dialog)
            widget.set_reference(
                model.ModelReference(
                    (model.Key(K.SUBMODEL, flow.lab.submodel.id),),
                    model.Submodel,
                )
            )
            box = widget._reference_box()
            keys = box.paramWidgets["key"]
            keys.findChild(QPushButton).click()
            key = keys.inputWidgets[-1]
            combo = key.paramWidgets["type_"].widget
            combo.setCurrentIndex(combo.findData(K.PROPERTY))
            key.paramWidgets["value"].widget.setText(ELEMENT_ID)
            widget.refresh_status()
            seen.append(box.paramWidgets["type_"].widget.currentData())
            seen.append(widget.current_reference())

        flow.edit("semantic_id", fill)

        assert seen[0] is model.Property
        assert seen[1].type is model.Property
        assert flow.lab.stack.can_undo


class TestPickerDialog:
    def test_search_narrows_the_list_by_name(self, picking) -> None:
        flow = picking(
            _property(), make_collection("Inner", [make_property("Deep")])
        )
        seen: list[list[str]] = []

        def script(picker: Any) -> None:
            picker.set_filter("Submodel elements")
            picker.set_search("deep")
            seen.append(picker.visible_labels())

        flow.edit(
            "semantic_id", lambda d: flow.pick(_picker(d), script), refused=True
        )

        assert seen == [["Inner/Deep"]]

    def test_filters_are_the_ones_the_field_can_use(self, picking) -> None:
        flow = picking(_property())
        seen: list[Any] = []

        flow.edit(
            "semantic_id",
            lambda d: flow.pick(
                _picker(d),
                lambda p: seen.append((p.filter_names(), p.kind_box.count())),
            ),
            refused=True,
        )

        names, kinds = seen[0]
        assert names[0] == "Anything"
        assert "Concept descriptions" in names
        assert kinds == 2


# Every field of the SDK that holds a reference, as (class, attribute).
REFERENCE_FIELDS = [
    (model.Property, "semantic_id"),
    (model.Property, "supplemental_semantic_id"),
    (model.Qualifier, "value_id"),
    (model.Qualifier, "semantic_id"),
    (model.Extension, "refers_to"),
    (model.ReferenceElement, "value"),
    (model.RelationshipElement, "first"),
    (model.RelationshipElement, "second"),
    (model.AssetAdministrationShell, "submodel"),
    (model.AssetAdministrationShell, "derived_from"),
    (model.SpecificAssetId, "external_subject_id"),
    (model.ConceptDescription, "is_case_of"),
    (model.BasicEventElement, "observed"),
    (model.BasicEventElement, "message_broker"),
    (model.AdministrativeInformation, "creator"),
    (model.EmbeddedDataSpecification, "data_specification"),
]


@pytest.mark.parametrize(
    ("owner", "attribute"),
    REFERENCE_FIELDS,
    ids=[f"{cls.__name__}.{attr}" for cls, attr in REFERENCE_FIELDS],
)
def test_every_reference_field_gets_the_picker(
    qapp: object, owner: type, attribute: str
) -> None:
    from aas_workingbench.ui.reference_fields import ReferenceFieldMixin
    from aas_workingbench.utils.util import getAttrTypeHint
    from aas_workingbench.utils.util import getIterItemTypeHint
    from aas_workingbench.utils.util_type import isIterableType
    from aas_workingbench.widgets.widgetUtil import InputWidgetUtil

    hint = getAttrTypeHint(owner, attribute)
    if isIterableType(hint):
        hint = getIterItemTypeHint(hint)

    widget = InputWidgetUtil.getInputWidget(hint)

    assert isinstance(widget, ReferenceFieldMixin)
    widget.deleteLater()


@pytest.mark.parametrize("kind", [model.ExternalReference, None])
def test_a_reference_form_shows_one_picker_and_one_status_line(
    qapp: object, qtbot: Any, kind: type | None
) -> None:
    from PyQt6.QtWidgets import QPushButton

    from aas_workingbench.ui.reference_fields import CHOOSE_TEXT
    from aas_workingbench.widgets.widgetUtil import InputWidgetUtil

    widget = InputWidgetUtil.getInputWidget(model.Reference)
    qtbot.addWidget(widget)
    if kind is not None:
        widget.typeComboBox.setCurrentIndex(widget.typeComboBox.findData(kind))
    widget.show()
    qtbot.waitExposed(widget)

    pickers = [
        button
        for button in widget.findChildren(QPushButton)
        if button.text() == CHOOSE_TEXT and button.isVisibleTo(widget)
    ]
    assert len(pickers) == 1


def test_editing_a_model_reference_keeps_the_type_its_last_key_names(
    qapp: object, qtbot: Any
) -> None:
    from aas_workingbench.ui.reference_fields import ReferenceFieldMixin  # noqa: F401
    from aas_workingbench.utils.util import getAttrTypeHint
    from aas_workingbench.widgets.widgetUtil import InputWidgetUtil

    # The SDK reads the target type of `observed` as a Referable, which the
    # list of the form does not offer. The form then took its first entry and
    # turned a reference to a Property into one to an annotated relationship.
    reference = model.ModelReference(
        (
            model.Key(K.SUBMODEL, "urn:sm"),
            model.Key(K.PROPERTY, "Speed"),
        ),
        model.Referable,
    )
    hint = getAttrTypeHint(model.BasicEventElement, "observed")
    widget = InputWidgetUtil.getInputWidget(hint, objVal=reference)
    qtbot.addWidget(widget)

    widget.refresh_status()

    assert widget.getObj2add().type is model.Property


def test_the_package_is_found_through_a_tab_widget_in_the_parents(
    qapp: object, qtbot: Any
) -> None:
    from PyQt6.QtWidgets import QDialog
    from PyQt6.QtWidgets import QTabWidget
    from PyQt6.QtWidgets import QWidget

    from aas_workingbench.settings.app_settings import PACKAGE_ROLE
    from aas_workingbench.ui.reference_fields import package_of

    package = object()

    class Index:
        def data(self, role: int) -> object | None:
            return package if role == PACKAGE_ROLE else None

    class ViewLike(QWidget):
        def currentIndex(self) -> Index:  # noqa: N802
            return Index()

    view = ViewLike()
    qtbot.addWidget(view)
    tabs = QTabWidget(view)  # its currentIndex is a number
    dialog = QDialog(tabs)
    inner = QWidget(dialog)

    assert package_of(inner) is package
