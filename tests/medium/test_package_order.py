"""The order of the shells, submodels and descriptions of a file survives (ADR 0021).

The SDK's set store listed them in an order that changed from run to run. The
store of a package keeps the order in which objects were added, so a file read
and written again lists them as before, and the editor can tell the order of
the file.
"""

from pathlib import Path

from basyx.aas import model
import pytest
from tests.factories import make_shell
from tests.factories import make_submodel

from aas_editor.application.save import SaveOptions
from aas_editor.domain.ordered_store import OrderedIdentifiableStore
from aas_editor.infrastructure.package_io import PackageParts
from aas_editor.infrastructure.package_io import read_package
from aas_editor.infrastructure.package_io import write_package

# Not sorted by name or by id, so that no sort can give this order.
CONCEPT_IDS = ("urn:c:zebra", "urn:c:apple", "urn:c:mango", "urn:c:banana")


def _parts() -> PackageParts:
    objects = OrderedIdentifiableStore()
    objects.add(make_shell(id_="urn:s:two", id_short="Two"))
    objects.add(make_shell(id_="urn:s:one", id_short="One"))
    objects.add(make_submodel(id_="urn:m:y", id_short="Why"))
    objects.add(make_submodel(id_="urn:m:x", id_short="Ex"))
    for number, id_ in enumerate(CONCEPT_IDS):
        objects.add(model.ConceptDescription(id_, id_short=f"C{number}"))
    return PackageParts(objects=objects)


def _ids(parts: PackageParts, kind: type[model.Identifiable]) -> list[str]:
    return [o.id for o in parts.objects if isinstance(o, kind)]


@pytest.mark.parametrize("suffix", [".aasx", ".json", ".xml"])
def test_the_order_of_every_kind_of_object_survives_a_save_and_a_read(
    tmp_path: Path, suffix: str
) -> None:
    target = tmp_path / f"package{suffix}"

    write_package(target, _parts(), SaveOptions())
    read = read_package(target)

    assert _ids(read, model.ConceptDescription) == list(CONCEPT_IDS)
    assert _ids(read, model.Submodel) == ["urn:m:y", "urn:m:x"]
    assert _ids(read, model.AssetAdministrationShell) == [
        "urn:s:two",
        "urn:s:one",
    ]


def test_a_package_that_is_read_lists_its_descriptions_in_the_file_order(
    tmp_path: Path,
) -> None:
    target = tmp_path / "package.json"
    write_package(target, _parts(), SaveOptions())

    first = read_package(target)
    second = read_package(target)

    assert isinstance(first.objects, OrderedIdentifiableStore)
    assert first.objects.order == second.objects.order
