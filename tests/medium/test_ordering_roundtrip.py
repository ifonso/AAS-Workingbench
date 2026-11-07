"""The order set through `domain.ordering` survives saving and reading (D16)."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from basyx.aas import model
from basyx.aas.adapter.json import read_aas_json_file
from basyx.aas.adapter.json import write_aas_json_file
from basyx.aas.adapter.xml import read_aas_xml_file
from basyx.aas.adapter.xml import write_aas_xml_file
import pytest

from aas_workingbench.domain.ordering import move_to
from aas_workingbench.domain.ordering import set_id_short
from tests.factories import make_annotated_relationship
from tests.factories import make_collection
from tests.factories import make_entity
from tests.factories import make_list
from tests.factories import make_operation
from tests.factories import make_property
from tests.factories import make_store
from tests.factories import make_submodel

Elements = model.NamespaceSet[Any]


def _letters() -> list[model.Property]:
    return [make_property(name, name) for name in ("a", "b", "c")]


def _build_submodel() -> model.Submodel:
    return make_submodel(
        elements=[
            *_letters(),
            make_collection("Collection", _letters()),
            make_entity("Entity", _letters()),
            # The variables of one operation share a namespace, so each kind
            # gets an operation of its own to reuse the same idShorts.
            make_operation("OperationIn", input_variables=_letters()),
            make_operation("OperationOut", output_variables=_letters()),
            make_operation("OperationInOut", in_output_variables=_letters()),
            make_annotated_relationship("Relationship", _letters()),
            make_list("List", _letters()),
        ]
    )


def _referable(submodel: model.Submodel, id_short: str) -> Any:
    return submodel.get_referable(id_short)


def _top(submodel: model.Submodel) -> Elements:
    return submodel.submodel_element


def _collection(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "Collection").value


def _entity(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "Entity").statement


def _input(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "OperationIn").input_variable


def _output(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "OperationOut").output_variable


def _in_output(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "OperationInOut").in_output_variable


def _annotations(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "Relationship").annotation


def _list(submodel: model.Submodel) -> Elements:
    return _referable(submodel, "List").value


CONTAINERS: dict[str, Callable[[model.Submodel], Elements]] = {
    "submodel": _top,
    "collection": _collection,
    "entity": _entity,
    "operation-input": _input,
    "operation-output": _output,
    "operation-in-output": _in_output,
    "annotations": _annotations,
    "list": _list,
}


def _round_trip(
    submodel: model.Submodel, file_format: str, directory: Path
) -> model.Submodel:
    store = make_store(submodel)
    path = directory / f"package.{file_format}"
    if file_format == "json":
        with path.open("w", encoding="utf-8") as file:
            write_aas_json_file(file, store)
        loaded = read_aas_json_file(path.as_posix(), failsafe=False)
    else:
        with path.open("wb") as file:
            write_aas_xml_file(file, store)
        loaded = read_aas_xml_file(path.as_posix(), failsafe=False)
    return loaded.get(submodel.id)  # type: ignore[return-value]


@pytest.mark.parametrize("file_format", ["json", "xml"])
@pytest.mark.parametrize("container", CONTAINERS)
def test_order_survives_saving_when_a_member_was_moved(
    container: str, file_format: str, tmp_path: Path
) -> None:
    submodel = _build_submodel()
    elements = CONTAINERS[container](submodel)
    move_to(elements, list(elements)[2], 0)

    loaded = _round_trip(submodel, file_format, tmp_path)

    first_three = list(CONTAINERS[container](loaded))[:3]
    assert [e.value for e in first_three] == ["c", "a", "b"]


@pytest.mark.parametrize("file_format", ["json", "xml"])
@pytest.mark.parametrize(
    "container",
    [name for name in CONTAINERS if name != "list"],
)
def test_order_survives_saving_when_a_member_was_renamed(
    container: str, file_format: str, tmp_path: Path
) -> None:
    submodel = _build_submodel()
    elements = CONTAINERS[container](submodel)
    set_id_short(list(elements)[0], "z")

    loaded = _round_trip(submodel, file_format, tmp_path)

    first_three = list(CONTAINERS[container](loaded))[:3]
    assert [e.id_short for e in first_three] == ["z", "b", "c"]
    assert [e.value for e in first_three] == ["a", "b", "c"]
