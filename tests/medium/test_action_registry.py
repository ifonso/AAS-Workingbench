"""Features add actions to the views through the registry."""

from collections.abc import Iterator

from basyx.aas import model
import pytest
from tests.factories import make_property
from tests.factories import make_submodel


@pytest.fixture
def registry(qapp: object) -> Iterator[object]:
    """Gives the default registry back in the state it had."""
    from aas_workingbench.ui.actions import default_registry

    registered: list[str] = []
    yield registered
    for action_id in registered:
        default_registry().unregister(action_id)


def _register(registry, **overrides):
    from aas_workingbench.application.edits import SetAttribute
    from aas_workingbench.application.changes import observer_for
    from aas_workingbench.settings.app_settings import OBJECT_ROLE
    from aas_workingbench.ui.actions import ActionContext
    from aas_workingbench.ui.actions import ActionSpec
    from aas_workingbench.ui.actions import register_action

    def tag(context: ActionContext) -> None:
        element = context.index.data(OBJECT_ROLE)
        context.push(
            SetAttribute(
                observer_for(context.package), element, "category", "Tagged"
            )
        )

    def is_property(context: ActionContext) -> bool:
        return isinstance(context.index.data(OBJECT_ROLE), model.Property)

    spec = {
        "action_id": "test.tag",
        "text": "Tag the element",
        "run": tag,
        "is_enabled": is_property,
    }
    spec.update(overrides)
    register_action(ActionSpec(**spec))
    registry.append(spec["action_id"])


def test_registered_action_is_in_the_context_menu_of_the_package_tree(
    views, registry
) -> None:
    _register(registry)

    shown = views()

    action = shown.view.registeredActions.find("test.tag")
    assert action is not None
    assert action in shown.view.attrsMenu.actions()
    assert action.text() == "Tag the element"


def test_registered_action_is_in_the_context_menu_of_a_detail_view(
    views, registry
) -> None:
    _register(registry)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))

    attrs = shown.attrs_view("submodels", "Submodel", "p")

    assert attrs.registeredActions.find("test.tag") in attrs.attrsMenu.actions()


def test_action_for_the_package_tree_is_not_in_a_detail_view(
    views, registry
) -> None:
    from aas_workingbench.ui.actions import ViewKind

    _register(registry, views=ViewKind.PACKAGES)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))

    attrs = shown.attrs_view("submodels", "Submodel", "p")

    assert shown.view.registeredActions.find("test.tag") is not None
    assert attrs.registeredActions.find("test.tag") is None


def test_triggering_the_action_runs_it_on_the_current_item_as_one_step(
    views, registry
) -> None:
    _register(registry)
    prop = make_property("p")
    shown = views()
    package = shown.open_package(make_submodel(elements=[prop]))
    shown.select(shown.index("submodels", "Submodel", "p"))

    action = shown.view.registeredActions.find("test.tag")
    action.trigger()
    tagged = prop.category
    shown.view.onUndo()

    assert tagged == "Tagged"
    assert prop.category is None
    assert not package.commandStack.can_undo


def test_action_follows_its_enable_rule(views, registry) -> None:
    _register(registry)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))

    shown.select(shown.index("submodels", "Submodel", "p"))
    on_property = shown.view.registeredActions.find("test.tag").isEnabled()
    shown.select(shown.index("submodels", "Submodel"))
    on_submodel = shown.view.registeredActions.find("test.tag").isEnabled()

    assert on_property
    assert not on_submodel


def test_action_that_changes_packages_is_disabled_in_read_mode(
    views, registry
) -> None:
    from aas_workingbench.application.editing import edit_mode

    _register(registry)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    shown.select(shown.index("submodels", "Submodel", "p"))

    edit_mode().set_editing(False)
    in_read_mode = shown.view.registeredActions.find("test.tag").isEnabled()
    edit_mode().set_editing(True)

    assert not in_read_mode
    assert shown.view.registeredActions.find("test.tag").isEnabled()


def test_action_that_only_reads_stays_enabled_in_read_mode(
    views, registry
) -> None:
    from aas_workingbench.application.editing import edit_mode

    _register(registry, action_id="test.look", mutates=False)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    shown.select(shown.index("submodels", "Submodel", "p"))

    edit_mode().set_editing(False)

    assert shown.view.registeredActions.find("test.look").isEnabled()


