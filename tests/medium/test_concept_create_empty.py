"""Create empty concept description (F-EDT-11 AC15, F-EDT-05 AC1).

The description has a generated id and nothing else, is added in one step, and
is selected. The semantic id of an element stays as it was.
"""

from pathlib import Path

from basyx.aas import model
import pytest
from tests.factories import make_external_reference
from tests.factories import make_property
from tests.factories import make_shell
from tests.factories import make_submodel
from tests.medium.concept_lab import CONCEPTS
from tests.medium.concept_lab import build_lab_class

from aas_editor.application.editing import edit_mode
from aas_editor.settings.app_settings import OBJECT_ROLE

ACTION = "concepts.create_empty"
SUBMODEL = ("submodels", "Submodel")


@pytest.fixture
def lab(views, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    return build_lab_class(views, monkeypatch, tmp_path)


def _speed() -> model.Property:
    prop = make_property("Speed")
    prop.semantic_id = make_external_reference("urn:cd:speed")
    return prop


def _concepts(lab) -> list[model.ConceptDescription]:
    return [o for o in lab.store if isinstance(o, model.ConceptDescription)]


def test_on_the_node_it_adds_a_description_with_a_generated_id(lab) -> None:
    lab = lab()

    enabled = lab.act(ACTION)

    assert enabled
    (concept,) = _concepts(lab)
    assert concept.id.startswith("urn:uuid:")
    assert concept.id_short is None
    assert not concept.embedded_data_specifications
    assert not concept.is_case_of


def test_the_new_description_is_selected_in_the_tree(lab) -> None:
    lab = lab()

    lab.act(ACTION)

    (concept,) = _concepts(lab)
    assert lab.view.currentIndex().data(OBJECT_ROLE) is concept


def test_it_is_one_step_that_undo_takes_back_and_a_save_keeps(lab) -> None:
    lab = lab()

    lab.act(ACTION)
    (concept,) = _concepts(lab)
    saved = lab.saved_order()
    lab.stack.undo()
    gone = _concepts(lab)
    lab.stack.redo()

    assert saved == [concept.id]
    assert gone == []
    assert _concepts(lab) == [concept]


def test_two_calls_make_two_descriptions_with_different_ids(lab) -> None:
    lab = lab()

    lab.act(ACTION)
    lab.select((CONCEPTS,))
    lab.act(ACTION)

    assert len({c.id for c in _concepts(lab)}) == 2


def test_on_an_element_the_semantic_id_stays_as_it_was(lab) -> None:
    speed = _speed()
    reference = speed.semantic_id
    lab = lab(make_submodel(elements=[speed]))
    lab.select((*SUBMODEL, "Speed"))

    enabled = lab.act(ACTION)

    assert enabled
    assert speed.semantic_id is reference
    assert len(_concepts(lab)) == 1


def test_it_is_off_on_a_shell(lab) -> None:
    lab = lab(make_shell())
    lab.select(("shells", "Shell"))

    assert not lab.enabled(ACTION)


def test_it_is_off_in_read_mode(lab) -> None:
    lab = lab()
    edit_mode().set_editing(False)
    try:
        lab.view.updateActions(lab.view.currentIndex())
        enabled = lab.enabled(ACTION)
    finally:
        edit_mode().set_editing(True)

    assert not enabled
    assert _concepts(lab) == []
