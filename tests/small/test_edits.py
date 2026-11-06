"""The commands for the edits of the editor, and the read gate (D18)."""

import io

from basyx.aas import model
from basyx.aas.adapter.aasx import DictSupplementaryFileContainer
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_editor.application.changes import Change
from aas_editor.application.changes import ChangeKind
from aas_editor.application.changes import ModelChangeObserver
from aas_editor.application.commands import CommandStack
from aas_editor.application.commands import ReadOnlyError
from aas_editor.application.editing import EditMode
from aas_editor.application.edits import AddMember
from aas_editor.application.edits import AddSupplementaryFile
from aas_editor.application.edits import RemoveMember
from aas_editor.application.edits import ReplaceMember
from aas_editor.application.edits import SetAttribute
from aas_editor.application.edits import link_submodels


@pytest.fixture
def observer() -> ModelChangeObserver:
    return ModelChangeObserver()


@pytest.fixture
def changes(observer: ModelChangeObserver) -> list[Change]:
    received: list[Change] = []
    observer.subscribe(received.append)
    return received


def _ids(submodel: model.Submodel) -> list[str]:
    return [element.id_short or "" for element in submodel.submodel_element]


def test_set_attribute_sets_and_restores_the_value(
    observer: ModelChangeObserver,
) -> None:
    prop = make_property("a")
    prop.category = "old"
    stack = CommandStack()

    stack.push(SetAttribute(observer, prop, "category", "new"))
    after_push = prop.category
    stack.undo()
    after_undo = prop.category
    stack.redo()

    assert (after_push, after_undo, prop.category) == ("new", "old", "new")


def test_set_attribute_keeps_the_position_when_it_renames(
    observer: ModelChangeObserver,
) -> None:
    submodel = make_submodel(
        elements=[make_property("a"), make_property("b"), make_property("c")]
    )
    element = next(iter(submodel.submodel_element))
    stack = CommandStack()

    stack.push(SetAttribute(observer, element, "id_short", "z"))
    renamed = _ids(submodel)
    stack.undo()

    assert (renamed, _ids(submodel)) == (["z", "b", "c"], ["a", "b", "c"])


def test_set_attribute_keeps_the_element_when_the_sdk_refuses_a_semantic_id(
    observer: ModelChangeObserver,
) -> None:
    # AASd-114: the items of a list must have equal semantic ids. The SDK takes
    # the item out of the list before it checks, and then loses it.
    items = model.SubmodelElementList(
        "Items",
        type_value_list_element=model.Property,
        value_type_list_element=model.datatypes.String,
        value=[
            model.Property(
                None,
                model.datatypes.String,
                value=text,
                semantic_id=make_external_reference("urn:same"),
            )
            for text in ("a", "b", "c")
        ],
    )
    second = list(items.value)[1]
    stack = CommandStack()

    with pytest.raises(model.AASConstraintViolation):
        stack.push(
            SetAttribute(
                observer,
                second,
                "semantic_id",
                make_external_reference("urn:different"),
            )
        )

    assert [item.value for item in items.value] == ["a", "b", "c"]
    assert second.semantic_id == make_external_reference("urn:same")
    assert not stack.can_undo


def test_set_attribute_keeps_the_position_when_it_sets_a_semantic_id(
    observer: ModelChangeObserver,
) -> None:
    submodel = make_submodel(
        elements=[make_property("a"), make_property("b"), make_property("c")]
    )
    element = next(iter(submodel.submodel_element))
    stack = CommandStack()

    stack.push(
        SetAttribute(
            observer, element, "semantic_id", make_external_reference("urn:x")
        )
    )
    after_push = _ids(submodel)
    stack.undo()

    assert (after_push, _ids(submodel)) == (["a", "b", "c"], ["a", "b", "c"])


