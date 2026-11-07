from basyx.aas import model
from basyx.aas.util import traversal
from tests.factories import make_collection
from tests.factories import make_file_element
from tests.factories import make_property
from tests.factories import make_submodel
from tests.package_factories import make_annotated_relationship

from aas_workingbench.domain.walking import descendants
from aas_workingbench.domain.walking import is_annotation
from aas_workingbench.domain.walking import walk_elements


def test_walk_elements_yields_annotations_when_relationship_is_annotated() -> (
    None
):
    note = make_file_element("Note", "/aasx/files/note.txt")
    submodel = make_submodel(
        elements=[make_annotated_relationship(annotations=(note,))]
    )

    names = [element.id_short for element in walk_elements(submodel)]

    assert names == ["Annotated", "Note"]


def test_walk_elements_yields_nested_annotations_when_in_collection() -> None:
    note = make_file_element("Note", "/aasx/files/note.txt")
    annotated = make_annotated_relationship(annotations=(note,))
    submodel = make_submodel(
        elements=[
            make_collection("Outer", [annotated]),
            make_property("Last"),
        ]
    )

    names = [element.id_short for element in walk_elements(submodel)]

    assert names == ["Annotated", "Note", "Outer", "Last"]


def test_walk_elements_yields_nothing_when_submodel_is_empty() -> None:
    assert list(walk_elements(make_submodel())) == []


def test_is_annotation_is_true_when_parent_is_annotated_relationship() -> None:
    note = make_file_element("Note")
    make_annotated_relationship(annotations=(note,))

    assert is_annotation(note) is True


def test_is_annotation_is_false_when_parent_is_submodel() -> None:
    file_element = make_file_element("Plain")
    make_submodel(elements=[file_element])

    assert is_annotation(file_element) is False


def test_sdk_walker_skips_annotations_which_is_why_walking_exists() -> None:
    # If the SDK starts to walk annotations, domain/walking.py is not needed.
    note = make_file_element("Note")
    submodel = make_submodel(
        elements=[make_annotated_relationship(annotations=(note,))]
    )

    names = [element.id_short for element in traversal.walk_submodel(submodel)]

    assert names == ["Annotated"]


def test_descendants_lists_parents_before_children_in_document_order() -> None:
    submodel = make_submodel(
        elements=[
            make_collection("Outer", [make_property("Inner")]),
            make_property("Last"),
        ]
    )

    names = [element.id_short for element in descendants(submodel)]

    assert names == ["Outer", "Inner", "Last"]


def test_descendants_includes_entity_statements_and_operation_variables() -> (
    None
):
    entity = model.Entity(
        "Part",
        model.EntityType.CO_MANAGED_ENTITY,
        statement=[make_property("Stated")],
    )
    operation = model.Operation(
        "Run",
        input_variable=[make_property("In")],
        output_variable=[make_property("Out")],
        in_output_variable=[make_property("Both")],
    )
    submodel = make_submodel(elements=[entity, operation])

    names = [element.id_short for element in descendants(submodel)]

    assert names == ["Part", "Stated", "Run", "In", "Out", "Both"]


def test_descendants_includes_annotations() -> None:
    note = make_file_element("Note", "/aasx/files/note.txt")
    submodel = make_submodel(
        elements=[make_annotated_relationship(annotations=(note,))]
    )

    assert [e.id_short for e in descendants(submodel)] == ["Annotated", "Note"]
