"""A lab for tests of the concept description actions through the tree view.

A lab opens a package in the package tree and offers ways to select a row, run
an action, answer its questions, and look at the result. The Qt modules of
`aas_workingbench` need a `QApplication`, so the class is built when a test asks for
the fixture, not when the module is imported.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from basyx.aas import model
import pytest

CONCEPTS = "concept_descriptions"


def build_lab_class(
    views: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> type:
    """Builds the class of labs for one test.

    Args:
        views: The `views` fixture.
        monkeypatch: The monkeypatch of the test.
        tmp_path: A folder for the files that a save writes.

    Returns:
        A class. `Lab(*objects)` opens a package with the objects.
    """
    from aas_workingbench.package import Package
    from aas_workingbench.settings.app_settings import NAME_ROLE
    from aas_workingbench.settings.app_settings import OBJECT_ROLE
    from aas_workingbench.ui import concept_actions
    from aas_workingbench.ui import concept_dialogs
    from aas_workingbench.ui import reference_dialogs
    from aas_workingbench.ui.concept_actions import register_concept_actions

    register_concept_actions()

    class Lab:
        def __init__(self, *objects: model.Identifiable) -> None:
            self.monkeypatch = monkeypatch
            self.shown = views()
            self.view = self.shown.view
            self.package = self.shown.open_package(*objects)
            self.stack = self.package.commandStack
            self.store = self.package.objStore
            self.messages: list[str] = []
            self.previews: list[list[list[str]]] = []
            self.confirm = True
            monkeypatch.setattr(
                reference_dialogs,
                "show_message",
                lambda title, text, parent=None: self.messages.append(text),
            )

            def confirm_preview(*args: Any, **kwargs: Any) -> bool:
                self.previews.append([list(row) for row in args[3]])
                return self.confirm

            monkeypatch.setattr(
                concept_dialogs, "confirm_preview", confirm_preview
            )
            self.select((CONCEPTS,))

        def select(self, *paths: tuple[str, ...]) -> None:
            self.shown.select(*(self.shown.index(*p) for p in paths))
            self.view.updateActions(self.view.currentIndex())

        def act(self, action_id: str) -> bool:
            action = self.view.registeredActions.find(action_id)
            enabled = action.isEnabled()
            action.trigger()
            return enabled

        def enabled(self, action_id: str) -> bool:
            return self.view.registeredActions.find(action_id).isEnabled()

        def fill(self, dialog_class: type, fill: Callable[[Any], None]) -> None:
            """Makes the real dialog fill itself and accept, instead of exec."""

            def run(dialog: Any) -> None:
                fill(dialog)
                dialog.accept()

            monkeypatch.setattr(dialog_class, "exec", run)

        def choose(self, order: Any) -> None:
            monkeypatch.setattr(
                concept_actions,
                "ask_concept_order",
                lambda current, parent=None: order,
            )
            self.act("concepts.order")

        def rows(self, *path: str) -> list[str]:
            proxy = self.view.model()
            parent = self.shown.index(*path)
            return [
                proxy.index(row, 0, parent).data(NAME_ROLE)
                for row in range(proxy.rowCount(parent))
            ]

        def listed(self) -> list[str]:
            """The ids of the descriptions in the order the tree lists them."""
            proxy = self.view.model()
            parent = self.shown.index(CONCEPTS)
            return [
                proxy.index(row, 0, parent).data(OBJECT_ROLE).id
                for row in range(proxy.rowCount(parent))
            ]

        def stored(self) -> list[str]:
            """The ids of the descriptions in the order of the store."""
            return [
                o.id
                for o in self.store
                if isinstance(o, model.ConceptDescription)
            ]

        def saved_order(self) -> list[str]:
            path = tmp_path / "saved.aasx"
            self.package.write(path)
            return [
                o.id
                for o in Package(path).objStore
                if isinstance(o, model.ConceptDescription)
            ]

        def concept(self, id_: str) -> model.ConceptDescription:
            found = self.store.get_item(id_)
            assert isinstance(found, model.ConceptDescription)
            return found

    return Lab