def test_set_attribute_reports_a_change_of_the_owner_when_applied_and_reverted(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    prop = make_property("a")
    stack = CommandStack()

    stack.push(SetAttribute(observer, prop, "category", "new"))
    stack.undo()

    assert [(c.kind, c.target) for c in changes] == [
        (ChangeKind.CHANGED, prop),
        (ChangeKind.CHANGED, prop),
    ]


def test_set_attribute_changes_nothing_when_the_sdk_refuses_the_value(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    prop = make_property("a", 5, model.datatypes.Int)
    stack = CommandStack()

    with pytest.raises((ValueError, TypeError)):
        stack.push(SetAttribute(observer, prop, "value", "abc"))

    assert (prop.value, stack.can_undo, changes) == (5, False, [])


def test_set_attribute_knows_when_it_would_change_nothing(
    observer: ModelChangeObserver,
) -> None:
    prop = make_property("a")
    prop.category = "same"

    assert SetAttribute(observer, prop, "category", "same").is_noop
    assert not SetAttribute(observer, prop, "category", "other").is_noop


def test_add_member_inserts_and_undo_removes_it(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    submodel = make_submodel(elements=[make_property("a"), make_property("b")])
    new = make_property("n")
    stack = CommandStack()

    stack.push(AddMember(observer, submodel.submodel_element, new, 1))
    added = _ids(submodel)
    stack.undo()

    assert (added, _ids(submodel)) == (["a", "n", "b"], ["a", "b"])
    assert [(c.kind, c.index) for c in changes] == [
        (ChangeKind.ADDED, 1),
        (ChangeKind.REMOVED, 1),
    ]


def test_add_member_reinserts_at_the_same_place_when_it_is_redone(
    observer: ModelChangeObserver,
) -> None:
    submodel = make_submodel(elements=[make_property("a"), make_property("b")])
    stack = CommandStack()

    stack.push(
        AddMember(observer, submodel.submodel_element, make_property("n"))
    )
    stack.undo()
    stack.redo()

    assert _ids(submodel) == ["a", "b", "n"]


def test_add_member_is_refused_without_a_trace_when_the_id_short_is_taken(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    submodel = make_submodel(elements=[make_property("a")])
    stack = CommandStack()

    with pytest.raises(model.AASConstraintViolation):
        stack.push(
            AddMember(observer, submodel.submodel_element, make_property("a"))
        )

    assert (stack.can_undo, changes) == (False, [])


def test_remove_member_undo_restores_the_position(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    elements = [make_property("a"), make_property("b"), make_property("c")]
    submodel = make_submodel(elements=elements)
    stack = CommandStack()

    stack.push(RemoveMember(observer, submodel.submodel_element, elements[1]))
    removed = _ids(submodel)
    stack.undo()

    assert (removed, _ids(submodel)) == (["a", "c"], ["a", "b", "c"])
    assert [(c.kind, c.index) for c in changes] == [
        (ChangeKind.REMOVED, 1),
        (ChangeKind.ADDED, 1),
    ]


def test_remove_member_from_a_set_reports_no_position(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    shell = make_shell(submodels=[make_submodel()])
    (reference,) = shell.submodel
    stack = CommandStack()

    stack.push(RemoveMember(observer, shell.submodel, reference))
    stack.undo()

    assert len(shell.submodel) == 1
    assert [(c.kind, c.index) for c in changes] == [
        (ChangeKind.REMOVED, None),
        (ChangeKind.ADDED, None),
    ]


def test_remove_member_of_a_mapping_reports_a_change_of_the_mapping(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    texts = model.MultiLanguageTextType({"en": "one", "de": "eins"})
    stack = CommandStack()

    stack.push(RemoveMember(observer, texts, ("en", "one")))
    stack.undo()

    assert list(texts) == ["en", "de"]
    assert [(c.kind, c.target) for c in changes] == [
        (ChangeKind.CHANGED, texts),
        (ChangeKind.CHANGED, texts),
    ]


def test_replace_member_swaps_in_place_and_undo_swaps_back(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    elements = [make_property("a"), make_property("b")]
    submodel = make_submodel(elements=elements)
    stack = CommandStack()

    stack.push(
        ReplaceMember(
            observer, submodel.submodel_element, elements[0], make_property("n")
        )
    )
    replaced = _ids(submodel)
    stack.undo()

    assert (replaced, _ids(submodel)) == (["n", "b"], ["a", "b"])
    assert [c.target for c in changes] == [submodel.submodel_element] * 2


def test_supplementary_file_is_added_and_deleted_again(
    observer: ModelChangeObserver, changes: list[Change]
) -> None:
    store = DictSupplementaryFileContainer()
    stored: list[str | None] = []
    shown = object()
    stack = CommandStack()

    stack.push(
        AddSupplementaryFile(
            observer,
            store,
            "/a.txt",
            b"data",
            "text/plain",
            shown,
            stored.append,
        )
    )
    present = "/a.txt" in store
    stack.undo()

    assert present
    assert "/a.txt" not in store
    assert stored == ["/a.txt", None]
    assert [(c.kind, c.target) for c in changes] == [
        (ChangeKind.ADDED, shown),
        (ChangeKind.REMOVED, shown),
    ]
    out = io.BytesIO()
    stack.redo()
    store.write_file("/a.txt", out)
    assert out.getvalue() == b"data"


def test_adding_a_file_the_store_has_already_leaves_it_alone_on_undo(
    observer: ModelChangeObserver,
) -> None:
    store = DictSupplementaryFileContainer()
    store.add_file("/a.txt", io.BytesIO(b"data"), "text/plain")
    stack = CommandStack()

    stack.push(
        AddSupplementaryFile(
            observer,
            store,
            "/a.txt",
            b"data",
            "text/plain",
            object(),
            lambda name: None,
        )
    )
    stack.undo()

    assert "/a.txt" in store


def test_link_submodels_is_one_step_that_adds_every_missing_reference(
    observer: ModelChangeObserver,
) -> None:
    first = make_submodel("urn:uuid:s1", "One")
    second = make_submodel("urn:uuid:s2", "Two")
    shell = make_shell(submodels=[first])
    stack = CommandStack()

    added = link_submodels(stack, observer, shell, [first, second])
    after_link = len(shell.submodel)
    stack.undo()

    assert (added, after_link, len(shell.submodel)) == (1, 2, 1)
    assert not stack.can_undo


def test_link_submodels_records_nothing_when_all_are_linked(
    observer: ModelChangeObserver,
) -> None:
    submodel = make_submodel()
    shell = make_shell(submodels=[submodel])
    stack = CommandStack()

    added = link_submodels(stack, observer, shell, [submodel])

    assert (added, stack.is_clean, stack.can_undo) == (0, True, False)


class TestReadGate:
    def test_push_is_refused_in_read_mode_and_changes_nothing(
        self, observer: ModelChangeObserver
    ) -> None:
        mode = EditMode()
        mode.set_editing(False)
        prop = make_property("a")
        stack = CommandStack(is_editing=lambda: mode.is_editing)

        with pytest.raises(ReadOnlyError, match="Read mode"):
            stack.push(SetAttribute(observer, prop, "category", "x"))

        assert (prop.category, stack.can_undo, stack.is_clean) == (
            None,
            False,
            True,
        )

    def test_undo_and_redo_are_refused_in_read_mode(
        self, observer: ModelChangeObserver
    ) -> None:
        mode = EditMode()
        prop = make_property("a")
        stack = CommandStack(is_editing=lambda: mode.is_editing)
        stack.push(SetAttribute(observer, prop, "category", "x"))
        mode.set_editing(False)

        with pytest.raises(ReadOnlyError):
            stack.undo()

        mode.set_editing(True)
        stack.undo()
        mode.set_editing(False)
        with pytest.raises(ReadOnlyError):
            stack.redo()
        assert prop.category is None

    def test_a_group_is_undone_when_the_mode_switches_inside_it(
        self, observer: ModelChangeObserver
    ) -> None:
        mode = EditMode()
        first, second = make_property("a"), make_property("b")
        stack = CommandStack(is_editing=lambda: mode.is_editing)

        with pytest.raises(ReadOnlyError), stack.group("Two edits"):
            stack.push(SetAttribute(observer, first, "category", "x"))
            mode.set_editing(False)
            stack.push(SetAttribute(observer, second, "category", "x"))

        assert (first.category, second.category) == (None, None)
        assert not stack.can_undo

    def test_edits_are_allowed_again_in_edit_mode(
        self, observer: ModelChangeObserver
    ) -> None:
        mode = EditMode()
        mode.set_editing(False)
        mode.set_editing(True)
        prop = make_property("a")
        stack = CommandStack(is_editing=lambda: mode.is_editing)

        stack.push(SetAttribute(observer, prop, "category", "x"))

        assert prop.category == "x"


def test_mark_unsaved_keeps_the_package_dirty_until_it_is_saved() -> None:
    stack = CommandStack()

    stack.mark_unsaved()
    unsaved = stack.is_clean
    stack.mark_saved()

    assert (unsaved, stack.is_clean) == (False, True)


class TestEditMode:
    def test_starts_in_edit_mode(self) -> None:
        assert EditMode().is_editing

    def test_tells_the_subscribers_when_the_mode_changes(self) -> None:
        mode = EditMode()
        seen: list[bool] = []
        mode.subscribe(seen.append)

        mode.set_editing(False)
        mode.set_editing(False)
        mode.set_editing(True)

        assert seen == [False, True]