def test_toolbar_actions_are_the_ones_that_ask_for_the_toolbar(
    views, registry
) -> None:
    _register(registry, toolbar=True)
    _register(registry, action_id="test.menu_only")

    shown = views()

    assert shown.view.registeredActions.toolbar_actions == [
        shown.view.registeredActions.find("test.tag")
    ]


def test_actions_are_ordered_by_their_order_value(views, registry) -> None:
    _register(registry, action_id="test.late", order=200)
    _register(registry, action_id="test.early", order=10)

    shown = views()

    assert [
        action.text() for action in shown.view.registeredActions.actions
    ] == ["Tag the element", "Tag the element"]
    assert shown.view.registeredActions.actions[0] is (
        shown.view.registeredActions.find("test.early")
    )


def test_registering_an_id_twice_is_refused(registry) -> None:
    _register(registry)

    with pytest.raises(ValueError, match="already registered"):
        _register(registry)


def test_actions_are_grouped_by_the_section_of_their_id(
    views, registry
) -> None:
    # Features chose their order values on their own, so the same number
    # (200, 300) used to put unrelated actions side by side.
    _register(registry, action_id="files.sample", order=1)
    _register(registry, action_id="create.sample", order=900)
    _register(registry, action_id="structure.sample", order=500)
    _register(registry, action_id="unknown.sample", order=0)

    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry

    views()

    ids = [
        spec.action_id
        for spec in default_registry().specs_for(ViewKind.PACKAGES)
        if spec.action_id.endswith(".sample")
    ]
    assert ids == [
        "create.sample",
        "structure.sample",
        "files.sample",
        "unknown.sample",
    ]


def test_the_menu_separates_the_sections_and_hides_what_does_not_apply(
    views, registry
) -> None:
    from PyQt6.QtWidgets import QMenu

    _register(registry, action_id="create.sample", order=1)
    _register(registry, action_id="conversion.sample", order=1)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    shown.select(shown.index("submodels", "Submodel"))

    menu = QMenu()
    shown.view.registeredActions.add_to_menu(menu)
    separators = [a for a in menu.actions() if a.isSeparator()]
    ids = ("create.sample", "conversion.sample")
    on_submodel = [
        shown.view.registeredActions.find(i).isVisible() for i in ids
    ]
    shown.select(shown.index("submodels", "Submodel", "p"))
    on_property = [
        shown.view.registeredActions.find(i).isVisible() for i in ids
    ]

    assert len(separators) == 2
    assert on_submodel == [False, False]
    assert on_property == [True, True]


def test_a_crowded_section_is_a_submenu_that_hides_when_nothing_applies(
    views, registry
) -> None:
    from PyQt6.QtWidgets import QMenu

    _register(registry, action_id="files.sample", order=1)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    menu = QMenu()
    shown.view.registeredActions.add_to_menu(menu)
    (submenu,) = [a for a in menu.actions() if a.menu() is not None]
    action = shown.view.registeredActions.find("files.sample")

    shown.select(shown.index("submodels", "Submodel"))
    on_submodel = submenu.isVisible()
    shown.select(shown.index("submodels", "Submodel", "p"))
    on_property = submenu.isVisible()

    assert submenu.text() == "Package files"
    assert action in submenu.menu().actions()
    assert action not in menu.actions()
    assert (on_submodel, on_property) == (False, True)


def test_an_action_of_the_toolbar_is_never_hidden(views, registry) -> None:
    _register(registry, toolbar=True)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    shown.select(shown.index("submodels", "Submodel"))

    action = shown.view.registeredActions.find("test.tag")

    assert not action.isEnabled()
    assert action.isVisible()


def test_a_menu_that_was_deleted_does_not_break_the_next_update(
    views, registry
) -> None:
    # A crowded section is a submenu that the view refreshes whenever the
    # clipboard changes. A menu that its owner deletes must not make every
    # later refresh of the view, and of any test after it, fail.
    from PyQt6.QtWidgets import QMenu

    _register(registry, action_id="files.sample", order=1)
    shown = views()
    shown.open_package(make_submodel(elements=[make_property("p")]))
    shown.select(shown.index("submodels", "Submodel", "p"))
    menu = QMenu()
    shown.view.registeredActions.add_to_menu(menu)

    del menu
    shown.view.registeredActions.update()

    assert shown.view.registeredActions.find("files.sample").isEnabled()
