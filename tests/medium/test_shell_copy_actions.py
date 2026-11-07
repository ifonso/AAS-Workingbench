"""Copy AAS with new Submodel ids, through the tree (F-EDT-02 AC3, AC4)."""

from pathlib import Path

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_workingbench.application.editing import edit_mode

ACTION = "create.copy_shell"


@pytest.fixture
def copying(views, monkeypatch: pytest.MonkeyPatch):
    """A package with an AAS of two Submodels, and the action."""
    from aas_workingbench.ui import create_actions
    from aas_workingbench.ui import shell_copy_actions
    from aas_workingbench.ui.shell_copy_actions import (
        register_shell_copy_actions,
    )

    register_shell_copy_actions()
    problems: list[str] = []
    monkeypatch.setattr(
        shell_copy_actions,
        "show_problem",
        lambda message, parent=None: problems.append(message),
    )
    monkeypatch.setattr(
        create_actions,
        "show_problem",
        lambda message, parent=None: problems.append(message),
    )

    class Copying:
        def __init__(self) -> None:
            self.monkeypatch = monkeypatch
            self.problems = problems
            self.shown = views()
            self.view = self.shown.view
            self.first = make_submodel(
                id_="urn:sm:1", id_short="First", elements=[make_property("P")]
            )
            self.second = make_submodel(id_="urn:sm:2", id_short="Second")
            self.shell = make_shell(
                id_="urn:shell:1",
                id_short="Pump",
                submodels=[self.first, self.second],
            )
            self.package = self.shown.open_package(
                self.shell, self.first, self.second
            )

        def select(self, *names: str) -> None:
            self.shown.select(self.shown.index(*names))
            self.view.updateActions(self.view.currentIndex())

        def action(self):
            return self.view.registeredActions.find(ACTION)

        def shells(self) -> list[model.AssetAdministrationShell]:
            return [
                o
                for o in self.package.objStore
                if isinstance(o, model.AssetAdministrationShell)
            ]

    return Copying()


def test_the_copy_has_new_ids_and_refers_to_new_submodels(
    copying, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package

    copying.select("shells", "Pump")
    assert copying.action().isEnabled()

    copying.action().trigger()

    (new,) = [s for s in copying.shells() if s is not copying.shell]
    store = copying.package.objStore
    resolved = [r.resolve(store) for r in new.submodel]
    assert new.id != copying.shell.id
    assert new.asset_information.global_asset_id != (
        copying.shell.asset_information.global_asset_id
    )
    assert sorted(s.id_short for s in resolved) == ["First", "Second"]
    assert not ({copying.first, copying.second} & set(resolved))
    assert {r.key[0].value for r in copying.shell.submodel} == {
        "urn:sm:1",
        "urn:sm:2",
    }
    assert copying.view.currentIndex().data(0) == "Pump"
    path = tmp_path / "copied.aasx"
    copying.package.write(path)
    reloaded = Package(path).objStore
    assert len([o for o in reloaded if isinstance(o, model.Submodel)]) == 4


def test_the_copy_is_one_undo_step(copying) -> None:
    copying.select("shells", "Pump")

    copying.action().trigger()
    copying.view.onUndo()

    assert copying.shells() == [copying.shell]
    assert len(copying.package.objStore) == 3
    assert not copying.package.commandStack.can_undo


def test_on_the_node_of_the_shells_it_asks_which_to_copy(
    copying, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.ui import shell_copy_actions

    asked: list[list[str]] = []

    def ask(shells, parent=None):
        asked.append([s.id for s in shells])
        return shells[0]

    monkeypatch.setattr(shell_copy_actions, "ask_shell", ask)
    copying.select("shells")

    enabled = copying.action().isEnabled()
    copying.action().trigger()

    assert enabled
    assert asked == [["urn:shell:1"]]
    assert len(copying.shells()) == 2


def test_cancelling_the_question_copies_nothing(
    copying, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aas_workingbench.ui import shell_copy_actions

    monkeypatch.setattr(shell_copy_actions, "ask_shell", lambda *a: None)
    copying.select("shells")

    copying.action().trigger()

    assert len(copying.shells()) == 1
    assert not copying.package.commandStack.can_undo


def test_the_environment_and_a_submodel_have_no_copy_of_an_aas(
    copying,
) -> None:
    copying.shown.select(copying.shown.index())
    copying.view.updateActions(copying.view.currentIndex())
    on_package = copying.action().isEnabled()
    copying.select("submodels", "First")

    assert not on_package
    assert not copying.action().isEnabled()


def test_it_is_off_in_read_mode(copying) -> None:
    copying.select("shells", "Pump")
    edit_mode().set_editing(False)
    copying.view.updateActions(copying.view.currentIndex())

    assert not copying.action().isEnabled()
