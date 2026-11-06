# ruff: noqa: F811
"""F-EDT-09 criteria that the first audit found open."""

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.medium.test_bulk_actions import bulk  # noqa: F401
from tests.medium.test_reference_integrity import Answers  # noqa: F401
from tests.medium.test_reference_integrity import answers  # noqa: F401
from tests.reference_factories import make_linked
from tests.serialization import snapshot

# -- AC6 ---------------------------------------------------------------------


def test_declining_the_delete_of_several_referenced_objects_changes_nothing(
    views, answers
) -> None:
    linked = make_linked()
    shown = views()
    package = shown.open_package(*linked.store)
    before = snapshot(package.objStore)
    shown.select(
        shown.index("submodels", "Main"), shown.index("submodels", "Other")
    )
    answers.dialog_action = lambda dialog: dialog.reject()

    shown.view.onDelClear()

    assert len(answers.dialogs) == 1
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_declining_the_question_for_several_submodels_changes_nothing(
    views, answers
) -> None:
    linked = make_linked()
    linked.shell.submodel.clear()
    linked.main.submodel_element.clear()
    linked.other.submodel_element.clear()
    shown = views()
    package = shown.open_package(linked.shell, linked.main, linked.other)
    before = snapshot(package.objStore)
    shown.select(
        shown.index("submodels", "Main"), shown.index("submodels", "Other")
    )
    answers.box_button = "Cancel"

    shown.view.onDelClear()

    assert len(answers.boxes) == 1
    assert snapshot(package.objStore) == before
    assert not package.commandStack.can_undo


def test_confirming_the_delete_of_several_rows_removes_all_of_them(
    views, answers
) -> None:
    linked = make_linked()
    linked.shell.submodel.clear()
    linked.main.submodel_element.clear()
    linked.other.submodel_element.clear()
    shown = views()
    package = shown.open_package(linked.shell, linked.main, linked.other)
    shown.select(
        shown.index("submodels", "Main"), shown.index("submodels", "Other")
    )
    answers.box_button = "Delete"

    shown.view.onDelClear()

    assert linked.main not in package.objStore
    assert linked.other not in package.objStore
    assert linked.shell in package.objStore


# -- AC21 --------------------------------------------------------------------


def _extended(*names: str) -> list[model.Property]:
    props = [make_property(name) for name in names]
    for prop in props:
        prop.extension.add(model.Extension("Alpha"))
    return props


def _move(lab) -> None:
    lab.action("structure.move_up").trigger()


def _delete(lab) -> None:
    lab.view.onDelClear()


def _cut(lab) -> None:
    lab.view.onCut()


def _change(lab) -> None:
    lab.change(lambda dialog: dialog.set_pattern("X_{old}"))


def _remove_extensions(lab) -> None:
    lab.remove_extensions("Alpha (2)")


@pytest.mark.parametrize(
    "act",
    [_move, _delete, _cut, _change, _remove_extensions],
    ids=lambda f: f.__name__.strip("_"),
)
def test_a_bulk_action_flags_the_package_until_it_is_undone(bulk, act) -> None:
    lab = bulk(*_extended("A", "B", "C"))
    lab.select(("B",), ("C",))
    assert not lab.package.changed

    act(lab)
    flagged = lab.package.changed
    lab.view.onUndo()

    assert flagged
    assert not lab.package.changed
    assert [m.id_short for m in lab.submodel.submodel_element] == list("ABC")
