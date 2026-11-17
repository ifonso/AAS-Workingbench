"""Each feature adds its actions to the registry once, and again after a reset."""

from collections.abc import Callable
import importlib

import pytest

# The modules that `__main__` asks to register their actions, with the name of
# the function that does it.
REGISTERING_MODULES = (
    ("blob_actions", "register_blob_actions"),
    ("bulk_actions", "register_bulk_actions"),
    ("bulk_edit_actions", "register_bulk_edit_actions"),
    ("concept_actions", "register_concept_actions"),
    ("conversion_actions", "register_conversion_actions"),
    ("create_actions", "register_create_actions"),
    ("file_actions", "register_file_actions"),
    ("load_report_actions", "register_load_report_actions"),
    ("location_actions", "register_location_actions"),
    ("move_actions", "register_move_actions"),
    ("paste_actions", "register_paste_actions"),
    ("preset_actions", "register_preset_actions"),
    ("reference_actions", "register_reference_actions"),
    ("reference_jump", "register_jump_actions"),
    ("shell_copy_actions", "register_shell_copy_actions"),
)


@pytest.fixture
def empty_registry(qapp: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gives the test a registry of its own, empty at the start."""
    from aas_workingbench.ui import actions

    monkeypatch.setattr(actions, "_registry", actions.ActionRegistry())


@pytest.fixture(params=REGISTERING_MODULES, ids=lambda pair: pair[0])
def register(request: pytest.FixtureRequest) -> Callable[[], None]:
    module_name, function_name = request.param
    module = importlib.import_module(f"aas_workingbench.ui.{module_name}")
    return getattr(module, function_name)


def _registered_ids() -> list[str]:
    from aas_workingbench.ui.actions import ViewKind
    from aas_workingbench.ui.actions import default_registry

    return [
        spec.action_id for spec in default_registry().specs_for(ViewKind.ANY)
    ]


def test_registering_twice_adds_each_action_once(
    empty_registry: None, register: Callable[[], None]
) -> None:
    register()
    register()

    ids = _registered_ids()
    assert ids
    assert len(ids) == len(set(ids))


def test_registering_after_the_actions_were_taken_out_adds_them_again(
    empty_registry: None, register: Callable[[], None]
) -> None:
    from aas_workingbench.ui.actions import default_registry

    register()
    added = _registered_ids()
    assert added
    # A test that registered the actions takes them out again for the next.
    for action_id in added:
        default_registry().unregister(action_id)

    register()

    assert _registered_ids() == added
