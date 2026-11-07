"""A shell or a submodel without an idShort is a valid object (V3.1).

The SDK keeps the idShort of an Identifiable optional, so a package can hold
such objects, and the editor must show, change, save and read them like any
other.
"""

from pathlib import Path

from basyx.aas import model
from tests.factories import make_property
from tests.factories import make_submodel


def _package(views, tmp_path: Path):
    submodel = make_submodel("urn:sub", None, [make_property("P")])
    shell = model.AssetAdministrationShell(
        id_=model.Identifier("urn:shell"),
        asset_information=model.AssetInformation(
            asset_kind=model.AssetKind.INSTANCE,
            global_asset_id="urn:asset",
        ),
        submodel={model.ModelReference.from_referable(submodel)},
    )
    shown = views()
    package = shown.open_package(shell, submodel)
    return shown, package, shell, submodel


def test_the_tree_lists_both_objects_and_the_element_below_one(
    views, tmp_path: Path
) -> None:
    from aas_workingbench.settings.app_settings import OBJECT_ROLE

    shown, _, shell, submodel = _package(views, tmp_path)

    proxy = shown.view.model()
    package_index = proxy.index(0, 0)
    found: dict[str, object] = {}
    stack = [package_index]
    while stack:
        index = stack.pop()
        found[repr(index.data(OBJECT_ROLE))] = index.data(OBJECT_ROLE)
        stack.extend(
            proxy.index(row, 0, index) for row in range(proxy.rowCount(index))
        )

    objects = list(found.values())
    assert any(obj is shell for obj in objects)
    assert any(obj is submodel for obj in objects)
    assert any(
        isinstance(obj, model.Property) and obj.id_short == "P"
        for obj in objects
    )


def test_both_objects_are_saved_and_read_again_without_an_id_short(
    views, tmp_path: Path
) -> None:
    from aas_workingbench.package import Package

    _, package, _, _ = _package(views, tmp_path)
    path = tmp_path / "no-id-short.aasx"

    package.write(path)
    reloaded = Package(path)

    shell = reloaded.objStore.get_item("urn:shell")
    submodel = reloaded.objStore.get_item("urn:sub")
    assert shell.id_short is None
    assert submodel.id_short is None
    assert [e.id_short for e in submodel.submodel_element] == ["P"]
    assert not reloaded.partial
